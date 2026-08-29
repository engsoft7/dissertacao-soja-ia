# -*- coding: utf-8 -*-
"""Comparacao COM MASCARA x SEM MASCARA em amostra controlada (Tabela 5, Figura 5).

Por que este script substitui 01_compara_mascara_e_baseline.py
-------------------------------------------------------------
O script anterior comparava os dois cenarios sobre arquivos diferentes:

    soja_para_sem_mascara_2001_2023.csv   493 registros, 44 municipios, ate 2023
    soja_para_mascarado_2001_2024.csv     415 registros, 38 municipios, ate 2024

O baseline nao usa nenhuma variavel ambiental -- so o historico do municipio e a
tendencia tecnologica --, entao ele deveria dar exatamente o mesmo resultado nos
dois cenarios. No desenho anterior nao dava, e essa diferenca denunciava que o
contraste observado vinha da amostra, e nao da mascara de soja.

Aqui os dois cenarios rodam sobre os 379 registros comuns as duas bases (mesmos
pares municipio-safra, mesmo alvo, mesmas dobras), de modo que a unica coisa que
muda entre eles e a origem das variaveis ambientais: media do municipio inteiro
ou media restrita aos pixels de soja do MapBiomas.

A verificacao embutida VERIFICA_BASELINE aborta a execucao se os baselines dos
dois cenarios divergirem -- se isso acontecer, o controle da amostra falhou e o
resultado nao deve ser publicado.

Protocolo (identico ao do script anterior, no que nao muda):
  - alvo: produtividade municipal da soja (kg/ha), PAM/IBGE;
  - baseline: media historica do municipio + tendencia tecnologica linear;
  - os modelos preveem o RESIDUO em relacao ao baseline; a previsao final e
    baseline + residuo_previsto;
  - validacao leave-one-year-out: cada safra e prevista por um modelo treinado
    sem ela; safras com menos de MIN_MUN municipios sao descartadas.

Saida: comparacao_controlada.json  e  results/fig_pa_mascara_controlada.png
Uso:   python 01_compara_mascara_controlada.py
"""
import json, os, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor

np.random.seed(42)
os.makedirs('results', exist_ok=True)

SEM  = '../dados/soja_para_sem_mascara_2001_2023.csv'
MASC = '../dados/soja_para_mascarado_2001_2024.csv'
MODELS = ['Random Forest', 'XGBoost', 'SVR', 'MLP']
SCALE  = {'SVR', 'MLP'}
MIN_MUN = 4          # safras com menos de 4 municipios nao viram dobra
TOL_BASELINE = 0.1   # kg/ha: tolerancia da verificacao (so ruido numerico)
FE = ['NDVI_mean', 'NDVI_max', 'EVI_mean', 'EVI_max', 'precip_total',
      'etp_total', 'balanco_hidrico', 'temp_mean', 'temp_max', 'srad_mean']

B1 = '#1F4E79'; B2 = '#2E75B6'; RED = '#B00020'

def M(yt, yp):
    return (float(np.sqrt(mean_squared_error(yt, yp))),
            float(mean_absolute_error(yt, yp)),
            float(r2_score(yt, yp)))

def build(n):
    if n == 'Random Forest':
        return RandomForestRegressor(n_estimators=300, max_depth=10,
                                     min_samples_leaf=4, n_jobs=-1, random_state=42)
    if n == 'XGBoost':
        return XGBRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                            subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
                            tree_method='hist', n_jobs=-1, verbosity=0, random_state=42)
    if n == 'SVR':
        return SVR(C=10, gamma='scale')
    if n == 'MLP':
        return MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-2, max_iter=800,
                            early_stopping=True, random_state=42)
    raise ValueError(n)

def carrega(path):
    d = pd.read_csv(path)
    d['balanco_hidrico'] = d['precip_total'] - d['etp_total']
    return d.dropna(subset=FE + ['rendimento_kg_ha']).reset_index(drop=True)

# ------------------------------------------------- amostra controlada
sem, masc = carrega(SEM), carrega(MASC)
chave = ['cod_ibge7', 'ano']
comuns = (pd.merge(sem[chave], masc[chave], on=chave, how='inner')
            .drop_duplicates().sort_values(chave).reset_index(drop=True))

def restringe(d):
    return (d.merge(comuns, on=chave, how='inner')
             .sort_values(chave).reset_index(drop=True))

sem_c, masc_c = restringe(sem), restringe(masc)

print('=' * 68)
print('AMOSTRA CONTROLADA')
print('=' * 68)
print(f'  sem mascara (arquivo) : {len(sem):4d} registros, {sem.cod_ibge7.nunique():2d} municipios, '
      f'{sem.ano.min()}-{sem.ano.max()}')
print(f'  com mascara (arquivo) : {len(masc):4d} registros, {masc.cod_ibge7.nunique():2d} municipios, '
      f'{masc.ano.min()}-{masc.ano.max()}')
print(f'  intersecao usada      : {len(comuns):4d} registros, '
      f'{comuns.cod_ibge7.nunique():2d} municipios, {comuns.ano.min()}-{comuns.ano.max()}')

assert len(sem_c) == len(masc_c) == len(comuns), 'intersecao inconsistente entre os cenarios'
assert np.allclose(sem_c.rendimento_kg_ha.values, masc_c.rendimento_kg_ha.values), \
    'o alvo difere entre os cenarios na amostra comum'

# ------------------------------------------------- avaliacao
def roda(d, feats, tag):
    y = d.rendimento_kg_ha.values.astype(float)
    yr = d.ano.values; mun = d.cod_ibge7.values
    X = d[feats].values
    years = [t for t in sorted(set(yr)) if (yr == t).sum() >= MIN_MUN]
    res = {m: {'yt': [], 'yp': []} for m in MODELS}
    b_yt, b_yp = [], []
    for ty in years:
        tr = yr != ty; te = yr == ty
        lin = LinearRegression().fit(yr[tr].reshape(-1, 1), y[tr])
        slope = lin.coef_[0]; my = yr[tr].mean()
        mmean = pd.Series(y[tr]).groupby(mun[tr]).mean(); gmean = y[tr].mean()
        def bl(idx):
            return np.array([mmean.get(mun[i], gmean) + slope * (yr[i] - my)
                             for i in np.where(idx)[0]])
        b_tr, b_te = bl(tr), bl(te)
        resid = y[tr] - b_tr
        b_yt += list(y[te]); b_yp += list(b_te)
        sc = StandardScaler().fit(X[tr])
        Xtr, Xte = sc.transform(X[tr]), sc.transform(X[te])
        for n in MODELS:
            m = build(n)
            if n in SCALE:
                m.fit(Xtr, resid); pr = m.predict(Xte)
            else:
                m.fit(X[tr], resid); pr = m.predict(X[te])
            res[n]['yt'] += list(y[te]); res[n]['yp'] += list(b_te + pr)
    ymean = float(y.mean())
    br = M(np.array(b_yt), np.array(b_yp))
    out = {'n': int(len(d)), 'mun': int(d.cod_ibge7.nunique()),
           'anos': [int(min(years)), int(max(years))], 'n_dobras': len(years),
           'ymean': round(ymean, 1),
           'baseline': {'RMSE': round(br[0], 1), 'MAE': round(br[1], 1),
                        'R2': round(br[2], 3), 'rRMSE': round(br[0] / ymean * 100, 1)}}
    print(f'\n----- {tag} -----')
    print(f'  BASELINE (sem clima)   RMSE={br[0]:6.1f}  R2={br[2]:+.3f}  rRMSE={br[0]/ymean*100:.1f}%')
    for n in MODELS:
        r = M(np.array(res[n]['yt']), np.array(res[n]['yp']))
        out[n] = {'RMSE': round(r[0], 1), 'MAE': round(r[1], 1), 'R2': round(r[2], 3),
                  'rRMSE': round(r[0] / ymean * 100, 1),
                  'ganho_RMSE_sobre_baseline': round(br[0] - r[0], 1)}
        marca = 'melhora' if r[0] < br[0] else 'NAO supera'
        print(f'  {n:14s}         RMSE={r[0]:6.1f}  R2={r[2]:+.3f}  '
              f'rRMSE={r[0]/ymean*100:5.1f}%   ({marca} o baseline)')
    melhor = min(MODELS, key=lambda n: out[n]['RMSE'])
    out['melhor'] = melhor
    out['algum_supera_baseline'] = bool(out[melhor]['RMSE'] < br[0])
    return out

a = roda(sem_c, FE, 'SEM MASCARA (media do municipio inteiro) - amostra controlada')
b = roda(masc_c, FE, 'COM MASCARA (so pixels de soja)        - amostra controlada')

# ------------------------------------------------- verificacao embutida
print('\n' + '=' * 68)
print('VERIFICACAO: o baseline deve ser identico nos dois cenarios')
print('=' * 68)
d_rmse = abs(a['baseline']['RMSE'] - b['baseline']['RMSE'])
d_r2 = abs(a['baseline']['R2'] - b['baseline']['R2'])
print(f'  baseline sem mascara : RMSE={a["baseline"]["RMSE"]:.1f}  R2={a["baseline"]["R2"]:+.3f}')
print(f'  baseline com mascara : RMSE={b["baseline"]["RMSE"]:.1f}  R2={b["baseline"]["R2"]:+.3f}')
print(f'  diferenca            : RMSE={d_rmse:.3f} kg/ha  R2={d_r2:.4f}')
if d_rmse > TOL_BASELINE:
    raise SystemExit(
        f'\nABORTADO: o baseline difere em {d_rmse:.1f} kg/ha entre os cenarios.\n'
        'O baseline nao usa variavel ambiental alguma, entao qualquer diferenca\n'
        'significa que os dois cenarios nao estao rodando sobre a mesma amostra.\n'
        'Sem esse controle a comparacao com/sem mascara nao e interpretavel.')
print('  OK: baselines identicos -- o contraste abaixo isola o efeito da mascara.')

# ------------------------------------------------- Tabela 5
print('\n' + '=' * 68)
print('TABELA 5 - efeito da mascara de soja, amostra controlada '
      f'({len(comuns)} registros)')
print('=' * 68)
print(f'{"Modelo":16s}{"sem masc.":>12s}{"com masc.":>12s}{"delta":>10s}')
for n in MODELS:
    dlt = b[n]['RMSE'] - a[n]['RMSE']
    print(f'{n:16s}{a[n]["RMSE"]:12.1f}{b[n]["RMSE"]:12.1f}{dlt:+10.1f}')
print(f'{"Baseline":16s}{a["baseline"]["RMSE"]:12.1f}{b["baseline"]["RMSE"]:12.1f}'
      f'{b["baseline"]["RMSE"]-a["baseline"]["RMSE"]:+10.1f}')
print('\n(RMSE em kg/ha; delta negativo = a mascara reduz o erro)')

saida = {
    'amostra': {
        'sem_mascara_arquivo': {'n': int(len(sem)), 'mun': int(sem.cod_ibge7.nunique()),
                                'anos': [int(sem.ano.min()), int(sem.ano.max())]},
        'com_mascara_arquivo': {'n': int(len(masc)), 'mun': int(masc.cod_ibge7.nunique()),
                                'anos': [int(masc.ano.min()), int(masc.ano.max())]},
        'controlada': {'n': int(len(comuns)), 'mun': int(comuns.cod_ibge7.nunique()),
                       'anos': [int(comuns.ano.min()), int(comuns.ano.max())]},
    },
    'verificacao_baseline': {
        'diferenca_RMSE_kg_ha': round(d_rmse, 3), 'diferenca_R2': round(d_r2, 4),
        'tolerancia_kg_ha': TOL_BASELINE, 'aprovada': True},
    'sem_mascara': a, 'com_mascara': b,
    'efeito_mascara_RMSE_kg_ha': {n: round(b[n]['RMSE'] - a[n]['RMSE'], 1) for n in MODELS},
    'algum_modelo_supera_baseline': bool(a['algum_supera_baseline'] or b['algum_supera_baseline']),
}
json.dump(saida, open('comparacao_controlada.json', 'w'), indent=2, ensure_ascii=False)

# ------------------------------------------------- Figura 5
fig, ax = plt.subplots(1, 2, figsize=(9.8, 3.9))
x = np.arange(len(MODELS)); w = 0.36
sem_v = [a[n]['RMSE'] for n in MODELS]; com_v = [b[n]['RMSE'] for n in MODELS]
ax[0].bar(x - w/2, sem_v, w, label='Município inteiro', color=B2)
ax[0].bar(x + w/2, com_v, w, label='Máscara de soja', color=B1)
ax[0].axhline(a['baseline']['RMSE'], ls='--', color=RED, lw=1.3,
              label=f'Baseline ({a["baseline"]["RMSE"]:.0f} kg/ha)')
ax[0].set_xticks(x); ax[0].set_xticklabels(MODELS, rotation=15, fontsize=8.5)
ax[0].set_ylabel('RMSE (kg/ha)')
ax[0].set_title(f'(a) Erro por modelo — amostra controlada\n({len(comuns)} registros comuns às duas bases)',
                fontsize=9.5)
ax[0].legend(fontsize=7.5)
lo = min(sem_v + com_v + [a['baseline']['RMSE']]); hi = max(sem_v + com_v + [a['baseline']['RMSE']])
ax[0].set_ylim(lo - (hi - lo) * 0.35, hi + (hi - lo) * 0.22)

dlt = [b[n]['RMSE'] - a[n]['RMSE'] for n in MODELS]
ax[1].bar(x, dlt, color=[B1 if d < 0 else RED for d in dlt])
ax[1].axhline(0, color='#333', lw=1.0)
ax[1].set_xticks(x); ax[1].set_xticklabels(MODELS, rotation=15, fontsize=8.5)
ax[1].set_ylabel('Δ RMSE com a máscara (kg/ha)')
ax[1].set_title('(b) Efeito isolado da máscara\n(negativo = máscara reduz o erro)', fontsize=9.5)
for i, d in enumerate(dlt):
    ax[1].text(i, d + (2 if d >= 0 else -2), f'{d:+.0f}', ha='center',
               va='bottom' if d >= 0 else 'top', fontsize=8.5)
m = max(abs(min(dlt)), abs(max(dlt))) * 1.45 + 1
ax[1].set_ylim(-m, m)
plt.tight_layout()
plt.savefig('results/fig_pa_mascara_controlada.png', dpi=200,
            bbox_inches='tight', facecolor='white')
plt.close()

print('\nOK: comparacao_controlada.json e results/fig_pa_mascara_controlada.png')
