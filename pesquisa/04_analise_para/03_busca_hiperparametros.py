# -*- coding: utf-8 -*-
"""
Busca de hiperparâmetros do estudo de caso do Pará.

A base tem 415 registros, pequena demais para reservar uma janela de
desenvolvimento. A busca é, por isso, aninhada: para cada safra de teste da
validação leave-one-year-out externa, as configurações competem numa validação
interna sobre as safras de treino; só então o modelo vencedor é reajustado no
conjunto de treino completo e aplicado à safra de teste. Nenhuma safra
participa da seleção do modelo que a prevê.

A busca é aleatória, com orçamento fixo por modelo (Bergstra e Bengio, 2012).
A configuração já adotada na dissertação entra como candidata, o que permite
medir se a busca a supera.

Replica a decomposição do Capítulo 6: os modelos preveem o resíduo sobre o
modelo de referência (média histórica do município + tendência tecnológica) e
a produtividade é reconstruída somando-se o resíduo previsto à referência.

Uso:  python 03_busca_hiperparametros.py "Random Forest" [n_configs]
      python 03_busca_hiperparametros.py baseline
"""
import json
import os
import sys
import time
import warnings
from collections import Counter

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from xgboost import XGBRegressor

SEED, MIN_MUN, N_INTERNAS = 42, 4, 4
DADOS, SAIDA = '../dados', 'results'
FEATURES = ['NDVI_mean', 'NDVI_max', 'EVI_mean', 'EVI_max', 'precip_total', 'etp_total',
            'balanco_hidrico', 'temp_mean', 'temp_max', 'srad_mean', 'log_area']
PRECISA_ESCALA = {'SVR', 'MLP'}

ESPACO = {
    'Random Forest': {'n_estimators': [100, 150, 200, 300], 'max_depth': [3, 5, 8, 10, None],
                      'min_samples_leaf': [1, 2, 4, 8], 'max_features': ['sqrt', 0.5, 1.0]},
    'XGBoost': {'n_estimators': [100, 200, 400], 'max_depth': [2, 3, 4, 6],
                'learning_rate': [0.02, 0.05, 0.1], 'subsample': [0.7, 0.8, 1.0],
                'colsample_bytree': [0.6, 0.8, 1.0], 'reg_lambda': [1, 2, 5, 10]},
    'SVR': {'C': [1, 3, 10, 30, 100], 'epsilon': [0.05, 0.1, 0.2], 'gamma': ['scale', 'auto', 0.05]},
    'MLP': {'hidden_layer_sizes': [(32,), (64, 32), (100, 50), (32, 16)], 'alpha': [1e-3, 1e-2, 1e-1],
            'learning_rate_init': [1e-3, 3e-3], 'max_iter': [500, 800]},
}
FIXOS = {'Random Forest': dict(n_jobs=-1, random_state=SEED),
         'XGBoost': dict(tree_method='hist', n_jobs=-1, verbosity=0, random_state=SEED),
         'SVR': dict(), 'MLP': dict(early_stopping=True, random_state=SEED)}
CLASSES = {'Random Forest': RandomForestRegressor, 'XGBoost': XGBRegressor,
           'SVR': SVR, 'MLP': MLPRegressor}
ATUAL = {'Random Forest': dict(n_estimators=300, max_depth=10, min_samples_leaf=4, max_features=1.0),
         'XGBoost': dict(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8,
                         colsample_bytree=0.8, reg_lambda=2),
         'SVR': dict(C=10, epsilon=0.1, gamma='scale'),
         'MLP': dict(hidden_layer_sizes=(64, 32), alpha=1e-2, learning_rate_init=1e-3, max_iter=800)}


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
    df = pd.read_csv(f'{DADOS}/soja_para_mascarado_2001_2024.csv')
    df['balanco_hidrico'] = df.precip_total - df.etp_total
    df['log_area'] = np.log1p(df.soy_area_ha)
    return (df.dropna(subset=FEATURES + ['rendimento_kg_ha'])
              .sort_values(['municipio', 'ano']).reset_index(drop=True))


def referencia(y, anos, mun, tr, alvo):
    lin = LinearRegression().fit(anos[tr].reshape(-1, 1), y[tr])
    incl, am = lin.coef_[0], anos[tr].mean()
    media, geral = pd.Series(y[tr]).groupby(mun[tr]).mean(), y[tr].mean()
    return np.array([media.get(mun[k], geral) + incl * (anos[k] - am) for k in np.where(alvo)[0]])


def preve(nome, cfg, X, y, anos, mun, tr, te):
    b_tr, b_te = referencia(y, anos, mun, tr, tr), referencia(y, anos, mun, tr, te)
    Xtr, Xte = X[tr], X[te]
    if nome in PRECISA_ESCALA:
        esc = StandardScaler().fit(Xtr)
        Xtr, Xte = esc.transform(Xtr), esc.transform(Xte)
    mdl = CLASSES[nome](**cfg, **FIXOS[nome]).fit(Xtr, y[tr] - b_tr)
    return b_te + mdl.predict(Xte)


def metricas(obs, prev, media):
    obs, prev = np.array(obs), np.array(prev)
    rmse = float(np.sqrt(mean_squared_error(obs, prev)))
    return {'RMSE': round(rmse, 1), 'MAE': round(float(mean_absolute_error(obs, prev)), 1),
            'R2': round(float(r2_score(obs, prev)), 3), 'rRMSE_%': round(rmse / media * 100, 1)}


def _matrizes(df):
    """Colunas na forma que as rotinas de avaliação esperam."""
    y = df.rendimento_kg_ha.values.astype(float)
    anos, mun, X = df.ano.values, df.municipio.values, df[FEATURES].values
    safras = [a for a in sorted(set(anos)) if (anos == a).sum() >= MIN_MUN]
    return y, anos, mun, X, safras


def avalia_baseline(df):
    """Modelo de referência sob leave-one-year-out: média do município + tendência."""
    y, anos, mun, _, safras = _matrizes(df)
    obs, prev = [], []
    for ty in safras:
        obs += list(y[anos == ty])
        prev += list(referencia(y, anos, mun, anos != ty, anos == ty))
    return metricas(obs, prev, y.mean())


def avalia_modelo(alvo, n_cfg, df):
    """Busca aninhada e avaliação externa de um algoritmo, na base completa."""
    t0 = time.time()
    y, anos, mun, X, safras = _matrizes(df)
    cands = [ATUAL[alvo]] + amostra(alvo, n_cfg, np.random.default_rng(SEED))
    obs, prev, escolhidas = [], [], []
    for ty in safras:
        tr_ext = anos != ty
        internas = [a for a in safras if a != ty][-N_INTERNAS:]
        melhor, melhor_r = None, np.inf
        for cfg in cands:
            erros = [np.sqrt(mean_squared_error(
                        y[anos == vi], preve(alvo, cfg, X, y, anos, mun, tr_ext & (anos != vi), anos == vi)))
                     for vi in internas if (anos == vi).sum() >= MIN_MUN]
            r = float(np.mean(erros)) if erros else np.inf
            if r < melhor_r:
                melhor, melhor_r = cfg, r
        escolhidas.append(tuple(sorted((k, str(v)) for k, v in melhor.items())))
        obs += list(y[anos == ty])
        prev += list(preve(alvo, melhor, X, y, anos, mun, tr_ext, anos == ty))
    modal = Counter(escolhidas).most_common(1)[0]
    resultado = metricas(obs, prev, y.mean())
    resultado.update({'config_modal': dict(modal[0]), 'freq_modal': f'{modal[1]}/{len(escolhidas)}',
                      'n_configs': len(cands), 'segundos': round(time.time() - t0)})
    return resultado


def main():
    os.makedirs(SAIDA, exist_ok=True)
    alvo = sys.argv[1]
    n_cfg = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    df = carrega()
    arq = f'{SAIDA}/busca_hiperparametros.json'
    saida = json.load(open(arq, encoding='utf-8')) if os.path.exists(arq) else {}

    if alvo == 'baseline':
        saida['Baseline (sem clima)'] = avalia_baseline(df)
        print('Baseline:', saida['Baseline (sem clima)'])
    else:
        saida[alvo] = avalia_modelo(alvo, n_cfg, df)
        print(f"{alvo}: {saida[alvo]}")

    json.dump(saida, open(arq, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('gravado em', arq)


if __name__ == '__main__':
    main()
