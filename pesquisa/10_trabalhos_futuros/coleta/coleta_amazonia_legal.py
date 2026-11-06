# -*- coding: utf-8 -*-
"""
Variáveis ambientais da base do Pará, medidas também em TO, MA, RO e MT.

A base paraense tem 415 registros, pouco para revelar ganhos pequenos, e a
dissertação aponta a extensão aos demais estados da Amazônia Legal. Aqui as
nove variáveis da base do Pará são medidas, do mesmo jeito, em todos os
municípios de Tocantins, Maranhão, Rondônia e Mato Grosso, safra a safra:

  NDVI e EVI médios e máximos (MODIS MOD13Q1) sob a máscara de soja do
  MapBiomas do ano; chuva total (CHIRPS); temperaturas média e máxima,
  radiação e evapotranspiração potencial (ERA5-Land); área de soja mapeada.
  Janela de 1º de novembro do ano anterior a 31 de maio do ano da safra.

É a mesma conta de software/automacao_github/coleta_gee_safra.py, que
reproduz a da base da dissertação; muda só o estado. A produtividade vem da
PAM, em 03_analise_nacional/pam_soja_municipios.csv, e é juntada na análise.

Uso:   python coleta_amazonia_legal.py TO [--anos 2001-2025] [--paralelo 4]
       (no Actions, "[coleta: amazonia_MT]" na mensagem do commit refaz um estado só;
       "[coleta: amazonia_MT_2008_2013]", só uma faixa de anos)
Saída: ../dados/amazonia_legal_<UF>.csv; com --anos, um arquivo por safra,
       ../dados/amazonia_legal_<UF>_<ano>.csv, gravado assim que a safra fecha.

Com faixa de anos, a coleta retoma de onde parou: pula as safras que já têm
arquivo (o de um ano ou o de uma faixa, como amazonia_legal_MT_2001_2007.csv).
Em 06/11/2026 o projeto passou a cota mensal do Earth Engine e entrou em modo
restrito, com menos chamadas simultâneas; um job de Mato Grosso coletou
safras de 2008 a 2016 e perdeu todas ao estourar o tempo, porque o arquivo só
era gravado no fim.
"""
import argparse
import glob
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from comum_gee import DADOS, conecta_gee, mascara_soja, municipios_gaul, reduz_em_lotes, tenta

BANDAS = ['NDVI_mean', 'NDVI_max', 'EVI_mean', 'EVI_max', 'precip_total', 'temp_mean', 'temp_max',
          'srad_mean', 'etp_total']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('uf')
    ap.add_argument('--anos', default='2001-2025')
    ap.add_argument('--paralelo', type=int, default=4, help='safras ao mesmo tempo')
    a = ap.parse_args()
    a0, a1 = map(int, a.anos.split('-'))
    por_safra = a.anos != '2001-2025'
    anos = list(range(a0, a1 + 1))
    if por_safra:
        feitos = safras_gravadas(a.uf)
        if feitos & set(anos):
            print(f'{a.uf}: safras já gravadas, puladas: {sorted(feitos & set(anos))}', flush=True)
        anos = [t for t in anos if t not in feitos]
        if not anos:
            return
    ee = conecta_gee()
    munis, _ = municipios_gaul(ee, [a.uf])
    munis = munis.select(['ADM2_NAME', 'UF'])
    print(f'{a.uf}: {munis.size().getInfo()} municípios no GAUL', flush=True)
    MODIS = ee.ImageCollection('MODIS/061/MOD13Q1')
    CHIRPS = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
    ERA5 = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')

    def ano(t):
        soja, am = mascara_soja(ee, t)
        ini, fim = ee.Date.fromYMD(t - 1, 11, 1), ee.Date.fromYMD(t, 5, 31)
        veg, e = MODIS.filterDate(ini, fim), ERA5.filterDate(ini, fim)
        bandas = ee.Image.cat([
            veg.select('NDVI').mean().multiply(0.0001).updateMask(soja).rename('NDVI_mean'),
            veg.select('NDVI').max().multiply(0.0001).updateMask(soja).rename('NDVI_max'),
            veg.select('EVI').mean().multiply(0.0001).updateMask(soja).rename('EVI_mean'),
            veg.select('EVI').max().multiply(0.0001).updateMask(soja).rename('EVI_max'),
            CHIRPS.filterDate(ini, fim).select('precipitation').sum().rename('precip_total'),
            e.select('temperature_2m').mean().subtract(273.15).rename('temp_mean'),
            e.select('temperature_2m_max').mean().subtract(273.15).rename('temp_max'),
            e.select('surface_solar_radiation_downwards_sum').mean().divide(1e6).rename('srad_mean'),
            e.select('potential_evaporation_sum').sum().multiply(-1000).rename('etp_total'),
        ])
        med = reduz_em_lotes(ee, bandas, munis, ee.Reducer.mean(), 250)
        area = soja.multiply(ee.Image.pixelArea()).divide(1e4).rename('soy_area_ha')
        ar = reduz_em_lotes(ee, area, munis, ee.Reducer.sum(), 30, tamanho=6)
        areas = {f['properties']['ADM2_NAME']: f['properties'].get('sum', 0) for f in ar}
        linhas = []
        for f in med:
            p = f['properties']
            if p.get('NDVI_mean') is None:      # município sem soja mapeada naquele ano
                continue
            linhas.append({'uf': a.uf, 'municipio_gaul': p['ADM2_NAME'], 'ano': t, 'mascara_mapbiomas': am,
                           'soy_area_ha': areas.get(p['ADM2_NAME'], 0), **{b: p.get(b) for b in BANDAS}})
        return t, linhas

    os.makedirs(DADOS, exist_ok=True)
    todas, falhas = [], []
    with ThreadPoolExecutor(a.paralelo) as ex:
        futuros = {ex.submit(tenta, ano, t): t for t in anos}
        for f in as_completed(futuros):
            try:
                t, linhas = f.result()
            except Exception as e:  # uma safra que não fecha não derruba as outras
                falhas.append(futuros[f])
                print(f'  {a.uf} {futuros[f]}: falhou ({type(e).__name__}: {str(e)[:150]})', flush=True)
                continue
            print(f'  {a.uf} {t}: {len(linhas)} municípios com soja mapeada', flush=True)
            if por_safra:
                # Grava já: se o job estourar o tempo, as safras prontas ficam.
                grava(linhas, os.path.join(DADOS, f'amazonia_legal_{a.uf}_{t}.csv'))
            todas += linhas
    if not por_safra:
        grava(todas, os.path.join(DADOS, f'amazonia_legal_{a.uf}.csv'))
    if falhas:
        raise SystemExit(f'{a.uf}: safras sem dado: {sorted(falhas)}')


COLUNAS = ['uf', 'municipio_gaul', 'ano', 'mascara_mapbiomas', 'soy_area_ha'] + BANDAS


def grava(linhas, saida):
    df = pd.DataFrame(linhas, columns=COLUNAS)
    df.sort_values(['municipio_gaul', 'ano']).to_csv(saida, index=False)
    print(f'{len(df)} registros gravados em {saida}', flush=True)


def safras_gravadas(uf):
    """Safras do estado que já têm arquivo, de uma safra ou de uma faixa."""
    feitas = set()
    for f in glob.glob(os.path.join(DADOS, f'amazonia_legal_{uf}_*.csv')):
        feitas |= set(pd.read_csv(f, usecols=['ano']).ano.astype(int))
        nome = os.path.basename(f)[len(f'amazonia_legal_{uf}_'):-4]
        if nome.isdigit():          # arquivo de uma safra: vale mesmo sem município com soja
            feitas.add(int(nome))
    return feitas


if __name__ == '__main__':
    main()
