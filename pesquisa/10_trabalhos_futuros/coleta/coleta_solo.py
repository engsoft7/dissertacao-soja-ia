# -*- coding: utf-8 -*-
"""
Atributos de solo do SoilGrids 2.0 por município, sob a máscara de soja.

A dissertação registra como limitação a ausência de atributos de solo. O
SoilGrids (Poggio et al., 2021, SOIL 7:217-240; ISRIC, CC BY 4.0) está no
Earth Engine em resolução de 250 m. Aqui se tira, para cada município, a média
de 0 a 30 cm (camadas de 0-5, 5-15 e 15-30 cm, ponderadas pela espessura) de:

  argila, areia e silte (%), carbono orgânico (g/kg), pH em água,
  capacidade de troca de cátions (cmol(c)/kg) e densidade do solo (g/cm³)

sob a máscara de soja do MapBiomas mais recente (onde a soja está, e não no
município inteiro, que no Pará é quase todo floresta). Município sem pixel de
soja na máscara recebe a média do município inteiro, e a coluna `sob_soja`
diz qual foi o caso.

Dois recortes, os da dissertação:
  para      os 38 municípios da base do Pará (cod_ibge7 da base)
  nacional  os 1.243 municípios da base de von Bloh et al. (2023), pareados ao
            GAUL pelo nome e pelo estado (rode antes 03_analise_nacional/00_baixa_dados.py)

Solo é estático: uma linha por município, que se junta a todas as safras.

Uso:   python coleta_solo.py para|nacional
Saída: ../dados/solo_para.csv ou ../dados/solo_nacional.csv
"""
import os
import sys

import pandas as pd

from comum_gee import DADOS, REPO, chave, conecta_gee, mascara_soja, municipios_gaul, tenta

PROPRIEDADES = {   # nome no SoilGrids -> (coluna, divisor para a unidade convencional)
    'clay': ('argila_pct', 10), 'sand': ('areia_pct', 10), 'silt': ('silte_pct', 10),
    'soc': ('carbono_org_g_kg', 10), 'phh2o': ('ph_agua', 10), 'cec': ('ctc_cmol_kg', 10),
    'bdod': ('densidade_g_cm3', 100),
}
CAMADAS = [('0-5cm', 5), ('5-15cm', 10), ('15-30cm', 15)]


def alvo(recorte):
    if recorte == 'para':
        base = pd.read_csv(os.path.join(REPO, 'pesquisa', 'dados', 'soja_para_mascarado_2001_2024.csv'))
        m = base.groupby('municipio').cod_ibge7.first().reset_index()
        return {('PA', chave(n)): {'municipio': n, 'id': int(c)} for n, c in zip(m.municipio, m.cod_ibge7)}
    nac = pd.read_csv(os.path.join(REPO, 'pesquisa', '03_analise_nacional', 'data', 'data_cast.csv'),
                      usecols=['CODE', 'COUNTY', 'STATE']).drop_duplicates()
    sigla = {'GOIAS': 'GO', 'MINAS_GERAIS': 'MG', 'PARANA': 'PR', 'RIO_GRANDE_DO_SUL': 'RS',
             'MATO_GROSSO': 'MT', 'MATO_GROSSO_DO_SUL': 'MS', 'BAHIA': 'BA'}
    return {(sigla[s], chave(c)): {'municipio': c, 'id': code} for code, c, s in
            zip(nac.CODE, nac.COUNTY, nac.STATE)}


def main(recorte):
    ee = conecta_gee()
    procura = alvo(recorte)
    siglas = sorted({uf for uf, _ in procura})
    munis, _ = municipios_gaul(ee, siglas)
    props = munis.select(['ADM2_NAME', 'UF']).getInfo()['features']
    achados = {(p['properties']['UF'], chave(p['properties']['ADM2_NAME'])): p['properties']['ADM2_NAME']
               for p in props}
    pares = {k: v for k, v in procura.items() if k in achados}
    print(f'{len(pares)} de {len(procura)} municípios pareados ao GAUL; '
          f'sem par: {sorted(n["municipio"] for k, n in procura.items() if k not in achados)[:30]}', flush=True)

    soja, ano_mb = mascara_soja(ee, 2100)
    imgs = []
    for nome, (coluna, div) in PROPRIEDADES.items():
        img = ee.Image(f'projects/soilgrids-isric/{nome}_mean')
        soma = None
        for camada, esp in CAMADAS:
            b = img.select(f'{nome}_{camada}_mean').multiply(esp)
            soma = b if soma is None else soma.add(b)
        imgs.append(soma.divide(sum(e for _, e in CAMADAS) * div).rename(coluna))
    solo = ee.Image.cat(imgs)
    sel = munis.filter(ee.Filter.inList('ADM2_NAME', list({achados[k] for k in pares})))

    def reduz(img):
        fc = img.reduceRegions(collection=sel, reducer=ee.Reducer.mean(), scale=250, tileScale=8)
        return {(f['properties']['UF'], chave(f['properties']['ADM2_NAME'])): f['properties']
                for f in fc.getInfo()['features']}

    sob = tenta(reduz, solo.updateMask(soja))
    todo = tenta(reduz, solo)
    linhas = []
    for k, info in pares.items():
        p = sob.get(k, {})
        usa_mascara = p.get('argila_pct') is not None
        p = p if usa_mascara else todo.get(k, {})
        linhas.append({'id': info['id'], 'municipio': info['municipio'], 'uf': k[0], 'sob_soja': usa_mascara,
                       **{c: (round(p[c], 3) if p.get(c) is not None else None)
                          for c, _ in PROPRIEDADES.values()}})
    os.makedirs(DADOS, exist_ok=True)
    saida = os.path.join(DADOS, f'solo_{recorte}.csv')
    pd.DataFrame(linhas).to_csv(saida, index=False)
    print(f'{len(linhas)} municípios gravados em {saida} (máscara de soja do MapBiomas {ano_mb}); '
          f'{sum(r["sob_soja"] for r in linhas)} sob a máscara', flush=True)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'para')
