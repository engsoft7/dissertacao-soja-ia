# -*- coding: utf-8 -*-
"""Testes da base do Pará e da estimativa do preço paraense ao longo do dia.

Rode com:  python -m pytest software -q
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import precos_para as pp  # noqa: E402

# Recorte da tabela de histórico da Agrolink, no formato publicado em 23/10/2026.
HTML = """
<table class="table table-main orange"><thead><tr>
<th scope="col" class="upper text-center">Mês/Ano</th>
<th scope="col" class="upper text-center">Estadual</th>
<th scope="col" class="upper text-center">Nacional</th></tr></thead><tbody>
<tr>
    <th class="text-center">10/2026</th>
    <td class="text-center">140,9741</td>
    <td class="text-center">139,3656</td>
</tr>
<tr>
    <th class="text-center">9/2026</th>
    <td class="text-center">144,1022</td>
    <td class="text-center">141,0084</td>
</tr>
<tr>
    <th class="text-center">8/2026</th>
    <td class="text-center">1.340,0717</td>
    <td class="text-center">129,0178</td>
</tr>
</tbody></table>
"""


def ts(ano, mes, dia, hora=15):
    return int(datetime(ano, mes, dia, hora, tzinfo=timezone.utc).timestamp())


def test_le_a_tabela_mensal_em_ordem_cronologica():
    h = pp.le_historico(HTML)
    assert [l["mes"] for l in h] == ["2026-09", "2026-10"]
    assert h[-1]["para"] == pytest.approx(140.97)
    assert h[-1]["nacional"] == pytest.approx(139.37)


def test_descarta_valor_fora_da_faixa_de_preco_de_saca():
    # 1.340,07 é número de outra grandeza (ou erro de digitação na fonte)
    assert "2026-08" not in [l["mes"] for l in pp.le_historico(HTML)]


def test_pagina_sem_tabela_nao_inventa_meses():
    assert pp.le_historico("<html>manutenção</html>") == []


def test_base_e_para_menos_chicago_no_mesmo_mes():
    velas = [{"t": ts(2026, 9, 2), "c": 140.0}, {"t": ts(2026, 9, 30), "c": 142.0},
             {"t": ts(2026, 10, 1), "c": 139.0}]
    serie = pp.combina(pp.le_historico(HTML), pp.medias_mensais(velas))
    assert serie[0]["chicago"] == pytest.approx(141.0)
    assert serie[0]["base"] == pytest.approx(144.10 - 141.0, abs=0.01)
    assert serie[1]["base"] == pytest.approx(140.97 - 139.0, abs=0.01)


def test_mes_sem_chicago_fica_de_fora():
    serie = pp.combina(pp.le_historico(HTML), {"2026-10": 139.0})
    assert [s["mes"] for s in serie] == ["2026-10"]


def test_cada_vela_soma_a_base_do_seu_mes():
    serie = [{"mes": "2026-09", "base": 3.0}, {"mes": "2026-10", "base": 2.0}]
    cot = {"velas": [{"t": ts(2026, 9, 29), "c": 140.0}, {"t": ts(2026, 10, 22), "c": 139.0}]}
    r = pp.estima(cot, serie)
    assert r["velas_pa"] == [143.0, 141.0]
    assert r["estimado_brl_saca"] == pytest.approx(141.0)
    assert r["mes_base"] == "2026-10"


def test_mes_ainda_sem_media_usa_a_ultima_base_publicada():
    serie = [{"mes": "2026-10", "base": 2.0}]
    cot = {"velas": [{"t": ts(2026, 11, 3), "c": 150.0}]}
    assert pp.estima(cot, serie)["estimado_brl_saca"] == pytest.approx(152.0)


def test_antes_da_primeira_base_nao_ha_estimativa():
    serie = [{"mes": "2026-10", "base": 2.0}]
    cot = {"velas": [{"t": ts(2026, 9, 3), "c": 150.0}]}
    r = pp.estima(cot, serie)
    assert r["velas_pa"] == [None]
    assert r["estimado_brl_saca"] is None


def test_nao_altera_a_cotacao_guardada_em_cache():
    cot = {"velas": [{"t": ts(2026, 10, 22), "c": 139.0}]}
    pp.estima(cot, [{"mes": "2026-10", "base": 2.0}])
    assert cot == {"velas": [{"t": ts(2026, 10, 22), "c": 139.0}]}


def test_sem_serie_nao_ha_estimativa():
    assert pp.estima({"velas": [{"t": ts(2026, 10, 22), "c": 139.0}]}, []) is None
