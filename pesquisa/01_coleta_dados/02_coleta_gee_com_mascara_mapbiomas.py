# -*- coding: utf-8 -*-
"""
Coleta de preditores para os municipios produtores de soja do Para,
COM mascara de soja do MapBiomas (Colecao 10.1, classe 39).

Esta e a versao utilizada nos resultados da Secao 6 da dissertacao.
Executar no Google Colab (requer conta Google para o Earth Engine).

Saida: dados_soja_para_mascarado.csv
"""

# !pip install earthengine-api sidrapy pandas -q

import ee, pandas as pd, sidrapy, time, unicodedata, re

PROJETO_GEE = "SEU-PROJETO-EARTH-ENGINE"   # ex.: "ee-usuario"
ANO_INI, ANO_FIM = 2001, 2024

# Janela do ciclo da soja no Para: plantio ~nov (ano-1), colheita ~mai (ano)
MES_INI, DIA_INI = 11, 1
MES_FIM, DIA_FIM = 5, 31

COLL_ID = 10.1        # Colecao MapBiomas
CLASSE_SOJA = 39      # codigo da classe "Soja" no MapBiomas

ee.Authenticate()
ee.Initialize(project=PROJETO_GEE)

# ------------------------------------------------------------------ limites
gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
brasil = gaul.filter(ee.Filter.eq("ADM0_NAME", "Brazil"))
nomes = brasil.aggregate_array("ADM1_NAME").distinct().getInfo()
alvo = [n for n in nomes if n.strip().lower() in ("pará", "para")]   # GAUL grava sem acento
assert alvo, f"Para nao encontrado: {sorted(nomes)}"
para = brasil.filter(ee.Filter.eq("ADM1_NAME", alvo[0]))
print("Municipios do Para:", para.size().getInfo())

MODIS  = ee.ImageCollection("MODIS/061/MOD13Q1")            # NDVI, EVI  (250 m)
CHIRPS = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")        # precipitacao (5 km)
ERA5   = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")   # clima (9 km)
MB     = (ee.ImageCollection("projects/mapbiomas-public/assets/brazil/lulc/v1")
            .filter(ee.Filter.eq("collection_id", COLL_ID)))

BANDAS = ["NDVI_mean","NDVI_max","EVI_mean","EVI_max","precip_total",
          "temp_mean","temp_max","srad_mean","etp_total"]


def coleta_ano(ano):
    ini = ee.Date.fromYMD(ano-1, MES_INI, DIA_INI)
    fim = ee.Date.fromYMD(ano,   MES_FIM, DIA_FIM)

    col = MB.filter(ee.Filter.eq("year", ano))
    assert col.size().getInfo() > 0, f"MapBiomas sem imagem para {ano}"
    soja = col.mosaic().select("classification").eq(CLASSE_SOJA)   # mascara binaria

    veg = MODIS.filterDate(ini, fim)
    e   = ERA5.filterDate(ini, fim)

    # indices de vegetacao: restritos aos pixels de soja
    # clima: media do municipio (grade grossa; mascarar nao muda o valor)
    bandas = ee.Image.cat([
        veg.select("NDVI").mean().multiply(0.0001).updateMask(soja).rename("NDVI_mean"),
        veg.select("NDVI").max().multiply(0.0001).updateMask(soja).rename("NDVI_max"),
        veg.select("EVI").mean().multiply(0.0001).updateMask(soja).rename("EVI_mean"),
        veg.select("EVI").max().multiply(0.0001).updateMask(soja).rename("EVI_max"),
        CHIRPS.filterDate(ini, fim).select("precipitation").sum().rename("precip_total"),
        e.select("temperature_2m").mean().subtract(273.15).rename("temp_mean"),
        e.select("temperature_2m_max").mean().subtract(273.15).rename("temp_max"),
        e.select("surface_solar_radiation_downwards_sum").mean().divide(1e6).rename("srad_mean"),
        e.select("potential_evaporation_sum").sum().multiply(-1000).rename("etp_total"),
    ])
    med = bandas.reduceRegions(collection=para, reducer=ee.Reducer.mean(), scale=250)

    # area plantada de soja (ha), derivada da propria mascara
    area = soja.multiply(ee.Image.pixelArea()).divide(1e4).rename("soy_area_ha")
    ar   = area.reduceRegions(collection=para, reducer=ee.Reducer.sum(), scale=30)
    return med, ar


linhas = []
for y in range(ANO_INI, ANO_FIM + 1):
    med, ar = coleta_ano(y)
    areas = {f["properties"]["ADM2_NAME"]: f["properties"].get("sum", 0)
             for f in ar.getInfo()["features"]}
    n_ok = 0
    for f in med.getInfo()["features"]:
        p = f["properties"]
        if p.get("NDVI_mean") is None:     # municipio sem soja mapeada naquele ano
            continue
        reg = {"municipio": p["ADM2_NAME"], "ano": y,
               "soy_area_ha": areas.get(p["ADM2_NAME"], 0)}
        for b in BANDAS:
            reg[b] = p.get(b)
        linhas.append(reg); n_ok += 1
    print(f"  {y}: {n_ok} municipios com soja")

pred = pd.DataFrame(linhas)
print("\nPreditores:", pred.shape)

# ------------------------------------------------- produtividade (IBGE/SIDRA)
# A API do SIDRA limita 50.000 valores por requisicao -> baixa ano a ano.
partes = []
for y in range(ANO_INI, ANO_FIM + 1):
    try:
        t = sidrapy.get_table(
            table_code="5457", territorial_level="6",
            ibge_territorial_code="all",
            variable="112",                     # rendimento medio (kg/ha)
            classifications={"782": "40124"},   # soja (em grao)
            period=str(y))
        t = t.iloc[1:][["D1C", "D1N", "V"]].rename(
            columns={"D1C": "cod_ibge7", "D1N": "nome_ibge", "V": "rendimento_kg_ha"})
        t["ano"] = y
        partes.append(t)
    except Exception as err:
        print(f"  IBGE {y}: sem dado ({err})")
    time.sleep(1)

ibge = pd.concat(partes, ignore_index=True)
ibge["rendimento_kg_ha"] = pd.to_numeric(ibge["rendimento_kg_ha"], errors="coerce")
ibge = ibge.dropna(subset=["rendimento_kg_ha"])
ibge = ibge[ibge["cod_ibge7"].astype(str).str.startswith("15")]     # UF 15 = Para

# ------------------------------------------------------------------- juncao
# O GAUL nao traz o codigo do IBGE: o pareamento e feito pelo nome normalizado.
# O IBGE devolve "Nome - PA"; o GAUL, "Nome" sem acento.
def chave(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\spa$", "", s)      # remove a sigla da UF ao final

ibge["chave"] = ibge["nome_ibge"].map(chave)
pred["chave"] = pred["municipio"].map(chave)
pred["ano"] = pred["ano"].astype(int)
ibge["ano"] = ibge["ano"].astype(int)

base = pred.merge(ibge[["chave", "ano", "cod_ibge7", "rendimento_kg_ha"]],
                  on=["chave", "ano"], how="inner").drop(columns=["chave"])
base = base.dropna(subset=BANDAS + ["rendimento_kg_ha"])
assert len(base) > 0, "juncao vazia: verifique as chaves"

print("\nBASE FINAL:", base.shape,
      "| municipios:", base.cod_ibge7.nunique(),
      "| anos:", base.ano.min(), "-", base.ano.max())
base.to_csv("dados_soja_para_mascarado.csv", index=False)
