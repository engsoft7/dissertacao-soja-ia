# -*- coding: utf-8 -*-
"""
Confirmação da busca de hiperparâmetros do estudo nacional.

A busca (03_busca_hiperparametros.py) usou subamostra de 4.000 registros por
custo computacional. Este script reavalia, no protocolo integral de 7.000
registros (5.000 para o SVR, como na avaliação), as três melhores
configurações de cada modelo mais a configuração originalmente adotada na
dissertação. O objetivo é verificar se a ordenação entre configurações — e,
portanto, a configuração vencedora — se mantém quando a subamostra aumenta.

As safras de validação continuam sendo 2014 e 2015, dentro da janela de
desenvolvimento; as safras de teste (2016-2020) seguem intocadas.

Uso:  python 06_confirma_busca.py ["Nome do Modelo"]
"""
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from xgboost import XGBRegressor

SEED, SUB, SUB_SVR, DEV_ATE = 42, 7000, 5000, 2015
VAL_INTERNAS = [2014, 2015]
PRECISA_ESCALA = {'SVR', 'MLP'}
SAIDA = 'results'
TOP = 3

FIXOS = {'Random Forest': dict(n_jobs=-1, random_state=SEED),
         'XGBoost': dict(tree_method='hist', n_jobs=-1, verbosity=0, random_state=SEED),
         'SVR': dict(), 'MLP': dict(early_stopping=True, random_state=SEED)}
CLASSES = {'Random Forest': RandomForestRegressor, 'XGBoost': XGBRegressor,
           'SVR': SVR, 'MLP': MLPRegressor}


def converte(cfg):
    """Reconstrói os tipos dos hiperparâmetros salvos como texto."""
    out = {}
    for k, v in cfg.items():
        if v == 'None':
            out[k] = None
        elif v in ('sqrt', 'scale', 'auto'):
            out[k] = v
        elif v.startswith('('):
            out[k] = tuple(int(x) for x in v.strip('()').replace(' ', '').rstrip(',').split(','))
        else:
            try:
                out[k] = int(v) if float(v) == int(float(v)) and 'e' not in v.lower() else float(v)
            except ValueError:
                out[k] = float(v)
    return out


def carrega():
    df = pd.read_csv('data/data_cast.csv')
    fora = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
    feat = [c for c in df.columns if c not in fora and df[c].dtype != 'object']
    return (df[feat].fillna(df[feat].median()).values, df['YIELD'].values.astype(float),
            df['YIELD_TREND'].values.astype(float),
            df['YIELD_TREND_CORRECTED'].values.astype(float), df['HARVESTED'].values)


def avalia(nome, cfg, X, Y, TREND, ANOM, anos):
    erros = []
    for val in VAL_INTERNAS:
        tr = (anos <= DEV_ATE) & (anos != val)
        te = anos == val
        idx = np.where(tr)[0]
        if len(idx) > SUB:
            idx = np.random.RandomState(1000 + val).choice(idx, SUB, replace=False)
        Xtr, Xte, atr = X[idx], X[te], ANOM[idx]
        if nome in PRECISA_ESCALA:
            esc = StandardScaler().fit(Xtr)
            Xtr, Xte = esc.transform(Xtr), esc.transform(Xte)
            if nome == 'SVR':
                Xtr, atr = Xtr[:SUB_SVR], atr[:SUB_SVR]
        mdl = CLASSES[nome](**cfg, **FIXOS[nome]).fit(Xtr, atr)
        erros.append(np.sqrt(mean_squared_error(Y[te], mdl.predict(Xte) + TREND[te])))
    return float(np.mean(erros))


def main():
    modelos = [sys.argv[1]] if len(sys.argv) > 1 else ['SVR', 'MLP', 'XGBoost', 'Random Forest']
    X, Y, TREND, ANOM, anos = carrega()
    arq = f'{SAIDA}/confirmacao_7000.json'
    saida = json.load(open(arq, encoding='utf-8')) if os.path.exists(arq) else {}

    for nome in modelos:
        ck = f'{SAIDA}/_ck_{nome.replace(" ", "_")}.json'
        linhas = sorted(json.load(open(ck, encoding='utf-8')), key=lambda r: r['rmse_val'])
        cands = linhas[:TOP]
        atual = next(r for r in linhas if r['atual'])
        if atual not in cands:
            cands = cands + [atual]

        print(f'===== {nome}: {len(cands)} candidatas reavaliadas com {SUB} registros =====', flush=True)
        res = []
        for r in cands:
            t0 = time.time()
            rmse = avalia(nome, converte(r['config']), X, Y, TREND, ANOM, anos)
            res.append({'config': r['config'], 'rmse_4000': r['rmse_val'],
                        'rmse_7000': round(rmse, 1), 'atual': r['atual']})
            print(f"  4000={r['rmse_val']:6.1f}  7000={rmse:6.1f}  ({time.time()-t0:5.1f}s)"
                  f"{'  (config adotada)' if r['atual'] else ''}  {r['config']}", flush=True)

        ordem_4k = [i for i, _ in sorted(enumerate(res), key=lambda p: p[1]['rmse_4000'])]
        ordem_7k = [i for i, _ in sorted(enumerate(res), key=lambda p: p[1]['rmse_7000'])]
        vencedor_mantido = ordem_4k[0] == ordem_7k[0]
        saida[nome] = {'candidatas': res, 'vencedor_mantido': vencedor_mantido,
                       'ordem_identica': ordem_4k == ordem_7k}
        print(f'  --> vencedor {"MANTIDO" if vencedor_mantido else "MUDOU"} | '
              f'ordenação {"idêntica" if ordem_4k == ordem_7k else "alterada"}\n', flush=True)
        json.dump(saida, open(arq, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
