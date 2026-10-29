# -*- coding: utf-8 -*-
"""
Tabela 3 sem subamostragem: cada safra de teste contra todas as outras.

A dissertação registra como limitação a subamostra de 7.000 registros por
safra (5.000 para o SVR), adotada por precaução com o custo do SVR, e a
medição de 10_mede_custo_escalabilidade.py mostrou depois que ela era
dispensável: o SVR ajusta 23.617 registros em menos de meio minuto. Aqui o
protocolo de 04_avalia_ajustado.py é repetido com o conjunto de treino
inteiro, para que a limitação deixe de ser só declarada e passe a ser medida.

Mesmos modelos e hiperparâmetros de 04_avalia_ajustado.py (escolhidos na
janela 2001-2015 com subamostra; não são rebuscados aqui, para que a única
diferença seja o tamanho do treino), mesmo alvo (anomalia + tendência) e
mesma validação leave-one-year-out 2016-2020.

A comparação com a Tabela 3 é feita nas mesmas observações de teste, com
intervalo de 95% da diferença de RMSE por reamostragem de municípios.

Uso:  python 12_sem_subamostragem.py
Saída: results/sem_subamostragem.json
"""
import importlib.util
import json
import os
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')
AQUI = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('aval', os.path.join(AQUI, '04_avalia_ajustado.py'))
aval = importlib.util.module_from_spec(spec); spec.loader.exec_module(aval)
SAFRAS, AJUSTADOS, PRECISA_ESCALA = aval.SAFRAS_TESTE, aval.AJUSTADOS, aval.PRECISA_ESCALA
SUB, SUB_SVR = aval.SUB, aval.SUB_SVR
B = 1000


def main():
    df = pd.read_csv(os.path.join(AQUI, 'data', 'data_cast.csv'))
    fora = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
    feat = [c for c in df.columns if c not in fora and df[c].dtype != 'object']
    X = df[feat].fillna(df[feat].median()).values
    Y = df['YIELD'].values.astype(float)
    TREND = df['YIELD_TREND'].values.astype(float)
    ANOM = df['YIELD_TREND_CORRECTED'].values.astype(float)
    anos = df['HARVESTED'].values
    muni = df['CODE'].values
    sub = {ty: np.random.RandomState(1000 + ty).choice(
        np.where(anos != ty)[0], min(SUB, int((anos != ty).sum())), replace=False) for ty in SAFRAS}

    teste = np.concatenate([np.where(anos == ty)[0] for ty in SAFRAS])
    saida = {'nota': ('Gerado por 12_sem_subamostragem.py: protocolo de 04_avalia_ajustado.py com o treino '
                      'inteiro (todas as safras fora a de teste), comparado à Tabela 3 (subamostra de 7.000; '
                      '5.000 no SVR) nas mesmas observações de teste.'),
             'modelos': {}}
    for nome, base in AJUSTADOS.items():
        prev = {}
        for modo in ('subamostra', 'completo'):
            t0 = time.time(); p = np.empty(len(df)); p[:] = np.nan
            for ty in SAFRAS:
                te = anos == ty
                idx = sub[ty] if modo == 'subamostra' else np.where(anos != ty)[0]
                Xtr, Xte, atr = X[idx], X[te], ANOM[idx]
                if nome in PRECISA_ESCALA:
                    esc = StandardScaler().fit(Xtr)
                    Xtr, Xte = esc.transform(Xtr), esc.transform(Xte)
                    if nome == 'SVR' and modo == 'subamostra':
                        Xtr, atr = Xtr[:SUB_SVR], atr[:SUB_SVR]
                p[te] = clone(base).fit(Xtr, atr).predict(Xte) + TREND[te]
                print(f'  {nome} {modo} {ty}: n_treino={len(atr)} ({time.time() - t0:.0f} s)', flush=True)
            prev[modo] = (p, round(time.time() - t0))
        obs = Y[teste]
        res = {}
        for modo, (p, seg) in prev.items():
            q = p[teste]
            res[modo] = {'RMSE_pool': round(float(np.sqrt(mean_squared_error(obs, q))), 1),
                         'MAE_pool': round(float(mean_absolute_error(obs, q)), 1),
                         'R2_pool': round(float(r2_score(obs, q)), 3), 'segundos': seg}
        # IC95 da diferença de RMSE (completo − subamostra), reamostrando municípios
        e_c = (prev['completo'][0][teste] - obs) ** 2
        e_s = (prev['subamostra'][0][teste] - obs) ** 2
        grupos = pd.Series(np.arange(len(teste))).groupby(muni[teste]).apply(list).tolist()
        rng = np.random.RandomState(7)
        difs = []
        for _ in range(B):
            sel = np.concatenate([grupos[i] for i in rng.randint(0, len(grupos), len(grupos))])
            difs.append(np.sqrt(e_c[sel].mean()) - np.sqrt(e_s[sel].mean()))
        res['dif_rmse_completo_menos_subamostra'] = round(float(np.sqrt(e_c.mean()) - np.sqrt(e_s.mean())), 1)
        res['ic95'] = [round(float(np.percentile(difs, 2.5)), 1), round(float(np.percentile(difs, 97.5)), 1)]
        saida['modelos'][nome] = res
        print(f'>>> {nome}: {res}', flush=True)
    json.dump(saida, open(os.path.join(AQUI, 'results', 'sem_subamostragem.json'), 'w', encoding='utf-8'),
              indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
