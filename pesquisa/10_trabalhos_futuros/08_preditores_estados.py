# -*- coding: utf-8 -*-
"""
Quais preditores acompanham o erro da referência, no Pará e nos estados vizinhos.

06_amazonia_legal.py mostrou que, em Mato Grosso e no Maranhão, os modelos da
Tabela 6 superam a referência (média do município mais a tendência), e no
Pará não. Este script pergunta por quê, variável por variável, nos mesmos
registros: para cada safra deixada de fora, o erro da referência ajustada nas
outras safras; para cada preditor, o quanto ele fugiu do normal do município
naquela safra (o valor menos a média do município). A correlação entre os
dois diz se o preditor carrega informação que a referência não tem.

O IC95 é por reamostragem de safras, como na Tabela 6: as safras são
reamostradas inteiras, porque os municípios de um mesmo ano não são
independentes (o clima de um ano é parecido no estado inteiro).

Uso:   python 08_preditores_estados.py
Saída: preditores_estados.json
"""
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

NOMES = {'NDVI_mean': 'NDVI médio', 'NDVI_max': 'NDVI máximo', 'EVI_mean': 'EVI médio',
         'EVI_max': 'EVI máximo', 'precip_total': 'chuva', 'etp_total': 'evapotranspiração',
         'balanco_hidrico': 'balanço hídrico', 'temp_mean': 'temperatura média',
         'temp_max': 'temperatura máxima', 'srad_mean': 'radiação solar', 'log_area': 'área (log)'}
REAMOSTRAGENS = 2000


def _carrega(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(AQUI, arquivo))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def erro_da_referencia(m, df):
    """Para cada registro, observado menos a referência ajustada sem a safra dele."""
    y, anos, mun, _, safras = m._matrizes(df)
    res = np.full(len(df), np.nan)
    for ty in safras:
        te = anos == ty
        res[te] = y[te] - m.referencia(y, anos, mun, anos != ty, te)
    return res


def correlacoes(df, res, variaveis, semente=42):
    ok = ~np.isnan(res)
    d = df[ok].reset_index(drop=True)
    r_res = res[ok]
    anos = d.ano.values
    unicos = np.unique(anos)
    por_ano = {a: np.where(anos == a)[0] for a in unicos}
    rng = np.random.default_rng(semente)
    sorteios = [np.concatenate([por_ano[a] for a in rng.choice(unicos, len(unicos))]) for _ in range(REAMOSTRAGENS)]
    saida = {}
    for v in variaveis:
        anom = (d[v] - d.groupby('municipio')[v].transform('mean')).values
        r = float(np.corrcoef(anom, r_res)[0, 1])
        bs = [np.corrcoef(anom[i], r_res[i])[0, 1] for i in sorteios]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        saida[NOMES.get(v, v)] = {'r': round(r, 3), 'IC95': [round(float(lo), 3), round(float(hi), 3)],
                                  'claro': bool(lo > 0 or hi < 0)}
    return dict(sorted(saida.items(), key=lambda kv: -abs(kv[1]['r'])))


def main():
    al = _carrega('amazonia_legal', '06_amazonia_legal.py')
    m = al.busca()
    bases = {'PA': m.carrega()}
    for uf in ('MT', 'MA'):
        bases[uf] = al.base_do_estado(uf, m)[0]
    saida = {'nota': ('Correlação entre o erro da referência da Tabela 6 (média do município mais a tendência, '
                      'ajustada sem a safra) e a anomalia de cada preditor (valor menos a média do município). '
                      f'IC95 por reamostragem de safras ({REAMOSTRAGENS}); "claro" quando o IC95 não inclui o zero. '
                      'Mesmos registros de 06_amazonia_legal.py.')}
    for uf, df in bases.items():
        res = erro_da_referencia(m, df)
        c = correlacoes(df, res, m.FEATURES)
        saida[uf] = {'registros': int(len(df)), 'municipios': int(df.municipio.nunique()),
                     'preditores_com_efeito_claro': sum(v['claro'] for v in c.values()),
                     'preditores': c}
        print(uf, len(df), '; '.join(f"{k} {v['r']:+.2f}{'*' if v['claro'] else ''}" for k, v in list(c.items())[:6]),
              flush=True)
    with open(os.path.join(AQUI, 'preditores_estados.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
