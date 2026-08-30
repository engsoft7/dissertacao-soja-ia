# -*- coding: utf-8 -*-
"""
Busca de hiperparâmetros do estudo nacional.

Protocolo: busca aleatória com orçamento fixo por modelo (Bergstra e Bengio,
2012). A seleção usa exclusivamente a janela de desenvolvimento 2001-2015, com
validação interna sobre as safras de 2014 e 2015. As safras de teste da
Tabela 3 (2016-2020) não participam de nenhuma etapa da seleção, de modo que as
métricas ali reportadas permanecem honestas.

O alvo e a reconstrução replicam 01_treina_modelos.py: os modelos preveem a
anomalia climática (YIELD_TREND_CORRECTED) e a produtividade é reconstruída
somando-se YIELD_TREND. O erro é medido na produtividade, em kg/ha.

Por custo computacional, a busca usa subamostra de 4.000 registros por safra de
treino, contra os 7.000 do protocolo de avaliação; a subamostra afeta o nível
absoluto do erro de validação, não a ordenação entre configurações, que é o que
a busca precisa resolver.

Uso:  python 03_busca_hiperparametros.py "XGBoost" [n_configs]
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

SEED, SUB, DEV_ATE = 42, 4000, 2015
VAL_INTERNAS = [2014, 2015]
PRECISA_ESCALA = {'SVR', 'MLP'}
SAIDA = 'results'

ESPACO = {
    'Random Forest': {'n_estimators': [70, 100, 200], 'max_depth': [6, 10, 16, None],
                      'min_samples_leaf': [1, 2, 5, 10], 'max_features': ['sqrt', 0.3, 1.0]},
    'XGBoost': {'n_estimators': [150, 250, 400, 600], 'max_depth': [3, 4, 6, 8],
                'learning_rate': [0.02, 0.05, 0.06, 0.1], 'subsample': [0.7, 0.8, 0.9],
                'colsample_bytree': [0.6, 0.8, 1.0], 'reg_lambda': [1, 2, 5],
                'min_child_weight': [1, 3, 5]},
    'SVR': {'C': [1, 3, 10, 30, 100], 'epsilon': [0.02, 0.05, 0.1, 0.2],
            'gamma': ['scale', 'auto', 0.005, 0.01]},
    'MLP': {'hidden_layer_sizes': [(64, 32), (100, 50), (200, 100), (128, 64, 32)],
            'alpha': [1e-5, 1e-4, 1e-3, 1e-2], 'learning_rate_init': [5e-4, 1e-3, 3e-3],
            'max_iter': [250, 400]},
}
FIXOS = {'Random Forest': dict(n_jobs=-1, random_state=SEED),
         'XGBoost': dict(tree_method='hist', n_jobs=-1, verbosity=0, random_state=SEED),
         'SVR': dict(), 'MLP': dict(early_stopping=True, random_state=SEED)}
CLASSES = {'Random Forest': RandomForestRegressor, 'XGBoost': XGBRegressor,
           'SVR': SVR, 'MLP': MLPRegressor}
ATUAL = {'Random Forest': dict(n_estimators=70, max_depth=16, min_samples_leaf=1, max_features=1.0),
         'XGBoost': dict(n_estimators=250, max_depth=6, learning_rate=0.06, subsample=0.8,
                         colsample_bytree=0.8, reg_lambda=1, min_child_weight=1),
         'SVR': dict(C=10, epsilon=0.1, gamma='scale'),
         'MLP': dict(hidden_layer_sizes=(100, 50), alpha=1e-3, learning_rate_init=1e-3, max_iter=250)}


def amostra(nome, n, rng):
    esp, vistas, saida = ESPACO[nome], set(), []
    for _ in range(n * 300):
        if len(saida) >= n:
            break
        cfg = {k: v[rng.integers(len(v))] for k, v in esp.items()}
        ch = tuple(sorted((k, str(v)) for k, v in cfg.items()))
        if ch not in vistas:
            vistas.add(ch)
            saida.append(cfg)
    return saida


def carrega():
    df = pd.read_csv('data/data_cast.csv')
    fora = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
    feat = [c for c in df.columns if c not in fora and df[c].dtype != 'object']
    return (df[feat].fillna(df[feat].median()).values, df['YIELD'].values.astype(float),
            df['YIELD_TREND'].values.astype(float), df['YIELD_TREND_CORRECTED'].values.astype(float),
            df['HARVESTED'].values, len(feat))


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
        mdl = CLASSES[nome](**cfg, **FIXOS[nome]).fit(Xtr, atr)
        erros.append(np.sqrt(mean_squared_error(Y[te], mdl.predict(Xte) + TREND[te])))
    return float(np.mean(erros))


def main():
    os.makedirs(SAIDA, exist_ok=True)
    nome = sys.argv[1]
    n_cfg = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    X, Y, TREND, ANOM, anos, nfeat = carrega()
    arq = f'{SAIDA}/busca_hiperparametros.json'
    saida = json.load(open(arq, encoding='utf-8')) if os.path.exists(arq) else {}
    ck = f'{SAIDA}/_ck_{nome.replace(" ", "_")}.json'
    linhas = json.load(open(ck, encoding='utf-8')) if os.path.exists(ck) else []
    feitas = {tuple(sorted(r['config'].items())) for r in linhas}

    cands = [ATUAL[nome]] + amostra(nome, n_cfg, np.random.default_rng(SEED))
    print(f'{nfeat} variáveis | desenvolvimento 2001-{DEV_ATE} | validação interna {VAL_INTERNAS} '
          f'| {len(cands)} configurações ({len(feitas)} já feitas)', flush=True)

    for i, cfg in enumerate(cands):
        chave = tuple(sorted((k, str(v)) for k, v in cfg.items()))
        if chave in feitas:
            continue
        t0 = time.time()
        r = avalia(nome, cfg, X, Y, TREND, ANOM, anos)
        linhas.append({'config': {k: str(v) for k, v in cfg.items()},
                       'rmse_val': round(r, 1), 'atual': i == 0})
        json.dump(linhas, open(ck, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print(f'  [{i:2d}] RMSE_val={r:6.1f} ({time.time()-t0:5.1f}s)'
              f'{" (config atual)" if i == 0 else ""}  {cfg}', flush=True)

    if len(linhas) == len(cands):
        linhas.sort(key=lambda r: r['rmse_val'])
        melhor = linhas[0]
        atual = next(r for r in linhas if r['atual'])
        saida[nome] = {'melhor': melhor, 'atual': atual, 'n_configs': len(cands),
                       'ganho_kg_ha': round(atual['rmse_val'] - melhor['rmse_val'], 1),
                       'posicao_da_atual': 1 + [r['rmse_val'] for r in linhas].index(atual['rmse_val']),
                       'todas': linhas}
        json.dump(saida, open(arq, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
        print(f"\n{nome}: melhor={melhor['rmse_val']} | atual={atual['rmse_val']} "
              f"(posição {saida[nome]['posicao_da_atual']}/{len(cands)}) "
              f"| ganho={saida[nome]['ganho_kg_ha']:+.1f} kg/ha")
    else:
        print(f'\nparcial: {len(linhas)}/{len(cands)} — rode de novo para continuar')


if __name__ == '__main__':
    main()
