# -*- coding: utf-8 -*-
"""
Avalia as configurações vencedoras da busca (03_busca_hiperparametros.py) no
protocolo oficial do estudo nacional: validação leave-one-year-out sobre
2016-2020, subamostra de 7.000 registros por safra (5.000 para o SVR),
sementes idênticas às de 01_treina_modelos.py.

As safras de teste não participaram da seleção dos hiperparâmetros, feita
apenas na janela 2001-2015, de modo que estas métricas são comparáveis às da
versão anterior da Tabela 3.

Uso:  python 04_avalia_ajustado.py
"""
import json
import os
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from xgboost import XGBRegressor

SEED, SUB, SUB_SVR = 42, 7000, 5000
SAFRAS_TESTE = [2016, 2017, 2018, 2019, 2020]
PRECISA_ESCALA = {'SVR', 'MLP'}
SAIDA = 'results'

AJUSTADOS = {
    'Random Forest': RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=2,
                                           max_features='sqrt', n_jobs=-1, random_state=SEED),
    'XGBoost': XGBRegressor(n_estimators=400, max_depth=6, learning_rate=0.02, subsample=0.7,
                            colsample_bytree=1.0, reg_lambda=5, min_child_weight=3,
                            tree_method='hist', n_jobs=-1, verbosity=0, random_state=SEED),
    'SVR': SVR(C=100, epsilon=0.05, gamma=0.005),
    'MLP': MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3, learning_rate_init=3e-3,
                        max_iter=250, early_stopping=True, random_state=SEED),
}


def main():
    os.makedirs(SAIDA, exist_ok=True)
    df = pd.read_csv('data/data_cast.csv')
    fora = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
    feat = [c for c in df.columns if c not in fora and df[c].dtype != 'object']
    X = df[feat].fillna(df[feat].median()).values
    Y = df['YIELD'].values.astype(float)
    TREND = df['YIELD_TREND'].values.astype(float)
    ANOM = df['YIELD_TREND_CORRECTED'].values.astype(float)
    anos = df['HARVESTED'].values

    # mesmas subamostras de 01_treina_modelos.py
    sub = {ty: np.random.RandomState(1000 + ty).choice(
        np.where(anos != ty)[0], min(SUB, int((anos != ty).sum())), replace=False)
        for ty in SAFRAS_TESTE}

    saida = {}
    for nome, base in AJUSTADOS.items():
        t0 = time.time()
        por_safra, obs, prev = {}, [], []
        for ty in SAFRAS_TESTE:
            idx, te = sub[ty], anos == ty
            Xtr, Xte, atr = X[idx], X[te], ANOM[idx]
            if nome in PRECISA_ESCALA:
                esc = StandardScaler().fit(Xtr)
                Xtr, Xte = esc.transform(Xtr), esc.transform(Xte)
                if nome == 'SVR':
                    Xtr, atr = Xtr[:SUB_SVR], atr[:SUB_SVR]
            from sklearn.base import clone
            mdl = clone(base).fit(Xtr, atr)
            pred = mdl.predict(Xte) + TREND[te]
            r = np.sqrt(mean_squared_error(Y[te], pred))
            por_safra[int(ty)] = {'rmse': round(float(r), 1),
                                  'mae': round(float(mean_absolute_error(Y[te], pred)), 1),
                                  'r2': round(float(r2_score(Y[te], pred)), 3)}
            obs += list(Y[te])
            prev += list(pred)
            print(f'  {nome} {ty}: RMSE={r:.0f} R2={r2_score(Y[te], pred):+.3f}', flush=True)
        obs, prev = np.array(obs), np.array(prev)
        saida[nome] = {'per_year': por_safra,
                       'RMSE_pool': round(float(np.sqrt(mean_squared_error(obs, prev))), 1),
                       'MAE_pool': round(float(mean_absolute_error(obs, prev)), 1),
                       'R2_pool': round(float(r2_score(obs, prev)), 3),
                       'segundos': round(time.time() - t0)}
        pd.DataFrame({'y_true': obs, 'y_pred': prev}).to_csv(
            f'{SAIDA}/pred_ajustado_{nome.replace(" ", "_")}.csv', index=False)
        print(f'>>> {nome}: RMSE={saida[nome]["RMSE_pool"]} MAE={saida[nome]["MAE_pool"]} '
              f'R2={saida[nome]["R2_pool"]}\n', flush=True)

    json.dump(saida, open(f'{SAIDA}/resultados_ajustados.json', 'w', encoding='utf-8'),
              indent=2, ensure_ascii=False)

    # Comparativo antes/depois: depende de 01_treina_modelos.py ter rodado antes,
    # pois e ele que gera results/all_results.json. Sem esse arquivo o
    # comparativo e apenas omitido -- os resultados acima ja foram gravados.
    caminho_antes = f'{SAIDA}/all_results.json'
    if not os.path.exists(caminho_antes):
        print(f'({caminho_antes} nao encontrado: rode 01_treina_modelos.py para '
              f'ver o comparativo antes/depois. Os resultados ajustados ja foram '
              f'gravados em {SAIDA}/resultados_ajustados.json.)')
        return
    antes = json.load(open(caminho_antes, encoding='utf-8'))
    print(f"{'Modelo':16s} {'antes (RMSE/R²)':>20s} {'ajustado':>20s}")
    for nome in AJUSTADOS:
        a, b = antes[nome], saida[nome]
        print(f"{nome:16s} {a['RMSE_pool']:>9} / {a['R2_pool']:<8} "
              f"{b['RMSE_pool']:>9} / {b['R2_pool']:<8}")


if __name__ == '__main__':
    main()
