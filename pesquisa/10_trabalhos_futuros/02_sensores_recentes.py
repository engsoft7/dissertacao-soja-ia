# -*- coding: utf-8 -*-
"""
Sensores lançados depois de 2014 no protocolo da Tabela 6, só nas safras recentes.

Item 3 de 08_previsao_futura/TRABALHOS_FUTUROS.md. Os dados vêm de
coleta/coleta_recentes.py, por município e safra, sob a máscara de soja:

  radar e umidade  Sentinel-1 (VV e VH, janeiro a março) e SMAP L4 (umidade da
                   zona radicular, novembro a março e fevereiro a março);
                   safras de 2016 em diante
  óptico novo      Sentinel-2 (NDVI e NDRE, a borda do vermelho, na mediana de
                   janeiro a março); safras de 2018 em diante

Como só existem nas safras recentes, a base é a do produto
(pesquisa/dados/soja_para_painel.csv, que vai até 2025) recortada a partir do
primeiro ano de cada família, e os dois braços, com e sem a família, rodam nos
mesmos registros: os que têm a família completa. O protocolo é o da Tabela 6
sem mudança (leave-one-year-out com busca aninhada, resíduo sobre a média do
município mais a tendência), e o critério, o ganho sobre o modelo de
referência com IC95 por reamostragem de safras. Com 8 a 10 safras, o
intervalo é largo: o teste só detecta ganho grande.

Uso:   python 02_sensores_recentes.py
Saída: sensores_recentes.json
"""
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
PESQUISA = os.path.abspath(os.path.join(AQUI, '..'))
PARA = os.path.join(PESQUISA, '04_analise_para')
sys.path.insert(0, os.path.join(PESQUISA, '08_previsao_futura'))
from comum import ganho_sobre_referencia  # noqa: E402

ORCAMENTO = {'Random Forest': 9, 'XGBoost': 15, 'SVR': 15, 'MLP': 15}
FAMILIAS = {
    'radar_e_umidade': (2016, ['s1_vv_db', 's1_vh_db', 'smap_raiz_nov_mar', 'smap_raiz_fev_mar']),
    'optico_sentinel2': (2018, ['ndvi_s2', 'ndre']),
}


def busca():
    spec = importlib.util.spec_from_file_location('busca', os.path.join(PARA, '03_busca_hiperparametros.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def avalia(m, df):
    y, anos, mun, _, safras = m._matrizes(df)
    ref = {ty: m.referencia(y, anos, mun, anos != ty, anos == ty) for ty in safras}
    obs = np.concatenate([y[anos == ty] for ty in safras])
    pref = np.concatenate([ref[ty] for ty in safras])
    aa = np.concatenate([anos[anos == ty] for ty in safras])
    preve_original, externas = m.preve, {}

    def preve_e_guarda(nome, cfg, X, y_, anos_, mun_, tr, te):
        p = preve_original(nome, cfg, X, y_, anos_, mun_, tr, te)
        if np.array_equal(tr, ~te):          # avaliação externa: treino = todas as outras safras
            externas[int(anos_[te][0])] = p
        return p

    m.preve = preve_e_guarda
    saida = {}
    for nome, n in ORCAMENTO.items():
        externas.clear()
        r = m.avalia_modelo(nome, n, df)
        prev = np.concatenate([externas[ty] for ty in safras])
        g = ganho_sobre_referencia(obs, prev, pref, aa)
        saida[nome] = {**{k: r[k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%')},
                       'ganho_sobre_referencia': g['ganho'], 'IC95': g['IC95'], 'p_unilateral': g['p_unilateral']}
        print(f'    {nome}: {saida[nome]}', flush=True)
    m.preve = preve_original
    return saida, m.avalia_baseline(df), [int(a) for a in safras]


def main():
    m = busca()
    base = pd.read_csv(os.path.join(PESQUISA, 'dados', 'soja_para_painel.csv'))
    base['balanco_hidrico'] = base.precip_total - base.etp_total
    base['log_area'] = np.log1p(base.soy_area_ha)
    sens = pd.read_csv(os.path.join(AQUI, 'dados', 'sensores_recentes_para.csv'))
    df0 = base.merge(sens.drop(columns=['municipio_gaul', 'mascara_mapbiomas'], errors='ignore'),
                     on=['cod_ibge7', 'ano'], how='left')
    originais = list(m.FEATURES)
    saida = {'nota': ('Protocolo da Tabela 6 nas safras recentes da base do produto, com e sem cada família de '
                      'sensores, nos mesmos registros. Ganho = 1 - MSE(modelo)/MSE(referência), IC95 por '
                      'reamostragem de safras.'), 'familias': {}}
    for familia, (desde, cols) in FAMILIAS.items():
        df = (df0[df0.ano >= desde].dropna(subset=originais + cols + ['rendimento_kg_ha'])
              .sort_values(['municipio', 'ano']).reset_index(drop=True))
        print(f'{familia}: {len(df)} registros, {df.municipio.nunique()} municípios, '
              f'safras {df.ano.min()}-{df.ano.max()}', flush=True)
        res = {'variaveis': cols, 'registros': int(len(df)), 'municipios': int(df.municipio.nunique())}
        m.FEATURES = originais
        print('  sem a família:', flush=True)
        res['sem'], res['referencia'], res['safras_avaliadas'] = avalia(m, df)
        m.FEATURES = originais + cols
        print('  com a família:', flush=True)
        res['com'], _, _ = avalia(m, df)
        m.FEATURES = originais
        saida['familias'][familia] = res
    with open(os.path.join(AQUI, 'sensores_recentes.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False, default=float)


if __name__ == '__main__':
    main()
