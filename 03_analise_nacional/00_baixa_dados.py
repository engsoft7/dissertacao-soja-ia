# -*- coding: utf-8 -*-
"""
Baixa a base nacional utilizada na Secao 5 da dissertacao.

Fonte original (dados de terceiros, nao redistribuidos aqui):
  von Bloh, M. et al. Machine learning for soybean yield forecasting in Brazil.
  Agricultural and Forest Meteorology, 2023.
  https://github.com/maltevb/ML_Soybean_Yield_Forecasting_Brazil

Conteudo: 24.860 registros municipio-safra, 2001-2020, 1.243 municipios
de 7 estados (RS, PR, MT, MS, GO, MG, BA). Nao inclui o Para.

Saida: data/data_cast.csv
"""
import os, urllib.request

URL = ("https://raw.githubusercontent.com/maltevb/"
       "ML_Soybean_Yield_Forecasting_Brazil/main/Data_cast_Paper.csv")
DESTINO = "data/data_cast.csv"

os.makedirs("data", exist_ok=True)
print("Baixando base de von Bloh et al. (2023)...")
urllib.request.urlretrieve(URL, DESTINO)

tam = os.path.getsize(DESTINO) / 1e6
print(f"OK: {DESTINO} ({tam:.1f} MB)")
print("Cite a fonte original ao utilizar estes dados.")
