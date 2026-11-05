# -*- coding: utf-8 -*-
"""
Atributos de solo como variáveis no protocolo da Tabela 6 (Pará).

A dissertação registra como limitação a ausência de solo. Aqui se repete a
avaliação da Tabela 6 (base completa do Pará, leave-one-year-out com busca
aninhada, mesmos orçamentos e semente) acrescentando às onze variáveis
ambientais os sete atributos do SoilGrids de 0 a 30 cm, ponderados pela fração
de soja de cada pixel (coleta/coleta_solo.py): argila, areia, silte, carbono
orgânico, pH, CTC e densidade. As rotinas são as de
04_analise_para/03_busca_hiperparametros.py, importadas e não recopiadas; só a
lista de variáveis muda.

O que se espera, antes de rodar: pouco ou nada. Solo é fixo no município, e os
modelos da Tabela 6 ajustam o resíduo sobre a média do município, que já
absorve tudo o que é fixo nele. O solo só pode ajudar por interação (o mesmo
veranico pesa mais em solo arenoso), e isso com 38 municípios. O teste existe
para trocar a suposição por um número.

Critério: o ganho de cada modelo sobre o modelo de referência (que não usa
variáveis e não muda), com intervalo de 95% por reamostragem de safras, ao
lado do ganho com as onze variáveis da Tabela 6 apenas, na mesma conta.

Uso:   python 05_solo_na_tabela6.py
Saída: solo_na_tabela6.json
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
SOLO = ['argila_pct', 'areia_pct', 'silte_pct', 'carbono_org_g_kg', 'ph_agua', 'ctc_cmol_kg', 'densidade_g_cm3']


def busca():
    spec = importlib.util.spec_from_file_location('busca', os.path.join(PARA, '03_busca_hiperparametros.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.DADOS = os.path.join(PESQUISA, 'dados')
    return m


def avalia(m, df, ref, y, anos, safras):
    """Roda os quatro modelos e devolve métricas e ganho sobre a referência."""
    preve_original, externas = m.preve, {}

    def preve_e_guarda(nome, cfg, X, y_, anos_, mun_, tr, te):
        p = preve_original(nome, cfg, X, y_, anos_, mun_, tr, te)
        if np.array_equal(tr, ~te):          # avaliação externa: treino = todas as outras safras
            externas[int(anos_[te][0])] = p
        return p

    m.preve = preve_e_guarda
    saida = {}
    obs = np.concatenate([y[anos == ty] for ty in safras])
    pref = np.concatenate([ref[ty] for ty in safras])
    aa = np.concatenate([anos[anos == ty] for ty in safras])
    for nome, n in ORCAMENTO.items():
        externas.clear()
        r = m.avalia_modelo(nome, n, df)
        prev = np.concatenate([externas[ty] for ty in safras])
        g = ganho_sobre_referencia(obs, prev, pref, aa)
        saida[nome] = {**{k: r[k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%')},
                       'ganho_sobre_referencia': g['ganho'], 'IC95': g['IC95'], 'p_unilateral': g['p_unilateral']}
        print(f'  {nome}: {saida[nome]}', flush=True)
    m.preve = preve_original
    return saida


def main():
    m = busca()
    solo = pd.read_csv(os.path.join(AQUI, 'dados', 'solo_para.csv'))
    df = m.carrega()
    df = df.merge(solo[['id'] + SOLO].rename(columns={'id': 'cod_ibge7'}), on='cod_ibge7', how='left')
    assert df[SOLO].notna().all().all(), 'município da base sem solo'
    with open(os.path.join(PARA, 'resultados_busca_aninhada.json'), encoding='utf-8') as f:
        publicado = json.load(f)
    y, anos, mun, _, safras = m._matrizes(df)
    ref = {ty: m.referencia(y, anos, mun, anos != ty, anos == ty) for ty in safras}

    base = list(m.FEATURES)
    print('Sem solo (a Tabela 6 refeita, para a mesma conta de ganho):', flush=True)
    sem = avalia(m, df, ref, y, anos, safras)
    m.FEATURES = base + SOLO
    print('Com solo:', flush=True)
    com = avalia(m, df, ref, y, anos, safras)
    m.FEATURES = base

    saida = {
        'nota': ('Tabela 6 do Pará refeita com e sem os sete atributos do SoilGrids (0-30 cm, ponderados pela '
                 'fração de soja). Ganho = 1 - MSE(modelo)/MSE(referência), IC95 por reamostragem de safras.'),
        'variaveis_solo': SOLO,
        'registros': int(len(df)), 'municipios': int(df.municipio.nunique()),
        'sem_solo': sem, 'com_solo': com,
        'tabela_6_publicada': {k: {c: publicado[k][c] for c in ('RMSE', 'MAE', 'R2', 'rRMSE_%')}
                               for k in list(ORCAMENTO) + ['Baseline (sem clima)']},
    }
    with open(os.path.join(AQUI, 'solo_na_tabela6.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
