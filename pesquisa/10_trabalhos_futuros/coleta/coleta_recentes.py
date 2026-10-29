# -*- coding: utf-8 -*-
"""
Sensores lançados depois de 2014, nos municípios da base do Pará.

Item 3 de 08_previsao_futura/TRABALHOS_FUTUROS.md: umidade do solo e índices
mais sensíveis ao enchimento de grãos, e radar, que atravessa as nuvens que
cobrem a Amazônia no ciclo. Como só existem nas safras recentes, a análise usa
um desenho próprio (10_trabalhos_futuros/02_sensores_recentes.py).

Por município e safra, sob a máscara de soja do MapBiomas do ano:
  Sentinel-2 (SR harmonizado, nuvem retirada pela classificação de cena):
      NDVI e NDRE (borda do vermelho, B8 e B5) na mediana de janeiro a março,
      o período de enchimento de grãos da soja paraense; safras de 2018 em diante
  Sentinel-1 (GRD, modo IW): retroespalhamento VV e VH, em dB, na média de
      janeiro a março; safras de 2016 em diante
  SMAP L4 (umidade do solo na zona radicular, sm_rootzone): médias de novembro
      a março e de fevereiro e março; safras de 2016 em diante

A fluorescência induzida pelo sol (TROPOMI) não está no catálogo do Earth
Engine, e fica de fora.

Uso:   python coleta_recentes.py
Saída: ../dados/sensores_recentes_para.csv
"""
import os

import pandas as pd

from comum_gee import DADOS, REPO, chave, conecta_gee, mascara_soja, municipios_gaul, reduz_em_lotes

SAFRAS = range(2016, 2026)


def main():
    ee = conecta_gee()
    base = pd.read_csv(os.path.join(REPO, 'pesquisa', 'dados', 'soja_para_mascarado_2001_2024.csv'))
    cods = base.groupby('municipio').cod_ibge7.first()
    alvo = {chave(m): int(c) for m, c in cods.items()}
    munis, _ = municipios_gaul(ee, ['PA'])
    nomes = munis.aggregate_array('ADM2_NAME').getInfo()
    usados = [n for n in nomes if chave(n) in alvo]
    munis = munis.filter(ee.Filter.inList('ADM2_NAME', usados)).select(['ADM2_NAME'])
    print(f'{len(usados)} de {len(alvo)} municípios da base no GAUL', flush=True)

    S2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    S1 = (ee.ImageCollection('COPERNICUS/S1_GRD').filter(ee.Filter.eq('instrumentMode', 'IW'))
          .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')))
    SMAP = ee.ImageCollection('NASA/SMAP/SPL4SMGP/008').select('sm_rootzone')

    def s2_limpa(img):
        scl = img.select('SCL')
        ok = scl.eq(4).Or(scl.eq(5))          # vegetação e solo exposto; fora nuvem, sombra e água
        ndvi = img.normalizedDifference(['B8', 'B4']).rename('ndvi_s2')
        ndre = img.normalizedDifference(['B8', 'B5']).rename('ndre')
        return ndvi.addBands(ndre).updateMask(ok)

    linhas = []
    for t in SAFRAS:
        soja, am = mascara_soja(ee, t)
        jan, abr = ee.Date.fromYMD(t, 1, 1), ee.Date.fromYMD(t, 4, 1)
        nov, fev = ee.Date.fromYMD(t - 1, 11, 1), ee.Date.fromYMD(t, 2, 1)
        # Um sensor por vez e em lotes de municípios: tudo junto, a 100 m, estourava o
        # tempo de computação do Earth Engine já na primeira safra. O SMAP vai na
        # escala dele (9 km), sem a máscara, que a 9 km não teria sentido.
        reducoes = [
            (S1.filterDate(jan, abr).select(['VV', 'VH']).mean().rename(['s1_vv_db', 's1_vh_db'])
             .updateMask(soja), 100),
            (SMAP.filterDate(nov, abr).mean().rename('smap_raiz_nov_mar')
             .addBands(SMAP.filterDate(fev, abr).mean().rename('smap_raiz_fev_mar')), 9000),
        ]
        if t >= 2018:
            reducoes.append((S2.filterDate(jan, abr).filterBounds(munis.geometry()).map(s2_limpa).median()
                             .updateMask(soja), 100))
        por_mun = {}
        for img, escala in reducoes:
            for f in reduz_em_lotes(ee, img, munis, ee.Reducer.mean(), escala, tamanho=8):
                por_mun.setdefault(f['properties']['ADM2_NAME'], {}).update(f['properties'])
        for nome, p in por_mun.items():
            linhas.append({'cod_ibge7': alvo[chave(nome)], 'municipio_gaul': nome,
                           'ano': t, 'mascara_mapbiomas': am,
                           **{k: p.get(k) for k in ('ndvi_s2', 'ndre', 's1_vv_db', 's1_vh_db',
                                                     'smap_raiz_nov_mar', 'smap_raiz_fev_mar')}})
        print(f'  safra {t}: {len(usados)} municípios (máscara {am})', flush=True)
    os.makedirs(DADOS, exist_ok=True)
    saida = os.path.join(DADOS, 'sensores_recentes_para.csv')
    pd.DataFrame(linhas).to_csv(saida, index=False)
    print(f'{len(linhas)} registros gravados em {saida}', flush=True)


if __name__ == '__main__':
    main()
