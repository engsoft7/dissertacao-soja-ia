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
