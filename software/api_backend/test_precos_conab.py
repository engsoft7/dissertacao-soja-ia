# -*- coding: utf-8 -*-
"""Preço mensal da CONAB por estado (precos_conab.py), que vai à tela Mercado.

Rode com:  python -m pytest software -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import precos_conab as pc  # noqa: E402

CSV = """uf,ano,mes,preco_kg,preco_saca
MT,2026,10,2.29,137.4
PA,2025,12,2.1,126
PA,2026,9,2.15,129
PA,2026,10,2.23,133.8
TO,2026,10,2.21,132.6
"""


def _arquivo(tmp_path, texto=CSV):
    a = tmp_path / "precos_soja_mensal_uf.csv"
    a.write_text(texto, encoding="utf-8")
    return a


def test_o_mes_mais_recente_do_estado(tmp_path):
    a = _arquivo(tmp_path)
    assert pc.mensal("PA", a) == {"uf": "PA", "mes": "2026-10", "preco_saca": 133.8,
                                  "fonte": pc.FONTE, "url": pc.URL}
    assert pc.mensal("MT", a)["mes"] == "2026-10"
    # A virada do ano conta: dezembro de 2025 vem antes de setembro de 2026.
    assert pc.mensal("PA", _arquivo(tmp_path, "uf,ano,mes,preco_kg,preco_saca\nPA,2025,12,2.1,126\n"
                                              "PA,2026,1,2.0,120\n"))["mes"] == "2026-01"


def test_estado_sem_preco_ou_arquivo_ausente(tmp_path):
    assert pc.mensal("RO", _arquivo(tmp_path)) is None
    assert pc.mensal("PA", tmp_path / "nao_existe.csv") is None


def test_linha_ilegivel_ou_fora_da_faixa_fica_de_fora(tmp_path):
    a = _arquivo(tmp_path, "uf,ano,mes,preco_kg,preco_saca\nPA,2026,11,0.2,12\nPA,2026,13,2.0,120\n"
                           "PA,2026,x,2.0,120\nPA,2026,10,2.23,133.8\n")
    assert pc.mensal("PA", a)["mes"] == "2026-10"


def test_relê_quando_a_coleta_troca_o_arquivo(tmp_path):
    import os
    a = _arquivo(tmp_path)
    assert pc.mensal("PA", a)["preco_saca"] == 133.8
    a.write_text(CSV + "PA,2026,11,2.3,138\n", encoding="utf-8")
    os.utime(a, ns=(a.stat().st_atime_ns, a.stat().st_mtime_ns + 1_000_000_000))
    assert pc.mensal("PA", a) == {"uf": "PA", "mes": "2026-11", "preco_saca": 138.0,
                                  "fonte": pc.FONTE, "url": pc.URL}


def test_arquivo_do_repositorio_quando_existe():
    """O CSV que a coleta automática grava: cada estado com preço tem um mês plausível."""
    if not pc.ARQUIVO.exists():
        return
    for uf in ("PA", "MT", "MA", "TO", "RO"):
        m = pc.mensal(uf)
        if m is not None:
            assert pc.PRECO_MIN <= m["preco_saca"] <= pc.PRECO_MAX
            assert m["mes"][:2] == "20" and m["mes"][4] == "-"
