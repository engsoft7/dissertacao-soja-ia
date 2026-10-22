# -*- coding: utf-8 -*-
"""
Previsão da produção de soja do Pará (toneladas) para as próximas safras.

Produção é área vezes produtividade, e no Pará quem move a produção é a área:
de 2017 a 2024 a área plantada na PAM passou de cerca de 500 mil para 1,19
milhão de hectares, enquanto a produtividade oscilou em torno de 3 t/ha. Por
isso a previsão é decomposta: modelos de área, modelos de produtividade e o
produto dos dois, além de modelos diretos sobre a produção.

Fonte: PAM (SIDRA, tabela 5457), todos os municípios paraenses, 2001-2024, em
pesquisa/03_analise_nacional/pam_soja_municipios.csv. A produção é a soma, por
município, de rendimento x área plantada; a PAM publica a produção sobre a área
colhida, de modo que o total aqui é uma aproximação dela.

Avaliação em origem móvel: de cada ano-origem t0 de 2010 a 2023, prevê-se t0+1,
t0+2 e t0+3 (até 2024) usando só os anos <= t0. Métrica: erro percentual
absoluto médio (MAPE) por antecedência. A combinação escolhida para a projeção
é a de menor MAPE médio nas três antecedências; como a escolha usa o mesmo
retroteste, o erro dela é otimista, e por isso também se reporta uma combinação
fixada de antemão (crescimento exponencial da área nos últimos 5 anos x
referência da produtividade).

A projeção de 2025-2027 parte de 2024 e traz faixa de 80% obtida dos erros do
retroteste (quantis 10% e 90% do erro relativo em cada antecedência).

Uso:  python 03_previsao_producao_para.py
Saídas: previsao_producao_para.json, fig_previsao_producao_para.png
"""
import json
import os
from itertools import product

import numpy as np
import pandas as pd

from comum import ALVO, RAIZ, carrega_pam_para

ORIGENS = range(2010, 2024)
HORIZ = (1, 2, 3)


def serie_estadual():
    pa = carrega_pam_para()
    pa['prod_t'] = pa[ALVO] * pa.area_plantada_ha / 1000
    s = pa.groupby('ano').agg(area=('area_plantada_ha', 'sum'), producao=('prod_t', 'sum'),
                              municipios=('municipio', 'nunique'))
    s['rendimento'] = s.producao / s.area * 1000
    return s


# ---------------------------------------------------------------- modelos --
def ultimo(x, h):
    return x.iloc[-1]


def linear(n):
    def f(x, h):
        z = x.iloc[-n:]
        return max(np.polyval(np.polyfit(z.index, z.values, 1), z.index[-1] + h), 0.0)
    return f


def exponencial(n):
    def f(x, h):
        z = x.iloc[-n:]
        return float(np.exp(np.polyval(np.polyfit(z.index, np.log(z.values), 1), z.index[-1] + h)))
    return f


def amortecido(n=3, phi=0.8):
    """Taxa média de crescimento dos últimos n anos, amortecida a cada ano."""
    def f(x, h):
        g = (x.iloc[-1] / x.iloc[-1 - n]) ** (1 / n) - 1
        return float(x.iloc[-1] * np.prod([1 + g * phi ** k for k in range(1, h + 1)]))
    return f


def media_tendencia(x, h):
    """Referência da dissertação levada ao estado: média + tendência linear."""
    return float(np.polyval(np.polyfit(x.index, x.values, 1), x.index[-1] + h))


def media3(x, h):
    return float(x.iloc[-3:].mean())


AREA = {'Último valor': ultimo, 'Linear (5 anos)': linear(5), 'Exponencial (5 anos)': exponencial(5),
        'Exponencial (10 anos)': exponencial(10), 'Crescimento amortecido': amortecido()}
REND = {'Último valor': ultimo, 'Média + tendência': media_tendencia, 'Média dos 3 últimos': media3}
DIRETO = {'Produção: exponencial (5 anos)': exponencial(5), 'Produção: linear (5 anos)': linear(5),
          'Produção: último valor': ultimo}
FIXADA = ('Exponencial (5 anos)', 'Média + tendência')


def retroteste(s):
    regs = []
    for t0, h in product(ORIGENS, HORIZ):
        alvo = t0 + h
        if alvo not in s.index:
            continue
        hist = s.loc[:t0]
        obs = s.loc[alvo]
        for na, fa in AREA.items():
            a = fa(hist.area, h)
            regs.append(dict(t0=t0, h=h, tipo='área', modelo=na, prev=a, obs=obs.area))
            for nr, fr in REND.items():
                r = fr(hist.rendimento, h)
                regs.append(dict(t0=t0, h=h, tipo='produção', modelo=f'{na} x {nr}',
                                 prev=a * r / 1000, obs=obs.producao))
        for nr, fr in REND.items():
            regs.append(dict(t0=t0, h=h, tipo='rendimento', modelo=nr, prev=fr(hist.rendimento, h),
                             obs=obs.rendimento))
        for nd, fd in DIRETO.items():
            regs.append(dict(t0=t0, h=h, tipo='produção', modelo=nd, prev=fd(hist.producao, h),
                             obs=obs.producao))
    d = pd.DataFrame(regs)
    d['erro_rel'] = d.prev / d.obs - 1
    return d


def main():
    s = serie_estadual()
    d = retroteste(s)
    mape = (d.assign(ape=d.erro_rel.abs() * 100)
              .groupby(['tipo', 'modelo', 'h']).ape.mean().unstack('h').round(1))
    mape['média'] = mape.mean(axis=1).round(1)
    prod = mape.loc['produção'].sort_values('média')
    melhor = prod.index[0]
    fixada = f'{FIXADA[0]} x {FIXADA[1]}'

    def projeta(nome):
        if nome in DIRETO:
            f = DIRETO[nome]
            centrais = {2024 + h: f(s.producao, h) for h in HORIZ}
        else:
            na, nr = nome.split(' x ')
            centrais = {2024 + h: AREA[na](s.area, h) * REND[nr](s.rendimento, h) / 1000 for h in HORIZ}
        out = {}
        for h in HORIZ:
            e = d[(d.tipo == 'produção') & (d.modelo == nome) & (d.h == h)].erro_rel
            lo, hi = np.percentile(e, [10, 90])
            c = centrais[2024 + h]
            # erro_rel = prev/obs - 1  =>  obs = prev / (1 + erro)
            out[str(2024 + h)] = {'central_t': round(c), 'faixa80_t': [round(c / (1 + hi)), round(c / (1 + lo))]}
        return out

    saida = {
        'serie_estadual': {str(a): {'area_ha': round(r.area), 'producao_t': round(r.producao),
                                    'rendimento_kg_ha': round(r.rendimento), 'municipios': int(r.municipios)}
                           for a, r in s.iterrows()},
        'mape_%': {tipo: {m: v.to_dict() for m, v in mape.loc[tipo].iterrows()}
                   for tipo in mape.index.get_level_values(0).unique()},
        'melhor_no_retroteste': melhor,
        'combinacao_fixada_de_antemao': fixada,
        'projecao': {melhor: projeta(melhor), fixada: projeta(fixada)},
        'ressalvas': ['produção = rendimento x área plantada (a PAM usa a área colhida)',
                      'origens 2010-2023; para h=3, a última origem é 2021',
                      'a escolha do melhor modelo usa o próprio retroteste; o erro dele é otimista',
                      'a área depende de preço, crédito e abertura de áreas, que não estão no modelo'],
    }
    with open(os.path.join(RAIZ, 'previsao_producao_para.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)

    pd.set_option('display.width', 200)
    print(s.tail(10).round(0))
    for tipo in ('área', 'rendimento', 'produção'):
        print(f'\nMAPE (%) — {tipo}\n', mape.loc[tipo].sort_values('média').head(8))
    print('\nmelhor:', melhor, json.dumps(saida['projecao'], ensure_ascii=False, indent=1))
    figura(s, saida['projecao'], melhor, fixada)


def figura(s, proj, melhor, fixada):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(s.index, s.producao / 1e6, '-o', color='#071D69', ms=4, label='PAM (rendimento x área plantada)')
    for nome, cor in [(melhor, '#0F5995'), (fixada, '#8FB0D6')]:
        if nome not in proj:
            continue
        anos = [2024] + [int(a) for a in proj[nome]]
        c = [s.producao.iloc[-1] / 1e6] + [v['central_t'] / 1e6 for v in proj[nome].values()]
        lo = [c[0]] + [v['faixa80_t'][0] / 1e6 for v in proj[nome].values()]
        hi = [c[0]] + [v['faixa80_t'][1] / 1e6 for v in proj[nome].values()]
        ax.plot(anos, c, '--o', color=cor, ms=4, label=f'projeção: {nome}')
        ax.fill_between(anos, lo, hi, color=cor, alpha=0.18)
    ax.set_ylabel('milhões de toneladas')
    ax.set_title('Produção de soja no Pará: série e projeção com faixa de 80%', loc='left', fontsize=11)
    ax.grid(axis='y', alpha=0.3)
    ax.legend(fontsize=8, frameon=False, loc='upper left')
    for lado in ('top', 'right'):
        ax.spines[lado].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(RAIZ, 'fig_previsao_producao_para.png'), dpi=200)


if __name__ == '__main__':
    main()
