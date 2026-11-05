# -*- coding: utf-8 -*-
"""
Variáveis por fase que faltam à base nacional, mês a mês, de setembro a março.

No Pará, as famílias de 08_previsao_futura/fases.py não superaram a
referência, e TRABALHOS_FUTUROS.md (item 3) deixou pendente o mesmo teste no
recorte nacional, que decide se o limite é o alvo do Pará ou a forma de medir
o ambiente. A base de von Bloh et al. (2023) já traz, mês a mês, chuva, dias
quentes, dias secos, SPI, STI, excedente e déficit hídrico; faltam as
famílias que no Pará vieram do ERA5-Land e do MODIS:

  umidade do solo nas camadas de 0-7 e 7-28 cm (ERA5-Land)
  déficit de pressão de vapor, pela temperatura e pelo ponto de orvalho
      (fórmula de Tetens; ERA5-Land, médias diárias)
  temperatura da superfície de dia (MODIS MOD11A2)

Médias mensais por município, nos meses da base nacional (setembro do ano
anterior a março do ano da safra), safras de 2001 a 2020, na média do
município (a base nacional também mede o clima no município inteiro).
Os municípios são pareados ao GAUL pelo nome e pelo estado, como em
coleta_solo.py.

Uso:   python coleta_fases_nacional.py     (rode antes 03_analise_nacional/00_baixa_dados.py)
Saída: ../dados/fases_nacional_mensal.csv
"""
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from coleta_solo import alvo
from comum_gee import DADOS, chave, conecta_gee, municipios_gaul, tenta

MESES = [9, 10, 11, 12, 1, 2, 3]


def main():
    ee = conecta_gee()
    procura = alvo('nacional')
    siglas = sorted({uf for uf, _ in procura})
    munis, _ = municipios_gaul(ee, siglas)
    props = munis.select(['ADM2_NAME', 'UF']).getInfo()['features']
    achados = {(p['properties']['UF'], chave(p['properties']['ADM2_NAME'])) for p in props}
    pares = {k: v for k, v in procura.items() if k in achados}
    print(f'{len(pares)} de {len(procura)} municípios pareados ao GAUL', flush=True)
    munis = munis.select(['ADM2_NAME', 'UF'])
    ERA5 = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
    LST = ee.ImageCollection('MODIS/061/MOD11A2').select('LST_Day_1km')

    def vpd(img):
        t = img.select('temperature_2m').subtract(273.15)
        td = img.select('dewpoint_temperature_2m').subtract(273.15)
        es = t.multiply(17.27).divide(t.add(237.3)).exp().multiply(0.6108)
        ea = td.multiply(17.27).divide(td.add(237.3)).exp().multiply(0.6108)
        return es.subtract(ea).rename('vpd_kpa')

    def mes(safra, m):
        a = safra - 1 if m >= 9 else safra
        ini = ee.Date.fromYMD(a, m, 1)
        fim = ini.advance(1, 'month')
        e = ERA5.filterDate(ini, fim)
        img = ee.Image.cat([
            e.select('volumetric_soil_water_layer_1').mean().rename('sw1'),
            e.select('volumetric_soil_water_layer_2').mean().rename('sw2'),
            e.map(vpd).mean(),
            LST.filterDate(ini, fim).mean().multiply(0.02).subtract(273.15).rename('lst_dia_c'),
        ])
        fc = img.reduceRegions(collection=munis, reducer=ee.Reducer.mean(), scale=5000, tileScale=4)
        linhas = []
        for f in fc.getInfo()['features']:
            p = f['properties']
            k = (p['UF'], chave(p['ADM2_NAME']))
            if k in pares:
                linhas.append({'id': pares[k]['id'], 'ano': safra, 'mes': m,
                               **{c: p.get(c) for c in ('sw1', 'sw2', 'vpd_kpa', 'lst_dia_c')}})
        return safra, m, linhas

    todas = []
    with ThreadPoolExecutor(6) as ex:
        futuros = [ex.submit(tenta, mes, s, m) for s in range(2001, 2021) for m in MESES]
        for f in as_completed(futuros):
            s, m, linhas = f.result()
            todas += linhas
            print(f'  safra {s}, mês {m}: {len(linhas)} municípios', flush=True)
    os.makedirs(DADOS, exist_ok=True)
    saida = os.path.join(DADOS, 'fases_nacional_mensal.csv')
    pd.DataFrame(todas).sort_values(['id', 'ano', 'mes']).to_csv(saida, index=False)
    print(f'{len(todas)} registros gravados em {saida}', flush=True)


if __name__ == '__main__':
    main()
