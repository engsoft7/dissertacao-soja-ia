# ============================================================================
#  COLETA DE DADOS — SOJA NO PARÁ  (para a dissertação)
#  Rode este notebook no GOOGLE COLAB (colab.research.google.com)
#  Ele coleta: NDVI, EVI, clima (Google Earth Engine) + produtividade (IBGE)
#  e baixa um único CSV: dados_soja_para.csv  -> me envie esse arquivo.
#
#  PRÉ-REQUISITO (uma vez só): crie um projeto no Google Cloud com o Earth
#  Engine ativado em https://code.earthengine.google.com  (é gratuito p/ uso
#  acadêmico). Anote o ID do projeto (ex.: "ee-seunome") e coloque abaixo.
# ============================================================================

# ------------------------------------------------------------------ CÉLULA 1
# Instalação e autenticação
!pip install earthengine-api sidrapy pandas -q

import ee, pandas as pd, sidrapy, time

PROJETO_GEE = "COLOQUE-SEU-PROJETO-AQUI"   # <<< EDITE AQUI (ex.: "ee-maycon")

ee.Authenticate()                # abre uma janela: faça login com sua conta Google
ee.Initialize(project=PROJETO_GEE)
print("Earth Engine conectado ao projeto:", PROJETO_GEE)


# ------------------------------------------------------------------ CÉLULA 2
# Parâmetros
ANO_INI, ANO_FIM = 2001, 2023     # período (MODIS começa em 2000)
# Janela da safra de soja no Pará: plantio ~nov, colheita ~mai do ano seguinte.
# Para o "ano de colheita" Y, a janela vai de nov(Y-1) a maio(Y).
MES_INI, DIA_INI = 11, 1
MES_FIM, DIA_FIM = 5, 31

# Municípios do Pará (limites oficiais FAO GAUL nível 2)
para = (ee.FeatureCollection("FAO/GAUL/2015/level2")
        .filter(ee.Filter.eq("ADM1_NAME", "Pará")))
print("Municípios do Pará carregados:", para.size().getInfo())

# Coleções de imagens
MODIS  = ee.ImageCollection("MODIS/061/MOD13Q1")          # NDVI, EVI (250 m, 16 dias)
CHIRPS = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")      # precipitação (mm)
ERA5   = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR") # temperatura, radiação, ET


# ------------------------------------------------------------------ CÉLULA 3
# Função que extrai os preditores de UM ano de colheita, por município
def preditores_do_ano(ano):
    ano = ee.Number(ano)
    ini = ee.Date.fromYMD(ano.subtract(1), MES_INI, DIA_INI)
    fim = ee.Date.fromYMD(ano, MES_FIM, DIA_FIM)

    veg = MODIS.filterDate(ini, fim)
    ndvi_mean = veg.select("NDVI").mean().multiply(0.0001).rename("NDVI_mean")
    ndvi_max  = veg.select("NDVI").max().multiply(0.0001).rename("NDVI_max")
    evi_mean  = veg.select("EVI").mean().multiply(0.0001).rename("EVI_mean")
    evi_max   = veg.select("EVI").max().multiply(0.0001).rename("EVI_max")

    precip = CHIRPS.filterDate(ini, fim).select("precipitation").sum().rename("precip_total")

    e = ERA5.filterDate(ini, fim)
    tmean = e.select("temperature_2m").mean().subtract(273.15).rename("temp_mean")
    tmax  = e.select("temperature_2m_max").mean().subtract(273.15).rename("temp_max")
    srad  = e.select("surface_solar_radiation_downwards_sum").mean().divide(1e6).rename("srad_mean")  # MJ/m2
    etp   = e.select("potential_evaporation_sum").sum().multiply(-1000).rename("etp_total")            # mm

    img = ee.Image.cat([ndvi_mean, ndvi_max, evi_mean, evi_max, precip, tmean, tmax, srad, etp])

    fc = img.reduceRegions(collection=para, reducer=ee.Reducer.mean(), scale=250)
    return fc.map(lambda f: f.set("ano", ano))

# Loop ano a ano (baixa direto, sem precisar do Google Drive)
BANDAS = ["NDVI_mean","NDVI_max","EVI_mean","EVI_max","precip_total",
          "temp_mean","temp_max","srad_mean","etp_total"]

linhas = []
for y in range(ANO_INI, ANO_FIM + 1):
    fc = preditores_do_ano(y).getInfo()
    for feat in fc["features"]:
        p = feat["properties"]
        reg = {"cod_ibge6": p.get("ADM2_CODE"), "municipio": p.get("ADM2_NAME"), "ano": y}
        for b in BANDAS:
            reg[b] = p.get(b)
        linhas.append(reg)
    print(f"  ano {y}: {len(fc['features'])} municípios OK")

pred = pd.DataFrame(linhas)
print("\nPreditores coletados:", pred.shape)
pred.head()


# ------------------------------------------------------------------ CÉLULA 4
# Produtividade da soja (IBGE / SIDRA) — Tabela 5457
# variável 112 = Rendimento médio (kg/ha); c782/40124 = Soja (em grão); n6 = município
ibge = sidrapy.get_table(
    table_code="5457", territorial_level="6", ibge_territorial_code="all",
    variable="112", classifications={"782": "40124"},
    period=f"{ANO_INI}-{ANO_FIM}"
)
ibge = ibge.iloc[1:]  # remove linha de cabeçalho duplicada
ibge = ibge[["D1C", "D2C", "V"]].rename(
    columns={"D1C": "cod_ibge7", "D2C": "ano", "V": "rendimento_kg_ha"})
ibge["ano"] = ibge["ano"].astype(int)
ibge["rendimento_kg_ha"] = pd.to_numeric(ibge["rendimento_kg_ha"], errors="coerce")
# só Pará (código IBGE do município começa com 15) e com produtividade válida
ibge = ibge[ibge["cod_ibge7"].str.startswith("15")].dropna(subset=["rendimento_kg_ha"])
ibge["cod_ibge6"] = ibge["cod_ibge7"].str[:6].astype(int)
print("Produtividade IBGE (Pará):", ibge.shape)
ibge.head()


# ------------------------------------------------------------------ CÉLULA 5
# Junta preditores (GEE) + produtividade (IBGE) pelo código do município e ano
pred["cod_ibge6"] = pred["cod_ibge6"].astype(int)
base = pred.merge(ibge[["cod_ibge6","ano","rendimento_kg_ha"]], on=["cod_ibge6","ano"], how="inner")
base = base.dropna(subset=BANDAS + ["rendimento_kg_ha"])
print("BASE FINAL (município-safra com soja):", base.shape)
print("Municípios:", base["cod_ibge6"].nunique(), "| Anos:", base["ano"].min(), "-", base["ano"].max())
base.describe().round(1)


# ------------------------------------------------------------------ CÉLULA 6
# Salva e baixa o CSV — ME ENVIE este arquivo
base.to_csv("dados_soja_para.csv", index=False)
from google.colab import files
files.download("dados_soja_para.csv")
print("Pronto! Envie 'dados_soja_para.csv' no chat que eu rodo a análise para o Pará.")
