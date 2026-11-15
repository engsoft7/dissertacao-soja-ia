# -*- coding: utf-8 -*-
"""Leitura da Portaria SDA/MAPA nº 1.579/2026 (calendário de semeadura e vazio
sanitário da soja). Os trechos reproduzem o texto da página do Diário Oficial
como o coletor o recebe: o número da nota colado ao primeiro nome da lista e as
regiões numa célula só. Uma data ou um município lido errado diria ao produtor
que ele pode plantar quando não pode.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import coleta_plantio as cp  # noqa: E402


def test_datas_com_ordinal_e_virada_de_ano():
    assert cp.datas("1º de outubro de 2026 a 28 de janeiro de 2027") == ["2026-10-01", "2027-01-28"]
    assert cp.datas("08 de junho de 2026 a 06 de setembro de 2026") == ["2026-06-08", "2026-09-06"]


def test_periodo_unico():
    p = cp.periodos("07 de setembro de 2026 a 07 de janeiro de 2027")
    assert p == [{"regiao": None, "nota": None, "inicio": "2026-09-07", "fim": "2027-01-07"}]


def test_regioes_com_nota_de_um_e_dois_digitos():
    celula = ("Região I8: 16 de setembro de 2026 a 14 de janeiro de 2027  Região II9: 1º de novembro de 2026 "
              "a 28 de fevereiro de 2027  Região III10: 16 de novembro de 2026 a 14 de março de 2027")
    p = cp.periodos(celula)
    assert [(x["regiao"], x["nota"]) for x in p] == [("I", "8"), ("II", "9"), ("III", "10")]
    assert p[2]["inicio"] == "2026-11-16" and p[2]["fim"] == "2027-03-14"


def test_regioes_separadas_por_barra():
    celula = ("Região I1: 26 de junho de 2026 a 07 de outubro de 2026/Região II2: 14 de junho de 2026 "
              "a 14 de setembro de 2026")
    assert [x["nota"] for x in cp.periodos(celula)] == ["1", "2"]


def test_notas_de_rodape_e_distritos():
    texto = ("CALENDÁRIO DE SEMEADURA AC 22 de junho de 2026 a 20 de setembro de 2026 "
             "Região I5: 03 de julho de 2026 "
             "5Alto Parnaíba, Balsas, São Raimundo das Mangabeiras e Tasso Fragoso. "
             "8Bannach, PauD'Arco, Redenção, Trairão, além dos distritos de Cachoeira da Serra e Castelo de "
             "Sonhos, pertencentes ao município de Altamira. "
             "10Abaetetuba, Altamira e Belém.")
    notas = cp.notas_de_rodape(texto)
    assert set(notas) == {"5", "8", "10"}
    nomes, exc, dist = cp.municipios_da_nota(notas["5"])
    assert nomes == ["Alto Parnaíba", "Balsas", "São Raimundo das Mangabeiras", "Tasso Fragoso"]
    assert exc == {} and dist is None
    nomes, exc, dist = cp.municipios_da_nota(notas["8"])
    assert nomes == ["Bannach", "PauD'Arco", "Redenção", "Trairão"]
    assert dist.startswith("além dos distritos de Cachoeira da Serra") and dist.endswith("Altamira")
    assert cp.DO_MUNICIPIO.search(dist).group(1) == "Altamira"
    assert cp.municipios_da_nota(notas["10"])[0] == ["Abaetetuba", "Altamira", "Belém"]


def test_parentese_depois_do_nome_vira_excecao():
    """Na Região III do Pará: 'Altamira (exceto os distritos de ...)', com vírgula e 'e' dentro."""
    nomes, exc, dist = cp.municipios_da_nota(
        "Abaetetuba, Altamira (exceto os distritos de Cachoeira Grande e Castelo de Sonhos), Anapu e Belém")
    assert nomes == ["Abaetetuba", "Altamira", "Anapu", "Belém"] and dist is None
    assert exc == {"Altamira": "exceto os distritos de Cachoeira Grande e Castelo de Sonhos"}
    nomes, exc, _ = cp.municipios_da_nota("Anapu, Belém e Altamira (exceto os distritos de A e B)")
    assert nomes == ["Anapu", "Belém", "Altamira"] and exc == {"Altamira": "exceto os distritos de A e B"}


def test_grafia_conferida_so_no_estado_dela():
    """O anexo escreve 'Lagoa da Pedra' no Maranhão; o município é Lago da Pedra."""
    ibge = {cp.normaliza("Lago da Pedra"): (2105708, "Lago da Pedra")}
    assert cp.codigo_ibge("MA", "Lagoa da Pedra", ibge) == (2105708, "Lago da Pedra")
    assert cp.codigo_ibge("MA", "Lago da Pedra", ibge) == (2105708, "Lago da Pedra")
    assert cp.codigo_ibge("PA", "Lagoa da Pedra", ibge) is None
    assert cp.codigo_ibge("MA", "Lagoa do Mato", ibge) is None


def test_nome_sem_espaco_bate_com_o_do_ibge():
    """O anexo escreve "PauD'Arco"; o IBGE, "Pau D'Arco"."""
    assert cp.normaliza("PauD'Arco") == cp.normaliza("Pau D'Arco")
    assert cp.normaliza("São Félix do Xingu") == "saofelixdoxingu"


def test_linhas_da_tabela():
    pagina = ("<table><tr><td>UF</td><td>VAZIO SANITÁRIO</td><td>CALENDÁRIO DE SEMEADURA</td></tr>"
              "<tr><td><p>MT</p></td><td>08 de junho de 2026 a 06 de setembro de 2026</td>"
              "<td>07 de setembro de 2026 a 07 de janeiro de 2027</td></tr></table>")
    assert cp.linhas_da_tabela(pagina) == {
        "MT": ("08 de junho de 2026 a 06 de setembro de 2026", "07 de setembro de 2026 a 07 de janeiro de 2027")}


def test_municipio_fora_das_regioes_distingue_omissao_de_leitura_perdida(capsys):
    """Fora de todas as listas: aviso, se a portaria não o cita; falha, se o
    nome está no texto das notas e a leitura o perdeu."""
    ibge = {cp.normaliza(n): (c, n) for c, n in [(1, "Belém"), (2, "Bannach"), (3, "Redenção")]}
    regioes = [{"municipios": [2]}]
    problemas = cp.fora_das_regioes("PA", ibge, regioes, ["Bannach, Redenção e Trairão"])
    assert problemas == ["PA: Redenção (3) aparece nas notas, mas não entrou em região nenhuma"]
    assert "Belém (1) não está em região nenhuma" in capsys.readouterr().out


# ── troca de safra: a portaria mais nova do Diário Oficial e a tábua do ZARC ──

# Um trecho da página de busca do Diário Oficial como ela vem: os atos num JSON
# dentro de um <script>. O segundo é de outra cultura; o terceiro, do ZARC (da
# SPA/MAPA, que também usa a frase); o quarto, mais antigo, vem com o destaque
# da busca no título.
BUSCA = """<html><body><script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params"
 type="application/json">{"jsonArray":[
 {"title":"PORTARIA SDA/MAPA Nº 2.001, DE 7 DE ABRIL DE 2027","urlTitle":"portaria-sda/mapa-n-2.001-de-7-de-abril-de-2027-1",
  "pubDate":"08/04/2027","content":"Estabelece o <b>calendário de semeadura</b> da soja para a safra 2027/2028"},
 {"title":"PORTARIA SDA/MAPA Nº 2.002, DE 8 DE ABRIL DE 2027","urlTitle":"portaria-sda/mapa-n-2.002-de-8-de-abril-de-2027-2",
  "pubDate":"09/04/2027","content":"Estabelece o calendário de semeadura do algodão"},
 {"title":"PORTARIA SPA/MAPA Nº 391, DE 5 DE NOVEMBRO DE 2026","urlTitle":"portaria-spa/mapa-n-391-de-5-de-novembro-de-2026-3",
  "pubDate":"11/11/2026","content":"pode ser melhorada pela assistência técnica local"},
 {"title":"PORTARIA <span class='highlight' style='background:#FFA;'>SDA</span>/MAPA Nº 1.579, DE 9 DE ABRIL DE 2026",
  "urlTitle":"portaria-sda/mapa-n-1.579-de-9-de-abril-de-2026-698696654",
  "pubDate":"10/04/2026","content":"calendário de semeadura e vazio sanitário da soja, safra 2026/2027"}
 ]}</script></body></html>"""


def test_busca_do_diario_oficial_fica_com_as_portarias_da_sda():
    c = cp.candidatas(cp.resultados_da_busca(BUSCA))
    # Só as da SDA/MAPA, as mais novas primeiro: a do ZARC sai, e a do algodão
    # fica (a página inteira decide). O destaque da busca sai do título.
    assert [x["titulo"] for x in c] == ["PORTARIA SDA/MAPA Nº 2.002, DE 8 DE ABRIL DE 2027",
                                        "PORTARIA SDA/MAPA Nº 2.001, DE 7 DE ABRIL DE 2027",
                                        "PORTARIA SDA/MAPA Nº 1.579, DE 9 DE ABRIL DE 2026"]
    assert c[1]["url"] == "https://www.in.gov.br/web/dou/-/portaria-sda/mapa-n-2.001-de-7-de-abril-de-2027-1"
    assert c[2]["url"] == cp.DOU
    assert cp.resultados_da_busca("<html>formato novo</html>") == []


class _Resposta:
    def __init__(self, atos):
        self.text = ('<script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params">'
                     + __import__("json").dumps({"jsonArray": atos}) + "</script>")

    def raise_for_status(self):
        pass


def test_busca_no_dou_le_pagina_a_pagina(monkeypatch):
    """A página seguinte começa depois do último ato da anterior, e a busca para quando nada novo chega."""
    from datetime import date
    atos = [{"urlTitle": f"ato-{i}", "score": 0, "classPK": str(900 - i), "displayDateSortable": str(5000 - i)}
            for i in range(70)]
    pedidos = []

    def get(url, headers=None, timeout=None, params=None):
        pedidos.append(dict(params))
        if "id" not in params:
            return _Resposta(atos[:50])
        if params["id"] == "851":                      # depois do ato-49
            return _Resposta(atos[50:])
        return _Resposta(atos[50:])                     # a busca repetiu: nada novo
    monkeypatch.setattr(cp.requests, "get", get)
    lidos = cp.busca_no_dou(cp.FRASE_DOU, date(2025, 11, 16), date(2026, 11, 15))
    assert [a["urlTitle"] for a in lidos] == [f"ato-{i}" for i in range(70)]
    assert pedidos[0]["q"] == '"calendário de semeadura"' and pedidos[0]["delta"] == "50"
    assert (pedidos[0]["publishFrom"], pedidos[0]["publishTo"]) == ("16-11-2025", "15-11-2026")
    assert {k: pedidos[1][k] for k in ("currentPage", "newPage", "id", "displayDate")} == \
        {"currentPage": "1", "newPage": "2", "id": "851", "displayDate": "4951"}
    assert len(pedidos) == 3


def test_nome_da_portaria_e_safra_no_texto():
    assert cp.nome_da_portaria("PORTARIA SDA/MAPA Nº 1.579, DE 9 DE ABRIL DE 2026") == cp.PORTARIA
    assert cp.nome_da_portaria("PORTARIA SDA/MAPA Nº 2.001, DE 1º DE MARÇO DE 2027") == \
        "Portaria SDA/MAPA nº 2.001, de 1 de março de 2027"
    assert cp.safras_no_texto("para a safra 2027/2028 e a safra 2027/28; safra 2026/2030") == ["2027/2028"]


def test_safras_do_catalogo_do_zarc():
    recursos = [{"name": "Tábua de risco ZARC 2025/2026"}, {"name": "Tábua de risco ZARC 2026/2027"},
                {"name": "Dicionário de dados"}]
    assert cp.safras_do_zarc(recursos) == ["2025/2026", "2026/2027"]


def test_data_da_portaria():
    from datetime import date
    assert cp.data_da_portaria(cp.PORTARIA) == date(2026, 4, 9)
    assert cp.data_da_portaria("Portaria SDA/MAPA nº 2.001, de 1 de março de 2027") == date(2027, 3, 1)
    assert cp.data_da_portaria("Portaria nova") is None


ATUAL = {"safra": "2026/2027", "fonte": cp.PORTARIA, "url": cp.DOU}


def test_calendario_de_safra_nova_vale_logo():
    nova = {"safra": "2027/2028", "fonte": "Portaria SDA/MAPA nº 2.001, de 7 de abril de 2027", "url": "https://x"}
    assert cp.escolhe_calendario(ATUAL, nova) == (nova, False)
    # Sem a busca, ou com a mesma portaria, nada muda.
    assert cp.escolhe_calendario(ATUAL, None) == (ATUAL, False)
    assert cp.escolhe_calendario(ATUAL, dict(ATUAL)) == (ATUAL, False)
    # Uma portaria de safra mais velha (a busca não achou a em uso) não volta a safra.
    assert cp.escolhe_calendario(ATUAL, dict(nova, safra="2025/2026"))[0] is ATUAL


def test_portaria_posterior_da_mesma_safra_e_tentada():
    depois = {"safra": "2026/2027", "fonte": "Portaria SDA/MAPA nº 1.700, de 2 de setembro de 2026", "url": "https://y"}
    assert cp.escolhe_calendario(ATUAL, depois) == (depois, True)
    antes = dict(depois, fonte="Portaria SDA/MAPA nº 1.200, de 2 de janeiro de 2026")
    assert cp.escolhe_calendario(ATUAL, antes) == (ATUAL, False)


def test_tabua_do_zarc_acompanha_o_calendario(capsys):
    assert cp.tabua_para("2026/2027", ["2025/2026", "2026/2027"]) == "2026/2027"
    # A portaria da safra nova saiu e a tábua dela ainda não: fica a anterior, e o log diz.
    assert cp.tabua_para("2027/2028", ["2025/2026", "2026/2027"]) == "2026/2027"
    assert "ainda não saiu" in capsys.readouterr().out
    # Tábua de safra mais nova que o calendário não entra: as datas seriam de outra safra.
    assert cp.tabua_para("2026/2027", ["2026/2027", "2027/2028"]) == "2026/2027"
    import pytest
    with pytest.raises(SystemExit):
        cp.tabua_para("2026/2027", ["2027/2028"])


CAL = {"MT": [{"regiao": None, "vazio": ["2026-06-08", "2026-09-06"], "semeadura": ["2026-09-07", "2027-01-07"],
               "municipios": None, "excecoes": {}, "distritos": []}]}
LINHAS = [{"uf": "MT", "geocodigo": 5107925, "municipio": "Sorriso", "ciclo": 21, "solo": 13, "riscos": "0" * 36}]


def _coleta_fixa(monkeypatch, alvo=ATUAL, mesma_safra=False, tabua="2026/2027", cal=CAL, problemas=()):
    monkeypatch.setattr(cp, "descobre", lambda saida: {"atual": ATUAL, "alvo": alvo, "mesma_safra": mesma_safra,
                                                       "tabua": tabua, "recursos": []})
    lidas = []
    monkeypatch.setattr(cp, "calendario", lambda url: lidas.append(url) or cal)
    monkeypatch.setattr(cp, "le_calendario", lambda url: (cal, list(problemas)))
    monkeypatch.setattr(cp, "zarc", lambda recursos, safra: (LINHAS, {"recurso": "https://dados",
                                                                       "portarias": {"MT": "Port.202_de_03-07-2026"}}))
    return lidas


def test_coleta_sem_mudanca_nao_muda_a_data(monkeypatch, tmp_path):
    import json
    _coleta_fixa(monkeypatch)
    cp.grava(tmp_path)
    fontes = json.loads((tmp_path / "fontes_plantio.json").read_text(encoding="utf-8"))
    assert fontes["zarc"]["safra"] == "2026/2027"
    fontes["lido_em"] = "2026-11-01"
    (tmp_path / "fontes_plantio.json").write_text(json.dumps(fontes, ensure_ascii=False, indent=1) + "\n",
                                                   encoding="utf-8")
    cp.grava(tmp_path)
    assert json.loads((tmp_path / "fontes_plantio.json").read_text(encoding="utf-8"))["lido_em"] == "2026-11-01"
    # Com uma data mudada na portaria, a data da leitura muda também.
    _coleta_fixa(monkeypatch, cal={"MT": [dict(CAL["MT"][0], semeadura=["2026-09-10", "2027-01-07"])]})
    cp.grava(tmp_path)
    assert json.loads((tmp_path / "fontes_plantio.json").read_text(encoding="utf-8"))["lido_em"] != "2026-11-01"


def test_safra_nova_sem_tabua_grava_o_calendario_novo_com_a_tabua_anterior(monkeypatch, tmp_path):
    import json
    nova = {"safra": "2027/2028", "fonte": "Portaria SDA/MAPA nº 2.001, de 7 de abril de 2027", "url": "https://x"}
    _coleta_fixa(monkeypatch, alvo=nova, tabua="2026/2027")
    cp.grava(tmp_path)
    assert (tmp_path / "calendario_soja_2027_2028.json").exists()
    assert (tmp_path / "zarc_soja_2026_2027.csv").exists()
    fontes = json.loads((tmp_path / "fontes_plantio.json").read_text(encoding="utf-8"))
    assert (fontes["safra"], fontes["zarc"]["safra"]) == ("2027/2028", "2026/2027")
    assert fontes["calendario"] == {"fonte": nova["fonte"], "url": "https://x"}


def test_portaria_da_mesma_safra_que_nao_se_le_vira_aviso(monkeypatch, tmp_path):
    import json
    depois = {"safra": "2026/2027", "fonte": "Portaria SDA/MAPA nº 1.700, de 2 de setembro de 2026", "url": "https://y"}
    lidas = _coleta_fixa(monkeypatch, alvo=depois, mesma_safra=True, problemas=["PA: sem linha na tabela"])
    aviso = tmp_path / "aviso.md"
    cp.grava(tmp_path / "plantio", aviso)
    # Segue na portaria em uso, e o aviso tem o título da issue e o que não bateu.
    assert lidas == [cp.DOU]
    fontes = json.loads((tmp_path / "plantio" / "fontes_plantio.json").read_text(encoding="utf-8"))
    assert fontes["calendario"]["fonte"] == cp.PORTARIA
    titulo, *corpo = aviso.read_text(encoding="utf-8").splitlines()
    assert titulo == "Calendário de semeadura: conferir a Portaria SDA/MAPA nº 1.700, de 2 de setembro de 2026"
    assert "- PA: sem linha na tabela" in corpo and any("https://y" in x for x in corpo)


def test_portaria_da_mesma_safra_com_o_calendario_inteiro_passa_a_valer(monkeypatch, tmp_path):
    import json
    depois = {"safra": "2026/2027", "fonte": "Portaria SDA/MAPA nº 1.700, de 2 de setembro de 2026", "url": "https://y"}
    _coleta_fixa(monkeypatch, alvo=depois, mesma_safra=True)
    aviso = tmp_path / "aviso.md"
    cp.grava(tmp_path / "plantio", aviso)
    assert not aviso.exists()
    fontes = json.loads((tmp_path / "plantio" / "fontes_plantio.json").read_text(encoding="utf-8"))
    assert fontes["calendario"] == {"fonte": depois["fonte"], "url": "https://y"}


def test_safra_em_uso_vem_da_ultima_coleta(tmp_path):
    assert cp.safra_em_uso(tmp_path) == {"safra": cp.SAFRA, "fonte": cp.PORTARIA, "url": cp.DOU}
    (tmp_path / "fontes_plantio.json").write_text(
        '{"safra": "2027/2028", "calendario": {"fonte": "Portaria nova", "url": "https://x"}}', encoding="utf-8")
    assert cp.safra_em_uso(tmp_path) == {"safra": "2027/2028", "fonte": "Portaria nova", "url": "https://x"}
