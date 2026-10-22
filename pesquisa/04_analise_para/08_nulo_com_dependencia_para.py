# -*- coding: utf-8 -*-
"""
Teste de acaso com dependência temporal para a repetição no Pará.

A subseção 6.4 compara os 40,1% de pares repetidos com uma permutação simples
dentro de cada município. Essa permutação destrói a ordem das séries, e uma
série de produtividade tem autocorrelação: safras vizinhas se parecem mais do
que safras sorteadas. Este script refaz a comparação contra nulos que preservam
essa dependência, os mesmos de 03_analise_nacional/08_nulo_com_dependencia.py,
cujas funções são importadas e não recopiadas:

  - permutação simples, para a comparação lado a lado;
  - IAAFT, que mantém a autocorrelação e exatamente os mesmos valores;
  - AR(1) com rho de 0,3 a 0,9, mapeado à marginal observada, inclusive com
    autocorrelação muito acima da observada (0,28).

Roda duas vezes: com todas as séries de pelo menos duas safras (os 377 pares
da subseção 6.4) e só com as de seis ou mais, o mínimo que o script nacional
exige para o IAAFT. O IAAFT usa 300 réplicas, por custo; os demais, 1.000.

Uso:  python 08_nulo_com_dependencia_para.py
Saída: nulo_com_dependencia_para.json
"""
import importlib.util
import json
import os

import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(RAIZ, '..', 'dados', 'soja_para_mascarado_2001_2024.csv')
NACIONAL = os.path.join(RAIZ, '..', '03_analise_nacional', '08_nulo_com_dependencia.py')
SAIDA = os.path.join(RAIZ, 'nulo_com_dependencia_para.json')

MINIMOS = (2, 6)
REPLICAS, REPLICAS_IAAFT = 1000, 300
RHOS = (0.3, 0.5, 0.7, 0.9)
SEED = 42


def nulo_nacional():
    """Importa 08_nulo_com_dependencia.py, cujo nome começa por dígito."""
    spec = importlib.util.spec_from_file_location('nulo_com_dependencia', NACIONAL)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def analisa(n, df, minimo):
    n.MIN_SAFRAS = minimo
    series = n.series_por_municipio(df)
    grupos = n.por_comprimento(series)
    rep = tot = 0
    for M in grupos.values():
        r, t = n.repeticoes(M)
        rep += r
        tot += t
    acf = np.nanmean([n.autocorrelacao_lag1(np.array([v])) for v in series])
    res = {'municipios': len(series), 'pares': tot, 'repetidos': rep,
           'taxa_obs': 100 * rep / tot, 'acf_lag1_obs': acf}

    rng = np.random.default_rng(SEED)
    nulos = {'permutacao': lambda M: n.permutacao_simples(M, rng),
             'iaaft': lambda M: n.iaaft(M, rng)}
    for rho in RHOS:
        nulos[f'ar1_{rho}'] = (lambda rho: lambda M: n.ar1_com_marginal(M, rho, rng))(rho)
    for nome, gera in nulos.items():
        taxas = []
        for _ in range(REPLICAS_IAAFT if nome == 'iaaft' else REPLICAS):
            rr = tt = 0
            for M in grupos.values():
                if M.shape[1] < 2:
                    continue
                r, t = n.repeticoes(gera(M))
                rr += r
                tt += t
            taxas.append(100 * rr / tt)
        taxas = np.array(taxas)
        res[nome] = {'media': taxas.mean(), 'dp': taxas.std(), 'max': taxas.max(),
                     'z': (res['taxa_obs'] - taxas.mean()) / taxas.std()}
    return res


def virgula(x, casas=1):
    return f'{x:.{casas}f}'.replace('.', ',')


def imprime(minimo, r):
    print(f'\n== séries com {minimo}+ safras: {r["municipios"]} municípios, '
          f'{r["repetidos"]} de {r["pares"]} pares repetidos ({virgula(r["taxa_obs"])}%), '
          f'autocorrelação de defasagem 1 = {virgula(r["acf_lag1_obs"], 2)}')
    for nome in ['permutacao', 'iaaft'] + [f'ar1_{rho}' for rho in RHOS]:
        d = r[nome]
        print(f'  {nome:11s} {virgula(d["media"])}% ± {virgula(d["dp"])}  '
              f'máx {virgula(d["max"])}%  z = {virgula(d["z"])}')


def main():
    n = nulo_nacional()
    df = pd.read_csv(CSV)
    saida = {}
    for minimo in MINIMOS:
        saida[f'min_safras_{minimo}'] = analisa(n, df, minimo)
        imprime(minimo, saida[f'min_safras_{minimo}'])
    with open(SAIDA, 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, default=float)
    print(f'\ngravado em {os.path.basename(SAIDA)}')


if __name__ == '__main__':
    main()
