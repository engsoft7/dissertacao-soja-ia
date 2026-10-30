# -*- coding: utf-8 -*-
"""As contas de tempo.py, com os mesmos casos de TempoCalculoTest.kt do aplicativo.

O painel e o aplicativo precisam dar a mesma janela de pulverização para a
mesma previsão: os casos e a resposta real do Open-Meteo (Paragominas,
25/10/2026, 17h45) são os do teste do aplicativo.

Rode com:  python -m pytest software -q
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tempo as t  # noqa: E402

PREV = json.loads((Path(__file__).parent / "dados_de_teste" / "openmeteo_paragominas_2026-10-25.json")
                  .read_text(encoding="utf-8"))
AGORA = datetime(2026, 10, 25, 17, 45)


def test_vento_a_2m():
    assert abs(t.vento_a_2m(10.0) - 7.48) < 0.01


def test_limites_da_embrapa():
    assert t.avalia_hora(25, 70, 8, False, False) == (t.BOA, [])
    assert t.avalia_hora(30.5, 70, 8, False, False)[0] == t.EVITAR
    assert t.avalia_hora(30.0, 70, 8, False, False)[0] == t.BOA
    assert t.avalia_hora(25, 59, 8, False, False)[0] == t.EVITAR
    nivel, motivos = t.avalia_hora(25, 70, 12, False, False)
    assert nivel == t.ATENCAO and "antideriva" in motivos[0]
    assert t.avalia_hora(25, 70, 15, False, False)[0] == t.EVITAR
    assert t.avalia_hora(25, 70, 3, False, False)[0] == t.ATENCAO
    assert t.avalia_hora(25, 70, 8, False, True) == (t.ATENCAO, ["chuva prevista nas 2 horas seguintes"])
    assert t.avalia_hora(None, 70, 8, False, False)[0] == t.ATENCAO


def test_resposta_real_igual_ao_aplicativo():
    horas = t.horas_de_pulverizacao(PREV["hourly"], AGORA)
    assert len(horas) == 24 and horas[0]["hora"] == datetime(2026, 10, 25, 17)
    assert horas[0]["nivel"] == t.EVITAR
    assert t.proxima_janela(horas) == (datetime(2026, 10, 26, 2), datetime(2026, 10, 26, 8))


def test_balanco_de_chuva():
    b = t.balanco_chuva(PREV["daily"], date(2026, 10, 25))
    assert b["dias_passados"] == 7 and abs(b["chuva_passada"] - 2.5) < 1e-6
    assert abs(b["et0_passada"] - 41.17) < 1e-6 and abs(b["chuva_prevista"] - 1.1) < 1e-6


def test_descricoes():
    assert t.descricao_tempo(3) == "Nublado" and t.direcao_vento(48) == "NE" and t.direcao_vento(350) == "N"
    assert t.categoria_uv(9.15) == "muito alto" and t.categoria_uv(11) == "extremo"
