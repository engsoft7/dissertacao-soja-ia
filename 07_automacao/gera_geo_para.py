# -*- coding: utf-8 -*-
"""Gera dados/para_geo.json: contorno do estado do Pará (malha do IBGE).

Baixa a malha oficial do Pará (API de malhas do IBGE, qualidade mínima) e grava
um GeoJSON compacto — coordenadas arredondadas a 3 casas (~100 m) — usado como
fundo do mapa desenhado do painel. A malha muda raríssimo; utilitário sob
demanda, com a saída versionada.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

SAIDA = Path(__file__).resolve().parents[1] / "dados" / "para_geo.json"
URL = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/15"
       "?formato=application/vnd.geo+json&qualidade=minima")


def arredonda(x, casas=3):
    if isinstance(x, list):
        return [arredonda(v, casas) for v in x]
    if isinstance(x, float):
        return round(x, casas)
    return x


def main() -> int:
    r = requests.get(URL, timeout=90)
    r.raise_for_status()
    fc = r.json()
    for feature in fc.get("features", []):
        feature.pop("properties", None)
        geom = feature.get("geometry", {})
        if "coordinates" in geom:
            geom["coordinates"] = arredonda(geom["coordinates"])
    SAIDA.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    print(f"{SAIDA.name}: {SAIDA.stat().st_size} bytes · "
          f"{len(fc.get('features', []))} feature(s) · tipo "
          f"{fc.get('features', [{}])[0].get('geometry', {}).get('type')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
