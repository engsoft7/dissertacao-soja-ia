# -*- coding: utf-8 -*-
import json, re, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from xgboost import XGBRegressor
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':11,'axes.grid':True,'grid.alpha':0.3})
OUT='results'
BLUE='#1F4E79'; BLUE2='#2E75B6'

res=json.load(open(f'{OUT}/all_results.json'))
order=sorted(res, key=lambda m:res[m]['R2_pool'], reverse=True)

# ---------- IMPORTANCIA (XGBoost sobre a anomalia) ----------
df=pd.read_csv('data/data_cast.csv')
drop=['YIELD','YIELD_TREND','YIELD_TREND_CORRECTED','CODE','COUNTY','STATE','CLIMATE_ZONE']
feat=[c for c in df.columns if c not in drop and df[c].dtype!='object']
X=df[feat].fillna(df[feat].median()); ANOM=df['YIELD_TREND_CORRECTED'].values.astype(float)
idx=np.random.RandomState(7).choice(len(df),10000,replace=False)
xgb=XGBRegressor(n_estimators=300,max_depth=6,learning_rate=0.05,tree_method='hist',n_jobs=-1,verbosity=0,random_state=42)
xgb.fit(X.iloc[idx].values, ANOM[idx])
imp=pd.Series(xgb.feature_importances_, index=feat)

GROUPS={'NDVI':'NDVI (vigor vegetativo)','EVI':'EVI (vigor vegetativo)','GLI':'Índices espectrais (outros)',
 'CVI':'Índices espectrais (outros)','TMAX':'Temperatura máxima','TMIN':'Temperatura mínima',
 'SRAD':'Radiação solar','ACC_RAINFALL':'Precipitação','LOWRAIN':'Dias de baixa chuva','HOT_DAYS':'Dias quentes',
 'SPI':'Índices de seca (SPI/STI)','STI':'Índices de seca (SPI/STI)','ETP':'Evapotranspiração/Balanço hídrico',
 'DEF':'Evapotranspiração/Balanço hídrico','EXC':'Evapotranspiração/Balanço hídrico',
 'ONI':'El Niño (ONI)','SOY_AREA':'Área de soja','HARVESTED':'Ano','MONTH':'Mês'}
def grp(c):
    for k,v in GROUPS.items():
        if k in c: return v
    return 'Outros'
g=imp.groupby(imp.index.map(grp)).sum().sort_values(ascending=False)
g=(g/g.sum()*100).round(2)
g.to_csv(f'{OUT}/importance_grouped.csv', header=['importancia_%'])
print('Top grupos de variáveis (% importância):'); print(g.head(10).to_string())

# ---------- FIG 2: comparacao dos modelos ----------
fig,ax=plt.subplots(1,2,figsize=(10,4.2))
r2=[res[m]['R2_pool'] for m in order]; rmse=[res[m]['RMSE_pool'] for m in order]
c=[BLUE if i==0 else BLUE2 for i in range(len(order))]
ax[0].bar(order,r2,color=c); ax[0].set_ylabel('R² (agregado)'); ax[0].set_title('(a) Coeficiente de determinação R²')
ax[0].set_ylim(0,max(r2)*1.25)
for i,v in enumerate(r2): ax[0].text(i,v+0.008,f'{v:.3f}',ha='center',fontsize=9)
ax[1].bar(order,rmse,color=c); ax[1].set_ylabel('RMSE (kg/ha)'); ax[1].set_title('(b) Raiz do erro quadrático médio')
ax[1].set_ylim(0,max(rmse)*1.18)
for i,v in enumerate(rmse): ax[1].text(i,v+5,f'{v:.0f}',ha='center',fontsize=9)
for a in ax: a.tick_params(axis='x',rotation=15)
plt.tight_layout(); plt.savefig(f'{OUT}/fig_modelos.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

# ---------- FIG 3: previsto vs observado (melhor modelo) ----------
best=order[0]
p=pd.read_csv(f'{OUT}/pred_{best.replace(" ","_")}.csv')
fig,ax=plt.subplots(figsize=(5.6,5.4))
ax.scatter(p.y_true,p.y_pred,s=6,alpha=0.25,color=BLUE2,edgecolors='none')
lim=[min(p.y_true.min(),p.y_pred.min()),max(p.y_true.max(),p.y_pred.max())]
ax.plot(lim,lim,'--',color='#B00020',lw=1.5,label='Linha 1:1 (previsão perfeita)')
ax.set_xlabel('Produtividade observada (kg/ha)'); ax.set_ylabel('Produtividade prevista (kg/ha)')
ax.set_title(f'Previsto vs. observado — {best}\n(R²={res[best]["R2_pool"]:.3f}; RMSE={res[best]["RMSE_pool"]:.0f} kg/ha)')
ax.legend(loc='upper left',fontsize=9); ax.set_xlim(lim); ax.set_ylim(lim)
plt.tight_layout(); plt.savefig(f'{OUT}/fig_scatter.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

# ---------- FIG 4: importancia por grupo ----------
fig,ax=plt.subplots(figsize=(8,4.6))
gg=g.head(10)[::-1]
ax.barh(gg.index,gg.values,color=BLUE2)
ax.set_xlabel('Importância relativa (%)'); ax.set_title('Importância dos grupos de variáveis (XGBoost)')
for i,v in enumerate(gg.values): ax.text(v+0.3,i,f'{v:.1f}%',va='center',fontsize=9)
ax.set_xlim(0,gg.values.max()*1.15)
plt.tight_layout(); plt.savefig(f'{OUT}/fig_importancia.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

# ---------- resumo final consolidado ----------
summary={'models':res,'order':order,'best':best,
 'n_rows':int(len(df)),'n_mun':int(df.groupby(['STATE','COUNTY']).ngroups),
 'states':sorted(df.STATE.unique().tolist()),
 'years':[int(df.HARVESTED.min()),int(df.HARVESTED.max())],
 'test_years':[2016,2017,2018,2019,2020],'n_features':len(feat),
 'yield_mean':float(df.YIELD.mean()),
 'importance_top':g.head(8).to_dict()}
json.dump(summary, open(f'{OUT}/summary.json','w'), indent=2, ensure_ascii=False)
import os
print('\nFiguras:', [f for f in os.listdir(OUT) if f.endswith('.png')])
print('Melhor modelo:', best, '| R2=',res[best]['R2_pool'],'RMSE=',res[best]['RMSE_pool'])
