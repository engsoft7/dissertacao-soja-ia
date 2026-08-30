# -*- coding: utf-8 -*-
"""
Regenera as Figuras 2, 3 e 4 do estudo nacional a partir dos modelos ajustados.

A importância das variáveis passa a ser calculada por permutação sobre o SVR
ajustado, que é o modelo de melhor desempenho após a busca de hiperparâmetros.
A importância nativa do XGBoost, usada na versão anterior, não se aplica ao
SVR; a permutação é agnóstica ao algoritmo e mede a degradação do erro quando
os valores de uma variável são embaralhados, o que a torna comparável entre
famílias de modelos.

Uso:  python 05_gera_figuras_ajustado.py
"""
import json
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

# --- ABNT: separador decimal com vírgula, nos rótulos e nos eixos --------------
from matplotlib.ticker import FuncFormatter as _FuncFormatter


def vg(x, fmt='.1f'):
    """Número com vírgula decimal, como pede a ABNT."""
    return format(x, fmt).replace('.', ',')


_VIRGULA = _FuncFormatter(lambda v, _pos: f'{v:g}'.replace('.', ','))


def eixos_virgula(*eixos, x=False, y=True):
    """Aplica vírgula decimal aos rótulos dos eixos informados.

    Só ao eixo Y por padrão: aplicar ao X estragaria rótulos categóricos
    (nomes de modelos) e anos, que não levam separador decimal.
    """
    for e in eixos:
        if y:
            e.yaxis.set_major_formatter(_VIRGULA)
        if x:
            e.xaxis.set_major_formatter(_VIRGULA)
# ------------------------------------------------------------------------------
from sklearn.inspection import permutation_importance
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 11,
                     'axes.grid': True, 'grid.alpha': 0.3})
OUT = 'results'
AZUL, AZUL2 = '#1F4E79', '#2E75B6'
SEED = 42

GRUPOS = {'NDVI': 'NDVI (vigor vegetativo)', 'EVI': 'EVI (vigor vegetativo)',
          'GLI': 'Índices espectrais (outros)', 'CVI': 'Índices espectrais (outros)',
          'TMAX': 'Temperatura máxima', 'TMIN': 'Temperatura mínima', 'SRAD': 'Radiação solar',
          'ACC_RAINFALL': 'Precipitação', 'LOWRAIN': 'Dias de baixa chuva', 'HOT_DAYS': 'Dias quentes',
          'SPI': 'Índices de seca (SPI/STI)', 'STI': 'Índices de seca (SPI/STI)',
          'ETP': 'Evapotranspiração/Balanço hídrico', 'DEF': 'Evapotranspiração/Balanço hídrico',
          'EXC': 'Evapotranspiração/Balanço hídrico', 'ONI': 'El Niño (ONI)',
          'SOY_AREA': 'Área de soja', 'HARVESTED': 'Ano', 'MONTH': 'Mês'}


def grupo(col):
    for k, v in GRUPOS.items():
        if k in col:
            return v
    return 'Outros'


res = json.load(open(f'{OUT}/resultados_ajustados.json', encoding='utf-8'))
ordem = sorted(res, key=lambda m: res[m]['R2_pool'], reverse=True)
melhor = ordem[0]
print(f'Melhor modelo ajustado: {melhor} '
      f'(R²={res[melhor]["R2_pool"]}, RMSE={res[melhor]["RMSE_pool"]})', flush=True)

df = pd.read_csv('data/data_cast.csv')
fora = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
feat = [c for c in df.columns if c not in fora and df[c].dtype != 'object']
X = df[feat].fillna(df[feat].median()).values
ANOM = df['YIELD_TREND_CORRECTED'].values.astype(float)

rng = np.random.RandomState(7)
tr = rng.choice(len(df), 3000, replace=False)
te = rng.choice(np.setdiff1d(np.arange(len(df)), tr), 900, replace=False)

esc = StandardScaler().fit(X[tr])
svr = SVR(C=100, epsilon=0.05, gamma=0.005).fit(esc.transform(X[tr]), ANOM[tr])
print('SVR ajustado treinado; calculando importância por permutação...', flush=True)

pi = permutation_importance(svr, esc.transform(X[te]), ANOM[te], n_repeats=2,
                            random_state=SEED, n_jobs=-1,
                            scoring='neg_root_mean_squared_error')
imp = pd.Series(np.clip(pi.importances_mean, 0, None), index=feat)
g = imp.groupby(imp.index.map(grupo)).sum().sort_values(ascending=False)
g = (g / g.sum() * 100).round(2)
g.to_csv(f'{OUT}/importance_grouped_ajustado.csv', header=['importancia_%'])
print('\nGrupos de variáveis (% de importância por permutação, SVR ajustado):')
print(g.head(10).to_string(), flush=True)

fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
r2 = [res[m]['R2_pool'] for m in ordem]
rmse = [res[m]['RMSE_pool'] for m in ordem]
cor = [AZUL if i == 0 else AZUL2 for i in range(len(ordem))]
ax[0].bar(ordem, r2, color=cor)
ax[0].set_ylabel('R² (agregado)')
ax[0].set_title('(a) Coeficiente de determinação R²')
ax[0].set_ylim(0, max(r2) * 1.25)
for i, v in enumerate(r2):
    ax[0].text(i, v + 0.008, vg(v, '.3f'), ha='center', fontsize=9)
ax[1].bar(ordem, rmse, color=cor)
ax[1].set_ylabel('RMSE (kg/ha)')
ax[1].set_title('(b) Raiz do erro quadrático médio')
ax[1].set_ylim(0, max(rmse) * 1.18)
for i, v in enumerate(rmse):
    ax[1].text(i, v + 5, vg(v, '.0f'), ha='center', fontsize=9)
for a in ax:
    a.tick_params(axis='x', rotation=15)
eixos_virgula(*ax)
plt.tight_layout()
plt.savefig(f'{OUT}/fig_modelos_ajustado.png', dpi=200, bbox_inches='tight', facecolor='white')
plt.close()

p = pd.read_csv(f'{OUT}/pred_ajustado_{melhor.replace(" ", "_")}.csv')
fig, ax = plt.subplots(figsize=(5.6, 5.4))
ax.scatter(p.y_true, p.y_pred, s=6, alpha=0.25, color=AZUL2, edgecolors='none')
lim = [min(p.y_true.min(), p.y_pred.min()), max(p.y_true.max(), p.y_pred.max())]
ax.plot(lim, lim, '--', color='#B00020', lw=1.5, label='Linha 1:1 (previsão perfeita)')
ax.set_xlabel('Produtividade observada (kg/ha)')
ax.set_ylabel('Produtividade prevista (kg/ha)')
ax.set_title(f'Previsto vs. observado — {melhor}\n'
             f'(R²={vg(res[melhor]["R2_pool"], ".3f")}; '
             f'RMSE={vg(res[melhor]["RMSE_pool"], ".0f")} kg/ha)')
ax.legend(fontsize=9)
eixos_virgula(ax, x=True)
plt.tight_layout()
plt.savefig(f'{OUT}/fig_scatter_ajustado.png', dpi=200, bbox_inches='tight', facecolor='white')
plt.close()

top = g.head(10)[::-1]
fig, ax = plt.subplots(figsize=(7.6, 4.6))
ax.barh(top.index, top.values, color=AZUL2)
ax.barh(top.index[-1:], top.values[-1:], color=AZUL)
ax.set_xlabel('Importância relativa (%)')
ax.set_title(f'Importância por permutação, agrupada — {melhor} ajustado')
for i, v in enumerate(top.values):
    ax.text(v + 0.4, i, vg(v, '.1f') + '%', va='center', fontsize=9)
eixos_virgula(ax, x=True, y=False)
plt.tight_layout()
plt.savefig(f'{OUT}/fig_importancia_ajustado.png', dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print('\nFiguras geradas.')
