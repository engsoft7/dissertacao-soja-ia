# -*- coding: utf-8 -*-
"""Testes das métricas de validação que a API entrega ao aplicativo.

Rode com:  python -m pytest software -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validacao  # noqa: E402

CALCULADAS = {"r2": 0.1, "r2_baseline": 0.1, "rmse": 500.0, "rrmse": 15.0}


def test_usa_o_arquivo_quando_ele_descreve_a_base_carregada():
    """São os números que o painel exibe e que a rotina regrava a cada safra."""
    salvas = json.loads(validacao.ARQUIVO.read_text(encoding="utf-8"))
    m = validacao.metricas_validacao(salvas["registros"], 38, CALCULADAS)
    assert m["fonte"] == "metricas_validacao.json"
    assert m["r2"] == round(salvas["r2"], 3)
    assert m["r2_referencia"] == round(salvas["r2_baseline"], 3)
    assert m["rmse_kg_ha"] == round(salvas["rmse"], 1)
    assert m["registros"] == salvas["registros"]


def test_arquivo_de_outra_base_da_lugar_as_calculadas(tmp_path):
    """Base com outro tamanho: o arquivo é de outra safra e não pode ser exibido."""
    arq = tmp_path / "m.json"
    arq.write_text(json.dumps({"registros": 415, "r2": 0.216, "r2_baseline": 0.216,
                               "rmse": 415.6, "rrmse": 13.9}), encoding="utf-8")
    m = validacao.metricas_validacao(451, 38, CALCULADAS, arquivo=arq)
    assert m["fonte"].startswith("calculadas")
    assert m["r2"] == 0.1 and m["registros"] == 451


def test_sem_arquivo_e_sem_calculadas_nao_inventa_numero(tmp_path):
    assert validacao.metricas_validacao(451, 38, None, arquivo=tmp_path / "nao_existe.json") is None
