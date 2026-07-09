# -*- coding: utf-8 -*-
"""Previsao de produtividade da soja: modelos preveem a ANOMALIA climatica
(YIELD_TREND_CORRECTED); reconstroi-se YIELD = anomalia_prevista + tendencia.
Validacao leave-one-year-out. Metricas na produtividade reconstruida (kg/ha)."""
import sys, json, os, time, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from xgboost import XGBRegressor

OUT='results'; os.makedirs(OUT, exist_ok=True)
TEST_YEARS=[2016,2017,2018,2019,2020]; SUB=7000; NEEDS_SCALE={'SVR','MLP'}

def build(name):
    if name=='Random Forest': return RandomForestRegressor(n_estimators=70,max_depth=16,n_jobs=-1,random_state=42)
    if name=='XGBoost': return XGBRegressor(n_estimators=250,max_depth=6,learning_rate=0.06,subsample=0.8,colsample_bytree=0.8,tree_method='hist',n_jobs=-1,verbosity=0,random_state=42)
    if name=='SVR': return SVR(C=10,gamma='scale',epsilon=0.1)
    if name=='MLP': return MLPRegressor(hidden_layer_sizes=(100,50),alpha=1e-3,max_iter=250,early_stopping=True,random_state=42)

df=pd.read_csv('data/data_cast.csv')
drop=['YIELD','YIELD_TREND','YIELD_TREND_CORRECTED','CODE','COUNTY','STATE','CLIMATE_ZONE']
feat=[c for c in df.columns if c not in drop and df[c].dtype!='object']
X=df[feat].fillna(df[feat].median())
YIELD=df['YIELD'].values.astype(float); TREND=df['YIELD_TREND'].values.astype(float)
ANOM=df['YIELD_TREND_CORRECTED'].values.astype(float); yr=df['HARVESTED'].values

def M(yt,yp): return (float(np.sqrt(mean_squared_error(yt,yp))), float(mean_absolute_error(yt,yp)), float(r2_score(yt,yp)))

subidx={ty: np.random.RandomState(1000+ty).choice(np.where(yr!=ty)[0], min(SUB,int((yr!=ty).sum())), replace=False) for ty in TEST_YEARS}
resfile=f'{OUT}/all_results.json'; allres=json.load(open(resfile)) if os.path.exists(resfile) else {}

for name in sys.argv[1:]:
    t0=time.time(); per={}; yt_all=[]; yp_all=[]; yy=[]
    for ty in TEST_YEARS:
        idx=subidx[ty]; te=yr==ty
        Xtr,Xte,atr=X.iloc[idx].values,X[te].values,ANOM[idx]
        if name in NEEDS_SCALE:
            sc=StandardScaler().fit(Xtr); Xtr,Xte=sc.transform(Xtr),sc.transform(Xte)
            if name=='SVR': Xtr,atr=Xtr[:5000],atr[:5000]
        mdl=build(name); mdl.fit(Xtr,atr)
        yhat=mdl.predict(Xte)+TREND[te]
        yreal=YIELD[te]
        rmse,mae,r2=M(yreal,yhat)
        per[int(ty)]={'rmse':round(rmse,1),'mae':round(mae,1),'r2':round(r2,3)}
        yt_all+=list(yreal); yp_all+=list(yhat); yy+=[int(ty)]*len(yreal)
        print('%s %d: RMSE=%.0f MAE=%.0f R2=%.3f'%(name,ty,rmse,mae,r2), flush=True)
    yt_all=np.array(yt_all); yp_all=np.array(yp_all)
    prmse,pmae,pr2=M(yt_all,yp_all)
    rm=[per[t]['rmse'] for t in per]; ma=[per[t]['mae'] for t in per]; r2s=[per[t]['r2'] for t in per]
    allres[name]={'per_year':per,
        'RMSE_mean':round(float(np.mean(rm)),1),'RMSE_std':round(float(np.std(rm)),1),
        'MAE_mean':round(float(np.mean(ma)),1),'MAE_std':round(float(np.std(ma)),1),
        'R2_mean':round(float(np.mean(r2s)),3),'R2_std':round(float(np.std(r2s)),3),
        'RMSE_pool':round(prmse,1),'MAE_pool':round(pmae,1),'R2_pool':round(pr2,3)}
    pd.DataFrame({'y_true':yt_all,'y_pred':yp_all,'year':yy}).to_csv('%s/pred_%s.csv'%(OUT,name.replace(' ','_')),index=False)
    json.dump(allres, open(resfile,'w'), indent=2, ensure_ascii=False)
    print('>>> %s OK (%.0fs) | R2_pool=%.3f RMSE_pool=%.0f\n'%(name,time.time()-t0,pr2,prmse), flush=True)
