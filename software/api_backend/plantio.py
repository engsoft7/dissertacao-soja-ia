# -*- coding: utf-8 -*-
"""Janela de plantio da soja: calendário de semeadura, vazio sanitário e ZARC.

Lê o que software/automacao_github/coleta_plantio.py grava em
pesquisa/dados/plantio/ (a safra mais recente que houver):

- o calendário de semeadura e o vazio sanitário da Portaria SDA/MAPA nº 1.579/2026,
  por estado e, no Pará e no Maranhão, por região;
- a tábua de risco do ZARC: para cada município, grupo de cultivar e classe de
  água disponível no solo, o risco de plantar em cada decêndio (20, 30 ou 40%,
  ou não indicado).

O plantio fora do calendário de semeadura é proibido; fora da janela do ZARC é
permitido, mas sem a cobertura do Proagro e de boa parte do crédito rural.
As telas mostram as duas coisas lado a lado e não decidem pelo produtor.
"""
from __future__ import annotations

import calendar
import csv
import json
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from idioma import data_en, juntar_com_and

PASTA = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "plantio"
RISCO = {"0": 0, "2": 20, "3": 30, "4": 40}


def _safra_mais_recente(pasta: Path) -> str | None:
    safras = sorted(p.stem.removeprefix("calendario_soja_") for p in pasta.glob("calendario_soja_*.json"))
    return safras[-1] if safras else None


@lru_cache(maxsize=4)
def carrega(pasta: Path = PASTA) -> dict | None:
    """Calendário, ZARC e fontes da safra mais recente; None sem os arquivos."""
    tag = _safra_mais_recente(pasta)
    if tag is None:
        return None
    cal = json.loads((pasta / f"calendario_soja_{tag}.json").read_text(encoding="utf-8"))
    fontes = json.loads((pasta / "fontes_plantio.json").read_text(encoding="utf-8"))
    zarc: dict[int, dict] = {}
    with open(pasta / f"zarc_soja_{tag}.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m = zarc.setdefault(int(r["geocodigo"]), {"uf": r["uf"], "municipio": r["municipio"], "riscos": {}})
            m["riscos"][f"{r['ciclo']}-{r['solo']}"] = r["riscos"]
    return {"calendario": cal, "zarc": zarc, "fontes": fontes}


def nome_da_portaria(codigo: str) -> str:
    """'Port.203_de_03-07-2026' -> 'Portaria nº 203, de 03/07/2026'."""
    m = re.fullmatch(r"Port\.?(\d+)_de_(\d{2})-(\d{2})-(\d{4})", codigo or "")
    return f"Portaria nº {m.group(1)}, de {m.group(2)}/{m.group(3)}/{m.group(4)}" if m else (codigo or "")


def regiao_do_municipio(regioes: list[dict], cod_ibge7: int) -> dict | None:
    """A região do calendário que vale para o município; a única, se o estado não se divide."""
    if len(regioes) == 1 and not isinstance(regioes[0].get("municipios"), list):
        return regioes[0]
    for reg in regioes:
        if cod_ibge7 in (reg.get("municipios") or []):
            return reg
    return None


def _br(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def observacao(regioes: list[dict], reg: dict, cod_ibge7: int, lang: str = "pt") -> str | None:
    """O que a portaria diz de diferente para uma parte do município.

    Hoje, Altamira: o município está numa região, mas dois distritos seguem
    outra ("além dos distritos de ..., pertencentes ao município de Altamira").
    Para os demais municípios, None. Com [lang] "en", em inglês, com os nomes
    dos distritos como a portaria os escreve.
    """
    frases = []
    for outra in regioes:
        if outra is reg:
            continue
        for d in outra.get("distritos") or []:
            if d.get("municipio") != cod_ibge7:
                continue
            m = re.search(r"distritos?\s+(?:de\s+)?(.+?),?\s+(?:pertencentes?\s+ao|do)\s+município", d["texto"])
            if lang == "en":
                quais = f"The districts of {juntar_com_and(m.group(1))}" if m else "Part of the municipality"
                frases.append(f"{quais} follow Region {outra['regiao']}: soybean-free period from "
                              f"{data_en(outra['vazio'][0])} to {data_en(outra['vazio'][1])} and sowing from "
                              f"{data_en(outra['semeadura'][0])} to {data_en(outra['semeadura'][1])}.")
                continue
            quais = f"Os distritos de {m.group(1)}" if m else "Parte do município"
            frases.append(f"{quais} seguem a Região {outra['regiao']}: vazio sanitário de "
                          f"{_br(outra['vazio'][0])} a {_br(outra['vazio'][1])} e semeadura de "
                          f"{_br(outra['semeadura'][0])} a {_br(outra['semeadura'][1])}.")
    if not frases:
        excecao = (reg.get("excecoes") or {}).get(str(cod_ibge7))
        if excecao and lang == "en":
            m = re.match(r"exceto\s+os\s+distritos\s+de\s+(.+)$", excecao)
            parte = f"except the districts of {juntar_com_and(m.group(1))}" if m else excecao
            frases.append(f"The ordinance places the municipality in this region, {parte}.")
        elif excecao:
            frases.append(f"A portaria põe o município nesta região, {excecao}.")
    return " ".join(frases) or None


def para_municipio(uf: str, cod_ibge7: int, pasta: Path = PASTA, lang: str = "pt") -> dict | None:
    """Calendário e ZARC do município; None quando não há dados da janela de plantio."""
    dados = carrega(pasta)
    if dados is None:
        return None
    cal = dados["calendario"]
    fontes = dados["fontes"]
    regioes = cal["estados"].get(uf, [])
    reg = regiao_do_municipio(regioes, cod_ibge7)
    calendario_mun = None
    if reg is not None:
        calendario_mun = {"regiao": reg.get("regiao"), "vazio": reg["vazio"], "semeadura": reg["semeadura"],
                          "observacao": observacao(regioes, reg, cod_ibge7, lang),
                          "fonte": cal["fonte"], "url": cal["url"]}
    z = dados["zarc"].get(cod_ibge7)
    zarc_mun = None
    if z is not None and z["uf"] == uf:
        meta = fontes["zarc"]
        zarc_mun = {
            "portaria": nome_da_portaria(meta["portarias"].get(uf, "")),
            "fonte": meta["fonte"], "url": meta["url"],
            "ciclos": [{"codigo": int(c), "nome": n} for c, n in meta["ciclos"].items()],
            "solos": [{"codigo": int(c), "nome": n} for c, n in meta["solos"].items()],
            "riscos": z["riscos"],
        }
    return {"safra": cal["safra"], "uf": uf, "calendario": calendario_mun, "zarc": zarc_mun,
            "lido_em": fontes.get("lido_em")}


def decendio(i: int, safra_ini: int) -> tuple[date, date]:
    """Datas do decêndio i (1 a 36) na safra que começa em safra_ini.

    De julho a dezembro (decêndios 19 a 36) é o ano de início; de janeiro a
    junho, o seguinte. O terceiro decêndio de cada mês vai do dia 21 ao fim.
    """
    mes = (i - 1) // 3 + 1
    ano = safra_ini if mes >= 7 else safra_ini + 1
    parte = (i - 1) % 3
    inicio = date(ano, mes, 1 + 10 * parte)
    fim = date(ano, mes, calendar.monthrange(ano, mes)[1]) if parte == 2 else inicio + timedelta(days=9)
    return inicio, fim


def janelas(riscos: str, safra_ini: int) -> list[dict]:
    """Os trechos seguidos de mesmo risco, de julho a junho, só os indicados.

    '000…2223…' -> [{"inicio": "2026-10-01", "fim": "2026-11-30", "risco": 20}, …]
    """
    ordem = list(range(19, 37)) + list(range(1, 19))
    saida: list[dict] = []
    for i in ordem:
        risco = RISCO[riscos[i - 1]]
        ini, fim = decendio(i, safra_ini)
        if risco and saida and saida[-1]["risco"] == risco and saida[-1]["_ultimo"] == ordem.index(i) - 1:
            saida[-1]["fim"] = fim.isoformat()
            saida[-1]["_ultimo"] = ordem.index(i)
        elif risco:
            saida.append({"inicio": ini.isoformat(), "fim": fim.isoformat(), "risco": risco, "_ultimo": ordem.index(i)})
    for j in saida:
        j.pop("_ultimo")
    return saida


# ── as mesmas contas de PlantioCalculo.kt, para o painel ──────────────────────
# O aplicativo faz as contas no celular (trocar grupo e solo não depende de
# rede); o painel usa estas, que repetem as de lá e os mesmos testes, para os
# dois mostrarem a mesma frase no mesmo dia.

def periodo(par: list[str] | None) -> tuple[date, date] | None:
    if not par or len(par) != 2:
        return None
    try:
        return date.fromisoformat(par[0]), date.fromisoformat(par[1])
    except ValueError:
        return None


def situacao_no_dia(calendario: dict | None, dia: date) -> str | None:
    """'vazio', 'semeadura' ou 'fora' do calendário da portaria; None sem calendário."""
    semeadura = periodo((calendario or {}).get("semeadura"))
    if semeadura is None:
        return None
    vazio = periodo(calendario.get("vazio"))
    if vazio and vazio[0] <= dia <= vazio[1]:
        return "vazio"
    if semeadura[0] <= dia <= semeadura[1]:
        return "semeadura"
    return "fora"


def frase_do_calendario(calendario: dict | None, dia: date) -> str | None:
    """A frase do cartão do aplicativo (fraseDoCalendario, Plantio.kt)."""
    situacao = situacao_no_dia(calendario, dia)
    if situacao is None:
        return None
    semeadura = periodo(calendario["semeadura"])
    vazio = periodo(calendario.get("vazio"))
    if situacao == "semeadura":
        return f"Semeadura permitida até {semeadura[1]:%d/%m/%Y}"
    if situacao == "vazio":
        return f"Vazio sanitário até {vazio[1]:%d/%m/%Y}; a semeadura começa em {semeadura[0]:%d/%m/%Y}"
    if vazio and dia < vazio[0]:
        return f"O vazio sanitário começa em {vazio[0]:%d/%m/%Y}"
    return f"Semeadura encerrada em {semeadura[1]:%d/%m/%Y}"


def risco_no_dia(riscos: str, safra_ini: int, dia: date) -> int:
    """O risco do ZARC no dia; 0 quando o decêndio não é indicado."""
    for j in janelas(riscos, safra_ini) if len(riscos) == 36 else []:
        if date.fromisoformat(j["inicio"]) <= dia <= date.fromisoformat(j["fim"]):
            return j["risco"]
    return 0


def proxima_janela(js: list[dict], dia: date, risco_maximo: int = 40) -> dict | None:
    """A primeira janela que ainda não terminou no dia, com risco até risco_maximo."""
    return next((j for j in js if j["risco"] <= risco_maximo and date.fromisoformat(j["fim"]) >= dia), None)


def dentro_do_calendario(j: dict, semeadura: tuple[date, date] | None) -> dict | None:
    """A parte da janela do ZARC que cai dentro do calendário de semeadura."""
    if semeadura is None:
        return j
    ini = max(date.fromisoformat(j["inicio"]), semeadura[0])
    fim = min(date.fromisoformat(j["fim"]), semeadura[1])
    return None if ini > fim else {**j, "inicio": ini.isoformat(), "fim": fim.isoformat()}
