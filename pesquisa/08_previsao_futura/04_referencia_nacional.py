# -*- coding: utf-8 -*-
"""
O modelo de referência também no recorte nacional.

A subseção 6.6 registra uma assimetria: o Pará foi confrontado com um modelo de
referência sem informação ambiental (média do município + tendência), e o
recorte nacional não. Sem esse contraste, não se podia afirmar que o R² de
0,425 do SVR representa ganho sobre o histórico. Este script faz a comparação,
nas mesmas safras de teste (2016-2020) e com a mesma subamostragem de
04_avalia_ajustado.py, cuja configuração do SVR é importada, e não recopiada.

Experimentos:
  E1  SVR da Tabela 3, como na dissertação: prevê a anomalia em relação à
      tendência fornecida na base de von Bloh et al. (YIELD_TREND) e soma a ela.
  E2  Referências sem ambiente: a tendência da base sozinha; média do município
      + tendência comum em leave-one-year-out; e a mesma só com safras
      anteriores (janela crescente).
  E3  SVR sobre o resíduo da referência ajustada no treino, sem a tendência
      externa: isola o que o ambiente acrescenta ao histórico.
  E4  E3 em janela crescente: treino só com safras anteriores à de teste.

Ganho = 1 - MSE(modelo)/MSE(referência correspondente), com intervalo de 95%
por reamostragem de municípios (5 safras de teste são poucas para reamostrar
safras).

Requer pesquisa/03_analise_nacional/data/data_cast.csv, que não é versionado
por ser de terceiros: gere-o com 03_analise_nacional/00_baixa_dados.py.

Uso:  python 04_referencia_nacional.py
Saída: referencia_nacional.json
"""
import importlib.util
import json
import os
import warnings

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

from comum import RAIZ

warnings.filterwarnings('ignore')
NAC = os.path.join(RAIZ, '..', '03_analise_nacional')


def config_nacional():
    spec = importlib.util.spec_from_file_location('avalia', os.path.join(NAC, '04_avalia_ajustado.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def ref_media_tendencia(y, anos, cod, tr, te):
    b = np.polyfit(anos[tr], y[tr], 1)[0]
    am = anos[tr].mean()
    media = pd.Series(y[tr]).groupby(cod[tr]).mean()
    return pd.Series(cod[te]).map(media).fillna(y[tr].mean()).values + b * (anos[te] - am)


def ganho_por_municipio(obs, prev, ref, cod, n_boot=2000, semente=42):
    em, er = (obs - prev) ** 2, (obs - ref) ** 2
    d = pd.DataFrame({'c': cod, 'm': em, 'r': er}).groupby('c').sum()
    rng = np.random.default_rng(semente)
    idx = np.arange(len(d))
    boot = []
    for _ in range(n_boot):
        s = d.iloc[rng.choice(idx, len(idx))]
        boot.append(1 - s.m.sum() / s.r.sum())
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {'ganho': round(float(1 - em.sum() / er.sum()), 3), 'IC95': [round(float(lo), 3), round(float(hi), 3)]}


def main():
    cfg = config_nacional()
    df = pd.read_csv(os.path.join(NAC, 'data', 'data_cast.csv'))
    fora = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
    feat = [c for c in df.columns if c not in fora and df[c].dtype != 'object']
    X = df[feat].fillna(df[feat].median()).values
    y = df.YIELD.values.astype(float)
    tend = df.YIELD_TREND.values.astype(float)
    anom = df.YIELD_TREND_CORRECTED.values.astype(float)
    anos, cod = df.HARVESTED.values, df.CODE.values
    svr = cfg.AJUSTADOS['SVR']

    def ajusta_svr(idx, alvo_tr, te):
        esc = StandardScaler().fit(X[idx])
        xtr, xte = esc.transform(X[idx])[:cfg.SUB_SVR], esc.transform(X[te])
        return clone(svr).fit(xtr, alvo_tr[:cfg.SUB_SVR]).predict(xte)

    P = {k: np.full(len(y), np.nan) for k in
         ['E1 SVR (tendência da base, como na Tabela 3)', 'E2 tendência da base sozinha',
          'E2 referência: média + tendência (LOYO)', 'E2 referência: média + tendência (só passado)',
          'E3 SVR sobre o resíduo da referência (LOYO)', 'E4 SVR sobre o resíduo da referência (só passado)']}
    for ty in cfg.SAFRAS_TESTE:
        te = anos == ty
        # mesma subamostra de 01_treina_modelos.py e 04_avalia_ajustado.py
        idx = np.random.RandomState(1000 + ty).choice(np.where(anos != ty)[0],
                                                      min(cfg.SUB, int((anos != ty).sum())), replace=False)
        P['E1 SVR (tendência da base, como na Tabela 3)'][te] = ajusta_svr(idx, anom[idx], te) + tend[te]
        P['E2 tendência da base sozinha'][te] = tend[te]
        tr = anos != ty
        ref_te = ref_media_tendencia(y, anos, cod, tr, te)
        P['E2 referência: média + tendência (LOYO)'][te] = ref_te
        ref_idx = ref_media_tendencia(y, anos, cod, tr, np.isin(np.arange(len(y)), idx))
        # ref_media_tendencia devolve na ordem dos índices crescentes; reordena para idx
        ordem = np.argsort(np.argsort(idx))
        P['E3 SVR sobre o resíduo da referência (LOYO)'][te] = ref_te + ajusta_svr(
            idx, y[idx] - ref_idx[ordem], te)
        # janela crescente
        pas = anos < ty
        ref_te_p = ref_media_tendencia(y, anos, cod, pas, te)
        P['E2 referência: média + tendência (só passado)'][te] = ref_te_p
        idx_p = np.random.RandomState(2000 + ty).choice(np.where(pas)[0], min(cfg.SUB, int(pas.sum())),
                                                        replace=False)
        ref_idx_p = ref_media_tendencia(y, anos, cod, pas, np.isin(np.arange(len(y)), idx_p))
        ordem_p = np.argsort(np.argsort(idx_p))
        P['E4 SVR sobre o resíduo da referência (só passado)'][te] = ref_te_p + ajusta_svr(
            idx_p, y[idx_p] - ref_idx_p[ordem_p], te)
        print(f'safra {ty} feita', flush=True)

    m = np.isin(anos, cfg.SAFRAS_TESTE)
    obs = y[m]
    saida = {'safras_teste': cfg.SAFRAS_TESTE, 'registros_teste': int(m.sum()), 'modelos': {}}
    pares = {'E1 SVR (tendência da base, como na Tabela 3)': 'E2 referência: média + tendência (LOYO)',
             'E3 SVR sobre o resíduo da referência (LOYO)': 'E2 referência: média + tendência (LOYO)',
             'E4 SVR sobre o resíduo da referência (só passado)': 'E2 referência: média + tendência (só passado)'}
    for k, p in P.items():
        r = {'RMSE': round(float(np.sqrt(mean_squared_error(obs, p[m]))), 1),
             'R2': round(float(r2_score(obs, p[m])), 3)}
        if k in pares:
            r['comparado_a'] = pares[k]
            r.update(ganho_por_municipio(obs, p[m], P[pares[k]][m], cod[m]))
        saida['modelos'][k] = r
        print(f'{k:55s} {r}')
    with open(os.path.join(RAIZ, 'referencia_nacional.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
