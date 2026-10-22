# -*- coding: utf-8 -*-
"""
Funções compartilhadas pelos experimentos de previsão de safras futuras.

A avaliação da dissertação é leave-one-year-out: para prever 2016, o modelo
treina com 2001-2015 e também com 2017-2024. Isso mede o quanto as variáveis
explicam uma safra que ficou de fora, mas não é previsão, porque usa safras
posteriores à prevista. Aqui a janela é crescente (origem móvel): para prever
a safra T com antecedência de h safras, só entra o que se conhecia ao fim da
safra T-h. É o desenho de quem prevê de verdade.
"""
import json
import os

import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(RAIZ, '..', 'dados')
PAM_NACIONAL = os.path.join(RAIZ, '..', '03_analise_nacional', 'pam_soja_municipios.csv')

ALVO = 'rendimento_kg_ha'
AMBIENTAIS = ['NDVI_mean', 'NDVI_max', 'EVI_mean', 'EVI_max', 'precip_total', 'etp_total',
              'balanco_hidrico', 'temp_mean', 'temp_max', 'srad_mean', 'log_area']


def carrega_base_para():
    """Base da dissertação (415 registros, 38 municípios, variáveis ambientais)."""
    df = pd.read_csv(os.path.join(DADOS, 'soja_para_mascarado_2001_2024.csv'))
    df['balanco_hidrico'] = df.precip_total - df.etp_total
    df['log_area'] = np.log1p(df.soy_area_ha)
    df = df.dropna(subset=AMBIENTAIS + [ALVO])
    return df.sort_values(['municipio', 'ano']).reset_index(drop=True)


def carrega_pam_para():
    """Todos os municípios paraenses da PAM (rendimento e área plantada)."""
    pam = pd.read_csv(PAM_NACIONAL)
    pa = pam[pam.uf == 'PA'].rename(columns={'nome': 'municipio'})
    pa = pa.dropna(subset=[ALVO, 'area_plantada_ha'])
    pa = pa[(pa.area_plantada_ha > 0) & (pa[ALVO] > 0)]
    return pa.sort_values(['municipio', 'ano']).reset_index(drop=True)


def oni():
    """ONI por ano: média de DJF e JFM (o miolo do ciclo da soja no Pará) e o
    de SON, que já se conhece no plantio da safra seguinte."""
    with open(os.path.join(DADOS, 'eventos_enso.json'), encoding='utf-8') as f:
        hist = json.load(f)['historico_detalhado']
    djf = {int(a): float(np.mean([v['trimestres']['DJF'], v['trimestres']['JFM']])) for a, v in hist.items()}
    son = {int(a): float(v['trimestres']['SON']) for a, v in hist.items() if 'SON' in v['trimestres']}
    return djf, son


def referencia(treino, alvo_df):
    """Modelo de referência da dissertação: média do município + tendência comum,
    ajustadas só no treino. Município sem histórico recebe a média geral."""
    b = np.polyfit(treino.ano, treino[ALVO], 1)[0]
    am = treino.ano.mean()
    media = treino.groupby('municipio')[ALVO].mean()
    geral = treino[ALVO].mean()
    return alvo_df.municipio.map(media).fillna(geral).values + b * (alvo_df.ano.values - am)


def metricas(obs, prev):
    obs, prev = np.asarray(obs, float), np.asarray(prev, float)
    rmse = float(np.sqrt(np.mean((obs - prev) ** 2)))
    return {'RMSE': round(rmse, 1), 'MAE': round(float(np.mean(np.abs(obs - prev))), 1),
            'rRMSE_%': round(rmse / obs.mean() * 100, 1), 'n': int(len(obs))}


def ganho_sobre_referencia(obs, prev, ref, anos, n_boot=2000, semente=42):
    """Ganho de habilidade 1 - MSE(modelo)/MSE(referência), com intervalo de 95%
    por reamostragem de safras inteiras (as safras não são independentes entre
    municípios: um ano ruim é ruim para todos)."""
    obs, prev, ref, anos = map(np.asarray, (obs, prev, ref, anos))
    e_m, e_r = (obs - prev) ** 2, (obs - ref) ** 2
    safras = np.unique(anos)
    por = {a: (e_m[anos == a].sum(), e_r[anos == a].sum()) for a in safras}
    rng = np.random.default_rng(semente)
    boot = []
    for _ in range(n_boot):
        s = rng.choice(safras, len(safras), replace=True)
        m = sum(por[a][0] for a in s)
        r = sum(por[a][1] for a in s)
        boot.append(1 - m / r if r > 0 else np.nan)
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    return {'ganho': round(float(1 - e_m.sum() / e_r.sum()), 3),
            'IC95': [round(float(lo), 3), round(float(hi), 3)]}
