# -*- coding: utf-8 -*-
"""O idioma das frases da API (idioma.py): o aplicativo em inglês recebe as
frases do preço e do custo em inglês, com os mesmos números e as mesmas regras;
sem pedido de idioma, tudo segue em português, como o painel exibe.

Rode com:  python -m pytest software -q
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import estados  # noqa: E402
import financas  # noqa: E402
from idioma import idioma, mes_por_extenso_en, periodo_curto_en, ordinal_en, textos_en  # noqa: E402


def test_idioma_do_pedido():
    assert idioma() == "pt"
    assert idioma("en") == "en" and idioma("EN-us") == "en" and idioma("es") == "pt"
    assert idioma(None, "en-US,en;q=0.9") == "en"
    assert idioma(None, "pt-BR,pt;q=0.9,en;q=0.8") == "pt"
    # Como o Android: o primeiro idioma que existe, na ordem de preferência.
    assert idioma(None, "es-ES,es;q=0.9,en-US;q=0.8") == "en"
    assert idioma(None, "es-ES") == "pt"
    assert idioma(None, "fr;q=0.5,en;q=0.9") == "en"
    assert idioma(None, "en;q=0") == "pt"
    # O parâmetro vale mais que o cabeçalho.
    assert idioma("pt", "en-US") == "pt"


def test_datas_e_numeros_em_ingles():
    assert mes_por_extenso_en("MAR-2026") == "March 2026" and mes_por_extenso_en("???") is None
    assert periodo_curto_en("mar/2023 a mar/2026") == "Mar/2023 to Mar/2026"
    assert [ordinal_en(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"]


def _somar_meses(base: date, n: int) -> date:
    total = base.month - 1 + n
    return date(base.year + total // 12, total % 12 + 1, 1)


@pytest.fixture
def publicado() -> date:
    sigla, _, ano = financas.LEVANTAMENTO["levantamento"].partition("-")
    return date(int(ano), financas.MESES_SIGLA[sigla.upper()], 1)


def test_avisos_em_ingles_com_os_mesmos_limites(publicado):
    """Os avisos em inglês calam e falam nos mesmos meses que os em português."""
    for meses in (2, 8, 15):
        dia = _somar_meses(publicado, meses)
        assert (financas.aviso_de_defasagem(dia) is None) == (financas.aviso_de_defasagem(dia, "en") is None)
        assert (financas.aviso_sobre_o_custo(dia) is None) == (financas.aviso_sobre_o_custo(dia, "en") is None)
    quando = mes_por_extenso_en(financas.LEVANTAMENTO["levantamento"])
    oito = financas.aviso_de_defasagem(_somar_meses(publicado, 8), "en")
    assert oito.startswith(f"This survey is from {quando}, 8 months ago.") and "price" in oito
    quinze = financas.aviso_de_defasagem(_somar_meses(publicado, 15), "en")
    assert "(more than a year)" in quinze and "historical reference" in quinze
    assert "cost field" in financas.aviso_sobre_o_custo(_somar_meses(publicado, 8), "en")
    # O padrão continua em português.
    assert "preço" in financas.aviso_de_defasagem(_somar_meses(publicado, 8))


def test_descricao_e_nota_do_preco_em_ingles():
    lev = financas.LEVANTAMENTO
    assert financas.descricao_do_levantamento() == lev["textos"]["descricao"]
    assert financas.nota_sobre_o_preco() == lev["textos"]["nota_preco"]
    assert financas.descricao_do_levantamento("en") == (
        f"CONAB, {lev['praca']}, {mes_por_extenso_en(lev['levantamento'])}")
    nota = financas.nota_sobre_o_preco("en")
    s = lev["serie"]
    assert nota.startswith(f"R$ {lev['preco_recebido_saca']:,.2f}/bag is ")
    assert f"of the {s['levantamentos']} surveys" in nota and f"median R$ {s['mediana_saca']:,.2f}" in nota
    # A mesma regra do gerador: metade de baixo da série é cenário conservador.
    conservador = "Cenário conservador" in lev["textos"]["nota_preco"]
    assert ("Conservative scenario" in nota) == conservador


def test_nota_dos_outros_estados_em_ingles():
    lev = estados.levantamento_da_praca("SORRISO-MT", "Sorriso (MT)", "MAR-2026", "março de 2026")
    t = textos_en(lev)
    assert t["descricao"] == "CONAB, Sorriso (MT), March 2026"
    assert t["nota_preco"] == ("R$ 103.90/bag is the price received in Sorriso (MT) in CONAB's March 2026 "
                               "survey. Reference scenario, not a price forecast.")
