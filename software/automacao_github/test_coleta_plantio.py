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
    nomes, obs = cp.municipios_da_nota(notas["5"])
    assert nomes == ["Alto Parnaíba", "Balsas", "São Raimundo das Mangabeiras", "Tasso Fragoso"] and obs is None
    nomes, obs = cp.municipios_da_nota(notas["8"])
    assert nomes == ["Bannach", "PauD'Arco", "Redenção", "Trairão"]
    assert obs.startswith("além dos distritos de Cachoeira da Serra") and obs.endswith("Altamira")
    assert cp.municipios_da_nota(notas["10"])[0] == ["Abaetetuba", "Altamira", "Belém"]


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
