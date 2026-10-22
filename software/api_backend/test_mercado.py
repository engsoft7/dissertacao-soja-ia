# -*- coding: utf-8 -*-
"""Testes da conversão da cotação de Chicago para reais por saca.

Rode com:  python -m pytest software -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mercado  # noqa: E402


def resposta(ts, closes, opens=None, preco=None, atraso=None):
    opens = opens or closes
    meta = {"regularMarketPrice": preco if preco is not None else closes[-1]}
    if atraso is not None:
        meta["exchangeDataDelayedBy"] = atraso
    return {"chart": {"result": [{"timestamp": ts, "meta": meta, "indicators": {"quote": [
        {"open": opens, "high": closes, "low": closes, "close": closes}]}}]}}


def test_converte_centavos_por_bushel_em_reais_por_saca():
    # 1000 centavos/bushel = US$ 10,00/bu; x 2,20462 bu/saca x R$ 5,00/US$
    v = mercado.velas_em_reais(resposta([100], [1000.0]), resposta([100], [5.0]))
    assert v[0]["c"] == pytest.approx(10 * 60 / 27.2155 * 5, abs=0.01)


def test_cada_vela_usa_o_cambio_do_seu_instante():
    """Se o dólar sobe no período e a soja fica parada, o preço em reais sobe
    junto, e a vela anterior não pode ser recalculada com o câmbio novo."""
    soja = resposta([100, 200], [1000.0, 1000.0])
    cambio = resposta([90, 190], [5.0, 6.0])
    v = mercado.velas_em_reais(soja, cambio)
    assert v[1]["c"] / v[0]["c"] == pytest.approx(6 / 5, rel=1e-4)   # velas em centavos


def test_minuto_sem_negocio_e_descartado():
    v = mercado.velas_em_reais(resposta([100, 200, 300], [1000.0, None, 1010.0]),
                               resposta([100], [5.0]))
    assert [x["t"] for x in v] == [100, 300]


def test_sem_serie_de_cambio_usa_a_ultima_cotacao_do_dolar():
    cambio = {"chart": {"result": [{"timestamp": [], "meta": {"regularMarketPrice": 5.0},
                                    "indicators": {"quote": [{}]}}]}}
    v = mercado.velas_em_reais(resposta([100], [1000.0]), cambio)
    assert v and v[0]["c"] > 0


def test_resumo_declara_atraso_e_variacao_do_periodo():
    r = mercado.resumo(resposta([100, 200], [1000.0, 1100.0], atraso=10),
                       resposta([100], [5.0]), "1d")
    assert r["atraso_min"] == 10
    assert r["variacao_periodo_pct"] == pytest.approx(10.0, abs=0.01)
    assert r["intervalo"] == "5m"


def test_fonte_fora_do_ar_nao_vira_cotacao(monkeypatch):
    mercado._cache.clear()

    def falha(*a, **k):
        raise ConnectionError("sem rede")

    monkeypatch.setattr(mercado, "_baixa", falha)
    assert mercado.cotacao("5d") is None


def test_periodo_desconhecido_e_recusado():
    with pytest.raises(ValueError):
        mercado.cotacao("10y")
