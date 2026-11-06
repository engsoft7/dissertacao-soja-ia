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


# A mesma página no formato publicado desde 25/10/2026: um ano por linha, um mês
# por coluna, só a média estadual, com o valor também no title da célula. Uma
# segunda tabela com o mesmo tipo de célula (outro produto) não pode entrar.
HTML_NOVO = """
<h2>Médias mensais</h2><div class="hidden lg:block"><table class="w-full table-fixed">
<caption class="sr-only">Médias mensais de <!-- -->Soja em Grão Sc 60Kg<!-- --> em <!-- -->PA<!-- -->.</caption>
<thead><tr><th scope="col">Ano</th><th scope="col">Jan</th></tr></thead><tbody>
<tr><th scope="row">2026</th>
<td class="px-1" title="Ago/2026: R$ 1.340,07">1.340,07</td>
<td class="px-1" title="Set/2026: R$ 144,10">144,10</td>
<td class="px-1" title="Out/2026: R$ 140,86">140,86</td>
<td class="px-1">·</td><td class="px-2 font-bold">127,81</td></tr>
<tr><th scope="row">2025</th>
<td class="px-1" title="Dez/2025: R$ 118,50">118,50</td></tr>
</tbody></table></div>
<table><tr><td title="Out/2026: R$ 99,00">99,00</td></tr></table>
"""


def test_le_o_formato_novo_da_pagina():
    h = pp.le_historico(HTML_NOVO)
    assert [l["mes"] for l in h] == ["2025-12", "2026-09", "2026-10"]
    assert h[-1]["para"] == pytest.approx(140.86)
    assert h[-1]["nacional"] is None


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


# ── cotação diária por praça ──────────────────────────────────────────────
# Trecho do JSON que a página regional da Agrolink traz no script (nov/2026),
# com as aspas escapadas como na página: duas praças em dia e uma parada.
PAGINA_PRACAS = (
    '<script>self.__next_f.push([1,"[{\\"cidade\\":\\"Barcarena\\",\\"uf\\":\\"PA\\",\\"preco\\":148.5,'
    '\\"variacaoPct\\":-0.66,\\"freq\\":\\"diario\\",\\"produto\\":\\"Soja em Grão Sc 60Kg\\",'
    '\\"codProduto\\":9,\\"atualizacaoMs\\":1793900220000},'
    '{\\"cidade\\":\\"Paragominas\\",\\"uf\\":\\"PA\\",\\"preco\\":133.12,\\"freq\\":\\"diario\\",'
    '\\"produto\\":\\"Soja em Grão Sc 60Kg\\",\\"codProduto\\":9,\\"atualizacaoMs\\":1791207120000},'
    '{\\"cidade\\":\\"Redenção\\",\\"uf\\":\\"PA\\",\\"preco\\":51.3,\\"freq\\":\\"diario\\",'
    '\\"produto\\":\\"Milho Seco Sc 60Kg\\",\\"codProduto\\":7,\\"atualizacaoMs\\":1793900220000}]"])</script>'
)


def test_le_a_cotacao_diaria_de_cada_praca_no_json_da_pagina():
    pracas = pp.le_pracas(PAGINA_PRACAS)
    assert pracas == [
        {"praca": "Barcarena", "uf": "PA", "valor": 148.5, "data": "2026-11-05"},
        {"praca": "Paragominas", "uf": "PA", "valor": 133.12, "data": "2026-10-05"},
    ]


def test_le_a_tabela_quando_o_json_nao_vem():
    # O texto da tabela, como a página mostra: a mesma praça em vários dias.
    tabela = ("<div>05/11/2026 Soja em Grão Sc 60Kg Redenção (PA) <span>148,50</span> ▼<!-- --> 0,7<!-- -->% "
              "05/11/26 Diário Histórico 04/11/2026 Soja em Grão Sc 60Kg Redenção (PA) 149,50 ▲ 0,7 % "
              "04/11/26 Diário Histórico Milho Seco Sc 60Kg Redenção (PA) 51,30 ▼ 0,9 % 05/11/26</div>")
    assert pp.le_pracas(tabela) == [
        {"praca": "Redenção", "uf": "PA", "valor": 148.5, "data": "2026-11-05"}]


def test_pagina_sem_cotacao_de_soja_nao_inventa_praca():
    assert pp.le_pracas("<html><body>Cotações</body></html>") == []


def test_sem_a_pagina_do_estado_junta_as_paginas_das_pracas(monkeypatch):
    pp._cache.pop("pracas", None)
    paginas = {
        pp.URL_PRACAS: [],
        pp.URLS_RESERVA[0]: [{"praca": "Barcarena", "uf": "PA", "valor": 148.5, "data": "2026-11-05"}],
        pp.URLS_RESERVA[1]: [{"praca": "Redenção", "uf": "PA", "valor": 148.5, "data": "2026-11-05"}],
        pp.URLS_RESERVA[2]: [],
    }
    monkeypatch.setattr(pp, "_baixa_pracas", lambda url: paginas[url])
    assert [c["praca"] for c in pp.pracas_do_para()] == ["Redenção", "Barcarena"]
    pp._cache.pop("pracas", None)
