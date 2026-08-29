# -*- coding: utf-8 -*-
"""Busca ANINHADA de hiperparametros para o estudo de caso do Para (Tabela 6).

Motivacao
---------
A comparacao com o baseline (01_compara_mascara_controlada.py) usa
hiperparametros fixos. Uma objecao legitima e que os modelos poderiam superar o
baseline se fossem melhor ajustados. Este script responde a essa objecao com
validacao cruzada ANINHADA, que e a forma honesta de ajustar e avaliar sobre a
mesma base pequena:

  - laco EXTERNO: leave-one-year-out. Cada safra e a safra de teste, uma vez.
  - laco INTERNO: dentro das safras restantes (a safra de teste nunca aparece),
    sorteiam-se N_INNER configuracoes por modelo e cada uma e avaliada por
    leave-one-year-out sobre as VAL_INNER ultimas safras de treino.
  - a configuracao vencedora do laco interno e reajustada em todas as safras de
    treino e aplicada a safra de teste.

Assim o hiperparametro e escolhido sem jamais ver a safra avaliada: o resultado
e o teto realista do que o ajuste pode entregar nesta base, e nao uma estimativa
otimista obtida por escolher o melhor numero depois de olhar o teste.

O baseline (media historica do municipio + tendencia tecnologica) atravessa o
mesmo laco externo e nao tem o que ajustar, servindo de termo de comparacao.

Saida: resultados_busca_aninhada.json
Uso:   python 03_busca_hiperparametros.py [n_configuracoes_por_modelo]
"""
import json, os, sys, time, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor

BASE = '../dados/soja_para_mascarado_2001_2024.csv'
MODELS = ['Random Forest', 'XGBoost', 'SVR', 'MLP']
SCALE = {'SVR', 'MLP'}
MIN_MUN = 4          # minimo de municipios para uma safra virar dobra
VAL_INNER = 4        # safras de validacao dentro de cada dobra externa
N_INNER = int(sys.argv[1]) if len(sys.argv) > 1 else 8
SEMENTE = 20260709
FE = ['NDVI_mean', 'NDVI_max', 'EVI_mean', 'EVI_max', 'precip_total',
      'etp_total', 'balanco_hidrico', 'temp_mean', 'temp_max', 'srad_mean']

ESPACO = {
    'Random Forest': {
        'n_estimators':     [100, 200, 300, 500],
        'max_depth':        [3, 5, 8, 10, None],
        'min_samples_leaf': [1, 2, 4, 8],
        'max_features':     ['sqrt', 0.5, 1.0],
    },
    'XGBoost': {
        'n_estimators':     [100, 200, 400],
        'max_depth':        [2, 3, 4, 6],
        'learning_rate':    [0.01, 0.03, 0.05, 0.1],
        'subsample':        [0.6, 0.8, 1.0],
        'colsample_bytree': [0.6, 0.8, 1.0],
        'reg_lambda':       [1, 2, 5, 10],
    },
    'SVR': {
        'C':       [1, 10, 50, 100],
        'gamma':   [0.005, 0.01, 0.05, 'scale'],
        'epsilon': [0.01, 0.05, 0.1, 0.2],
    },
    'MLP': {
        'hidden_layer_sizes': [(32,), (64, 32), (100, 50)],
        'alpha':              [1e-3, 1e-2, 1e-1],
        'learning_rate_init': [1e-3, 3e-3, 1e-2],
        'max_iter':           [300],
    },
}

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

def amostra(rng, espaco):
    return {k: espaco[k][int(rng.integers(len(espaco[k])))] for k in sorted(espaco)}

def M(yt, yp):
    return (float(np.sqrt(mean_squared_error(yt, yp))),
            float(mean_absolute_error(yt, yp)),
            float(r2_score(yt, yp)))

# --------------------------------------------------------------- dados
d = pd.read_csv(BASE)
d['balanco_hidrico'] = d['precip_total'] - d['etp_total']
d = d.dropna(subset=FE + ['rendimento_kg_ha']).reset_index(drop=True)
y = d.rendimento_kg_ha.values.astype(float)
yr = d.ano.values; mun = d.cod_ibge7.values; X = d[FE].values
ymean = float(y.mean())
ANOS = [t for t in sorted(set(yr)) if (yr == t).sum() >= MIN_MUN]
print(f'{len(d)} registros, {d.cod_ibge7.nunique()} municipios, '
      f'{yr.min()}-{yr.max()}, {len(ANOS)} dobras externas, '
      f'produtividade media {ymean:.0f} kg/ha')
print(f'busca aninhada: {N_INNER} configuracoes por modelo por dobra externa\n')

def baseline_de(tr_mask, alvo_mask):
    """Media historica do municipio + tendencia linear, ajustadas so no treino."""
    lin = LinearRegression().fit(yr[tr_mask].reshape(-1, 1), y[tr_mask])
    s = lin.coef_[0]; my = yr[tr_mask].mean()
    mm = pd.Series(y[tr_mask]).groupby(mun[tr_mask]).mean(); gm = y[tr_mask].mean()
    return np.array([mm.get(mun[i], gm) + s * (yr[i] - my)
                     for i in np.where(alvo_mask)[0]])

def ajusta_prediz(nome, p, tr_mask, te_mask):
    """Ajusta no residuo em relacao ao baseline e devolve a previsao final."""
    b_tr = baseline_de(tr_mask, tr_mask); b_te = baseline_de(tr_mask, te_mask)
    resid = y[tr_mask] - b_tr
    if nome in SCALE:
        sc = StandardScaler().fit(X[tr_mask])
        Xtr, Xte = sc.transform(X[tr_mask]), sc.transform(X[te_mask])
    else:
        Xtr, Xte = X[tr_mask], X[te_mask]
    mdl = build(nome, p).fit(Xtr, resid)
    return b_te + mdl.predict(Xte)

# --------------------------------------------------------------- aninhada
res = {m: {'yt': [], 'yp': [], 'escolhas': []} for m in MODELS}
b_yt, b_yp = [], []
t0 = time.time()

for ano in ANOS:
    te = yr == ano; tr = (yr != ano) & np.isin(yr, ANOS)
    b_yt += list(y[te]); b_yp += list(baseline_de(tr, te))

    anos_tr = [a for a in ANOS if a != ano]
    val_anos = anos_tr[-VAL_INNER:]          # safras de validacao interna
    for nome in MODELS:
        rng = np.random.default_rng(SEMENTE + ano)
        melhor, melhor_rmse = None, np.inf
        for _ in range(N_INNER):
            p = amostra(rng, ESPACO[nome])
            iyt, iyp = [], []
            for va in val_anos:
                ite = yr == va
                itr = np.isin(yr, [a for a in anos_tr if a != va])
                if ite.sum() < MIN_MUN or itr.sum() < 20:
                    continue
                iyt += list(y[ite]); iyp += list(ajusta_prediz(nome, p, itr, ite))
            if not iyt:
                continue
            rmse = float(np.sqrt(mean_squared_error(np.array(iyt), np.array(iyp))))
            if rmse < melhor_rmse:
                melhor, melhor_rmse = p, rmse
        yp = ajusta_prediz(nome, melhor, tr, te)
        res[nome]['yt'] += list(y[te]); res[nome]['yp'] += list(yp)
        res[nome]['escolhas'].append({
            'ano_teste': int(ano),
            'params': {k: (list(v) if isinstance(v, tuple) else v)
                       for k, v in melhor.items()},
            'rmse_validacao_interna': round(melhor_rmse, 1)})
    print(f'  safra {ano} concluida ({time.time()-t0:.0f}s)', flush=True)

# --------------------------------------------------------------- saida
br = M(np.array(b_yt), np.array(b_yp))
saida = {'protocolo': {
    'base': os.path.basename(BASE), 'n': int(len(d)),
    'municipios': int(d.cod_ibge7.nunique()),
    'anos': [int(min(ANOS)), int(max(ANOS))], 'dobras_externas': len(ANOS),
    'safras_validacao_interna': VAL_INNER,
    'configuracoes_por_modelo_por_dobra': N_INNER,
    'produtividade_media_kg_ha': round(ymean, 1),
    'variaveis': FE},
    'baseline': {'RMSE': round(br[0], 1), 'MAE': round(br[1], 1),
                 'R2': round(br[2], 3), 'rRMSE': round(br[0] / ymean * 100, 1)},
    'modelos': {}}

print('\n' + '=' * 70)
print('TABELA 6 - busca aninhada de hiperparametros, Para')
print('=' * 70)
print(f'{"Modelo":16s}{"RMSE":>9s}{"MAE":>9s}{"R2":>9s}{"rRMSE":>9s}{"vs baseline":>14s}')
print(f'{"Baseline":16s}{br[0]:9.1f}{br[1]:9.1f}{br[2]:9.3f}'
      f'{br[0]/ymean*100:8.1f}%{"—":>14s}')
for nome in MODELS:
    r = M(np.array(res[nome]['yt']), np.array(res[nome]['yp']))
    ganho = br[0] - r[0]
    saida['modelos'][nome] = {
        'RMSE': round(r[0], 1), 'MAE': round(r[1], 1), 'R2': round(r[2], 3),
        'rRMSE': round(r[0] / ymean * 100, 1),
        'ganho_RMSE_sobre_baseline': round(ganho, 1),
        'supera_baseline': bool(r[0] < br[0]),
        'escolhas_por_dobra': res[nome]['escolhas']}
    print(f'{nome:16s}{r[0]:9.1f}{r[1]:9.1f}{r[2]:9.3f}'
          f'{r[0]/ymean*100:8.1f}%{ganho:+13.1f}')

melhor = min(MODELS, key=lambda n: saida['modelos'][n]['RMSE'])
saida['melhor_modelo'] = melhor
saida['algum_supera_baseline'] = any(saida['modelos'][n]['supera_baseline'] for n in MODELS)
print('\n(vs baseline em kg/ha; positivo = o modelo erra menos que o baseline)')
print(f'\nMelhor modelo: {melhor} '
      f'(RMSE {saida["modelos"][melhor]["RMSE"]:.1f} kg/ha, '
      f'baseline {br[0]:.1f} kg/ha)')
print('Algum modelo supera o baseline?',
      'SIM' if saida['algum_supera_baseline'] else 'NAO')
if not saida['algum_supera_baseline']:
    print('\nMesmo com hiperparametros escolhidos dobra a dobra, as variaveis')
    print('ambientais nao adicionam informacao sobre o historico do municipio.')

json.dump(saida, open('resultados_busca_aninhada.json', 'w'), indent=2, ensure_ascii=False)
print(f'\nOK: resultados_busca_aninhada.json ({time.time()-t0:.0f}s)')
