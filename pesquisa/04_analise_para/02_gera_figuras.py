# -*- coding: utf-8 -*-
import json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg')
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
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':10,'axes.grid':True,'grid.alpha':0.3})
OUT='results'
B1='#1F4E79'; B2='#2E75B6'; RED='#B00020'

m = pd.read_csv('../dados/soja_para_mascarado_2001_2024.csv')

# A primeira figura deste script vem de results/comparacao.json, produzido pelo
# 01_compara_mascara_e_baseline_DEPRECADO.py -- o desenho confundido, que
# comparava as duas bases inteiras. Ela foi superada pela Figura 5, gerada por
# 01_compara_mascara_controlada.py sobre a amostra comum. Se o JSON antigo nao
# estiver presente, esta figura e simplesmente pulada; as demais nao dependem
# dele.
import os
cmp = (json.load(open(f'{OUT}/comparacao.json', encoding='utf-8'))
       if os.path.exists(f'{OUT}/comparacao.json') else None)

# ---- FIG A: sem mascara vs com mascara (RMSE e rRMSE) ----
if cmp is None:
    print('results/comparacao.json ausente: figura do desenho antigo pulada '
          '(use 01_compara_mascara_controlada.py para a Figura 5).')
else:
    fig,ax=plt.subplots(1,2,figsize=(9.6,3.8))
    labs=['Random Forest','XGBoost','SVR','MLP']
    sem=[cmp['sem_mascara'][k]['RMSE'] for k in labs]
    com=[cmp['com_mascara'][k]['RMSE'] for k in labs]
    x=np.arange(len(labs)); w=0.36
    ax[0].bar(x-w/2,sem,w,label='Município inteiro',color=B2)
    ax[0].bar(x+w/2,com,w,label='Máscara de soja',color=B1)
    ax[0].axhline(cmp['com_mascara']['baseline']['RMSE'],ls='--',color=RED,lw=1.3,label='Baseline (sem clima)')
    ax[0].set_xticks(x); ax[0].set_xticklabels(labs,rotation=15,fontsize=8.5)
    ax[0].set_ylabel('RMSE (kg/ha)'); ax[0].set_title('(a) Erro por modelo'); ax[0].legend(fontsize=7.5)
    ax[0].set_ylim(380,460)
    r2s=[cmp['com_mascara'][k]['R2'] for k in labs]
    ax[1].bar(x,r2s,color=B2)
    ax[1].axhline(cmp['com_mascara']['baseline']['R2'],ls='--',color=RED,lw=1.3,label='Baseline (R²=0,221)')
    ax[1].set_xticks(x); ax[1].set_xticklabels(labs,rotation=15,fontsize=8.5)
    ax[1].set_ylabel('R² (agregado)'); ax[1].set_title('(b) R² não supera a baseline'); ax[1].legend(fontsize=7.5)
    ax[1].set_ylim(0,0.30)
    plt.tight_layout(); plt.savefig(f'{OUT}/fig_pa_modelos.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

# ---- FIG B: valores repetidos (o achado) ----
rep=0; tot=0; per_year={}
mm=m.sort_values(['municipio','ano'])
for mun,d in mm.groupby('municipio'):
    v=d.rendimento_kg_ha.values; a=d.ano.values
    for i in range(1,len(v)):
        tot+=1
        if v[i]==v[i-1]:
            rep+=1; per_year[a[i]]=per_year.get(a[i],0)+1
        else:
            per_year.setdefault(a[i],0)
tot_year={}
for mun,d in mm.groupby('municipio'):
    a=d.ano.values
    for i in range(1,len(a)): tot_year[a[i]]=tot_year.get(a[i],0)+1
anos=sorted(tot_year); pct=[per_year.get(y,0)/tot_year[y]*100 for y in anos]

fig,ax=plt.subplots(1,2,figsize=(9.6,3.6))
ax[0].pie([rep,tot-rep],labels=[f'Repetido\n'+vg(rep/tot*100)+'%',f'Variou\n'+vg((tot-rep)/tot*100)+'%'],
          colors=[RED,B2],autopct='',startangle=90,textprops={'fontsize':9})
ax[0].set_title('(a) Rendimento idêntico ao ano anterior\n'
                f'(municípios do Pará, {min(anos)}–{max(anos)})',fontsize=9.5)
ax[1].bar(anos,pct,color=B2); ax[1].axhline(rep/tot*100,ls='--',color=RED,lw=1.2,label='média '+vg(rep/tot*100)+'%')
ax[1].set_xlabel('Ano'); ax[1].set_ylabel('% de municípios'); ax[1].set_title('(b) Proporção por safra',fontsize=9.5)
eixos_virgula(ax[1])
ax[1].legend(fontsize=8)
plt.tight_layout(); plt.savefig(f'{OUT}/fig_pa_repetidos.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

# ---- FIG C: previsto vs observado (MLP, melhor) ----
m['balanco_hidrico']=m.precip_total-m.etp_total; m['log_area']=np.log1p(m.soy_area_ha)
FE=['NDVI_mean','NDVI_max','EVI_mean','EVI_max','precip_total','etp_total','balanco_hidrico','temp_mean','temp_max','srad_mean']
y=m.rendimento_kg_ha.values.astype(float); yr=m.ano.values; mun=m.municipio.values; X=m[FE].values
years=[t for t in sorted(set(yr)) if (yr==t).sum()>=4]
yt=[];yp=[]
for ty in years:
    tr=yr!=ty; te=yr==ty
    lin=LinearRegression().fit(yr[tr].reshape(-1,1),y[tr]); slope=lin.coef_[0]; my=yr[tr].mean()
    mmean=pd.Series(y[tr]).groupby(mun[tr]).mean(); gmean=y[tr].mean()
    bl=lambda idx: np.array([mmean.get(mun[i],gmean)+slope*(yr[i]-my) for i in np.where(idx)[0]])
    b_tr,b_te=bl(tr),bl(te)
    sc=StandardScaler().fit(X[tr])
    mdl=MLPRegressor(hidden_layer_sizes=(64,32),alpha=1e-2,max_iter=800,early_stopping=True,random_state=42)
    mdl.fit(sc.transform(X[tr]), y[tr]-b_tr)
    yt+=list(y[te]); yp+=list(b_te+mdl.predict(sc.transform(X[te])))
yt=np.array(yt); yp=np.array(yp)
fig,ax=plt.subplots(figsize=(5.2,5.0))
ax.scatter(yt,yp,s=16,alpha=0.45,color=B2,edgecolors='none')
lim=[min(yt.min(),yp.min())*0.97,max(yt.max(),yp.max())*1.03]
ax.plot(lim,lim,'--',color=RED,lw=1.4,label='Linha 1:1')
ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel('Produtividade observada (kg/ha)'); ax.set_ylabel('Produtividade prevista (kg/ha)')
ax.set_title('Previsto vs. observado — Pará (MLP)\n(RMSE=416 kg/ha; rRMSE=13,9%)',fontsize=10)
ax.legend(fontsize=8.5)
plt.tight_layout(); plt.savefig(f'{OUT}/fig_pa_scatter.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

# ---- FIG D: importancia ----
# results/importance_mask.csv era produzido pelo script hoje aposentado
# (01_compara_mascara_e_baseline_DEPRECADO.py). Para nao depender dele, a
# importancia e recalculada aqui quando o arquivo nao existe -- mesmo modelo,
# mesmas variaveis e mesma semente, de modo que o resultado e identico.
if os.path.exists(f'{OUT}/importance_mask.csv'):
    imp=pd.read_csv(f'{OUT}/importance_mask.csv',index_col=0).iloc[:,0]
else:
    from sklearn.ensemble import RandomForestRegressor
    FE_MASK=['NDVI_mean','NDVI_max','EVI_mean','EVI_max','precip_total','etp_total',
             'balanco_hidrico','temp_mean','temp_max','srad_mean','log_area']
    _d=pd.read_csv('../dados/soja_para_mascarado_2001_2024.csv')
    _d['balanco_hidrico']=_d.precip_total-_d.etp_total
    _d['log_area']=np.log1p(_d.soy_area_ha)
    _y=_d.rendimento_kg_ha.values.astype(float); _yr=_d.ano.values
    _lin=LinearRegression().fit(_yr.reshape(-1,1),_y)
    _anom=_y-_lin.predict(_yr.reshape(-1,1))
    _rf=RandomForestRegressor(n_estimators=400,max_depth=10,min_samples_leaf=4,
                              n_jobs=-1,random_state=42).fit(_d[FE_MASK].values,_anom)
    imp=pd.Series(_rf.feature_importances_,index=FE_MASK).sort_values(ascending=False)
    imp.to_csv(f'{OUT}/importance_mask.csv')
    print('importance_mask.csv recalculado (o script aposentado nao e mais necessario)')
NOMES={'EVI_max':'EVI máximo','log_area':'Área de soja (log)','NDVI_max':'NDVI máximo','srad_mean':'Radiação solar',
 'precip_total':'Precipitação total','etp_total':'Evapotranspiração','EVI_mean':'EVI médio','temp_mean':'Temperatura média',
 'NDVI_mean':'NDVI médio','temp_max':'Temperatura máxima','balanco_hidrico':'Balanço hídrico'}
imp.index=[NOMES.get(i,i) for i in imp.index]
g=(imp*100).sort_values()
fig,ax=plt.subplots(figsize=(7.4,4.2))
ax.barh(g.index,g.values,color=B2)
ax.set_xlabel('Importância relativa (%)'); ax.set_title('Importância das variáveis — Pará (Random Forest)',fontsize=10)
eixos_virgula(ax, x=True, y=False)
for i,v in enumerate(g.values): ax.text(v+0.25,i,vg(v)+'%',va='center',fontsize=8)
ax.set_xlim(0,g.values.max()*1.16)
plt.tight_layout(); plt.savefig(f'{OUT}/fig_pa_importancia.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

# stats p/ o texto
stats={'n':len(m),'mun':int(m.municipio.nunique()),'ymean':float(y.mean()),
 'rep_pct':round(rep/tot*100,1),'rep':rep,'tot':tot,
 'area_med':float(m.soy_area_ha.median()),'area_max':float(m.soy_area_ha.max()),
 'ndvi_masc':float(m.NDVI_mean.mean()),'ndvi_sem':float(pd.read_csv('../dados/soja_para_sem_mascara_2001_2023.csv').NDVI_mean.mean())}
json.dump(stats,open(f'{OUT}/stats_pa.json','w'),indent=2)
print('figuras OK'); print(stats)
