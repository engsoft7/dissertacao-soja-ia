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

A safra troca sozinha. A cada mês a coleta procura no Diário Oficial a portaria
mais nova da SDA/MAPA com o calendário de semeadura da soja, e no catálogo do
Ministério as safras da tábua do ZARC. Quando há portaria de uma safra mais nova
que a em uso e a tábua dessa safra já saiu, a coleta passa para ela; os
arquivos da safra anterior ficam, e a API usa a mais recente. Sem a busca do
Diário Oficial (fora do ar ou com formato novo), segue a safra em uso, lida de
fontes_plantio.json, ou a portaria abaixo. Uma portaria nova que não se deixe
ler faz a coleta falhar, como qualquer leitura errada, e nada é gravado.

A verificação de certificado fica sempre ligada.

Uso:  python coleta_plantio.py [--saida DIR] [--descobre]
      --descobre só mostra a portaria e as safras encontradas, sem gravar.
"""
import argparse
import csv
import html as html_mod
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

import requests

UA = {"User-Agent": "AgroInteligencia-Dissertacao/1.0 (UFPA; pesquisa academica)"}
ESTADOS = ("PA", "MT", "MA", "TO", "RO")
# A portaria de partida, usada quando ainda não há fontes_plantio.json e a busca
# no Diário Oficial não responde. A safra em uso fica em fontes_plantio.json.
SAFRA = "2026/2027"
DOU = "https://www.in.gov.br/web/dou/-/portaria-sda/mapa-n-1.579-de-9-de-abril-de-2026-698696654"
PORTARIA = "Portaria SDA/MAPA nº 1.579, de 9 de abril de 2026"
BUSCA_DOU = "https://www.in.gov.br/consulta/-/buscar/dou"
PAGINA_DOU = "https://www.in.gov.br/web/dou/-/"
SAFRA_NO_TEXTO = re.compile(r"safra\s+(\d{4})\s*/\s*(\d{4}|\d{2})\b", re.I)
TITULO_PORTARIA = re.compile(
    r"PORTARIA\s+SDA\s*/\s*MAPA\s+N[º°ºO.]*\s*([\d.]+)\s*,?\s+DE\s+(\d{1,2})\s*º?\s+DE\s+([A-ZÇÃ]+)\s+DE\s+(\d{4})", re.I)
CKAN = ("https://dados.agricultura.gov.br/api/3/action/package_show"
        "?id=tabua-de-risco-zoneamento-agricola-de-risco-climatico")
IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
# A mesma lista aberta que gera_municipios.py e monta_base_estados.py usam, com
# o código do IBGE de cada município: a reserva quando a API do IBGE não
# responde ao Actions (14/11/2026, tempo esgotado em 60 s).
KELVINS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
CODIGO_UF = {"PA": 15, "MT": 51, "MA": 21, "TO": 17, "RO": 11}
RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "pesquisa" / "dados" / "plantio"

MESES = {"janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
DATA = re.compile(r"(\d{1,2})\s*º?\s+de\s+([a-zçã]+)\s+de\s+(\d{4})", re.I)
REGIAO = re.compile(r"Região\s+([IVX]+)\s*(\d{1,2})\s*:\s*(.+?)(?=Região\s+[IVX]+\s*\d|$)")
CODIGO_RISCO = {"0": "0", "20": "2", "30": "3", "40": "4"}
DO_MUNICIPIO = re.compile(r"(?:pertencentes?\s+ao|do)\s+município\s+de\s+(.+)$")
# Grafias do anexo que não batem com a lista do IBGE, conferidas uma a uma. Um
# nome novo que não bata continua fazendo a coleta falhar.
GRAFIAS = {
    # Região II do Maranhão: o anexo escreve "Lagoa da Pedra"; o município é Lago
    # da Pedra (IBGE 2105708, que planta soja na PAM), o único do estado com nome
    # parecido.
    ("MA", "lagoadapedra"): "Lago da Pedra",
}


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


def municipios_da_nota(nota: str) -> tuple[list[str], dict[str, str], str | None]:
    """'A, B (exceto ...) e C' -> (['A', 'B', 'C'], {'B': 'exceto ...'}, distritos).

    O parêntese depois de um nome ("Altamira (exceto os distritos de ...)") e a
    menção a distritos de outro município ("além dos distritos de ..., do
    município de ...") saem da lista antes de separá-la, porque também têm
    vírgulas e "e".
    """
    distritos = None
    m = re.search(r",?\s*além d[oa]s? distritos? .*$", nota)
    if m:
        distritos = m.group(0).lstrip(", ").strip()
        nota = nota[:m.start()]
    excecoes: dict[str, str] = {}

    def tira_parentese(mp: re.Match) -> str:
        antes = mp.group(1)
        excecoes[re.split(r"\s+e\s+", antes.strip())[-1]] = mp.group(2).strip()
        return antes.rstrip()

    nota = re.sub(r"([^,()]+?)\s*\(([^()]*)\)", tira_parentese, nota)
    partes = [p.strip() for p in nota.split(",") if p.strip()]
    if partes and " e " in partes[-1]:
        ultimo = partes.pop()
        partes += [p.strip() for p in ultimo.split(" e ") if p.strip()]
    return partes, excecoes, distritos


def codigo_ibge(uf: str, nome: str, ibge: dict[str, tuple[int, str]]) -> tuple[int, str] | None:
    """(código, nome no IBGE) de um nome do anexo, com as grafias conferidas; None se não bate."""
    return ibge.get(normaliza(GRAFIAS.get((uf, normaliza(nome)), nome)))


def fora_das_regioes(uf: str, ibge: dict[str, tuple[int, str]], regioes: list[dict],
                     textos: list[str]) -> list[str]:
    """Os municípios do estado que não entraram em região nenhuma.

    Se o nome aparece no texto das notas do estado, a leitura perdeu o nome: é
    problema, e a coleta falha. Se não aparece, a portaria não o lista: fica um
    aviso no log, e o aplicativo diz que não há calendário para ele.
    """
    cobertos = {c for r in regioes for c in (r["municipios"] or [])}
    corrido = normaliza(" ".join(textos))
    problemas = []
    for chave, (cod, nome) in sorted(ibge.items(), key=lambda x: x[1][1]):
        if cod in cobertos:
            continue
        if chave in corrido:
            problemas.append(f"{uf}: {nome} ({cod}) aparece nas notas, mas não entrou em região nenhuma")
        else:
            print(f"::warning::{uf}: {nome} ({cod}) não está em região nenhuma da portaria; "
                  "o aplicativo diz que não há calendário para ele")
    return problemas


def municipios_ibge(uf: str) -> dict[str, tuple[int, str]]:
    """Nome normalizado -> (código do IBGE, nome) de todos os municípios do estado."""
    try:
        r = requests.get(IBGE.format(uf=uf), headers=UA, timeout=20)
        r.raise_for_status()
        return {normaliza(m["nome"]): (int(m["id"]), m["nome"]) for m in r.json()}
    except requests.RequestException as e:
        print(f"API do IBGE indisponível ({type(e).__name__}); usando a lista de municípios do kelvins")
    r = requests.get(KELVINS, headers=UA, timeout=90)
    r.raise_for_status()
    r.encoding = "utf-8"
    import io
    return {normaliza(row["nome"]): (int(row["codigo_ibge"]), row["nome"])
            for row in csv.DictReader(io.StringIO(r.text)) if int(row["codigo_uf"]) == CODIGO_UF[uf]}


# ── a safra: a portaria mais nova do Diário Oficial e as tábuas do ZARC ──────

def texto_da_pagina(pagina: str) -> str:
    return html_mod.unescape(re.sub(r"\s+", " ", re.sub(r"(?is)<[^>]+>", " ", pagina)))


def safras_no_texto(texto: str) -> list[str]:
    """'safra 2027/2028' ou 'safra 2027/28' -> ['2027/2028'], sem repetir, em ordem."""
    vistas = []
    for a, b in SAFRA_NO_TEXTO.findall(texto):
        fim = b if len(b) == 4 else a[:2] + b
        if int(fim) == int(a) + 1 and f"{a}/{fim}" not in vistas:
            vistas.append(f"{a}/{fim}")
    return vistas


def nome_da_portaria(titulo: str) -> str:
    """'PORTARIA SDA/MAPA Nº 1.579, DE 9 DE ABRIL DE 2026' -> 'Portaria SDA/MAPA nº 1.579, de 9 de abril de 2026'."""
    m = TITULO_PORTARIA.search(titulo or "")
    if not m:
        return " ".join((titulo or "").split())
    numero, dia, mes, ano = m.groups()
    return f"Portaria SDA/MAPA nº {numero}, de {int(dia)} de {mes.lower()} de {ano}"


def resultados_da_busca(pagina: str) -> list[dict]:
    """Os atos que a busca do Diário Oficial devolve, do JSON que a página traz embutido."""
    m = re.search(r'<script[^>]*id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params"[^>]*>(.*?)</script>',
                  pagina, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(1)).get("jsonArray") or []
    except json.JSONDecodeError:
        return []


def candidatas(resultados: list[dict]) -> list[dict]:
    """Portarias da SDA/MAPA da busca: primeiro as que o resumo diz ser do calendário da soja, as mais novas antes.

    O resumo da busca é um trecho curto em volta dos termos procurados e pode
    não trazer "soja"; quem decide é a página inteira (portaria_mais_nova).
    """
    saida = []
    for r in resultados:
        titulo = r.get("title") or r.get("titulo") or ""
        if not TITULO_PORTARIA.search(titulo) or not r.get("urlTitle"):
            continue
        try:
            publicada = datetime.strptime(r.get("pubDate", ""), "%d/%m/%Y").date()
        except ValueError:
            continue
        resumo = texto_da_pagina(r.get("content") or "").lower()
        da_soja = "semeadura" in resumo and "soja" in resumo
        saida.append({"titulo": titulo, "url": PAGINA_DOU + r["urlTitle"], "publicada": publicada, "da_soja": da_soja})
    return sorted(saida, key=lambda c: (c["da_soja"], c["publicada"]), reverse=True)


def portaria_mais_nova(hoje: date | None = None) -> dict | None:
    """A portaria mais nova do calendário de semeadura da soja, com a safra que ela fixa; None se não achar."""
    hoje = hoje or date.today()
    r = requests.get(BUSCA_DOU, headers=UA, timeout=120, params={
        "q": '"calendário de semeadura" soja', "s": "todos", "exactDate": "personalizado", "sortType": "0",
        "publishFrom": f"01-01-{hoje.year - 1}", "publishTo": hoje.strftime("%d-%m-%Y"), "delta": "50"})
    r.raise_for_status()
    resultados = resultados_da_busca(r.text)
    # O que a busca devolveu, no log: é por aqui que se vê um formato novo do DOU.
    print(f"::group::busca no Diário Oficial: {len(resultados)} atos")
    print(f"{r.status_code} {r.url} ({len(r.text)} caracteres)")
    for x in resultados[:15]:
        print(f"- {x.get('pubDate')} | {x.get('artType')} | {x.get('title') or x.get('titulo')} | "
              f"{texto_da_pagina(x.get('content') or '')[:140]}")
    print("::endgroup::")
    for c in candidatas(resultados)[:8]:
        pagina = requests.get(c["url"], headers=UA, timeout=120)
        pagina.raise_for_status()
        texto = texto_da_pagina(pagina.text)
        safras = safras_no_texto(texto)
        if safras and "CALENDÁRIO DE SEMEADURA" in texto.upper() and "SOJA" in texto.upper():
            return {"safra": max(safras), "fonte": nome_da_portaria(c["titulo"]), "url": c["url"]}
    return None


def safra_em_uso(saida: Path) -> dict:
    """A safra, a portaria e o endereço da última coleta (fontes_plantio.json), ou os de partida."""
    try:
        f = json.loads((saida / "fontes_plantio.json").read_text(encoding="utf-8"))
        return {"safra": f["safra"], "fonte": f["calendario"]["fonte"], "url": f["calendario"]["url"]}
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return {"safra": SAFRA, "fonte": PORTARIA, "url": DOU}


def safras_do_zarc(recursos: list[dict]) -> list[str]:
    """As safras das tábuas do ZARC no catálogo ("... 2026/2027 ..." no nome), da mais antiga à mais nova."""
    safras = set()
    for x in recursos:
        for a, b in re.findall(r"\b(\d{4})/(\d{4})\b", x.get("name") or ""):
            if int(b) == int(a) + 1:
                safras.add(f"{a}/{b}")
    return sorted(safras)


def escolhe_safra(atual: dict, nova: dict | None, safras_zarc: list[str]) -> dict:
    """A safra a coletar: a da portaria nova, se for mais nova que a em uso e a tábua dela já saiu."""
    if nova and nova["safra"] > atual["safra"]:
        if nova["safra"] in safras_zarc:
            return nova
        print(f"::notice::Portaria da safra {nova['safra']} publicada ({nova['fonte']}); a tábua do ZARC "
              f"dessa safra ainda não saiu, e a coleta segue na {atual['safra']}.")
    return atual


def calendario(url: str = DOU) -> dict:
    r = requests.get(url, headers=UA, timeout=120)
    r.raise_for_status()
    pagina = r.text
    texto = html_mod.unescape(re.sub(r"\s+", " ", re.sub(r"(?is)<[^>]+>", " ", pagina)))
    # as notas ficam depois da tabela; antes dela o texto não tem listas
    notas = notas_de_rodape(texto[texto.find("CALENDÁRIO DE SEMEADURA"):])
    # As notas dos estados com regiões, por inteiro, para quem conferir a leitura.
    for uf, celulas in linhas_da_tabela(pagina).items():
        if uf in ESTADOS and "Região" in celulas[0]:
            print(f"::group::notas do anexo para {uf}")
            for p in periodos(celulas[0]):
                print(f"Região {p['regiao']} (nota {p['nota']}): {notas.get(p['nota'], '(sem nota)')}")
            print("::endgroup::")
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

        def codigo(nome: str, regiao: str) -> int | None:
            achado = codigo_ibge(uf, nome, ibge)
            if achado is None:
                problemas.append(f"{uf} região {regiao}: {nome!r} não está na lista do IBGE")
                return None
            if normaliza(achado[1]) != normaliza(nome):
                print(f"{uf} região {regiao}: {nome!r} do anexo lido como {achado[1]} ({achado[0]})")
            return achado[0]

        regioes, onde = [], {}
        for v, s in zip(vazio, semeadura):
            reg = {"regiao": v["regiao"], "vazio": [v["inicio"], v["fim"]],
                   "semeadura": [s["inicio"], s["fim"]], "municipios": None, "excecoes": {}, "distritos": []}
            if v["regiao"]:
                nota = notas.get(v["nota"], "")
                if not nota:
                    problemas.append(f"{uf} região {v['regiao']}: sem a nota {v['nota']}")
                if "demais" in nota.lower():
                    reg["municipios"] = "demais"
                else:
                    nomes, excecoes, distritos = municipios_da_nota(nota)
                    codigos = [c for c in (codigo(n, v["regiao"]) for n in nomes) if c is not None]
                    for c in codigos:
                        if c in onde:
                            problemas.append(f"{uf}: o município {c} está nas regiões {onde[c]} e {v['regiao']}")
                        onde[c] = v["regiao"]
                    reg["municipios"] = sorted(codigos)
                    for nome, texto in excecoes.items():
                        c = codigo(nome, v["regiao"])
                        if c is not None:
                            reg["excecoes"][str(c)] = texto
                    if distritos:
                        m = DO_MUNICIPIO.search(distritos)
                        c = codigo(m.group(1).strip(), v["regiao"]) if m else None
                        if m is None:
                            problemas.append(f"{uf} região {v['regiao']}: distritos sem o município: {distritos!r}")
                        elif c is not None:
                            reg["distritos"].append({"municipio": c, "texto": distritos})
            regioes.append(reg)
        for reg in regioes:
            if reg["municipios"] == "demais":
                reg["municipios"] = sorted({c for c, _ in ibge.values()} - set(onde))
        if ibge:
            problemas += fora_das_regioes(uf, ibge, regioes, [notas.get(v["nota"], "") for v in vazio])
        saida[uf] = regioes
    if problemas:
        for p in problemas:
            print("::error::" + p)
        raise SystemExit("calendário com problemas; nada foi gravado")
    return saida


def recursos_do_zarc() -> list[dict]:
    """Os arquivos da tábua de risco do ZARC no catálogo do Ministério, um por safra."""
    r = requests.get(CKAN, headers=UA, timeout=60)
    r.raise_for_status()
    return r.json()["result"]["resources"]


def zarc(recursos: list[dict], safra: str = SAFRA) -> tuple[list[dict], dict]:
    alvo = next(x for x in recursos if safra in (x.get("name") or ""))
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


def descobre(saida: Path) -> tuple[dict, list[dict]]:
    """A safra a coletar e os arquivos do ZARC, com o que se achou impresso no log."""
    atual = safra_em_uso(saida)
    recursos = recursos_do_zarc()
    safras_zarc = safras_do_zarc(recursos)
    try:
        nova = portaria_mais_nova()
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"::warning::A busca no Diário Oficial falhou ({type(e).__name__}: {e}); a coleta segue na safra em uso.")
        nova = None
    print(f"Safra em uso: {atual['safra']} ({atual['fonte']})")
    print(f"Portaria mais nova no Diário Oficial: "
          + (f"{nova['fonte']}, safra {nova['safra']}, {nova['url']}" if nova else "não encontrada"))
    print(f"Tábuas do ZARC no catálogo: {', '.join(safras_zarc) or 'nenhuma'}")
    escolha = escolhe_safra(atual, nova, safras_zarc)
    if escolha is not atual:
        print(f"::notice::Troca de safra: de {atual['safra']} para {escolha['safra']} ({escolha['fonte']}).")
    return escolha, recursos


def grava(saida: Path) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    escolha, recursos = descobre(saida)
    safra, portaria, url = escolha["safra"], escolha["fonte"], escolha["url"]
    tag = safra.replace("/", "_")
    cal = calendario(url)
    linhas, meta = zarc(recursos, safra)
    # Grava só depois de ler as duas fontes: uma falha no meio não deixa o
    # calendário de uma safra com a tábua de outra.
    (saida / f"calendario_soja_{tag}.json").write_text(json.dumps(
        {"safra": safra, "fonte": portaria, "url": url, "estados": cal},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(saida / f"zarc_soja_{tag}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["uf", "geocodigo", "municipio", "ciclo", "solo", "riscos"])
        w.writeheader()
        w.writerows(linhas)
    (saida / "fontes_plantio.json").write_text(json.dumps({
        "safra": safra,
        "calendario": {"fonte": portaria, "url": url},
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
            extra = [f"exceção em {c}: {t}" for c, t in reg["excecoes"].items()]
            extra += [f"distritos de {d['municipio']}: {d['texto']}" for d in reg["distritos"]]
            print(f"{uf} região {reg['regiao'] or '-'}: vazio {reg['vazio']}, semeadura {reg['semeadura']}, "
                  f"{n} municípios" + "".join("; " + e for e in extra))
    print(f"ZARC: {len(linhas)} linhas; portarias {meta['portarias']}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path, default=SAIDA)
    ap.add_argument("--descobre", action="store_true", help="só mostra a portaria e as safras encontradas")
    args = ap.parse_args(argv)
    if args.descobre:
        escolha, _ = descobre(args.saida)
        print(f"Safra que a coleta usaria: {escolha['safra']} ({escolha['fonte']})")
        return 0
    grava(args.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
