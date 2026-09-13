# -*- coding: utf-8 -*-
"""
A repetição corresponde a alguma coisa no campo? Confronto com o satélite.

O diagnóstico proposto afirma que safras consecutivas com produtividade
idêntica indicam valor não medido. A afirmação precisa de uma referência
externa: alguém poderia objetar que a lavoura simplesmente rendeu o mesmo nas
duas safras, e que a repetição é fiel à realidade.

O teste é direto. Se dois anos seguidos renderam de fato o mesmo, as condições
da lavoura nesses dois anos tinham de ser parecidas — e o satélite teria
registrado isso. Se a variação do NDVI, do EVI e da chuva entre os dois anos
for tão grande quanto a de pares em que o rendimento mudou, então o zero no
rendimento não veio do campo.

A comparação é feita **dentro do município**, sobre a variação interanual, o
que elimina de saída a diferença de nível entre municípios grandes e pequenos.
Também é repetida em estratos de área plantada, porque a repetição é mais comum
em município pequeno e o NDVI de área pequena é mais ruidoso: sem estratificar,
um crítico poderia atribuir o resultado à qualidade do pixel, e não à do dado.

Fonte: base do Pará com máscara anual do MapBiomas, 2001-2024.

Uso:  python 06_repeticao_e_sinal_espectral.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import mannwhitneyu

RAIZ = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(RAIZ, '..', 'dados', 'soja_para_mascarado_2001_2024.csv')
SAIDA = os.path.join(RAIZ, 'repeticao_e_sinal_espectral.json')

SINAIS = ['NDVI_mean', 'NDVI_max', 'EVI_mean', 'EVI_max', 'precip_total', 'temp_mean']
SEED = 42


def pares(df):
    """Um registro por par de safras consecutivas do mesmo município.

    Guarda a variação relativa de cada sinal entre as duas safras, em módulo, e
    se o rendimento repetiu. A variação é relativa porque NDVI e chuva têm
    escalas incomparáveis, e o que interessa é quanto mudou, não em que unidade.
    """
    linhas = []
    for mun, d in df.groupby('municipio'):
        d = d.sort_values('ano')
        if len(d) < 2:
            continue
        ant, atual = d.iloc[:-1], d.iloc[1:]
        for i in range(len(atual)):
            a, b = ant.iloc[i], atual.iloc[i]
            reg = {'municipio': mun, 'ano': int(b.ano),
                   'repetiu': bool(b.rendimento_kg_ha == a.rendimento_kg_ha),
                   'area': float(a.soy_area_ha),
                   'delta_rendimento': abs(float(b.rendimento_kg_ha - a.rendimento_kg_ha))}
            for s in SINAIS:
                base = abs(float(a[s]))
                reg[f'delta_{s}'] = abs(float(b[s] - a[s])) / base * 100 if base else np.nan
            linhas.append(reg)
    return pd.DataFrame(linhas)


def compara(p, rotulo):
    """Variação dos sinais nos pares que repetiram contra os que não repetiram."""
    rep, nao = p[p.repetiu], p[~p.repetiu]
    if len(rep) < 5 or len(nao) < 5:
        return None
    saida = {'estrato': rotulo, 'pares_repetidos': int(len(rep)),
             'pares_nao_repetidos': int(len(nao)), 'sinais': {}}
    for s in SINAIS:
        c = f'delta_{s}'
        a, b = rep[c].dropna(), nao[c].dropna()
        if len(a) < 5 or len(b) < 5:
            continue
        u, pv = mannwhitneyu(a, b, alternative='two-sided')
        saida['sinais'][s] = {
            'mediana_repetiu': round(float(a.median()), 2),
            'mediana_nao_repetiu': round(float(b.median()), 2),
            'razao': round(float(a.median() / b.median()), 2) if b.median() else None,
            'p_mannwhitney': float(f'{pv:.3g}'),
        }
    return saida


def ols(X, y):
    """Mínimos quadrados com erros-padrão, sem trazer statsmodels para o projeto.

    São três colunas e algumas centenas de linhas: a álgebra cabe em cinco
    linhas de numpy, e acrescentar uma dependência ao repositório para isso
    custaria mais do que economiza — inclusive no hash do INPI, que precisaria
    ser refeito por causa de um import.
    """
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    residuo = y - X @ beta
    gl = len(y) - X.shape[1]
    s2 = residuo @ residuo / gl
    ep = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return beta, ep, gl


def regressao(p):
    """Efeito da repetição sobre a variação do sinal, com a área controlada.

    Estratificar em terços responde ao confundimento, mas gasta o poder de uma
    amostra que já é pequena — o Pará tem 377 pares. A regressão usa todos
    eles e mantém a área como covariável contínua, que é o que a objeção pede:
    município pequeno repete mais e tem pixel mais ruidoso, então o contraste
    tem de sobreviver ao porte, não ser explicado por ele.

    O alvo é o logaritmo da variação, porque ela é positiva e assimétrica; o
    coeficiente de `repetiu` lê-se como variação proporcional.
    """
    saida = {}
    for s_ in SINAIS:
        d = p[['repetiu', 'area', f'delta_{s_}']].dropna()
        d = d[d[f'delta_{s_}'] > 0]
        if len(d) < 30:
            continue
        X = np.column_stack([np.ones(len(d)), d.repetiu.astype(float).values,
                             np.log1p(d.area.values)])
        beta, ep, gl = ols(X, np.log(d[f'delta_{s_}'].values))
        t = beta[1] / ep[1]
        margem = stats.t.ppf(0.975, gl) * ep[1]
        saida[s_] = {
            'coef_repetiu': round(float(beta[1]), 3),
            'efeito_%': round(float((np.exp(beta[1]) - 1) * 100), 1),
            'p': float(f'{2 * stats.t.sf(abs(t), gl):.3g}'),
            'ic95': [round(float(beta[1] - margem), 3), round(float(beta[1] + margem), 3)],
            'n': int(len(d)),
        }
    return saida


def imprime(r):
    print(f'\n{"─" * 74}\n{r["estrato"]}  '
          f'({r["pares_repetidos"]} pares repetidos, {r["pares_nao_repetidos"]} não)')
    print(f'  {"sinal":14s}{"repetiu":>12s}{"não repetiu":>14s}{"razão":>9s}{"p":>11s}')
    for s, v in r['sinais'].items():
        print(f'  {s:14s}{v["mediana_repetiu"]:>12.2f}{v["mediana_nao_repetiu"]:>14.2f}'
              f'{v["razao"]:>9.2f}{v["p_mannwhitney"]:>11.3g}')


def main():
    df = pd.read_csv(CSV)
    p = pares(df)
    print(f'{len(p):,} pares de safras consecutivas em {p.municipio.nunique()} municípios '
          f'do Pará')
    print(f'{int(p.repetiu.sum()):,} repetiram ({p.repetiu.mean() * 100:.1f}%)')
    print('\nVariação interanual de cada sinal, em % do valor da safra anterior.')
    print('Medianas. "razão" abaixo de 1 indicaria lavoura de fato parecida nos')
    print('dois anos; perto de 1 indica que o satélite não viu a igualdade que a')
    print('estatística oficial declara.')

    resultados = [compara(p, 'todos os pares')]
    imprime(resultados[0])

    # estratos de área: a repetição concentra-se em município pequeno, e é lá
    # que o pixel é mais ruidoso — o contraste precisa sobreviver ao estrato
    q = pd.qcut(p.area, 3, labels=['área pequena', 'área média', 'área grande'])
    for rotulo in q.cat.categories:
        r = compara(p[q == rotulo], str(rotulo))
        if r:
            resultados.append(r)
            imprime(r)

    reg = regressao(p)
    print(f'\n{"─" * 74}')
    print('Regressão: log da variação do sinal ~ repetiu + log(área)')
    print('Coeficiente positivo significa que o satélite viu MAIS mudança')
    print('justamente quando a estatística oficial declarou rendimento idêntico.')
    print(f'  {"sinal":14s}{"efeito":>10s}{"IC 95%":>20s}{"p":>10s}{"n":>7s}')
    for s_, v in reg.items():
        ic = f'[{v["ic95"][0]:+.2f}, {v["ic95"][1]:+.2f}]'
        print(f'  {s_:14s}{v["efeito_%"]:>9.1f}%{ic:>20s}{v["p"]:>10.3g}{v["n"]:>7d}')

    saida = {'regressao': reg,
             'pares': int(len(p)), 'municipios': int(p.municipio.nunique()),
             'repetidos': int(p.repetiu.sum()),
             'taxa': round(float(p.repetiu.mean() * 100), 1),
             'estratos': resultados,
             'fonte': 'soja_para_mascarado_2001_2024.csv'}
    with open(SAIDA, 'w', encoding='utf-8') as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print(f'\ngravado em {os.path.basename(SAIDA)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
