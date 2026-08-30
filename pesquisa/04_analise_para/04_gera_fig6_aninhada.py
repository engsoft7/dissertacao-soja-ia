# -*- coding: utf-8 -*-
"""Regera a Figura 6 a partir das previsões do MLP com busca aninhada (Tabela 6)."""
import warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, r2_score
import importlib.util
spec=importlib.util.spec_from_file_location('busca','03_busca_hiperparametros.py')
b=importlib.util.module_from_spec(spec)
import sys; sys.argv=['x','baseline']; spec.loader.exec_module.__self__ if False else None
# reexecuta a lógica sem chamar main()
src=open('03_busca_hiperparametros.py',encoding='utf-8').read().split("def main()")[0]
ns={}; exec(src, ns)

df=ns['carrega']()
y=df.rendimento_kg_ha.values.astype(float)
anos, mun, X = df.ano.values, df.municipio.values, df[ns['FEATURES']].values
safras=[a for a in sorted(set(anos)) if (anos==a).sum()>=ns['MIN_MUN']]
cands=[ns['ATUAL']['MLP']]+ns['amostra']('MLP',15,np.random.default_rng(ns['SEED']))
obs, prev = [], []
for ty in safras:
    tr=anos!=ty
    internas=[a for a in safras if a!=ty][-ns['N_INTERNAS']:]
    melhor, mr = None, np.inf
    for cfg in cands:
        e=[np.sqrt(mean_squared_error(y[anos==vi], ns['preve']('MLP',cfg,X,y,anos,mun,tr&(anos!=vi),anos==vi)))
           for vi in internas if (anos==vi).sum()>=ns['MIN_MUN']]
        r=float(np.mean(e)) if e else np.inf
        if r<mr: melhor, mr = cfg, r
    obs+=list(y[anos==ty]); prev+=list(ns['preve']('MLP',melhor,X,y,anos,mun,tr,anos==ty))
yt, yp = np.array(obs), np.array(prev)
rmse=np.sqrt(mean_squared_error(yt,yp)); rr=rmse/y.mean()*100
print(f'MLP aninhado: RMSE={rmse:.1f} R2={r2_score(yt,yp):.3f} rRMSE={rr:.1f}%  (n={len(yt)})')

plt.rcParams.update({'font.family':'DejaVu Serif','font.size':11,'axes.grid':True,'grid.alpha':0.3})
B2, RED = '#2E75B6', '#B00020'
fig, ax = plt.subplots(figsize=(5.4,5.2))
ax.scatter(yt,yp,s=16,alpha=0.45,color=B2,edgecolors='none')
lim=[min(yt.min(),yp.min())*0.97, max(yt.max(),yp.max())*1.03]
ax.plot(lim,lim,'--',color=RED,lw=1.4,label='Linha 1:1')
ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel('Produtividade observada (kg/ha)'); ax.set_ylabel('Produtividade prevista (kg/ha)')
ax.set_title(f'Previsto vs. observado — Pará (MLP)\n(RMSE={rmse:.0f} kg/ha; rRMSE={rr:.1f}%)',fontsize=10)
ax.legend(fontsize=8.5)
plt.tight_layout(); plt.savefig('results/fig_pa_scatter_aninhada.png',dpi=200,bbox_inches='tight',facecolor='white')
print('figura gravada')
