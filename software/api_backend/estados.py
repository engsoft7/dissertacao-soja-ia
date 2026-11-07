# -*- coding: utf-8 -*-
"""Os estados do produto: o Pará da dissertação e, como extensão, Mato Grosso e Maranhão.

O Pará é o recorte da dissertação, e tudo dele fica como estava: base, nomes,
custo de Pedro Afonso (TO), praças da Agrolink. Mato Grosso e Maranhão entram
com a mesma conta (pesquisa/10_trabalhos_futuros/06_amazonia_legal.py mostrou
ganho sobre a referência nos dois) e a base montada por
software/automacao_github/monta_base_estados.py, em pesquisa/dados/estados/.

O custo e o preço de porteira são os da CONAB no próprio estado, no mesmo
levantamento do Pará (custo_producao_por_municipio.csv): Sorriso ou Primavera
do Leste em Mato Grosso, a mais perto da sede do município, e Balsas no
Maranhão. Diferente de Pedro Afonso, essas praças não têm o custo aberto por
item na extração, e o aplicativo usa os dois rateios do custo variável.

Sem parâmetro de estado, a API responde pelo Pará: o aplicativo já instalado
não manda estado e continua igual.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "pesquisa" / "dados"
CONAB = DADOS / "conab"


@dataclass(frozen=True)
class Estado:
    uf: str
    nome: str
    base: Path
    pam: Path
    municipios: Path
    geo: Path
    rios: Path | None
    # Praças da CONAB no estado, com a sede (latitude, longitude); vazio no Pará,
    # que usa o levantamento de Pedro Afonso (financas.LEVANTAMENTO).
    pracas_conab: tuple[tuple[str, str, float, float], ...] = ()


# Sedes das praças: kelvins/municipios-brasileiros, como municipios_<UF>.csv.
ESTADOS: dict[str, Estado] = {
    "PA": Estado("PA", "Pará", DADOS / "soja_para_painel.csv", DADOS / "pam_soja_para.csv",
                 DADOS / "municipios_para.csv", DADOS / "para_geo.json", DADOS / "rios_para.json"),
    "MT": Estado("MT", "Mato Grosso", DADOS / "estados" / "soja_MT_painel.csv", DADOS / "estados" / "pam_soja_MT.csv",
                 DADOS / "estados" / "municipios_MT.csv", DADOS / "estados" / "mt_geo.json", None,
                 (("SORRISO-MT", "Sorriso (MT)", -12.5425, -55.7211),
                  ("PRIMAVERA DO LESTE-MT", "Primavera do Leste (MT)", -15.544, -54.2811))),
    "MA": Estado("MA", "Maranhão", DADOS / "estados" / "soja_MA_painel.csv", DADOS / "estados" / "pam_soja_MA.csv",
                 DADOS / "estados" / "municipios_MA.csv", DADOS / "estados" / "ma_geo.json", None,
                 (("BALSAS-MA", "Balsas (MA)", -7.53214, -46.0372),)),
}
PADRAO = "PA"


def estado(uf: str | None) -> Estado | None:
    """O estado pedido (sem pedido, o Pará); None se não for um dos do produto."""
    return ESTADOS.get((uf or PADRAO).strip().upper())


def disponiveis() -> list[Estado]:
    """Os estados cuja base está no disco: o Pará sempre; os outros, depois de montados."""
    return [e for e in ESTADOS.values() if e.base.exists()]


def sedes(e: Estado) -> dict[int, tuple[str, float, float]]:
    """cod_ibge7 → (nome oficial, latitude, longitude) das sedes do estado."""
    if not e.municipios.exists():
        return {}
    with open(e.municipios, encoding="utf-8") as f:
        return {int(r["cod_ibge7"]): (r["municipio"], float(r["latitude"]), float(r["longitude"]))
                for r in csv.DictReader(f) if r.get("latitude")}


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def praca_conab(e: Estado, sede: tuple[float, float] | None) -> tuple[str, str] | None:
    """A praça da CONAB do estado mais perto da sede (nome no CSV, rótulo); None no Pará."""
    if not e.pracas_conab:
        return None
    if sede is None:
        return e.pracas_conab[0][:2]
    return min(e.pracas_conab, key=lambda p: _km(sede, (p[2], p[3])))[:2]


def _le_conab(nome: str) -> dict[str, dict[str, float]]:
    with open(CONAB / nome, encoding="utf-8") as f:
        linhas = list(csv.reader(f, delimiter=";"))
    cab = [c.strip('"') for c in linhas[0]]
    return {l[0].strip('"'): {c: float(v) for c, v in zip(cab[1:], l[1:])} for l in linhas[1:] if l}


def levantamento_da_praca(praca_csv: str, rotulo: str, levantamento: str, extenso: str) -> dict:
    """Preço e custo da praça no levantamento em uso, no formato de financas.LEVANTAMENTO.

    A CONAB publica por saca; o hectare sai da produtividade de referência da
    própria praça, como em gera_levantamento_conab.py.
    """
    comp = _le_conab("custo_producao_por_municipio.csv")[praca_csv]
    prod = _le_conab("custo_variavel_e_produtividade_por_municipio.csv")[praca_csv]
    kg = prod["Produtividade"]
    sc = kg / 60
    var, fixo, renda = comp["CUSTO VARIAVEL"], comp["CUSTO FIXO"], comp["RENDA DE FATORES"]
    operacional = var + fixo
    preco = comp["PRECO RECEBIDO"]

    def reais(v: float) -> str:
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return {
        "praca": rotulo, "praca_csv": praca_csv, "levantamento": levantamento,
        "levantamento_extenso": extenso,
        "preco_recebido_saca": preco, "custo_variavel_saca": var, "custo_fixo_saca": fixo,
        "custo_operacional_saca": round(operacional, 2), "renda_fatores_saca": renda,
        "produtividade_referencia_kg_ha": kg, "produtividade_referencia_sc_ha": sc,
        "custo_variavel_ha": round(var * sc, 2), "custo_operacional_ha": round(operacional * sc, 2),
        "custo_total_ha": round((operacional + renda) * sc, 2),
        "custo_por_componente": None,
        "textos": {
            "descricao": f"CONAB, {rotulo}, {extenso}",
            "nota_preco": (f"R$ {reais(preco)}/sc é o preço recebido em {rotulo} no levantamento de {extenso} "
                           "da CONAB. Cenário de referência, não previsão de preço."),
            "nota_custo": (f"Custo operacional de R$ {reais(operacional)}/sc, convertido para "
                           f"R$ {reais(operacional * sc)}/ha pela produtividade de referência da praça "
                           f"({kg:,.0f} kg/ha, {sc:.0f} sc/ha).".replace(",", ".")),
        },
    }
