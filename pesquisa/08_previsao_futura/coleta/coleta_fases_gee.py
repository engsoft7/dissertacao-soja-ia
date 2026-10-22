# -*- coding: utf-8 -*-
"""
Séries diárias e de 8/16 dias para medir o ambiente por fase da soja.

Item 3 de TRABALHOS_FUTUROS.md. A base da dissertação resume a safra em totais
e médias de novembro a maio. Para medir o estresse na fase em que ele importa
(floração e enchimento de grãos), este script baixa as séries dentro da safra,
município a município, e deixa a definição das fases para a análise: assim a
mesma coleta serve a janelas fixas no calendário e a janelas ancoradas no pico
de verdor de cada município e safra.

Séries, de outubro do ano anterior a junho do ano de colheita, safras
2001-2025, nos municípios da base da dissertação:
  diária     CHIRPS (chuva) e ERA5-Land (temperaturas média, mínima e máxima,
             ponto de orvalho, umidade do solo em duas camadas, radiação,
             evapotranspiração potencial), média do município
  16 dias    MODIS MOD13Q1 (EVI, NDVI), sobre a máscara de soja do MapBiomas
  8 dias     MODIS MOD11A2 (temperatura da superfície de dia), idem

Clima na média do município e vegetação sob a máscara: é o mesmo critério da
base da dissertação (02_coleta_gee_com_mascara_mapbiomas.py). Safras sem
máscara publicada usam a mais recente, como na rotina do painel.

Requer GEE_SERVICE_ACCOUNT_JSON (e, opcional, GEE_PROJECT). Roda no Actions.

Uso:  python coleta_fases_gee.py [--anos 2001-2025]
Saída: ../dados/gee_clima_diario.csv.gz, ../dados/gee_vegetacao_16d.csv,
       ../dados/gee_lst_8d.csv, ../dados/gee_coleta.json
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(RAIZ, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'software', 'automacao_github'))
from coleta_gee_safra import COLL_ID, CLASSE_SOJA, chave, conecta_gee  # noqa: E402

SAIDA = os.path.join(RAIZ, '..', 'dados')
BASE = os.path.join(REPO, 'pesquisa', 'dados', 'soja_para_mascarado_2001_2024.csv')
ERA = ['temperature_2m', 'temperature_2m_min', 'temperature_2m_max', 'dewpoint_temperature_2m',
       'volumetric_soil_water_layer_1', 'volumetric_soil_water_layer_2',
       'surface_solar_radiation_downwards_sum', 'potential_evaporation_sum']
CURTO = {'precipitation': 'precip_mm', 'temperature_2m': 'tmean_k', 'temperature_2m_min': 'tmin_k',
         'temperature_2m_max': 'tmax_k', 'dewpoint_temperature_2m': 'tdew_k',
         'volumetric_soil_water_layer_1': 'sw1', 'volumetric_soil_water_layer_2': 'sw2',
         'surface_solar_radiation_downwards_sum': 'srad_j', 'potential_evaporation_sum': 'etp_m'}


def tenta(f, *a, tentativas=4):
    for i in range(tentativas):
        try:
            return f(*a)
        except Exception as e:  # o Earth Engine devolve erros transitórios variados
            if i == tentativas - 1:
                raise
            print(f'  {f.__name__}{a}: {type(e).__name__}: {str(e)[:150]}; nova tentativa', flush=True)
            time.sleep(20 * (i + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--anos', default='2001-2025')
    a0, a1 = map(int, ap.parse_args().anos.split('-'))
    ee = conecta_gee()

    base = pd.read_csv(BASE)
    cods = base.groupby('municipio').cod_ibge7.first()
    alvo = {chave(m): (m, int(c)) for m, c in cods.items()}
    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
    uf = [n for n in gaul.aggregate_array('ADM1_NAME').distinct().getInfo() if n.strip().lower() in ('pará', 'para')]
    para = gaul.filter(ee.Filter.eq('ADM1_NAME', uf[0]))
    nomes = para.aggregate_array('ADM2_NAME').getInfo()
    usados = [n for n in nomes if chave(n) in alvo]
    faltam = sorted(set(alvo) - {chave(n) for n in usados})
    print(f'{len(usados)} de {len(alvo)} municípios da base encontrados no GAUL; faltam: {faltam}', flush=True)
    munis = para.filter(ee.Filter.inList('ADM2_NAME', usados)).select(['ADM2_NAME'])
    cod_de = {n: alvo[chave(n)][1] for n in usados}

    CHIRPS = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY').select('precipitation')
    ERA5 = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR').select(ERA)
    MOD13 = ee.ImageCollection('MODIS/061/MOD13Q1').select(['EVI', 'NDVI'])
    MOD11 = ee.ImageCollection('MODIS/061/MOD11A2').select('LST_Day_1km')
    MB = (ee.ImageCollection('projects/mapbiomas-public/assets/brazil/lulc/v1')
          .filter(ee.Filter.eq('collection_id', COLL_ID)))
    anos_mb = sorted(MB.aggregate_array('year').distinct().getInfo())

    def mascara(ano):
        am = max(x for x in anos_mb if x <= ano)
        return MB.filter(ee.Filter.eq('year', am)).mosaic().select('classification').eq(CLASSE_SOJA), am

    def reduz(img, escala):
        # a consulta interativa tem limite de tempo; se estourar, reduz a resolução
        try:
            fc = img.reduceRegions(collection=munis, reducer=ee.Reducer.mean(), scale=escala, tileScale=4)
            return [f['properties'] for f in fc.getInfo()['features']]
        except ee.EEException as e:
            print(f'  escala {escala} m falhou ({str(e)[:80]}); repetindo em {2 * escala} m', flush=True)
            fc = img.reduceRegions(collection=munis, reducer=ee.Reducer.mean(), scale=2 * escala, tileScale=8)
            return [f['properties'] for f in fc.getInfo()['features']]

    def longo(props, campos):
        """Propriedades 'AAAAMMDD_banda' (ou 'AAAA_MM_DD_banda') viram linhas."""
        linhas = {}
        for p in props:
            n = p['ADM2_NAME']
            for k, v in p.items():
                if k == 'ADM2_NAME' or v is None:
                    continue
                d, _, banda = k.partition('_') if k[8:9] == '_' else (k[:10].replace('_', ''), None, k[11:])
                linhas.setdefault((n, d), {})[campos.get(banda, banda)] = v
        return [{'municipio_gaul': n, 'cod_ibge7': cod_de[n], 'data': f'{d[:4]}-{d[4:6]}-{d[6:8]}', **v}
                for (n, d), v in linhas.items()]

    def clima_mes(ano, mes):
        ini = ee.Date.fromYMD(ano, mes, 1)
        fim = ini.advance(1, 'month')
        img = CHIRPS.filterDate(ini, fim).toBands().addBands(ERA5.filterDate(ini, fim).toBands())
        return longo(reduz(img, 5000), CURTO)

    def vegetacao(safra):
        ini, fim = ee.Date.fromYMD(safra - 1, 10, 1), ee.Date.fromYMD(safra, 7, 1)
        soja, _ = mascara(safra)
        return longo(reduz(MOD13.filterDate(ini, fim).toBands().updateMask(soja), 250), {'EVI': 'evi', 'NDVI': 'ndvi'})

    def lst(safra):
        ini, fim = ee.Date.fromYMD(safra - 1, 10, 1), ee.Date.fromYMD(safra, 7, 1)
        soja, _ = mascara(safra)
        return longo(reduz(MOD11.filterDate(ini, fim).toBands().updateMask(soja), 1000), {'LST_Day_1km': 'lst_dia'})

    tarefas = []
    for s in range(a0, a1 + 1):
        tarefas += [('clima', clima_mes, (s - 1, m)) for m in (10, 11, 12)]
        tarefas += [('clima', clima_mes, (s, m)) for m in range(1, 7)]
        tarefas += [('veg', vegetacao, (s,)), ('lst', lst, (s,))]
    res, erros = {'clima': [], 'veg': [], 'lst': []}, []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        fut = {ex.submit(tenta, f, *arg): (tipo, arg) for tipo, f, arg in tarefas}
        for i, ft in enumerate(as_completed(fut), 1):
            tipo, arg = fut[ft]
            try:
                res[tipo] += ft.result()
            except Exception as e:
                erros.append(f'{tipo}{arg}: {type(e).__name__}: {str(e)[:200]}')
                print('ERRO', erros[-1], flush=True)
            if i % 20 == 0:
                print(f'{i}/{len(tarefas)} tarefas, {time.time() - t0:.0f} s', flush=True)

    os.makedirs(SAIDA, exist_ok=True)
    ordem = ['cod_ibge7', 'data']
    clima = pd.DataFrame(res['clima']).sort_values(ordem)
    clima.round(5).to_csv(os.path.join(SAIDA, 'gee_clima_diario.csv.gz'), index=False, compression='gzip')
    pd.DataFrame(res['veg']).sort_values(ordem).round(1).to_csv(os.path.join(SAIDA, 'gee_vegetacao_16d.csv'), index=False)
    pd.DataFrame(res['lst']).sort_values(ordem).round(2).to_csv(os.path.join(SAIDA, 'gee_lst_8d.csv'), index=False)
    meta = {'coletado_em': date.today().isoformat(), 'safras': [a0, a1], 'municipios': len(usados),
            'municipios_sem_par_no_gaul': faltam, 'mapbiomas': {'colecao': COLL_ID, 'anos': [anos_mb[0], anos_mb[-1]]},
            'escalas_m': {'clima': 5000, 'vegetacao': 250, 'lst': 1000},
            'unidades': {'precip_mm': 'mm/dia', '*_k': 'K', 'sw1/sw2': 'm3/m3 (0-7 e 7-28 cm)',
                         'srad_j': 'J/m2/dia', 'etp_m': 'm/dia (negativo = evaporação)',
                         'evi/ndvi': 'x10000', 'lst_dia': 'K x 50 (fator 0,02)'},
            'linhas': {k: len(v) for k, v in res.items()}, 'erros': erros}
    with open(os.path.join(SAIDA, 'gee_coleta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(json.dumps(meta['linhas']), f'{len(erros)} erros', flush=True)
    return 1 if erros else 0


if __name__ == '__main__':
    sys.exit(main())
