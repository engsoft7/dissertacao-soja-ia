# -*- coding: utf-8 -*-
"""As correções de gera_municipios.py estão no CSV versionado.

Sem isto, rodar o gerador de novo devolveria Pau D'Arco ao nordeste do Pará,
e ninguém notaria até a previsão do tempo sair errada para o município.
"""
import csv
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import gera_municipios as gm  # noqa: E402


def test_csv_traz_as_coordenadas_corrigidas():
    with open(gm.SAIDA, encoding="utf-8") as f:
        linhas = {int(r["cod_ibge7"]): (r["latitude"], r["longitude"]) for r in csv.DictReader(f)}
    for cod, coords in gm.CORRECOES.items():
        assert linhas[cod] == coords


def test_sedes_dentro_do_para():
    with open(gm.SAIDA, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            assert -10.0 <= float(r["latitude"]) <= 2.7, r["municipio"]
            assert -59.0 <= float(r["longitude"]) <= -46.0, r["municipio"]
