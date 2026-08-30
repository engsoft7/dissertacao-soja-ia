# -*- coding: utf-8 -*-
"""Confirmacao do topo do ranking da busca com 7.000 registros de treino.

A busca de 03_busca_hiperparametros.py treina cada dobra com uma subamostra de
3.000 registros, para manter o custo viavel. Este script reavalia as TOP_K
melhores configuracoes de cada modelo com 7.000 registros -- o mesmo tamanho
usado na avaliacao final (04_avalia_ajustado.py) -- ainda dentro da janela
2001-2015, sem tocar nas safras de teste.

O objetivo e medir o quao AGUDO e o topo do ranking. O que interessa nao e se
a ordem entre as tres primeiras se mantem -- elas costumam estar separadas por
poucos kg/ha, e nessa faixa a ordem troca com qualquer mudanca de subamostra --,
e sim a AMPLITUDE entre elas. Amplitude pequena significa que o topo e um plato:
qualquer configuracao do grupo serve, e a escolha entre elas nao e critica.
Amplitude grande significaria que a vencedora foi eleita por artefato da
subamostra da busca, e o resultado nao seria confiavel.

Entrada: resultados_busca.json
Saida:   confirmacao_7000.json
Uso:     python 06_confirma_busca.py [top_k]
"""
import json, os, sys, time, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from xgboost import XGBRegressor

OUT = 'results'
BUSCA_ANOS = list(range(2001, 2016))
VAL_ANOS   = [2011, 2012, 2013, 2014, 2015]
SUB_CONF   = 7000
SVR_MAX    = 5000
TOP_K      = int(sys.argv[1]) if len(sys.argv) > 1 else 3
LIMIAR_PLATO = 20.0   # kg/ha: amplitude ate a qual o topo e considerado plato
NEEDS_SCALE = {'SVR', 'MLP'}

busca = json.load(open('resultados_busca.json'))

def build(nome, p):
    p = dict(p)
    if nome == 'Random Forest':
        return RandomForestRegressor(n_jobs=-1, random_state=42, **p)
    if nome == 'XGBoost':
        return XGBRegressor(tree_method='hist', n_jobs=-1, verbosity=0,
                            random_state=42, **p)
    if nome == 'SVR':
        return SVR(**p)
    if nome == 'MLP':
        p['hidden_layer_sizes'] = tuple(p['hidden_layer_sizes'])
        return MLPRegressor(early_stopping=True, random_state=42, **p)
    raise ValueError(nome)

df = pd.read_csv('data/data_cast.csv')
DROP = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED',
        'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
feat = [c for c in df.columns if c not in DROP and df[c].dtype != 'object']
X = df[feat].fillna(df[feat].median())
YIELD = df['YIELD'].values.astype(float)
TREND = df['YIELD_TREND'].values.astype(float)
ANOM  = df['YIELD_TREND_CORRECTED'].values.astype(float)
yr    = df['HARVESTED'].values
na_busca = np.isin(yr, BUSCA_ANOS)
ymean = float(YIELD[na_busca].mean())

# Mesmas sementes da busca; muda so o tamanho da subamostra (3.000 -> 7.000).
SUBIDX = {}
for a in VAL_ANOS:
    elegivel = np.where(na_busca & (yr != a))[0]
    rs = np.random.RandomState(1000 + a)
    SUBIDX[a] = rs.choice(elegivel, min(SUB_CONF, len(elegivel)), replace=False)

def avalia(nome, p):
    yt, yp = [], []
    for ano in VAL_ANOS:
        idx = SUBIDX[ano]; te = na_busca & (yr == ano)
        Xtr, Xte, atr = X.iloc[idx].values, X[te].values, ANOM[idx]
        if nome in NEEDS_SCALE:
            sc = StandardScaler().fit(Xtr)
            Xtr, Xte = sc.transform(Xtr), sc.transform(Xte)
            if nome == 'SVR':
                Xtr, atr = Xtr[:SVR_MAX], atr[:SVR_MAX]
        mdl = build(nome, p).fit(Xtr, atr)
        yt += list(YIELD[te]); yp += list(mdl.predict(Xte) + TREND[te])
    yt, yp = np.array(yt), np.array(yp)
    rmse = float(np.sqrt(mean_squared_error(yt, yp)))
    return {'RMSE': round(rmse, 1),
            'MAE':  round(float(mean_absolute_error(yt, yp)), 1),
            'R2':   round(float(r2_score(yt, yp)), 3),
            'rRMSE': round(rmse / ymean * 100, 1)}

saida = {'protocolo': {
    'janela_busca': [BUSCA_ANOS[0], BUSCA_ANOS[-1]],
    'anos_validacao': VAL_ANOS,
    'sub_treino_busca': busca['protocolo']['sub_treino'],
    'sub_treino_confirmacao': SUB_CONF,
    'svr_max_treino': SVR_MAX,
    'top_k': TOP_K,
}, 'modelos': {}}

for nome, ranking in busca['ranking'].items():
    print(f'\n===== {nome} (top {TOP_K}) =====', flush=True)
    linhas = []
    for pos, cand in enumerate(ranking[:TOP_K], 1):
        t0 = time.time()
        m = avalia(nome, cand['params'])
        linhas.append({'posicao_busca': pos, 'params': cand['params'],
                       'busca_3000': {k: cand[k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE')},
                       'confirmacao_7000': m})
        print(f'  #{pos}  3.000: RMSE={cand["RMSE"]:6.1f} R2={cand["R2"]:+.3f}   '
              f'|  7.000: RMSE={m["RMSE"]:6.1f} R2={m["R2"]:+.3f}   ({time.time()-t0:.0f}s)',
              flush=True)
    melhor_7000 = min(linhas, key=lambda d: d['confirmacao_7000']['RMSE'])
    rmses = [d['confirmacao_7000']['RMSE'] for d in linhas]
    amplitude = max(rmses) - min(rmses)
    plato = amplitude <= LIMIAR_PLATO
    saida['modelos'][nome] = {
        'candidatos': linhas,
        'melhor_com_7000_era_posicao': melhor_7000['posicao_busca'],
        'amplitude_top_k_kg_ha': round(amplitude, 1),
        'topo_e_plato': bool(plato),
        'escolhido': melhor_7000['params'],
    }
    print(f'  >>> amplitude entre as {len(linhas)} melhores, com 7.000 registros: '
          f'{amplitude:.1f} kg/ha -> {"PLATO" if plato else "TOPO AGUDO"}', flush=True)
    if plato:
        print('      (a ordem entre elas troca conforme a subamostra, mas qualquer '
              'uma do grupo serve: a escolha nao e critica)', flush=True)

saida['topo_e_plato_em_todos'] = all(v['topo_e_plato'] for v in saida['modelos'].values())
saida['limiar_plato_kg_ha'] = LIMIAR_PLATO
json.dump(saida, open('confirmacao_7000.json', 'w'), indent=2,
          ensure_ascii=False, default=str)
print('\nOK: confirmacao_7000.json')
print('Amplitude do topo, por modelo (kg/ha):',
      {n: v['amplitude_top_k_kg_ha'] for n, v in saida['modelos'].items()})
print('Topo e plato em todos os modelos:', saida['topo_e_plato_em_todos'])
if saida['topo_e_plato_em_todos']:
    print('\nO topo do ranking e um plato em todos os modelos: a busca decide com')
    print('seguranca QUAL MODELO vence, e nao uma configuracao unica e insubstituivel.')
