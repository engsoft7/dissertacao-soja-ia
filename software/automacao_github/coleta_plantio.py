# -*- coding: utf-8 -*-
"""Janela de plantio da soja: ZARC e calendário de semeadura, de fontes oficiais.

- Calendário de semeadura e vazio sanitário: Portaria SDA/MAPA nº 1.579, de 9 de
  abril de 2026 (DOU de 10/04/2026), safra 2026/2027. Lida da página do Diário
  Oficial, que traz a tabela em HTML. No Pará e no Maranhão o estado se divide em
  regiões, definidas por listas de municípios nas notas de rodapé; cada nome é
  conferido contra a lista oficial do IBGE, e um nome que não bate faz a coleta
  falhar em vez de gravar uma região errada.
- ZARC: a tábua de risco do Zoneamento Agrícola de Risco Climático, publicada pelo
  Ministério da Agricultura como dado aberto (licença Creative Commons Atribuição)
  no catálogo dados.agricultura.gov.br. Para cada município, grupo de cultivar
  (Grupo I, II e III) e classe de água disponível no solo (AD1 a AD6), o risco
  de plantar em cada um dos 36 decêndios do ano: 20, 30 ou 40%, ou 0 quando o
  decêndio não é indicado.

Saída, em pesquisa/dados/plantio/:
- calendario_soja_<safra>.json: vazio sanitário e semeadura por estado e região,
  com os municípios de cada região pelo código do IBGE;
- zarc_soja_<safra>.csv: uma linha por município, grupo e solo, com os 36 riscos
  numa sequência de dígitos (0, 2, 3 ou 4, de 0%, 20%, 30% ou 40%);
- fontes_plantio.json: de onde veio cada coisa e quando foi lida.

A verificação de certificado fica sempre ligada.

Uso:  python coleta_plantio.py [--saida DIR]
"""
import argparse
import csv
import html as html_mod
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import requests

UA = {"User-Agent": "AgroInteligencia-Dissertacao/1.0 (UFPA; pesquisa academica)"}
ESTADOS = ("PA", "MT", "MA", "TO", "RO")
SAFRA = "2026/2027"
DOU = "https://www.in.gov.br/web/dou/-/portaria-sda/mapa-n-1.579-de-9-de-abril-de-2026-698696654"
PORTARIA = "Portaria SDA/MAPA nº 1.579, de 9 de abril de 2026"
CKAN = ("https://dados.agricultura.gov.br/api/3/action/package_show"
        "?id=tabua-de-risco-zoneamento-agricola-de-risco-climatico")
IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "pesquisa" / "dados" / "plantio"

MESES = {"janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
DATA = re.compile(r"(\d{1,2})\s*º?\s+de\s+([a-zçã]+)\s+de\s+(\d{4})", re.I)
REGIAO = re.compile(r"Região\s+([IVX]+)\s*(\d{1,2})\s*:\s*(.+?)(?=Região\s+[IVX]+\s*\d|$)")
CODIGO_RISCO = {"0": "0", "20": "2", "30": "3", "40": "4"}


def normaliza(nome: str) -> str:
    """Para comparar nomes: sem acento, sem espaço, sem apóstrofo, minúsculas."""
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def datas(trecho: str) -> list[str]:
    """'22 de junho de 2026 a 20 de setembro de 2026' -> ['2026-06-22', '2026-09-20']."""
    saida = []
    for dia, mes, ano in DATA.findall(trecho):
        m = MESES.get(mes.lower())
        if m is None:
            raise ValueError(f"mês desconhecido: {mes!r} em {trecho!r}")
        saida.append(date(int(ano), m, int(dia)).isoformat())
    return saida


def periodos(celula: str) -> list[dict]:
    """Uma célula da tabela: um período só ou, com regiões, um por região.

    Devolve [{"regiao": "I" | None, "nota": "5" | None, "inicio": ..., "fim": ...}].
    """
    regioes = REGIAO.findall(celula)
    if not regioes:
        d = datas(celula)
        if len(d) != 2:
            raise ValueError(f"esperava duas datas em {celula!r}")
        return [{"regiao": None, "nota": None, "inicio": d[0], "fim": d[1]}]
    saida = []
    for numeral, nota, trecho in regioes:
        d = datas(trecho)
        if len(d) != 2:
            raise ValueError(f"esperava duas datas na região {numeral} de {celula!r}")
        saida.append({"regiao": numeral, "nota": nota, "inicio": d[0], "fim": d[1]})
    return saida


def linhas_da_tabela(pagina: str) -> dict[str, tuple[str, str]]:
    """UF -> (célula do vazio sanitário, célula do calendário de semeadura)."""
    linhas = {}
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", pagina):
        celulas = [html_mod.unescape(re.sub(r"<[^>]+>|\s+", " ", c)).strip()
                   for c in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", tr)]
        if len(celulas) == 3 and re.fullmatch(r"[A-Z]{2}", celulas[0]) and re.search(r"\d", celulas[1]):
            linhas[celulas[0]] = (celulas[1], celulas[2])
    return linhas


def notas_de_rodape(texto: str) -> dict[str, str]:
    """As notas do anexo: número -> texto até o ponto final.

    No texto da página o número vem colado ao primeiro nome ('5Alto Parnaíba'),
    o que o distingue das datas e dos números de região ('Região I5:').
    """
    notas = {}
    for m in re.finditer(r"(?<![\d\wº])(\d{1,2})(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç])", texto):
        fim = texto.find(".", m.end())
        if fim < 0:
            continue
        notas.setdefault(m.group(1), texto[m.end():fim].strip())
    return notas


def municipios_da_nota(nota: str) -> tuple[list[str], str | None]:
    """'A, B e C' -> ['A', 'B', 'C']; separa a menção a distritos, que vira observação."""
    observacao = None
    m = re.search(r",?\s*além d[oa]s? distritos? .*$", nota)
    if m:
        observacao = m.group(0).lstrip(", ").strip()
        nota = nota[:m.start()]
    partes = [p.strip() for p in nota.split(",") if p.strip()]
    if partes and " e " in partes[-1]:
        ultimo = partes.pop()
        partes += [p.strip() for p in ultimo.split(" e ") if p.strip()]
    return partes, observacao


def municipios_ibge(uf: str) -> dict[str, tuple[int, str]]:
    r = requests.get(IBGE.format(uf=uf), headers=UA, timeout=60)
    r.raise_for_status()
    return {normaliza(m["nome"]): (int(m["id"]), m["nome"]) for m in r.json()}


def calendario() -> dict:
    r = requests.get(DOU, headers=UA, timeout=120)
    r.raise_for_status()
    pagina = r.text
    texto = html_mod.unescape(re.sub(r"\s+", " ", re.sub(r"(?is)<[^>]+>", " ", pagina)))
    # as notas ficam depois da tabela; antes dela o texto não tem listas
    notas = notas_de_rodape(texto[texto.find("CALENDÁRIO DE SEMEADURA"):])
    tabela = linhas_da_tabela(pagina)
    saida = {}
    problemas = []
    for uf in ESTADOS:
        if uf not in tabela:
            problemas.append(f"{uf}: sem linha na tabela")
            continue
        vazio, semeadura = (periodos(c) for c in tabela[uf])
        if len(vazio) != len(semeadura):
            problemas.append(f"{uf}: {len(vazio)} períodos de vazio e {len(semeadura)} de semeadura")
            continue
        ibge = municipios_ibge(uf) if vazio[0]["regiao"] else {}
        regioes, cobertos = [], set()
        for v, s in zip(vazio, semeadura):
            reg = {"regiao": v["regiao"], "vazio": [v["inicio"], v["fim"]],
                   "semeadura": [s["inicio"], s["fim"]], "municipios": None, "observacao": None}
            if v["regiao"]:
                nota = notas.get(v["nota"], "")
                if "demais" in nota.lower():
                    reg["municipios"] = "demais"
                else:
                    nomes, reg["observacao"] = municipios_da_nota(nota)
                    codigos = []
                    for nome in nomes:
                        achado = ibge.get(normaliza(nome))
                        if achado is None:
                            problemas.append(f"{uf} região {v['regiao']}: {nome!r} não está na lista do IBGE")
                        else:
                            codigos.append(achado[0])
                    reg["municipios"] = sorted(codigos)
                    cobertos |= set(codigos)
            regioes.append(reg)
        for reg in regioes:
            if reg["municipios"] == "demais":
                reg["municipios"] = sorted({c for c, _ in ibge.values()} - cobertos)
        saida[uf] = regioes
    if problemas:
        for p in problemas:
            print("::error::" + p)
        raise SystemExit("calendário com problemas; nada foi gravado")
    return saida


def zarc() -> tuple[list[dict], dict]:
    r = requests.get(CKAN, headers=UA, timeout=60)
    r.raise_for_status()
    recursos = r.json()["result"]["resources"]
    alvo = next(x for x in recursos if SAFRA in (x.get("name") or ""))
    linhas, portarias = [], {}
    with requests.get(alvo["url"], headers=UA, timeout=600, stream=True) as resp:
        resp.raise_for_status()
        cab = None
        for bruto in resp.iter_lines():
            campos = [c.strip().strip('"') for c in bruto.decode("utf-8", "replace").split(";")]
            if cab is None:
                cab = [c.lstrip("﻿") for c in campos]
                continue
            reg = dict(zip(cab, campos))
            if reg.get("Nome_cultura", "").lower() != "soja" or reg.get("UF") not in ESTADOS:
                continue
            if reg.get("Cod_Outros_Manejos") not in ("1", ""):  # só sequeiro
                continue
            riscos = "".join(CODIGO_RISCO[reg[f"dec{i}"]] for i in range(1, 37))
            linhas.append({"uf": reg["UF"], "geocodigo": int(reg["geocodigo"]), "municipio": reg["municipio"],
                           "ciclo": int(reg["Cod_Ciclo"]), "solo": int(reg["Cod_Solo"]), "riscos": riscos})
            portarias[reg["UF"]] = reg["Portaria"]
    linhas.sort(key=lambda x: (x["uf"], x["geocodigo"], x["ciclo"], x["solo"]))
    if not linhas or set(portarias) != set(ESTADOS):
        raise SystemExit(f"ZARC sem soja em todos os estados: {sorted(portarias)}")
    return linhas, {"recurso": alvo["url"], "portarias": portarias}


def grava(saida: Path) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    tag = SAFRA.replace("/", "_")
    cal = calendario()
    (saida / f"calendario_soja_{tag}.json").write_text(json.dumps(
        {"safra": SAFRA, "fonte": PORTARIA, "url": DOU, "estados": cal},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    linhas, meta = zarc()
    with open(saida / f"zarc_soja_{tag}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["uf", "geocodigo", "municipio", "ciclo", "solo", "riscos"])
        w.writeheader()
        w.writerows(linhas)
    (saida / "fontes_plantio.json").write_text(json.dumps({
        "safra": SAFRA,
        "calendario": {"fonte": PORTARIA, "url": DOU},
        "zarc": {"fonte": "Tábua de risco do ZARC, Ministério da Agricultura (dados abertos, "
                          "licença Creative Commons Atribuição)",
                 "url": meta["recurso"], "portarias": meta["portarias"],
                 "ciclos": {"20": "Grupo I", "21": "Grupo II", "22": "Grupo III"},
                 "solos": {str(c): f"AD{c - 10}" for c in range(11, 17)}},
        "lido_em": date.today().isoformat(),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for uf, regs in cal.items():
        for reg in regs:
            n = len(reg["municipios"]) if isinstance(reg["municipios"], list) else "todos"
            print(f"{uf} região {reg['regiao'] or '-'}: vazio {reg['vazio']}, semeadura {reg['semeadura']}, "
                  f"{n} municípios{'; ' + reg['observacao'] if reg['observacao'] else ''}")
    print(f"ZARC: {len(linhas)} linhas; portarias {meta['portarias']}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path, default=SAIDA)
    args = ap.parse_args(argv)
    grava(args.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
