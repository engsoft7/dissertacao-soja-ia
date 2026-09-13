# -*- coding: utf-8 -*-
"""
A repetição no alvo, sozinha, apaga a vantagem do modelo ambiental?

Observar que nenhum algoritmo supera uma baseline de história e tendência onde
a repetição é alta não prova que a culpa é da repetição: os preditores podem
simplesmente ser fracos ali. As duas explicações produzem a mesma tabela, e o
artigo precisava separá-las.

Este experimento separa. Os preditores ficam **intactos** — os mesmos NDVI,
EVI, chuva, temperatura e radiação, nos mesmos municípios e anos. Só o alvo é
corrompido: uma fração crescente dos registros passa a repetir o valor da
safra anterior, imitando o que uma pesquisa faz quando carrega o registro em
vez de medir. Se a vantagem do modelo ambiental sobre a baseline encolher à
medida que a fração sobe, a causa só pode estar no alvo, porque nada mais mudou.

Cada nível é medido de duas maneiras, e o contraste entre elas é o resultado:

  - **contra o alvo corrompido**, que é o que um pesquisador veria se a
    pesquisa tivesse carregado aqueles valores e ele não soubesse;
  - **contra o valor original**, que é o que de fato aconteceu na lavoura.

A primeira medida sobe com a injeção: valores carregados são triviais de
prever pela própria história, e o R² aparente melhora. A segunda cai: o modelo
treinado em registros carregados perde a capacidade de acertar o valor
verdadeiro. Um dado que piora enquanto parece melhorar é a definição do
problema que este artigo descreve.

A configuração de cada algoritmo é mantida fixa, a adotada na dissertação. A
busca aninhada refeita a cada nível e réplica custaria dias e acrescentaria uma
fonte de variação onde se quer isolar uma só.

Uso:  python 07_injecao_de_repeticao.py
      python 07_injecao_de_repeticao.py --replicas 5   # ensaio rápido
"""
import importlib.util
import json
import os
import sys
import time

import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(RAIZ, 'injecao_de_repeticao.json')

NIVEIS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
REPLICAS = 20
MODELO = 'Random Forest'
SEED = 42


def carrega_modulo():
    caminho = os.path.join(RAIZ, '03_busca_hiperparametros.py')
    spec = importlib.util.spec_from_file_location('busca_hiperparametros', caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo.DADOS = os.path.join(RAIZ, '..', 'dados')
    return modulo


def injeta(df, fracao, rng):
    """Carrega o valor da safra anterior numa fração dos registros.

    Elegível é todo registro que tem safra anterior imediata no mesmo
    município. A injeção é sequencial dentro da série, de modo que carregar
    dois registros seguidos produz um platô de três safras — o mesmo formato
    que a PAM exibe, e não pares isolados.
    """
    d = df.sort_values(['municipio', 'ano']).reset_index(drop=True).copy()
    y = d.rendimento_kg_ha.values.astype(float)
    pos = {}
    for i, (mun, ano) in enumerate(zip(d.municipio.values, d.ano.values)):
        pos[(mun, ano)] = i
    elegiveis = [i for i, (mun, ano) in enumerate(zip(d.municipio.values, d.ano.values))
                 if (mun, ano - 1) in pos]
    n = int(round(fracao * len(elegiveis)))
    if n:
        for i in sorted(rng.choice(elegiveis, size=n, replace=False)):
            mun, ano = d.municipio.values[i], d.ano.values[i]
            y[i] = y[pos[(mun, ano - 1)]]
    d['rendimento_kg_ha'] = y
    return d


def taxa_de_repeticao(df):
    r = t = 0
    for _, d in df.groupby('municipio'):
        v = d.sort_values('ano').rendimento_kg_ha.values
        if len(v) < 2:
            continue
        r += int((np.diff(v) == 0).sum())
        t += len(v) - 1
    return r / t * 100 if t else float('nan')


def avalia(mod, df, y_verdadeiro):
    """Leave-one-year-out, medido contra o alvo corrompido e contra o original.

    O treino usa sempre o alvo corrompido — é o único que a pesquisa publicaria.
    O que muda é o gabarito da conferência: o mesmo vetor de previsões é
    comparado ao que foi publicado e ao que de fato ocorreu.
    """
    y, anos, mun, X, safras = mod._matrizes(df)
    saida = {}
    for nome in ('baseline', 'modelo'):
        obs_c, obs_v, prev = [], [], []
        for ty in safras:
            te = anos == ty
            p = (mod.referencia(y, anos, mun, ~te, te) if nome == 'baseline'
                 else mod.preve(MODELO, mod.ATUAL[MODELO], X, y, anos, mun, ~te, te))
            prev += list(p)
            obs_c += list(y[te])
            obs_v += list(y_verdadeiro[te])
        saida[nome] = {'corrompido': mod.metricas(obs_c, prev, np.mean(obs_c)),
                       'verdadeiro': mod.metricas(obs_v, prev, np.mean(obs_v))}
    return saida


def uma_replica(mod, base, fracao, rng):
    d = injeta(base, fracao, rng)
    d['balanco_hidrico'] = d.precip_total - d.etp_total
    d['log_area'] = np.log1p(d.soy_area_ha)
    # o original, na mesma ordem que _matrizes devolve
    ordem = base.sort_values(['municipio', 'ano']).reset_index(drop=True)
    y_verd = ordem.rendimento_kg_ha.values.astype(float)
    a = avalia(mod, d, y_verd)
    return {
        'taxa': taxa_de_repeticao(d),
        'aparente_baseline_R2': a['baseline']['corrompido']['R2'],
        'aparente_modelo_R2': a['modelo']['corrompido']['R2'],
        'aparente_diferenca': a['modelo']['corrompido']['R2'] - a['baseline']['corrompido']['R2'],
        'real_baseline_R2': a['baseline']['verdadeiro']['R2'],
        'real_modelo_R2': a['modelo']['verdadeiro']['R2'],
        'real_modelo_MAE': a['modelo']['verdadeiro']['MAE'],
    }


def main():
    replicas = REPLICAS
    if '--replicas' in sys.argv:
        replicas = int(sys.argv[sys.argv.index('--replicas') + 1])
    mod = carrega_modulo()
    base = mod.carrega()
    rng = np.random.default_rng(SEED)

    print(f'{len(base):,} registros, {base.municipio.nunique()} municípios do Pará')
    print(f'taxa de repetição observada: {taxa_de_repeticao(base):.1f}%')
    print(f'{MODELO}, configuração da dissertação, {replicas} réplicas por nível\n')
    print(f'{"":>9s}{"":>11s}{"  aparente (alvo publicado)":>28s}'
          f'{"    real (valor verdadeiro)":>28s}')
    print(f'{"injeção":>9s}{"repetição":>11s}{"baseline":>11s}{"modelo":>9s}{"dif.":>8s}'
          f'{"baseline":>11s}{"modelo":>9s}{"MAE":>8s}')

    linhas = []
    t0 = time.time()
    for fracao in NIVEIS:
        reps = [uma_replica(mod, base, fracao, rng) for _ in range(replicas)]
        agg = {k: (float(np.mean([r[k] for r in reps])),
                   float(np.std([r[k] for r in reps]))) for k in reps[0]}
        linhas.append({'injecao': fracao, 'replicas': replicas,
                       **{k: [round(v[0], 3), round(v[1], 3)] for k, v in agg.items()}})
        print(f'{fracao * 100:>8.0f}%{agg["taxa"][0]:>10.1f}%'
              f'{agg["aparente_baseline_R2"][0]:>11.3f}{agg["aparente_modelo_R2"][0]:>9.3f}'
              f'{agg["aparente_diferenca"][0]:>+8.3f}'
              f'{agg["real_baseline_R2"][0]:>11.3f}{agg["real_modelo_R2"][0]:>9.3f}'
              f'{agg["real_modelo_MAE"][0]:>8.0f}')

    print(f'\n{time.time() - t0:.0f}s')
    print('\nOs preditores são os mesmos em todas as linhas. O que muda é só quanto')
    print('do alvo foi carregado do ano anterior. O R² aparente sobe enquanto o real')
    print('cai: a corrupção do alvo fabrica desempenho onde destrói capacidade.')

    r = {'niveis': linhas, 'replicas': replicas, 'modelo': MODELO,
         'configuracao': {k: str(v) for k, v in mod.ATUAL[MODELO].items()},
         'semente': SEED, 'registros': int(len(base)),
         'municipios': int(base.municipio.nunique()),
         'taxa_observada': round(taxa_de_repeticao(base), 1)}
    with open(SAIDA, 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    print(f'gravado em {os.path.basename(SAIDA)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
