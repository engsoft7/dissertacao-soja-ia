# -*- coding: utf-8 -*-
"""
O erro do estudo nacional por estado.

O objetivo específico d da dissertação pede o comportamento do erro por
região. A Tabela 3 e o Apêndice C reportam o erro no conjunto e por safra.
Este script reparte as mesmas previsões (protocolo de 04_avalia_ajustado.py,
safras de teste de 2016 a 2020) pelos sete estados da base: RMSE, MAE, erro
relativo à média do estado, viés e R² de cada modelo, e o ganho do SVR sobre
o modelo de referência (média do município mais tendência) em cada estado,
com IC95 por reamostragem de municípios, como em
08_previsao_futura/04_referencia_nacional.py. Ao lado, a taxa de repetição da
produtividade entre safras sucessivas em cada estado (a medida da subseção
6.4, nas vinte safras da base), para ver se o ganho acompanha a repetição.

Requer data/data_cast.csv (00_baixa_dados.py). Uso: python 15_erro_por_estado.py
Saída: erro_por_estado.json
"""
import importlib.util
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..', '08_previsao_futura'))   # 04_referencia_nacional.py importa comum


def carrega(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    cfg = carrega('avalia', os.path.join(AQUI, '04_avalia_ajustado.py'))
    ref_nac = carrega('ref', os.path.join(AQUI, '..', '08_previsao_futura', '04_referencia_nacional.py'))
    df = pd.read_csv(os.path.join(AQUI, 'data', 'data_cast.csv'))
    fora = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
    feat = [c for c in df.columns if c not in fora and df[c].dtype != 'object']
    X = df[feat].fillna(df[feat].median()).values
    y, tend = df.YIELD.values.astype(float), df.YIELD_TREND.values.astype(float)
    anom = df.YIELD_TREND_CORRECTED.values.astype(float)
    anos, cod, uf = df.HARVESTED.values, df.CODE.values, df.STATE.values

    P = {nome: np.full(len(y), np.nan) for nome in cfg.AJUSTADOS}
    R = np.full(len(y), np.nan)
    for ty in cfg.SAFRAS_TESTE:
        te = anos == ty
        idx = np.random.RandomState(1000 + ty).choice(np.where(~te)[0], min(cfg.SUB, int((~te).sum())),
                                                      replace=False)
        R[te] = ref_nac.ref_media_tendencia(y, anos, cod, ~te, te)
        for nome, base in cfg.AJUSTADOS.items():
            xtr, xte, atr = X[idx], X[te], anom[idx]
            if nome in cfg.PRECISA_ESCALA:
                esc = StandardScaler().fit(xtr)
                xtr, xte = esc.transform(xtr), esc.transform(xte)
                if nome == 'SVR':
                    xtr, atr = xtr[:cfg.SUB_SVR], atr[:cfg.SUB_SVR]
            P[nome][te] = clone(base).fit(xtr, atr).predict(xte) + tend[te]
        print(f'safra {ty} feita', flush=True)

    m = np.isin(anos, cfg.SAFRAS_TESTE)

    def repeticao(k):
        r = t = 0
        for _, d in df[k].groupby('CODE'):
            v = d.sort_values('HARVESTED').YIELD.values
            r += int((np.diff(v) == 0).sum())
            t += len(v) - 1
        return round(r / t * 100, 1)

    def mede(k, p):
        rmse = float(np.sqrt(mean_squared_error(y[k], p[k])))
        return {'RMSE': round(rmse, 1), 'MAE': round(float(mean_absolute_error(y[k], p[k])), 1),
                'erro_relativo_%': round(float(rmse / y[k].mean() * 100), 1),
                'vies': round(float((p[k] - y[k]).mean()), 1), 'R2': round(float(r2_score(y[k], p[k])), 3)}

    saida = {'nota': ('Previsões do protocolo da Tabela 3 (04_avalia_ajustado.py, safras de 2016 a 2020) repartidas '
                      'por estado. Erro relativo = RMSE sobre a produtividade média do estado nas safras de teste; '
                      'viés = previsto menos observado; repetição = pares de safras sucessivas com produtividade idêntica, '
                      'nas vinte safras da base. Ganho do SVR sobre a referência (média do município + '
                      'tendência) = 1 − MSE(SVR)/MSE(referência), IC95 por reamostragem de municípios.'),
             'produtividade_media': {'base inteira (2001-2020)': round(float(y.mean()), 1),
                                     'safras de teste (2016-2020)': round(float(y[m].mean()), 1)},
             'conjunto': {nome: mede(m, p) for nome, p in P.items()}, 'estados': {}}
    for e in sorted(set(uf[m])):
        k = m & (uf == e)
        linha = {'registros': int(k.sum()), 'municipios': int(len(set(cod[k]))),
                 'produtividade_media': round(float(y[k].mean()), 1),
                 'desvio_padrao': round(float(y[k].std()), 1),
                 'repeticao_%': repeticao(uf == e),
                 'Referência': mede(k, R)}
        linha.update({nome: mede(k, p) for nome, p in P.items()})
        linha['ganho_do_SVR_sobre_a_referencia'] = ref_nac.ganho_por_municipio(y[k], P['SVR'][k], R[k], cod[k])
        saida['estados'][str(e)] = linha
        print(e, linha['registros'], linha['SVR'], linha['ganho_do_SVR_sobre_a_referencia'], flush=True)
    est = saida['estados']
    rep = [est[e]['repeticao_%'] for e in est]
    saida['repeticao_contra_desempenho_(Spearman, 7 estados)'] = {
        nome: {'rho': round(float(s.statistic), 2), 'p': round(float(s.pvalue), 3)} for nome, s in (
            ('ganho do SVR sobre a referência', spearmanr(rep, [est[e]['ganho_do_SVR_sobre_a_referencia']['ganho'] for e in est])),
            ('R² do SVR', spearmanr(rep, [est[e]['SVR']['R2'] for e in est])))}
    with open(os.path.join(AQUI, 'erro_por_estado.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: saida[k] for k in saida if k not in ('nota', 'estados')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
