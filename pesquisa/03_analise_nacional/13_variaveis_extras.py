# -*- coding: utf-8 -*-
"""
Variáveis que faltam à base nacional, no protocolo da Tabela 3.

Dois testes, com as coletas de pesquisa/10_trabalhos_futuros/coleta:

  solo   os sete atributos do SoilGrids de 0 a 30 cm, ponderados pela fração
         de soja (argila, areia, silte, carbono orgânico, pH, CTC, densidade).
         A base de von Bloh et al. (2023) não traz solo nenhum, e aqui, ao
         contrário do Pará, o modelo não vê a média do município: o alvo é a
         anomalia sobre a tendência, e o solo pode explicar por que um
         município reage mais que outro ao mesmo clima.
  fases  umidade do solo (0-7 e 7-28 cm), déficit de pressão de vapor e
         temperatura da superfície, mês a mês de setembro a março. No Pará
         essas famílias não superaram a referência (08_previsao_futura/
         07_variaveis_por_fase.py); o teste aqui decide se o limite era o alvo
         do Pará ou a forma de medir o ambiente.

Mesmos modelos, hiperparâmetros, subamostras e validação leave-one-year-out
2016-2020 de 04_avalia_ajustado.py. Os dois braços (com e sem as variáveis
novas) rodam nos mesmos registros, os dos municípios que a coleta pareou ao
GAUL, e a diferença de RMSE leva intervalo de 95% por reamostragem de
municípios.

Uso:   python 13_variaveis_extras.py solo|fases
Saída: variaveis_extras_<teste>.json
"""
import importlib.util
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')
AQUI = os.path.dirname(os.path.abspath(__file__))
COLETAS = os.path.join(AQUI, '..', '10_trabalhos_futuros', 'dados')
spec = importlib.util.spec_from_file_location('aval', os.path.join(AQUI, '04_avalia_ajustado.py'))
aval = importlib.util.module_from_spec(spec); spec.loader.exec_module(aval)
SAFRAS, AJUSTADOS, PRECISA_ESCALA = aval.SAFRAS_TESTE, aval.AJUSTADOS, aval.PRECISA_ESCALA
SUB, SUB_SVR = aval.SUB, aval.SUB_SVR
SOLO = ['argila_pct', 'areia_pct', 'silte_pct', 'carbono_org_g_kg', 'ph_agua', 'ctc_cmol_kg', 'densidade_g_cm3']
B = 1000


def extras(teste):
    """Tabela (CODE, HARVESTED) ou (CODE) -> colunas novas."""
    if teste == 'solo':
        s = pd.read_csv(os.path.join(COLETAS, 'solo_nacional.csv'))
        return s.rename(columns={'id': 'CODE'})[['CODE'] + SOLO], ['CODE'], SOLO
    f = pd.read_csv(os.path.join(COLETAS, 'fases_nacional_mensal.csv'))
    vars_ = [c for c in f.columns if c not in ('id', 'ano', 'mes')]
    w = f.pivot_table(index=['id', 'ano'], columns='mes', values=vars_)
    w.columns = [f'{v}_m{m:02d}' for v, m in w.columns]
    w = w.reset_index().rename(columns={'id': 'CODE', 'ano': 'HARVESTED'})
    return w, ['CODE', 'HARVESTED'], [c for c in w.columns if c not in ('CODE', 'HARVESTED')]


def main(teste):
    df = pd.read_csv(os.path.join(AQUI, 'data', 'data_cast.csv'))
    fora = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
    base_feat = [c for c in df.columns if c not in fora and df[c].dtype != 'object']
    novos, chaves, cols = extras(teste)
    total = len(df)
    df = df.merge(novos, on=chaves, how='inner').reset_index(drop=True)
    df = df[df[cols].notna().mean(axis=1) >= 0.5].reset_index(drop=True)
    print(f'{teste}: {len(cols)} variáveis novas; {len(df)} de {total} registros, '
          f'{df.CODE.nunique()} municípios', flush=True)
    Y = df['YIELD'].values.astype(float)
    TREND = df['YIELD_TREND'].values.astype(float)
    ANOM = df['YIELD_TREND_CORRECTED'].values.astype(float)
    anos, muni = df['HARVESTED'].values, df['CODE'].values
    sub = {ty: np.random.RandomState(1000 + ty).choice(
        np.where(anos != ty)[0], min(SUB, int((anos != ty).sum())), replace=False) for ty in SAFRAS}
    teste_idx = np.concatenate([np.where(anos == ty)[0] for ty in SAFRAS])
    obs = Y[teste_idx]
    grupos = pd.Series(np.arange(len(teste_idx))).groupby(muni[teste_idx]).apply(list).tolist()

    saida = {'teste': teste, 'variaveis_novas': cols, 'registros': int(len(df)), 'registros_base': total,
             'municipios': int(df.CODE.nunique()),
             'nota': ('Protocolo de 04_avalia_ajustado.py (subamostra de 7.000, 5.000 no SVR; LOYO 2016-2020), '
                      'com e sem as variáveis novas, nos mesmos registros. IC95 da diferença de RMSE '
                      '(com − sem) por reamostragem de municípios: negativo é melhora.'),
             'modelos': {}}
    for nome, modelo in AJUSTADOS.items():
        prev, seg = {}, {}
        for braco, feat in (('sem', base_feat), ('com', base_feat + cols)):
            t0 = time.time()
            X = df[feat].fillna(df[feat].median()).values
            p = np.full(len(df), np.nan)
            for ty in SAFRAS:
                te = anos == ty
                Xtr, Xte, atr = X[sub[ty]], X[te], ANOM[sub[ty]]
                if nome in PRECISA_ESCALA:
                    esc = StandardScaler().fit(Xtr)
                    Xtr, Xte = esc.transform(Xtr), esc.transform(Xte)
                    if nome == 'SVR':
                        Xtr, atr = Xtr[:SUB_SVR], atr[:SUB_SVR]
                p[te] = clone(modelo).fit(Xtr, atr).predict(Xte) + TREND[te]
            prev[braco], seg[braco] = p[teste_idx], round(time.time() - t0)
        res = {b: {'RMSE_pool': round(float(np.sqrt(mean_squared_error(obs, q))), 1),
                   'MAE_pool': round(float(mean_absolute_error(obs, q)), 1),
                   'R2_pool': round(float(r2_score(obs, q)), 3), 'segundos': seg[b]} for b, q in prev.items()}
        e_c, e_s = (prev['com'] - obs) ** 2, (prev['sem'] - obs) ** 2
        rng = np.random.RandomState(7)
        difs = []
        for _ in range(B):
            sel = np.concatenate([grupos[i] for i in rng.randint(0, len(grupos), len(grupos))])
            difs.append(np.sqrt(e_c[sel].mean()) - np.sqrt(e_s[sel].mean()))
        res['dif_rmse_com_menos_sem'] = round(float(np.sqrt(e_c.mean()) - np.sqrt(e_s.mean())), 1)
        res['ic95'] = [round(float(np.percentile(difs, 2.5)), 1), round(float(np.percentile(difs, 97.5)), 1)]
        saida['modelos'][nome] = res
        print(f'>>> {nome}: {res}', flush=True)
    with open(os.path.join(AQUI, f'variaveis_extras_{teste}.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'solo')
