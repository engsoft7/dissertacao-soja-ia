# -*- coding: utf-8 -*-
"""Figuras 2, 3 e 4 do estudo nacional, com os hiperparametros ajustados.

  Figura 2  comparacao dos modelos ajustados (R2 e RMSE agregados)
  Figura 3  previsto vs. observado do melhor modelo
  Figura 4  importancia das variaveis, por PERMUTACAO, agrupada por familia

Por que importancia por permutacao
----------------------------------
Com o ajuste de hiperparametros o melhor modelo passou a ser o SVR, que nao
expoe feature_importances_ -- o atributo usado em 02_gera_figuras.py, que so
existe em modelos de arvore. A importancia por permutacao resolve isso: ela
mede quanto o erro do modelo piora quando os valores de uma variavel sao
embaralhados, o que funciona para qualquer estimador e e medido na propria
metrica de interesse (RMSE na produtividade reconstruida).

Por que agregar as cinco safras
-------------------------------
A permutacao e calculada em TODAS as safras de teste e somada, e nao em uma
safra so. A diferenca nao e cosmetica: medida apenas em 2020 -- safra atipica,
de maior dispersao --, a ordem das duas familias dominantes se INVERTE, e o
grupo hidrico aparece a frente dos indices espectrais. Agregando as cinco, os
indices espectrais lideram, como reporta a subsecao 5.3. Uma safra isolada nao
sustenta a leitura de importancia.

Entrada: resultados_ajustados.json (de 04_avalia_ajustado.py) e data/data_cast.csv
Saida:   results/fig2_modelos_ajustados.png
         results/fig3_scatter_ajustado.png
         results/fig4_importancia_permutacao.png
         results/importancia_permutacao.csv
Uso:     python 05_gera_figuras_ajustado.py
"""
import json, os, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_squared_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from xgboost import XGBRegressor

plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 11,
                     'axes.grid': True, 'grid.alpha': 0.3})
OUT = 'results'; os.makedirs(OUT, exist_ok=True)
TEST_YEARS = [2016, 2017, 2018, 2019, 2020]
BLUE = '#1F4E79'; BLUE2 = '#2E75B6'; RED = '#B00020'
N_REPEATS = 5         # repeticoes de embaralhamento por variavel e por safra
SUB = 7000; SVR_MAX = 5000
NEEDS_SCALE = {'SVR', 'MLP'}

res = json.load(open('resultados_ajustados.json'))
mods = res['modelos']
order = sorted(mods, key=lambda m: mods[m]['R2_pool'], reverse=True)
best = res.get('melhor', order[0])

def build(name):
    if name == 'Random Forest':
        return RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=2,
                                     max_features='sqrt', n_jobs=-1, random_state=42)
    if name == 'XGBoost':
        return XGBRegressor(n_estimators=400, max_depth=6, learning_rate=0.02,
                            subsample=0.7, colsample_bytree=1.0, reg_lambda=5,
                            min_child_weight=3, tree_method='hist', n_jobs=-1,
                            verbosity=0, random_state=42)
    if name == 'SVR':
        return SVR(C=100, gamma=0.005, epsilon=0.05)
    if name == 'MLP':
        return MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3,
                            learning_rate_init=3e-3, max_iter=250,
                            early_stopping=True, random_state=42)
    raise ValueError(name)

# ------------------------------------------------------------ FIG 2
fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
r2 = [mods[m]['R2_pool'] for m in order]
rmse = [mods[m]['RMSE_pool'] for m in order]
cor = [BLUE if m == best else BLUE2 for m in order]
ax[0].bar(order, r2, color=cor); ax[0].set_ylabel('R² (agregado)')
ax[0].set_title('(a) Coeficiente de determinação R²')
ax[0].set_ylim(0, max(r2) * 1.25)
for i, v in enumerate(r2): ax[0].text(i, v + 0.008, f'{v:.3f}', ha='center', fontsize=9)
ax[1].bar(order, rmse, color=cor); ax[1].set_ylabel('RMSE (kg/ha)')
ax[1].set_title('(b) Raiz do erro quadrático médio')
ax[1].set_ylim(0, max(rmse) * 1.18)
for i, v in enumerate(rmse): ax[1].text(i, v + 5, f'{v:.0f}', ha='center', fontsize=9)
for a in ax: a.tick_params(axis='x', rotation=15)
fig.suptitle('Modelos com hiperparâmetros ajustados — safras de 2016 a 2020',
             fontsize=11, y=1.02)
plt.tight_layout()
plt.savefig(f'{OUT}/fig2_modelos_ajustados.png', dpi=200, bbox_inches='tight', facecolor='white')
plt.close()

# ------------------------------------------------------------ FIG 3
p = pd.read_csv(f'{OUT}/pred_ajustado_{best.replace(" ", "_")}.csv')
fig, ax = plt.subplots(figsize=(5.6, 5.4))
ax.scatter(p.y_true, p.y_pred, s=6, alpha=0.25, color=BLUE2, edgecolors='none')
lim = [min(p.y_true.min(), p.y_pred.min()), max(p.y_true.max(), p.y_pred.max())]
ax.plot(lim, lim, '--', color=RED, lw=1.5, label='Linha 1:1 (previsão perfeita)')
ax.set_xlabel('Produtividade observada (kg/ha)')
ax.set_ylabel('Produtividade prevista (kg/ha)')
ax.set_title(f'Previsto vs. observado — {best} ajustado\n'
             f'(R²={mods[best]["R2_pool"]:.3f}; RMSE={mods[best]["RMSE_pool"]:.0f} kg/ha; '
             f'rRMSE={mods[best]["rRMSE_pool"]:.1f}%)')
ax.legend(loc='upper left', fontsize=9); ax.set_xlim(lim); ax.set_ylim(lim)
plt.tight_layout()
plt.savefig(f'{OUT}/fig3_scatter_ajustado.png', dpi=200, bbox_inches='tight', facecolor='white')
plt.close()

# ------------------------------------------------------------ FIG 4
df = pd.read_csv('data/data_cast.csv')
DROP = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED',
        'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
feat = [c for c in df.columns if c not in DROP and df[c].dtype != 'object']
X = df[feat].fillna(df[feat].median())
YIELD = df['YIELD'].values.astype(float)
TREND = df['YIELD_TREND'].values.astype(float)
ANOM = df['YIELD_TREND_CORRECTED'].values.astype(float)
yr = df['HARVESTED'].values

# Uma dobra por safra de teste, identica a de 04_avalia_ajustado.py: o modelo
# nunca viu a safra sobre a qual as variaveis sao embaralhadas.
print(f'Importancia por permutacao ({best}, {len(TEST_YEARS)} safras de teste, '
      f'{N_REPEATS} repeticoes, {len(feat)} variaveis)...', flush=True)
soma = pd.Series(0.0, index=feat)
soma_sd = pd.Series(0.0, index=feat)
for ano in TEST_YEARS:
    idx = np.random.RandomState(1000 + ano).choice(
        np.where(yr != ano)[0], min(SUB, int((yr != ano).sum())), replace=False)
    te = yr == ano
    Xtr, Xte, atr = X.iloc[idx].values, X[te].values, ANOM[idx]
    if best in NEEDS_SCALE:
        sc = StandardScaler().fit(Xtr)
        Xtr, Xte = sc.transform(Xtr), sc.transform(Xte)
        if best == 'SVR':
            Xtr, atr = Xtr[:SVR_MAX], atr[:SVR_MAX]
    mdl = build(best).fit(Xtr, atr)

    # A permutacao mede a piora do RMSE na PRODUTIVIDADE reconstruida, nao na
    # anomalia: e a metrica que o trabalho reporta.
    trend_te = TREND[te]; yreal = YIELD[te]
    def score_prod(estimator, Xm, _, _t=trend_te, _y=yreal):
        return -float(np.sqrt(mean_squared_error(_y, estimator.predict(Xm) + _t)))

    pi = permutation_importance(mdl, Xte, ANOM[te], scoring=score_prod,
                                n_repeats=N_REPEATS, random_state=42, n_jobs=1)
    # piora negativa = variavel sem informacao naquela safra
    soma += pd.Series(pi.importances_mean, index=feat).clip(lower=0)
    soma_sd += pd.Series(pi.importances_std, index=feat)
    print(f'  safra {ano} concluida', flush=True)
imp = soma
imp_sd = soma_sd / len(TEST_YEARS)
pi_mean = soma.values

GROUPS = {'NDVI': 'NDVI (vigor vegetativo)', 'EVI': 'EVI (vigor vegetativo)',
          'GLI': 'Índices espectrais (outros)', 'CVI': 'Índices espectrais (outros)',
          'TMAX': 'Temperatura máxima', 'TMIN': 'Temperatura mínima',
          'SRAD': 'Radiação solar', 'ACC_RAINFALL': 'Precipitação',
          'LOWRAIN': 'Dias de baixa chuva', 'HOT_DAYS': 'Dias quentes',
          'SPI': 'Índices de seca (SPI/STI)', 'STI': 'Índices de seca (SPI/STI)',
          'ETP': 'Evapotranspiração/Balanço hídrico',
          'DEF': 'Evapotranspiração/Balanço hídrico',
          'EXC': 'Evapotranspiração/Balanço hídrico',
          'ONI': 'El Niño (ONI)', 'SOY_AREA': 'Área de soja',
          'HARVESTED': 'Ano', 'MONTH': 'Mês'}
def grp(c):
    for k, v in GROUPS.items():
        if k in c: return v
    return 'Outros'

pd.DataFrame({'variavel': feat, 'grupo': [grp(c) for c in feat],
              'piora_rmse_kg_ha_somada': pi_mean.round(3),
              'desvio_medio': imp_sd.values.round(3)}
             ).sort_values('piora_rmse_kg_ha_somada', ascending=False
             ).to_csv(f'{OUT}/importancia_permutacao.csv', index=False)

g = imp.groupby(imp.index.map(grp)).sum().sort_values(ascending=False)
g = (g / g.sum() * 100).round(2) if g.sum() > 0 else g
print('Top grupos de variáveis (% da piora total do RMSE):')
print(g.head(10).to_string())

fig, ax = plt.subplots(figsize=(8, 4.6))
gg = g.head(10)[::-1]
ax.barh(gg.index, gg.values, color=BLUE2)
ax.set_xlabel('Importância relativa (%)')
ax.set_title(f'Importância por permutação — {best} ajustado\n'
             f'(agregada nas safras de {TEST_YEARS[0]} a {TEST_YEARS[-1]})',
             fontsize=11)
for i, v in enumerate(gg.values): ax.text(v + 0.3, i, f'{v:.1f}%', va='center', fontsize=9)
ax.set_xlim(0, gg.values.max() * 1.15)
plt.tight_layout()
plt.savefig(f'{OUT}/fig4_importancia_permutacao.png', dpi=200,
            bbox_inches='tight', facecolor='white')
plt.close()

print('\nFiguras:', sorted(f for f in os.listdir(OUT) if f.startswith('fig') and f.endswith('.png')))
print(f'Melhor modelo: {best} | R2={mods[best]["R2_pool"]} '
      f'RMSE={mods[best]["RMSE_pool"]} rRMSE={mods[best]["rRMSE_pool"]}%')
