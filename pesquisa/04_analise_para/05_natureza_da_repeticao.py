# -*- coding: utf-8 -*-
"""
Natureza dos valores repetidos na PAM do Pará.

A subseção 6.4 da dissertação afirma que os rendimentos que se repetem entre
safras consecutivas não são medições, e sim convenções expressas em sacas por
hectare. Este script produz todos os números usados naquela subseção, de modo
que cada afirmação possa ser conferida contra a base.

Uso:  python3 05_natureza_da_repeticao.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

SACA_KG = 60
BASE = Path(__file__).resolve().parents[1] / "dados" / "soja_para_mascarado_2001_2024.csv"


def carrega():
    return pd.read_csv(BASE).sort_values(["municipio", "ano"]).reset_index(drop=True)


def pares_consecutivos(pa):
    """Um registro por par de safras consecutivas do mesmo município."""
    linhas = []
    for municipio, d in pa.groupby("municipio"):
        d = d.reset_index(drop=True)
        for i in range(1, len(d)):
            ant, atual = d.loc[i - 1], d.loc[i]
            linhas.append(dict(
                municipio=municipio, ano=int(atual.ano), ordem=i,
                rendimento=int(atual.rendimento_kg_ha),
                repetiu=bool(atual.rendimento_kg_ha == ant.rendimento_kg_ha),
                dNDVI=abs(atual.NDVI_mean - ant.NDVI_mean),
                dchuva=abs(atual.precip_total - ant.precip_total),
                dArea=abs(atual.soy_area_ha - ant.soy_area_ha) / max(ant.soy_area_ha, 1) * 100,
            ))
    return pd.DataFrame(linhas)


def virgula(x, casas=1):
    return f"{x:.{casas}f}".replace(".", ",")


def main():
    pa = carrega()
    P = pares_consecutivos(pa)
    rep = P[P.repetiu]
    taxa = P.repetiu.mean() * 100

    print(f"Base: {len(pa)} registros, {pa.municipio.nunique()} municípios, "
          f"{pa.ano.min()}-{pa.ano.max()}")
    print(f"Pares consecutivos: {len(P)} | repetidos: {len(rep)} ({virgula(taxa)}%)\n")

    print("== A unidade escondida no dado ==")
    inteiro_rep = (rep.rendimento % SACA_KG == 0).mean() * 100
    inteiro_var = (P[~P.repetiu].rendimento % SACA_KG == 0).mean() * 100
    print(f"  múltiplo exato de uma saca ({SACA_KG} kg):")
    print(f"    onde repetiu: {virgula(inteiro_rep)}%   onde variou: {virgula(inteiro_var)}%")
    cinco = [40, 45, 50, 55, 60]
    em_cinco = rep.rendimento.isin([v * SACA_KG for v in cinco])
    print(f"  em {', '.join(map(str, cinco))} sacas/ha: {em_cinco.sum()} de {len(rep)} "
          f"({virgula(em_cinco.mean() * 100)}%)")
    n3000 = int((rep.rendimento == 3000).sum())
    print(f"  em 3.000 kg/ha (50 sacas): {n3000} de {len(rep)} "
          f"({virgula(n3000 / len(rep) * 100)}%)")
    print(f"  3.000 kg/ha em toda a série: {int((pa.rendimento_kg_ha == 3000).sum())} "
          f"de {len(pa)} registros")
    print(f"  mediana da série: {virgula(pa.rendimento_kg_ha.median(), 0)} kg/ha "
          f"({virgula(pa.rendimento_kg_ha.median() / SACA_KG)} sc/ha)")
    print(f"  moda da série:    {virgula(pa.rendimento_kg_ha.mode().iloc[0], 0)} kg/ha")
    print(f"  média da série:   {virgula(pa.rendimento_kg_ha.mean(), 0)} kg/ha "
          f"({virgula(pa.rendimento_kg_ha.mean() / SACA_KG)} sc/ha)\n")

    print("== O ambiente variou onde o rendimento não variou ==")
    for col, nome, casas in (("dNDVI", "NDVI médio", 3),
                             ("dArea", "área mapeada (%)", 1),
                             ("dchuva", "precipitação (mm)", 0)):
        a, b = rep[col], P[~P.repetiu][col]
        p = stats.mannwhitneyu(a, b).pvalue
        print(f"  {nome:20s} repetiu {virgula(a.median(), casas):>8s} | "
              f"variou {virgula(b.median(), casas):>8s} | Mann-Whitney p = {virgula(p, 3)}")
    print("  ressalva: o NDVI é calculado sobre a máscara anual de soja; parte da")
    print("            diferença pode refletir a instabilidade da própria máscara.\n")

    print("== Onde a repetição se concentra ==")
    inicio = P.ordem <= 3
    print(f"  três primeiras safras do município: {virgula(P[inicio].repetiu.mean() * 100)}% "
          f"| demais: {virgula(P[~inicio].repetiu.mean() * 100)}%")
    faixas = pd.cut(P.ano, [2001, 2008, 2015, 2024],
                    labels=["2002-2008", "2009-2015", "2016-2024"])
    for faixa, d in P.groupby(faixas, observed=True):
        print(f"  {faixa}: {virgula(d.repetiu.mean() * 100)}% ({int(d.repetiu.sum())}/{len(d)})")
    municipios_por_ano = pa.groupby("ano").municipio.nunique()
    print(f"  municípios levantados: {municipios_por_ano.iloc[0]} em {pa.ano.min()} "
          f"-> {municipios_por_ano.iloc[-1]} em {pa.ano.max()}\n")

    print("== Floresta do Araguaia ==")
    d = pa[pa.municipio == "Floresta Do Araguaia"]
    plato = d[(d.ano >= 2005) & (d.ano <= 2016)]
    assert (plato.rendimento_kg_ha == 3000).all(), "o platô de 50 sc/ha não se confirma"
    print(f"  3.000 kg/ha em todas as {len(plato)} safras de 2005 a 2016 presentes na base")
    print(f"  área mapeada no período: {plato.soy_area_ha.min():.0f} a "
          f"{plato.soy_area_ha.max():.0f} ha")
    for ano in (2017, 2018, 2021, 2023):
        linha = d[d.ano == ano]
        if len(linha):
            print(f"  {ano}: {int(linha.rendimento_kg_ha.iloc[0])} kg/ha "
                  f"({virgula(linha.rendimento_kg_ha.iloc[0] / SACA_KG)} sc/ha), "
                  f"área {linha.soy_area_ha.iloc[0]:.0f} ha")


if __name__ == "__main__":
    main()
