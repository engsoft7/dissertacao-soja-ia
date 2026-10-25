# -*- coding: utf-8 -*-
"""Testes dos avisos do INMET para um ponto ou um município.

Rode com:  python -m pytest software -q
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import avisos_inmet as ai  # noqa: E402

# Recorte da resposta real de 25/10/2026: a tempestade de 26/10 que atinge o
# sul do Pará (56174), uma de hoje fora do Pará (56171) e a de baixa umidade
# de 26/10, também fora (56176).
DADOS = json.loads((Path(__file__).parent / "dados_de_teste" / "avisos_inmet_2026-10-25.json")
                   .read_text(encoding="utf-8"))


def ids(lista):
    return [a["id"] for a in lista]


def test_ponto_no_quadrado():
    quadrado = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    assert ai.dentro(5, 5, quadrado)
    assert not ai.dentro(15, 5, quadrado)
    assert not ai.dentro(5, -1, quadrado)


def test_multipoligono_tem_um_anel_por_parte():
    g = {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]],
                                                  [[[5, 5], [6, 5], [6, 6], [5, 5]]]]}
    assert len(ai.aneis(g)) == 2


def test_municipio_pelo_geocodigo():
    # Água Azul do Norte (1500347) está na lista de municípios da tempestade de 26/10.
    assert ids(ai.filtra(DADOS, None, None, "1500347")) == ["56174"]


def test_fazenda_pelo_gps_dentro_do_poligono():
    # Sede de Redenção, sem geocódigo: só o polígono decide.
    assert ids(ai.filtra(DADOS, -8.02529, -50.0317, None)) == ["56174"]


def test_lugar_sem_aviso():
    # Santarém, pela sede e pelo geocódigo: nenhum dos três avisos chega lá.
    assert ai.filtra(DADOS, -2.43849, -54.6996, "1506807") == []


def test_resumo_do_aviso():
    a = ai.filtra(DADOS, None, None, "1500347")[0]
    assert a["evento"] == "Tempestade"
    assert a["severidade"] == "Perigo Potencial" and a["nivel"] == 1
    assert a["inicio"] == "2026-10-26 00:00" and a["fim"] == "2026-10-26 23:59"
    assert a["riscos"] and "granizo" in a["riscos"][0]
    assert any("199" in i for i in a["instrucoes"])


def test_riscos_em_texto_de_lista():
    assert ai._lista("['um', 'dois ']") == ["um", "dois"]
    assert ai._lista("texto solto") == ["texto solto"]
    assert ai._lista(None) == []


def test_aviso_encerrado_fica_de_fora():
    dados = json.loads(json.dumps(DADOS))
    dados["futuro"][0]["encerrado"] = True
    assert ai.filtra(dados, None, None, "1500347") == []


def test_fonte_fora_do_ar_sem_leitura_anterior(monkeypatch):
    monkeypatch.setattr(ai, "_cache", {})
    def falha():
        raise ConnectionError("sem rede")
    monkeypatch.setattr(ai, "_baixa", falha)
    r = ai.avisos(-8.0, -50.0, None)
    assert r["disponivel"] is False and r["avisos"] == []


def test_fonte_fora_do_ar_usa_a_ultima_leitura(monkeypatch):
    monkeypatch.setattr(ai, "_cache", {"ativos": (0.0, DADOS)})  # vencida
    def falha():
        raise ConnectionError("sem rede")
    monkeypatch.setattr(ai, "_baixa", falha)
    r = ai.avisos(None, None, "1500347")
    assert r["disponivel"] is True and ids(r["avisos"]) == ["56174"]
