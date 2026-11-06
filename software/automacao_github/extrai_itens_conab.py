#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrai_itens_conab.py

Extrai, da série histórica de custos de soja da CONAB, o custo aberto por item
de uma praça, ano a ano, para pesquisa/dados/conab/custo_itens_<praça>.csv.

A planilha (serie-historica-custos-soja-1997-a-2026.xls, 6 MB, uma aba por
praça e ano) traz cada item do custo por hectare e por saca: sementes,
fertilizantes, defensivos, operações com máquinas, transporte externo, CESSR,
juros, depreciações. O portal de informações, de onde saem os outros CSVs desta
pasta, só dá os totais (custo variável, fixo e renda de fatores). Com os itens,
gera_levantamento_conab.py separa o que acompanha a área do que acompanha a
produção, e o produto deixa de mostrar dois rateios possíveis do custo.

O arquivo da CONAB não é versionado (é grande e é dela); só o CSV extraído.

Uso:
    python software/automacao_github/extrai_itens_conab.py serie-historica-custos-soja-1997-a-2026.xls
Fonte:
    https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/custos-de-producao/arquivos-custo-de-producao/agricolas/serie-historica-custos-soja-1997-a-2026.xls
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import xlrd

RAIZ = Path(__file__).resolve().parents[2]
CONAB = RAIZ / "pesquisa" / "dados" / "conab"
PRACA_ABA = "Pedro Afonso-TO"
SAIDA = CONAB / "custo_itens_pedro_afonso_to.csv"

MESES = {"janeiro": "JAN", "fevereiro": "FEV", "março": "MAR", "marco": "MAR", "abril": "ABR",
         "maio": "MAI", "junho": "JUN", "julho": "JUL", "agosto": "AGO", "setembro": "SET",
         "outubro": "OUT", "novembro": "NOV", "dezembro": "DEZ"}


def _numero_br(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def le_aba(aba) -> list[dict]:
    """Linhas de uma aba: o levantamento (MAR-2026), a produtividade e cada item com valor.

    As abas mudam de leiaute com os anos (até 2020 os valores ficam em colunas
    espalhadas e a produtividade numa célula à parte): a leitura usa o texto da
    linha inteira e os dois primeiros números depois do rótulo.
    """
    levantamento, produtividade = None, None
    linhas = []
    for r in range(aba.nrows):
        celulas = [aba.cell_value(r, c) for c in range(aba.ncols)]
        textos = [str(c).strip() for c in celulas if isinstance(c, str) and str(c).strip()]
        rotulo = textos[0] if textos else ""
        inteira = " ".join(textos)
        m = re.search(r"Mês/Ano:\s*([A-Za-zçÇ]+)\s*/\s*(\d{4})", inteira)
        if m:
            levantamento = f"{MESES[m.group(1).lower()]}-{m.group(2)}"
            continue
        m = re.search(r"Produtividade[^\d]*([\d.,]+)\s*kg", inteira)
        if m:
            produtividade = _numero_br(m.group(1))
            continue
        numeros = [c for c in celulas[1:] if isinstance(c, float)]
        if rotulo and len(numeros) >= 2:
            linhas.append({"item": re.sub(r"\s+", " ", rotulo), "custo_ha": round(numeros[0], 2),
                           "custo_saca": round(numeros[1], 2)})
    return [{"levantamento": levantamento, "produtividade_kg_ha": produtividade, **l} for l in linhas]


def extrai(caminho: Path, praca: str = PRACA_ABA) -> list[dict]:
    livro = xlrd.open_workbook(str(caminho), on_demand=True)
    saida = []
    for nome in livro.sheet_names():
        m = re.fullmatch(re.escape(praca) + r"-(\d{4})", nome)
        if m:
            for linha in le_aba(livro.sheet_by_name(nome)):
                saida.append({"aba": nome, **linha})
    return saida


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("planilha", type=Path)
    a = ap.parse_args(argv)
    linhas = extrai(a.planilha)
    if not linhas:
        print(f"::error::nenhuma aba de {PRACA_ABA} em {a.planilha}")
        return 1
    with SAIDA.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["aba", "levantamento", "produtividade_kg_ha", "item",
                                           "custo_ha", "custo_saca"])
        w.writeheader()
        w.writerows(linhas)
    abas = sorted({l["aba"] for l in linhas})
    print(f"{SAIDA.name}: {len(linhas)} linhas de {len(abas)} abas ({abas[0]} a {abas[-1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
