# -*- coding: utf-8 -*-
"""
El Niño, La Niña e a soja no Pará: chuva, vigor e produtividade por safra.

A dissertação não mede o efeito do ENSO no Pará: no recorte nacional o ONI é
uma das 121 variáveis, e no Pará ele só aparece no painel, como rótulo da
safra. Este script faz o teste exploratório que faltava, sobre a base da
dissertação (415 registros, 2001-2024).

O ONI de cada safra é a média de dezembro-fevereiro e janeiro-março do ano de
colheita, o miolo do ciclo no Pará. Para cada registro calcula-se a anomalia em
relação à média do município e a uma tendência comum, para a produtividade, a
chuva e o EVI máximo. O teste é feito por safra (média das anomalias do ano),
porque o ONI é o mesmo para todos os municípios de uma safra: tratar os 415
registros como independentes inflaria a significância.

Hipóteses (bilaterais, Spearman, n = 24 safras):
  H1: o ONI se associa à chuva da safra no Pará;
  H2: o ONI se associa à produtividade da safra;
  H3: H2 se mantém sem os registros repetidos da PAM.
Não há correção para testes múltiplos; o resultado é exploratório e serve para
formular hipóteses, não para confirmá-las. O efeito preditivo do ONI é testado
em 02_previsao_rendimento_para.py.

Uso:  python 01_enso_para.py
Saída: enso_para.json
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

from comum import ALVO, RAIZ, carrega_base_para, oni

ONI_DJF, _ = oni()


def anomalia(df, col):
    """Desvio em relação à média do município e a uma tendência comum."""
    r = df[col] - df.groupby('municipio')[col].transform('mean')
    b = np.polyfit(df.ano, r, 1)
    return r - np.polyval(b, df.ano)


def main():
    df = carrega_base_para()
    df['oni'] = df.ano.map(ONI_DJF)
    df['fase'] = np.where(df.oni >= 0.5, 'El Niño', np.where(df.oni <= -0.5, 'La Niña', 'Neutro'))
    for c, nome in [(ALVO, 'a_rend'), ('precip_total', 'a_chuva'), ('EVI_max', 'a_evi')]:
        df[nome] = anomalia(df, c)
    df['repetido'] = df.groupby('municipio')[ALVO].diff().eq(0)

    por_safra = df.groupby('ano').agg(oni=('oni', 'first'), a_rend=('a_rend', 'mean'),
                                      a_chuva=('a_chuva', 'mean'), a_evi=('a_evi', 'mean'),
                                      n=('a_rend', 'size'))
    sem_rep = df[~df.repetido].groupby('ano').agg(oni=('oni', 'first'), a_rend=('a_rend', 'mean'))

    def sp(x, y):
        r, p = stats.spearmanr(x, y)
        return {'rho': round(float(r), 3), 'p': round(float(p), 4), 'n_safras': int(len(x))}

    rng = np.random.default_rng(42)
    fases = {}
    for f, g in df.groupby('fase'):
        anos = g.ano.unique()
        medias = g.groupby('ano')[['a_rend', 'a_chuva']].mean()
        boot = [medias.loc[rng.choice(anos, len(anos))].a_rend.mean() for _ in range(2000)]
        fases[f] = {'safras': [int(a) for a in sorted(anos)], 'registros': int(len(g)),
                    'anomalia_rendimento_kg_ha': round(float(g.a_rend.mean()), 1),
                    'IC95_por_safras': [round(float(v), 1) for v in np.percentile(boot, [2.5, 97.5])],
                    'anomalia_chuva_mm': round(float(g.a_chuva.mean()), 1)}

    saida = {
        'oni': 'média de DJF e JFM do ano de colheita (NOAA CPC); El Niño >= 0,5, La Niña <= -0,5',
        'H1_oni_x_chuva': sp(por_safra.oni, por_safra.a_chuva),
        'H2_oni_x_rendimento': sp(por_safra.oni, por_safra.a_rend),
        'H3_oni_x_rendimento_sem_repetidos': sp(sem_rep.oni, sem_rep.a_rend),
        'oni_x_evi_max': sp(por_safra.oni, por_safra.a_evi),
        'chuva_x_rendimento_por_registro': {k: v for k, v in sp(df.a_chuva, df.a_rend).items()
                                            if k != 'n_safras'} | {'n_registros': int(len(df))},
        'por_fase': fases,
        'ressalvas': ['24 safras, com 5 a 36 municípios por safra; sem correção para testes múltiplos',
                      'anomalias calculadas sobre a série inteira (descritivo, não preditivo)',
                      'o alvo repete o valor anterior em 40,1% dos pares de safras sucessivas'],
    }
    with open(os.path.join(RAIZ, 'enso_para.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    print(json.dumps(saida, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
