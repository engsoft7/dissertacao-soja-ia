# -*- coding: utf-8 -*-
"""
Figuras 1 a 4 do manuscrito submetido à Computers and Electronics in Agriculture.

Reconstrói as quatro figuras a partir das fontes versionadas — o CSV nacional da
PAM e o JSON de medidas derivadas — em vez de deixá-las como binários sem
origem. A carta de apresentação afirma que toda afirmação numérica do
manuscrito pode ser recomputada a partir do depósito; um PNG que ninguém sabe
regerar não sustenta essa afirmação, e é justamente na revisão que ele precisa
ser refeito.

DIVERGÊNCIA CONHECIDA, na figura 3
──────────────────────────────────
O manuscrito submetido declara Spearman −0,456 no país, −0,489 fora da Amazônia
Legal e −0,240 dentro dela. Recomputando aqui a partir do CSV depositado, com a
mesma população — 2.460 municípios com ao menos cinco pares, 2.207 fora e 253
dentro, contagens que conferem exatamente —, os valores são −0,459, −0,492 e
−0,235.

A diferença é de 0,003 a 0,005 e não altera nenhuma conclusão: a correlação
continua se fortalecendo fora da Amazônia, que é o argumento. Mas os números
impressos não são reproduzíveis pelo depósito, e isso precisa ser corrigido na
revisão. Tudo o mais confere: 46.536 pares, 8.192 repetições, 17,6% no país,
45,7% no Pará.

Há ainda um erro de rótulo. Os 253 municípios que a figura submetida chama de
"Legal Amazon" excluem Mato Grosso, que integra a Amazônia Legal. Com MT são
378 municípios, e a correlação fora dela passa a −0,503 — ou seja, corrigir o
rótulo reforça o argumento do artigo em vez de enfraquecê-lo. Este script usa a
definição correta e imprime as duas, para que a revisão possa escolher com o
número à vista.

Uso:  python gera_figuras_cea.py           # gera as quatro figuras em saida/
      python gera_figuras_cea.py --sem-permutacao   # pula a figura 2 (2 min)
"""
import importlib.util
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

RAIZ = os.path.dirname(os.path.abspath(__file__))
NACIONAL = os.path.join(RAIZ, '..', '03_analise_nacional')
CSV = os.path.join(NACIONAL, 'pam_soja_municipios.csv')
JSON = os.path.join(NACIONAL, 'repeticao_27_estados.json')
SAIDA = os.path.join(RAIZ, 'saida')

DPI = 400
MIN_PARES_MUNICIPIO = 5          # legenda da figura 3: "at least five pairs"
DESTAQUE = ['Floresta do Araguaia', 'Uruará', 'Paragominas']

# Amazônia Legal, Lei 12.651/2012: os sete estados do Norte, Mato Grosso e a
# parte do Maranhão a oeste do meridiano 44°O. Como a medida é estadual, o
# Maranhão entra inteiro — aproximação declarada, não descuido.
AMAZONIA_LEGAL = {'AC', 'AP', 'AM', 'MA', 'MT', 'PA', 'RO', 'RR', 'TO'}
AMAZONIA_SUBMETIDA = AMAZONIA_LEGAL - {'MT'}   # o recorte da figura submetida

AZUL, VERMELHO, LARANJA, CINZA = '#2E75B6', '#B00020', '#C55A11', '#808080'
plt.rcParams.update({'font.size': 11, 'axes.grid': True, 'grid.alpha': 0.3})


def salva(fig, nome):
    os.makedirs(SAIDA, exist_ok=True)
    caminho = os.path.join(SAIDA, nome)
    fig.savefig(caminho, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  {nome}')


def por_municipio(df):
    """Uma linha por município: UF, área mediana da série e taxa de repetição.

    A taxa tem como denominador o par de safras, nunca o registro — a mesma
    escolha de 07_repeticao_27_estados.py, e pelo mesmo motivo: a primeira
    safra de cada município não tem par e diluiria a taxa sem informar nada.
    """
    linhas = []
    for _, d in df.groupby('cod_ibge7'):
        d = d.sort_values('ano')
        v = d.rendimento_kg_ha.values
        if len(v) - 1 < MIN_PARES_MUNICIPIO:
            continue
        linhas.append((d.uf.iloc[0],
                       np.median(d.area_plantada_ha.values),
                       (np.diff(v) == 0).mean() * 100))
    return pd.DataFrame(linhas, columns=['uf', 'area', 'taxa'])


# ─────────────────────────── figura 1 ───────────────────────────
def figura1(res):
    ufs = {s: v for s, v in res['estados'].items() if v['amostra_suficiente']}
    s = pd.Series({k: v['taxa'] for k, v in ufs.items()}).sort_values()
    cores = [VERMELHO if u == 'PA' else LARANJA if u == 'SP' else AZUL
             for u in s.index]
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.barh(s.index, s.values, color=cores)
    ax.axvline(res['brasil']['taxa'], ls='--', color=CINZA, lw=1.6,
               label=f"Brazil ({res['brasil']['taxa']:.1f}%)")
    for i, v in enumerate(s.values):
        ax.text(v + 0.8, i, f'{v:.1f}%', va='center', fontsize=10)
    ax.set_xlim(0, 70)
    ax.set_xlabel('Consecutive seasons with identical yield (%)')
    ax.set_ylabel('State')
    ax.legend(loc='lower right')
    salva(fig, 'Figure_1.png')


# ─────────────────────────── figura 2 ───────────────────────────
def figura2(df, res):
    """Distribuição nula refeita pela função canônica, com a mesma semente.

    Importar de 07_repeticao_27_estados.py em vez de reimplementar garante que
    o histograma seja a mesma distribuição que produziu os h0_* do JSON. São
    cerca de dois minutos.
    """
    spec = importlib.util.spec_from_file_location(
        'repeticao', os.path.join(NACIONAL, '07_repeticao_27_estados.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    nulos = mod.teste_de_permutacao(df, np.random.default_rng(mod.SEED))
    b = res['brasil']
    assert round(nulos.mean(), 1) == b['h0_media'], (nulos.mean(), b['h0_media'])
    assert round(nulos.std(), 1) == b['h0_dp'], (nulos.std(), b['h0_dp'])

    obs = b['taxa']
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    ax.hist(nulos, bins=60, color=AZUL, alpha=0.75,
            label=f"Null distribution ({mod.PERMUTACOES:,} permutations)")
    ax.axvline(obs, color=VERMELHO, lw=3, label=f'Observed: {obs:.1f}%')
    ax.annotate(f"> {int(b['z'] // 1)} standard deviations\n"
                f"(p < {1 / mod.PERMUTACOES / 2:.4f})",
                xy=(obs, ax.get_ylim()[1] * 0.5),
                xytext=(obs - 4.3, ax.get_ylim()[1] * 0.72),
                color=VERMELHO, fontsize=10,
                arrowprops=dict(arrowstyle='->', color=VERMELHO, lw=1.8))
    ax.set_xlabel('Consecutive seasons with identical yield (%)')
    ax.set_ylabel('Frequency')
    ax.legend(loc='upper center')
    salva(fig, 'Figure_2.png')


# ─────────────────────────── figura 3 ───────────────────────────
def figura3(m):
    dentro = m.uf.isin(AMAZONIA_LEGAL)
    rho, _ = spearmanr(m.area, m.taxa)
    r_fora, _ = spearmanr(m.loc[~dentro, 'area'], m.loc[~dentro, 'taxa'])
    r_dentro, _ = spearmanr(m.loc[dentro, 'area'], m.loc[dentro, 'taxa'])

    fig, ax = plt.subplots(figsize=(6.6, 3.3))
    ax.scatter(m.loc[~dentro, 'area'], m.loc[~dentro, 'taxa'], s=12, alpha=0.35,
               color=AZUL, label=f'Other states (n = {(~dentro).sum():,})')
    ax.scatter(m.loc[dentro, 'area'], m.loc[dentro, 'taxa'], s=14, alpha=0.65,
               color=VERMELHO, label=f'Legal Amazon (n = {dentro.sum():,})')
    corte = pd.qcut(m.area, 10, duplicates='drop')
    dec = m.groupby(corte, observed=True).agg(area=('area', 'median'),
                                              taxa=('taxa', 'mean'))
    ax.plot(dec.area, dec.taxa, 'o-', color='black', lw=2.4, ms=6,
            label='Mean per area decile')
    ax.set_xscale('log')
    ax.set_xlabel('Municipal soybean planted area (ha, series median)')
    ax.set_ylabel('Repetition rate (%)')
    ax.set_title(f'Spearman = {rho:.3f} (n = {len(m):,} municipalities)')
    ax.legend(loc='upper right', fontsize=9)
    salva(fig, 'Figure_3.png')
    return rho, r_fora, r_dentro


# ─────────────────────────── figura 4 ───────────────────────────
def figura4(df):
    pa = df[df.uf == 'PA']
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    for nome, cor in zip(DESTAQUE, [VERMELHO, LARANJA, '#1F4E79']):
        d = pa[pa.nome.str.startswith(nome)].sort_values('ano')
        assert not d.empty, f'município não encontrado: {nome}'
        ax.plot(d.ano, d.rendimento_kg_ha, 'o-', color=cor, ms=5, label=nome)
    ax.set_xlabel('Crop year')
    ax.set_ylabel('Yield (kg ha$^{-1}$)')
    ax.legend(loc='lower right')
    salva(fig, 'Figure_4.png')


def main():
    df = pd.read_csv(CSV)
    res = json.load(open(JSON, encoding='utf-8'))
    print(f'{len(df):,} registros, {df.cod_ibge7.nunique():,} municípios')

    figura1(res)
    if '--sem-permutacao' not in sys.argv:
        figura2(df, res)
    else:
        print('  Figure_2.png pulada (--sem-permutacao)')
    m = por_municipio(df)
    rho, r_fora, r_dentro = figura3(m)
    figura4(df)

    sub = m.uf.isin(AMAZONIA_SUBMETIDA)
    r_sub_fora, _ = spearmanr(m.loc[~sub, 'area'], m.loc[~sub, 'taxa'])
    r_sub_dentro, _ = spearmanr(m.loc[sub, 'area'], m.loc[sub, 'taxa'])
    print('\nCorrelação de Spearman entre área plantada e taxa de repetição')
    print(f'  país                        : {rho:+.3f}   (manuscrito: -0.456)')
    print(f'  fora da Amazônia Legal      : {r_fora:+.3f}   com MT, {(~m.uf.isin(AMAZONIA_LEGAL)).sum():,} municípios')
    print(f'  dentro da Amazônia Legal    : {r_dentro:+.3f}   com MT, {m.uf.isin(AMAZONIA_LEGAL).sum():,} municípios')
    print(f'  fora, recorte da figura     : {r_sub_fora:+.3f}   sem MT, {(~sub).sum():,} municípios (manuscrito: -0.489)')
    print(f'  dentro, recorte da figura   : {r_sub_dentro:+.3f}   sem MT, {sub.sum():,} municípios (manuscrito: -0.240)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
