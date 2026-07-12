# -*- coding: utf-8 -*-
"""Gera dados/rios_para.json: principais rios do Pará (Natural Earth, recortado).

Baixa a malha de rios do Natural Earth (10m, centerlines), recorta pelo polígono
do Pará (dados/para_geo.json) e mantém só os trechos maiores — dá contexto
geográfico ao mapa do painel sem poluir. Coordenadas arredondadas a 3 casas.
Utilitário sob demanda; a malha muda raríssimo e a saída é versionada.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

RAIZ = Path(__file__).resolve().parents[1]
GEO_PARA = RAIZ / "dados" / "para_geo.json"
SAIDA = RAIZ / "dados" / "rios_para.json"
URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
       "geojson/ne_10m_rivers_lake_centerlines.geojson")
MIN_GRAUS = 0.4  # descarta trechos curtos (slivers) medidos em graus


def arredonda(x, casas=3):
    if isinstance(x, list):
        return [arredonda(v, casas) for v in x]
    if isinstance(x, float):
        return round(x, casas)
    return x


def baixa(tentativas: int = 5, espera_s: int = 30) -> dict:
    for i in range(1, tentativas + 1):
        try:
            r = requests.get(URL, timeout=120)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as err:
            if i == tentativas:
                raise
            print(f"Falha ao baixar ({type(err).__name__}, {i}/{tentativas}); "
                  f"nova tentativa em {espera_s}s")
            time.sleep(espera_s)


def main() -> int:
    para = shape(json.loads(GEO_PARA.read_text(encoding="utf-8"))["features"][0]["geometry"])
    rios = baixa()
    feats = []
    for feature in rios.get("features", []):
        geom = feature.get("geometry")
        if not geom:
            continue
        try:
            recorte = shape(geom).intersection(para)
        except Exception:
            continue
        if recorte.is_empty or recorte.length < MIN_GRAUS:
            continue
        feats.append({"type": "Feature", "properties": {},
                      "geometry": arredonda(mapping(recorte), 3)})
    fc = {"type": "FeatureCollection", "features": feats}
    SAIDA.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    print(f"{SAIDA.name}: {SAIDA.stat().st_size} bytes · {len(feats)} trecho(s) de rio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
