# -*- coding: utf-8 -*-
import numpy as np, pandas as pd, json, warnings, os
warnings.filterwarnings('ignore')
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor
np.random.seed(42)
os.makedirs('results', exist_ok=True)

def M(yt,yp): return (float(np.sqrt(mean_squared_error(yt,yp))),float(mean_absolute_error(yt,yp)),float(r2_score(yt,yp)))
def build(n):
    if n=='Random Forest': return RandomForestRegressor(n_estimators=300,max_depth=10,min_samples_leaf=4,n_jobs=-1,random_state=42)
    if n=='XGBoost': return XGBRegressor(n_estimators=200,max_depth=3,learning_rate=0.05,subsample=0.8,colsample_bytree=0.8,reg_lambda=2.0,tree_method='hist',n_jobs=-1,verbosity=0,random_state=42)
    if n=='SVR': return SVR(C=10,gamma='scale')
    if n=='MLP': return MLPRegressor(hidden_layer_sizes=(64,32),alpha=1e-2,max_iter=800,early_stopping=True,random_state=42)
MODELS=['Random Forest','XGBoost','SVR','MLP']; SCALE={'SVR','MLP'}

def run(path, feats, tag):
    df=pd.read_csv(path)
    df['balanco_hidrico']=df['precip_total']-df['etp_total']
    if 'soy_area_ha' in df.columns: df['log_area']=np.log1p(df['soy_area_ha'])
    df=df.dropna(subset=feats+['rendimento_kg_ha']).reset_index(drop=True)
    y=df.rendimento_kg_ha.values.astype(float); yr=df.ano.values; mun=df.municipio.values; X=df[feats].values
    years=[t for t in sorted(set(yr)) if (yr==t).sum()>=4]
    res={m:{'yt':[],'yp':[]} for m in MODELS}; b_yt=[]; b_yp=[]
    for ty in years:
        tr=yr!=ty; te=yr==ty
        lin=LinearRegression().fit(yr[tr].reshape(-1,1),y[tr]); slope=lin.coef_[0]; my=yr[tr].mean()
        mmean=pd.Series(y[tr]).groupby(mun[tr]).mean(); gmean=y[tr].mean()
        def bl(idx): return np.array([mmean.get(mun[i],gmean)+slope*(yr[i]-my) for i in np.where(idx)[0]])
        b_tr,b_te=bl(tr),bl(te); resid=y[tr]-b_tr
        b_yt+=list(y[te]); b_yp+=list(b_te)
        sc=StandardScaler().fit(X[tr]); Xtr,Xte=sc.transform(X[tr]),sc.transform(X[te])
        for n in MODELS:
            m=build(n)
            if n in SCALE: m.fit(Xtr,resid); pr=m.predict(Xte)
            else: m.fit(X[tr],resid); pr=m.predict(X[te])
            res[n]['yt']+=list(y[te]); res[n]['yp']+=list(b_te+pr)
    br=M(np.array(b_yt),np.array(b_yp))
    out={'n':len(df),'mun':int(df.municipio.nunique()),'ymean':float(y.mean()),
         'baseline':{'RMSE':round(br[0],1),'MAE':round(br[1],1),'R2':round(br[2],3)}}
    print(f'\n===== {tag} | {len(df)} linhas, {df.municipio.nunique()} municipios =====')
    print(f'  BASELINE (sem clima)      RMSE={br[0]:6.0f}  R2={br[2]:+.3f}')
    for n in MODELS:
        r=M(np.array(res[n]['yt']),np.array(res[n]['yp']))
        out[n]={'RMSE':round(r[0],1),'MAE':round(r[1],1),'R2':round(r[2],3),'rRMSE':round(r[0]/y.mean()*100,1)}
        print(f'  {n:14s}            RMSE={r[0]:6.0f}  R2={r[2]:+.3f}  rRMSE={r[0]/y.mean()*100:.1f}%')
    best=max(MODELS,key=lambda n:out[n]['R2'])
    out['best']=best
    print(f'  >>> melhor: {best}  (ganho sobre baseline: R2 {br[2]:+.3f} -> {out[best]["R2"]:+.3f})')
    return out, df

FE_SEM=['NDVI_mean','NDVI_max','EVI_mean','EVI_max','precip_total','etp_total','balanco_hidrico','temp_mean','temp_max','srad_mean']
FE_MASK=FE_SEM+['log_area']

a,_=run('../dados/soja_para_sem_mascara_2001_2023.csv', FE_SEM, 'SEM MASCARA (municipio inteiro)')
b,dfm=run('../dados/soja_para_mascarado_2001_2024.csv', FE_SEM, 'COM MASCARA (so pixels de soja)')
c,_=run('../dados/soja_para_mascarado_2001_2024.csv', FE_MASK, 'COM MASCARA + AREA DE SOJA')

json.dump({'sem_mascara':a,'com_mascara':b,'com_mascara_area':c}, open('results/comparacao.json','w'), indent=2, ensure_ascii=False)

# importancia no melhor cenario
df=pd.read_csv('../dados/soja_para_mascarado_2001_2024.csv'); df['balanco_hidrico']=df.precip_total-df.etp_total; df['log_area']=np.log1p(df.soy_area_ha)
y=df.rendimento_kg_ha.values.astype(float); yr=df.ano.values
lin=LinearRegression().fit(yr.reshape(-1,1),y); anom=y-lin.predict(yr.reshape(-1,1))
rf=RandomForestRegressor(n_estimators=400,max_depth=10,min_samples_leaf=4,n_jobs=-1,random_state=42).fit(df[FE_MASK].values,anom)
imp=pd.Series(rf.feature_importances_,index=FE_MASK).sort_values(ascending=False)
print('\n=== Importancia (com mascara + area) ===')
print((imp*100).round(1).to_string())
imp.to_csv('results/importance_mask.csv')
