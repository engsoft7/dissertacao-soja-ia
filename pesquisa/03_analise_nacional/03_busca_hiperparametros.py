# -*- coding: utf-8 -*-
"""Busca aleatoria de hiperparametros para o estudo nacional (Tabela 2).

Protocolo, desenhado para nao contaminar a janela de teste:

  - a busca usa APENAS as safras de 2001 a 2015. As safras de 2016 a 2020,
    reservadas para a avaliacao final (04_avalia_ajustado.py), nao entram
    aqui nem no treino nem na validacao;
  - dentro dessa janela, cada configuracao e avaliada por leave-one-year-out
    sobre as safras de 2011 a 2015: cada uma dessas safras e prevista por um
    modelo treinado sem ela;
  - o treino de cada dobra usa uma subamostra de SUB_BUSCA registros, para
    manter o custo da busca viavel. O topo do ranking e depois reavaliado com
    7.000 registros em 06_confirma_busca.py, confirmando que a ordem nao e
    artefato do tamanho da subamostra.

Como em 01_treina_modelos.py, os modelos preveem a ANOMALIA climatica
(YIELD_TREND_CORRECTED) e a produtividade e reconstruida somando a tendencia
(YIELD_TREND). As metricas sao sempre calculadas na produtividade em kg/ha.

O que a busca decide, e o que ela nao decide
--------------------------------------------
Esta e uma busca ALEATORIA: as configuracoes avaliadas saem de um sorteio, e
reexecutar o script tende a eleger uma configuracao diferente. Isso nao
compromete o resultado, porque o que a busca decide com seguranca e QUAL MODELO
vence -- e essa conclusao e estavel. A configuracao exata nao e: como mostra
06_confirma_busca.py, o topo do ranking e um plato de poucos kg/ha, dentro do
qual a ordem troca com qualquer mudanca de subamostra.

As configuracoes reportadas na dissertacao estao fixas em 04_avalia_ajustado.py,
que reproduz a Tabela 3 sem depender de repetir esta etapa -- a mais cara do
estudo nacional.

Saida: resultados_busca.json
Uso:   python 03_busca_hiperparametros.py [n_iteracoes_por_modelo]
"""
import json, os, sys, time, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from xgboost import XGBRegressor

OUT = 'results'; os.makedirs(OUT, exist_ok=True)
BUSCA_ANOS = list(range(2001, 2016))   # janela da busca (exclui 2016-2020)
VAL_ANOS   = [2011, 2012, 2013, 2014, 2015]
SUB_BUSCA  = 3000                      # subamostra de treino por dobra
SVR_MAX    = 5000                      # teto de treino do SVR (custo quadratico)
N_ITER     = int(sys.argv[1]) if len(sys.argv) > 1 else 25
NEEDS_SCALE = {'SVR', 'MLP'}

# ---------------------------------------------------------------- espacos
ESPACO = {
    'Random Forest': {
        'n_estimators':     [100, 200, 300, 400],
        'max_depth':        [6, 10, 16, 24, None],
        'min_samples_leaf': [1, 2, 4, 8],
        'max_features':     ['sqrt', 0.3, 0.6, 1.0],
    },
    'XGBoost': {
        'n_estimators':     [200, 300, 400, 600],
        'max_depth':        [3, 4, 6, 8],
        'learning_rate':    [0.01, 0.02, 0.05, 0.1],
        'subsample':        [0.6, 0.7, 0.8, 1.0],
        'colsample_bytree': [0.6, 0.8, 1.0],
        'reg_lambda':       [1, 2, 5, 10],
        'min_child_weight': [1, 3, 5],
    },
    'SVR': {
        'C':       [1, 10, 50, 100, 300],
        'gamma':   [0.001, 0.005, 0.01, 'scale'],
        'epsilon': [0.01, 0.05, 0.1, 0.2],
    },
    'MLP': {
        'hidden_layer_sizes': [(64, 32), (100, 50), (128, 64), (100,)],
        'alpha':              [1e-4, 1e-3, 1e-2],
        'learning_rate_init': [1e-3, 3e-3, 1e-2],
        'max_iter':           [250, 400],
    },
}

def build(nome, p):
    if nome == 'Random Forest':
        return RandomForestRegressor(n_jobs=-1, random_state=42, **p)
    if nome == 'XGBoost':
        return XGBRegressor(tree_method='hist', n_jobs=-1, verbosity=0,
                            random_state=42, **p)
    if nome == 'SVR':
        # max_iter e cache_size: teto explicito de custo. Sem eles, uma
        # configuracao patologica (C alto com gamma alto) pode nao convergir e
        # travar a busca inteira. O teto e generoso o bastante para nao afetar
        # as configuracoes que convergem normalmente.
        return SVR(cache_size=500, max_iter=2_000_000, **p)
    if nome == 'MLP':
        return MLPRegressor(early_stopping=True, random_state=42, **p)
    raise ValueError(nome)

def amostra(rng, espaco):
    """Sorteia uma configuracao do espaco (chaves em ordem fixa: reprodutivel)."""
    p = {}
    for k in sorted(espaco):
        v = espaco[k]
        p[k] = v[int(rng.integers(len(v)))]
    return p

# ---------------------------------------------------------------- dados
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
print(f'{na_busca.sum()} registros na janela de busca ({BUSCA_ANOS[0]}-{BUSCA_ANOS[-1]}), '
      f'{len(feat)} variaveis, produtividade media {ymean:.0f} kg/ha')

# Subamostra de treino fixa por safra de validacao: todas as configuracoes
# competem exatamente sobre os mesmos dados.
def subamostra(ano, n):
    elegivel = np.where(na_busca & (yr != ano))[0]
    rs = np.random.RandomState(1000 + ano)
    return rs.choice(elegivel, min(n, len(elegivel)), replace=False)

SUBIDX = {a: subamostra(a, SUB_BUSCA) for a in VAL_ANOS}

def avalia(nome, p, subidx):
    """Leave-one-year-out nas safras de validacao. Devolve metricas agregadas."""
    yt, yp = [], []
    for ano in VAL_ANOS:
        idx = subidx[ano]; te = na_busca & (yr == ano)
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

# ---------------------------------------------------------------- busca
resultado = {'protocolo': {
    'janela_busca': [BUSCA_ANOS[0], BUSCA_ANOS[-1]],
    'anos_validacao': VAL_ANOS,
    'sub_treino': SUB_BUSCA,
    'svr_max_treino': SVR_MAX,
    'n_iteracoes': N_ITER,
    'n_variaveis': len(feat),
    'produtividade_media_kg_ha': round(ymean, 1),
}, 'ranking': {}}

for nome in ['Random Forest', 'XGBoost', 'SVR', 'MLP']:
    rng = np.random.default_rng(20260709)   # mesma semente para todos os modelos
    vistas, linhas = set(), []
    t0 = time.time()
    print(f'\n===== {nome} =====', flush=True)
    for i in range(N_ITER):
        p = amostra(rng, ESPACO[nome])
        chave = json.dumps(p, sort_keys=True, default=str)
        if chave in vistas:          # sorteio repetido: nao reavalia
            continue
        vistas.add(chave)
        m = avalia(nome, p, SUBIDX)
        linhas.append({'params': {k: (list(v) if isinstance(v, tuple) else v)
                                  for k, v in p.items()}, **m})
        print(f'  [{i+1:2d}/{N_ITER}] RMSE={m["RMSE"]:6.1f} R2={m["R2"]:+.3f}  {p}', flush=True)
    linhas.sort(key=lambda d: d['RMSE'])
    resultado['ranking'][nome] = linhas
    melhor = linhas[0]
    print(f'  >>> melhor {nome}: RMSE={melhor["RMSE"]} R2={melhor["R2"]} '
          f'({time.time()-t0:.0f}s)\n      {melhor["params"]}', flush=True)

resultado['vencedores'] = {n: r[0] for n, r in resultado['ranking'].items()}
json.dump(resultado, open('resultados_busca.json', 'w'),
          indent=2, ensure_ascii=False)
print('\nOK: resultados_busca.json')
print('Proximo passo: 06_confirma_busca.py (reavalia o topo com 7.000 registros).')
