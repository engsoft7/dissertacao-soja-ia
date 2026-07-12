# -*- coding: utf-8 -*-
"""Gera dados/municipios_para.csv: nome oficial acentuado + centroide (lat/lon).

Fontes abertas:
  - Nomes: API de localidades do IBGE (autoritativa, com acentuação oficial).
  - Coordenadas: dataset aberto de municípios brasileiros (derivado do IBGE),
    kelvins/municipios-brasileiros.

Casa tudo pelo código IBGE de 7 dígitos com os municípios presentes na base do
painel e grava um CSV pequeno que o painel usa para exibir os nomes corretos
(a base bruta vem do GAUL, sem acento) e desenhar o mapa do estado. A base muda
raramente, então este utilitário é executado sob demanda e a saída é versionada.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
BASE = RAIZ / "dados" / "soja_para_mascarado_2001_2024.csv"
SAIDA = RAIZ / "dados" / "municipios_para.csv"

IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/15/municipios"
COORDS = ("https://raw.githubusercontent.com/kelvins/municipios-brasileiros/"
          "main/csv/municipios.csv")


def main() -> int:
    codigos = sorted(pd.read_csv(BASE)["cod_ibge7"].astype(int).unique())

    nomes = {m["id"]: m["nome"] for m in requests.get(IBGE, timeout=90).json()}

    coords_csv = requests.get(COORDS, timeout=90)
    coords_csv.encoding = "utf-8"
    coords = {int(row["codigo_ibge"]): (row["latitude"], row["longitude"])
              for row in csv.DictReader(io.StringIO(coords_csv.text))}

    linhas = []
    for cod in codigos:
        nome = nomes.get(cod)
        lat, lon = coords.get(cod, ("", ""))
        if not nome or not lat:
            print(f"AVISO: faltou dado para {cod} (nome={nome!r}, lat={lat!r})")
        linhas.append({"cod_ibge7": cod, "municipio": nome or "",
                       "latitude": lat, "longitude": lon})

    with open(SAIDA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cod_ibge7", "municipio", "latitude", "longitude"])
        w.writeheader()
        w.writerows(linhas)

    print(f"{len(linhas)} municípios gravados em {SAIDA.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
