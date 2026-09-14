# -*- coding: utf-8 -*-
"""
Graphical abstract: o artigo inteiro em um olhar.

A Elsevier pede uma imagem só, legível impressa a cerca de 13 cm de largura, e
com pouquíssimo texto. Isso obriga a escolher **uma** afirmação, e a escolhida
é a que o artigo tem de mais novo: a repetição no alvo não esconde capacidade
preditiva — ela fabrica desempenho aparente e apaga a diferença entre um modelo
e outro.

Dois painéis, na ordem em que o argumento se constrói:

  esquerda   a causa, que é o dado: uma série municipal com platô, o fato bruto
             de que safras consecutivas repetem o valor ao quilograma;
  direita    a consequência, que é a contribuição: com os preditores fixos e só
             o alvo corrompido, o R² aparente sobe enquanto o verdadeiro não se
             move, e a distância entre modelo e baseline vai a zero.

Tudo vem dos JSON versionados e do CSV do Pará. Nenhum número é digitado aqui:
um resumo gráfico que divergisse do artigo seria pior que não ter resumo.

Uso:  python gera_resumo_grafico.py
"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
NACIONAL = os.path.join(RAIZ, '..', '03_analise_nacional')
PARA = os.path.join(RAIZ, '..', 'dados', 'soja_para_mascarado_2001_2024.csv')
JSON_NAC = os.path.join(NACIONAL, 'repeticao_27_estados.json')
JSON_INJ = os.path.join(RAIZ, '..', '04_analise_para', 'injecao_de_repeticao.json')
SAIDA = os.path.join(RAIZ, 'saida')

DPI = 300
AZUL, VERMELHO, CINZA = '#2E75B6', '#B00020', '#7F7F7F'


def serie_com_maior_plato(csv):
    """A série paraense com o platô mais longo, para o painel da esquerda.

    Escolhida pelo dado e não à mão: se a base mudar, o exemplo continua sendo
    o mais eloquente que existe nela, e não um município que já foi.
    """
    df = pd.read_csv(csv)
    melhor, tamanho = None, 0
    for nome, d in df.groupby('municipio'):
        d = d.sort_values('ano')
        v = d.rendimento_kg_ha.values
        corrida = maior = 1
        for a, b in zip(v[:-1], v[1:]):
            corrida = corrida + 1 if a == b else 1
            maior = max(maior, corrida)
        if maior > tamanho:
            melhor, tamanho = (nome, d.ano.values, v), maior
    return melhor, tamanho


def main():
    res = json.load(open(JSON_NAC, encoding='utf-8'))
    inj = json.load(open(JSON_INJ, encoding='utf-8'))
    (nome, anos, y), plato = serie_com_maior_plato(PARA)

    plt.rcParams.update({'font.size': 12, 'axes.grid': True, 'grid.alpha': 0.25})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.6, 4.3),
                                   gridspec_kw={'width_ratios': [1, 1.15]})

    # ── esquerda: o fato bruto ──
    ax1.plot(anos, y, 'o-', color=CINZA, lw=2, ms=5, zorder=2)
    igual = np.r_[False, np.diff(y) == 0]
    for k in np.where(igual)[0]:
        ax1.plot(anos[k - 1:k + 1], y[k - 1:k + 1], '-', color=VERMELHO,
                 lw=4, zorder=3, solid_capstyle='round')
    ax1.set_xlabel('Crop year')
    ax1.set_ylabel('Reported yield (kg ha$^{-1}$)')
    ax1.set_title(f'{res["brasil"]["taxa"]}% of consecutive seasons\n'
                  'report identical yield', fontsize=13, pad=10)
    # canto superior esquerdo: é o único quadrante que a série não ocupa, e
    # no inferior o texto cruzava a subida dos primeiros anos
    ax1.text(0.03, 0.97, f'{res["brasil"]["pares"]:,} pairs\n'
                         f'{res["brasil"]["municipios"]:,} municipalities',
             transform=ax1.transAxes, fontsize=10, color=CINZA, va='top')

    # ── direita: a consequência ──
    n = inj['niveis']
    x = [v['injecao'] * 100 for v in n]
    ap = [v['aparente_modelo_R2'][0] for v in n]
    re = [v['real_modelo_R2'][0] for v in n]
    ax2.plot(x, ap, 'o-', color=AZUL, lw=3, ms=7, label='Apparent skill')
    ax2.plot(x, re, 's-', color=VERMELHO, lw=3, ms=7, label='True skill')
    ax2.fill_between(x, re, ap, color=AZUL, alpha=0.12)
    ax2.set_xlabel('Repetition injected into the target (%)')
    ax2.set_ylabel('R²')
    ax2.set_title('Repetition inflates measured skill\nwithout improving it',
                  fontsize=13, pad=10)
    ax2.legend(fontsize=11, loc='upper left', framealpha=0.95)
    ax2.text(0.5, 0.04, 'predictors unchanged throughout',
             transform=ax2.transAxes, fontsize=10, color=CINZA, ha='center')

    fig.tight_layout()
    os.makedirs(SAIDA, exist_ok=True)
    caminho = os.path.join(SAIDA, 'Graphical_abstract.png')
    fig.savefig(caminho, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    from PIL import Image
    im = Image.open(caminho)
    print(f'Graphical_abstract.png  {im.size[0]}x{im.size[1]} px')
    print(f'exemplo do painel esquerdo: {nome}, platô de {plato} safras')
    # A Elsevier pede ao menos 1100 px de largura; abaixo disso o resumo sai
    # ilegível na página de sumário, que é o único lugar onde ele aparece.
    assert im.size[0] >= 1100, f'largura insuficiente: {im.size[0]} px'
    return 0


if __name__ == '__main__':
    sys.exit(main())
