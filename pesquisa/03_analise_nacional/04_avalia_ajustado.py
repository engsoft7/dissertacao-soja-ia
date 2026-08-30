# -*- coding: utf-8 -*-
"""Avaliacao final do estudo nacional com os hiperparametros ajustados.
Gera a Tabela 3 da dissertacao.

As configuracoes abaixo sao as reportadas na dissertacao. Elas saem da busca
de 03_busca_hiperparametros.py, que ocorre inteiramente na janela 2001-2015;
aqui os modelos sao reavaliados nas safras de 2016 a 2020, que nao participaram
da selecao.

Sobre reproduzir a busca
------------------------
03_busca_hiperparametros.py e uma busca ALEATORIA: o conjunto de configuracoes
sorteadas -- e portanto a vencedora -- depende do sorteio. Reexecutar a busca
tende a eleger uma configuracao diferente das que estao escritas abaixo, sem
que isso invalide a Tabela 3. Duas razoes:

  - o topo do ranking e um platô, nao um otimo agudo. Em 06_confirma_busca.py
    as tres melhores configuracoes de cada modelo ficam a poucos kg/ha umas das
    outras, e a ordem entre elas muda conforme o tamanho da subamostra;
  - o que a busca decide de fato e QUAL MODELO vence, e essa conclusao e
    estavel. Em uma reexecucao independente da busca neste repositorio, a
    configuracao de SVR eleita rendeu 461,6 kg/ha nesta mesma janela de teste,
    contra 460,7 kg/ha da configuracao abaixo -- diferenca de menos de 1 kg/ha,
    com o SVR na frente nos dois casos.

Por isso este script traz as configuracoes fixas: ele reproduz a Tabela 3 sem
depender de repetir a busca, que e a etapa cara.

Protocolo identico ao de 01_treina_modelos.py (o registro da versao sem
ajuste), para que a unica diferenca entre os dois resultados seja o
hiperparametro:

  - modelos preveem a ANOMALIA climatica (YIELD_TREND_CORRECTED) e a
    produtividade e reconstruida como anomalia_prevista + YIELD_TREND;
  - validacao leave-one-year-out sobre 2016-2020: cada safra e prevista por um
    modelo treinado sem ela, simulando a previsao de um ano futuro;
  - treino de cada dobra sorteado com SUB=7.000 registros, semente fixa por
    safra, de modo que todos os modelos vejam exatamente os mesmos dados;
  - o SVR treina com no maximo 5.000 registros (custo quadratico no numero de
    amostras), como em 01_treina_modelos.py;
  - metricas calculadas na produtividade reconstruida, em kg/ha.

Saida: resultados_ajustados.json  e  results/pred_ajustado_<modelo>.csv
Uso:   python 04_avalia_ajustado.py ["Random Forest" "XGBoost" "SVR" "MLP"]
"""
import json, os, sys, time, platform, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
import sklearn, xgboost
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from xgboost import XGBRegressor

OUT = 'results'; os.makedirs(OUT, exist_ok=True)
TEST_YEARS = [2016, 2017, 2018, 2019, 2020]
SUB = 7000; SVR_MAX = 5000
NEEDS_SCALE = {'SVR', 'MLP'}
MODELOS = sys.argv[1:] or ['Random Forest', 'XGBoost', 'SVR', 'MLP']

def build(name):
    if name == 'Random Forest':
        return RandomForestRegressor(
            n_estimators=100, max_depth=10, min_samples_leaf=2, max_features='sqrt',
            n_jobs=-1, random_state=42)
    if name == 'XGBoost':
        return XGBRegressor(
            n_estimators=400, max_depth=6, learning_rate=0.02, subsample=0.7,
            colsample_bytree=1.0, reg_lambda=5, min_child_weight=3,
            tree_method='hist', n_jobs=-1, verbosity=0, random_state=42)
    if name == 'SVR':
        return SVR(C=100, gamma=0.005, epsilon=0.05)
    if name == 'MLP':
        return MLPRegressor(
            hidden_layer_sizes=(64, 32), alpha=1e-3, learning_rate_init=3e-3,
            max_iter=250, early_stopping=True, random_state=42)
    raise ValueError(name)

df = pd.read_csv('data/data_cast.csv')
DROP = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED',
        'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
feat = [c for c in df.columns if c not in DROP and df[c].dtype != 'object']
X = df[feat].fillna(df[feat].median())
YIELD = df['YIELD'].values.astype(float)
TREND = df['YIELD_TREND'].values.astype(float)
ANOM  = df['YIELD_TREND_CORRECTED'].values.astype(float)
yr    = df['HARVESTED'].values
ymean = float(YIELD.mean())

def M(yt, yp):
    return (float(np.sqrt(mean_squared_error(yt, yp))),
            float(mean_absolute_error(yt, yp)),
            float(r2_score(yt, yp)))

# Mesmas subamostras de 01_treina_modelos.py: a comparacao ajustado x sem
# ajuste isola o efeito do hiperparametro.
subidx = {ty: np.random.RandomState(1000 + ty).choice(
              np.where(yr != ty)[0], min(SUB, int((yr != ty).sum())), replace=False)
          for ty in TEST_YEARS}

resfile = 'resultados_ajustados.json'
allres = json.load(open(resfile)) if os.path.exists(resfile) else {}
# 'protocolo' descreve ESTA execucao: sempre reescrito, nunca herdado de um
# JSON anterior (so os resultados por modelo se acumulam entre chamadas).
allres['protocolo'] = {
    'anos_teste': TEST_YEARS, 'sub_treino': SUB, 'svr_max_treino': SVR_MAX,
    'n_registros': int(len(df)), 'n_variaveis': len(feat),
    'produtividade_media_kg_ha': round(ymean, 1),
    'origem_hiperparametros': 'Quadro 6 da dissertacao (busca na janela 2001-2015)',
}
# Procedencia: o Random Forest e o XGBoost mudam de resultado entre versoes das
# bibliotecas, mesmo com random_state fixo e os mesmos hiperparametros -- o
# sorteio interno e a discretizacao do histograma nao sao estaveis entre
# versoes. O SVR (libsvm) e o MLP sao estaveis. Registrar as versoes torna a
# diferenca rastreavel em vez de misteriosa.
allres['ambiente'] = {
    'python': platform.python_version(),
    'scikit_learn': sklearn.__version__,
    'xgboost': xgboost.__version__,
    'numpy': np.__version__,
    'pandas': pd.__version__,
}
allres.setdefault('modelos', {})

for name in MODELOS:
    t0 = time.time(); per = {}; yt_all = []; yp_all = []; yy = []
    for ty in TEST_YEARS:
        idx = subidx[ty]; te = yr == ty
        Xtr, Xte, atr = X.iloc[idx].values, X[te].values, ANOM[idx]
        if name in NEEDS_SCALE:
            sc = StandardScaler().fit(Xtr)
            Xtr, Xte = sc.transform(Xtr), sc.transform(Xte)
            if name == 'SVR':
                Xtr, atr = Xtr[:SVR_MAX], atr[:SVR_MAX]
        mdl = build(name).fit(Xtr, atr)
        yhat = mdl.predict(Xte) + TREND[te]
        yreal = YIELD[te]
        rmse, mae, r2 = M(yreal, yhat)
        per[int(ty)] = {'rmse': round(rmse, 1), 'mae': round(mae, 1), 'r2': round(r2, 3)}
        yt_all += list(yreal); yp_all += list(yhat); yy += [int(ty)] * len(yreal)
        print('%s %d: RMSE=%.0f MAE=%.0f R2=%.3f' % (name, ty, rmse, mae, r2), flush=True)
    yt_all = np.array(yt_all); yp_all = np.array(yp_all)
    prmse, pmae, pr2 = M(yt_all, yp_all)
    rm = [per[t]['rmse'] for t in per]; ma = [per[t]['mae'] for t in per]
    r2s = [per[t]['r2'] for t in per]
    allres['modelos'][name] = {
        'params': build(name).get_params(),
        'per_year': per,
        'RMSE_mean': round(float(np.mean(rm)), 1), 'RMSE_std': round(float(np.std(rm)), 1),
        'MAE_mean': round(float(np.mean(ma)), 1),  'MAE_std': round(float(np.std(ma)), 1),
        'R2_mean': round(float(np.mean(r2s)), 3),  'R2_std': round(float(np.std(r2s)), 3),
        'RMSE_pool': round(prmse, 1), 'MAE_pool': round(pmae, 1), 'R2_pool': round(pr2, 3),
        'rRMSE_pool': round(prmse / ymean * 100, 1)}
    pd.DataFrame({'y_true': yt_all, 'y_pred': yp_all, 'year': yy}).to_csv(
        '%s/pred_ajustado_%s.csv' % (OUT, name.replace(' ', '_')), index=False)
    json.dump(allres, open(resfile, 'w'), indent=2, ensure_ascii=False, default=str)
    print('>>> %s OK (%.0fs) | R2_pool=%.3f RMSE_pool=%.0f rRMSE=%.1f%%\n'
          % (name, time.time() - t0, pr2, prmse, prmse / ymean * 100), flush=True)

mods = allres['modelos']
if mods:
    ordem = sorted(mods, key=lambda m: mods[m]['RMSE_pool'])
    allres['melhor'] = ordem[0]
    json.dump(allres, open(resfile, 'w'), indent=2, ensure_ascii=False, default=str)
    print('=' * 62)
    print('TABELA 3 - estudo nacional, hiperparametros ajustados (2016-2020)')
    print('=' * 62)
    print(f'{"Modelo":16s}{"RMSE":>8s}{"MAE":>8s}{"R2":>8s}{"rRMSE":>9s}')
    for m in ordem:
        d = mods[m]
        print(f'{m:16s}{d["RMSE_pool"]:8.0f}{d["MAE_pool"]:8.0f}'
              f'{d["R2_pool"]:8.3f}{d["rRMSE_pool"]:8.1f}%')
    print(f'\nMelhor modelo: {ordem[0]}')
