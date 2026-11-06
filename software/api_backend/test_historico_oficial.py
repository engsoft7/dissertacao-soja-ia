# -*- coding: utf-8 -*-
"""Safras do IBGE fora da base do modelo e a safra de onde partem as projeções.

Rode com:  python -m pytest software -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import historico_oficial as H  # noqa: E402

PAU_DARCO = 1505551


def test_le_o_arquivo_versionado():
    pam = H.carrega_pam()
    assert len(pam) == 38
    # O caso que a auditoria achou: a base para em 2017, o IBGE publicou até 2025.
    assert pam[PAU_DARCO][2025] == 3700.0
    assert all(v > 0 for safras in pam.values() for v in safras.values())


def test_sem_arquivo_fica_vazio(tmp_path):
    assert H.carrega_pam(tmp_path / "nao_existe.csv") == {}


def test_projecao_parte_da_ultima_safra_publicada_para_todos():
    pam = {PAU_DARCO: {2016: 3000.0, 2025: 3700.0}, 1: {2024: 3200.0}}
    assert H.ultima_safra_publicada(2025, pam) == 2025
    assert H.ultima_safra_publicada(2025, {}) == 2025
    # IBGE publicou a safra nova antes da coleta de satélite: projeta depois dela.
    assert H.ultima_safra_publicada(2025, {1: {2026: 3300.0}}) == 2026


def test_safras_fora_da_base_em_ordem_e_sem_repetir_a_base():
    oficiais = {2025: 3700.0, 2016: 3000.0, 2017: 3100.0, 2020: 3300.0}
    assert H.safras_fora_da_base(oficiais, {2017}, 2025) == [(2016, 3000.0), (2020, 3300.0), (2025, 3700.0)]
    assert H.safras_fora_da_base(oficiais, {2017}, 2020) == [(2016, 3000.0), (2020, 3300.0)]
