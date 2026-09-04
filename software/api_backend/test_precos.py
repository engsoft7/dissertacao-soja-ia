# -*- coding: utf-8 -*-
"""Testes das cotações e dos avisos de idade do levantamento.

O preço é o parâmetro que dirige quase toda a margem exibida pelo produto, e
tem duas fontes de natureza diferente: o levantamento da CONAB, bimestral, e o
físico de Paranaguá, diário. O que é testado aqui é o que separa um número
confiável de um inventado — a extração recusar lixo, a falha de rede não virar
cotação, e o produto avisar quando o levantamento envelhece.

Rode com:  python -m pytest software -q
"""
import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import financas  # noqa: E402


# ── extração do físico em Paranaguá ──────────────────────────────────────────

def test_extrai_o_preco_e_ignora_a_coluna_de_variacao():
    """A tabela da fonte traz variação e volume ao lado da cotação. Pegar a
    coluna errada publicaria "-2,15" ou um total em milhares como preço."""
    html = ('<tr><td>Paranaguá</td><td>-2,15</td><td>1.250.000,00</td>'
            '<td>131,50</td></tr>')
    assert financas.extrair_preco_paranagua(html) == 131.50


def test_extracao_devolve_none_quando_nao_ha_numero_plausivel():
    """Sem cotação na faixa, None — e nunca um número qualquer da página."""
    assert financas.extrair_preco_paranagua(
        "<tr><td>Paranaguá</td><td>-2,15</td></tr>") is None
    assert financas.extrair_preco_paranagua(
        "<tr><td>Rondonópolis</td><td>120,00</td></tr>") is None
    assert financas.extrair_preco_paranagua("<html>fora do ar</html>") is None


def test_falha_de_rede_nao_vira_cotacao(monkeypatch):
    """Exibir um valor de reserva como se fosse a cotação do dia é pior que não
    exibir cotação nenhuma. Foi assim que a versão anterior mostrou R$ 120,00
    inventados como preço recebido pelo produtor."""
    def cai(*_a, **_k):
        raise OSError("sem rede")

    monkeypatch.setattr(financas.urllib.request, "urlopen", cai)
    assert financas.buscar_preco_paranagua() is None


# ── idade do levantamento ────────────────────────────────────────────────────

def _somar_meses(base: date, n: int) -> date:
    total = base.month - 1 + n
    return date(base.year + total // 12, total % 12 + 1, 1)


@pytest.fixture
def publicado() -> date:
    sigla, _, ano = financas.LEVANTAMENTO["levantamento"].partition("-")
    return date(int(ano), financas.MESES_SIGLA[sigla.upper()], 1)


def test_aviso_do_custo_acompanha_o_do_preco(publicado):
    """Quando o produtor informa o próprio preço, o aviso do preço perde
    sentido — mas o custo continua saindo do mesmo levantamento e entrando na
    margem. Sem o aviso do custo, informar o preço próprio faria o produto
    parecer atualizado com metade da conta velha."""
    # Dentro da cadência da CONAB, os dois calam.
    assert financas.aviso_de_defasagem(_somar_meses(publicado, 2)) is None
    assert financas.aviso_sobre_o_custo(_somar_meses(publicado, 2)) is None
    # Fora dela, os dois falam, cada um do seu lado da conta.
    velho = _somar_meses(publicado, 8)
    assert "preço" in (financas.aviso_de_defasagem(velho) or "")
    aviso_custo = financas.aviso_sobre_o_custo(velho)
    assert aviso_custo and "custo" in aviso_custo
    assert "campo de custo" in aviso_custo


def test_rotulo_ilegivel_nao_derruba_o_aviso(monkeypatch):
    """Um levantamento com rótulo inesperado tem que calar, não estourar: estas
    funções são chamadas na montagem de toda resposta da API."""
    monkeypatch.setitem(financas.LEVANTAMENTO, "levantamento", "???")
    assert financas.meses_desde_o_levantamento() is None
    assert financas.aviso_de_defasagem() is None
    assert financas.aviso_sobre_o_custo() is None

# ── cotações por praça ───────────────────────────────────────────────────────

import precos  # noqa: E402

PAGINA = """
<table>
<tr><td>Paranaguá</td><td>-2,15</td><td>1.250.000,00</td><td>131,50</td></tr>
<tr><td>Barcarena</td><td>+1,05</td><td>118,40</td></tr>
<tr><td>Sorriso</td><td>112,00</td></tr>
<tr><td>Santarém</td><td>sem negócio</td></tr>
<tr><td>Rondonópolis</td><td>0,00</td></tr>
</table>
"""


def test_praca_do_para_vem_antes_do_porto_do_sul():
    """O produtor paraense não recebe o preço de Paranaguá. Entre uma cotação
    do corredor do Pará e uma do Paraná, a do Pará é a que importa."""
    achados = precos.extrair_precos(PAGINA)
    assert precos.preferida(achados)["praca"] == "Barcarena"
    nomes = [a["praca"] for a in achados]
    assert nomes.index("Barcarena") < nomes.index("Paranaguá")


def test_ignora_variacao_e_volume_da_mesma_linha():
    """Na linha de Paranaguá há -2,15 e 1.250.000,00 antes da cotação."""
    achados = {a["praca"]: a["valor"] for a in precos.extrair_precos(PAGINA)}
    assert achados["Paranaguá"] == 131.50
    assert achados["Barcarena"] == 118.40


def test_praca_sem_numero_plausivel_fica_de_fora():
    """Melhor não ter cotação do que publicar a coluna errada. Santarém aparece
    na página sem preço, e Rondonópolis só com 0,00."""
    achados = {a["praca"] for a in precos.extrair_precos(PAGINA)}
    assert "Santarém" not in achados
    assert "Rondonópolis" not in achados


def test_pagina_sem_pracas_conhecidas():
    assert precos.extrair_precos("<html>fora do ar</html>") == []
    assert precos.preferida([]) is None


def test_falha_de_rede_devolve_lista_vazia(monkeypatch):
    """Nunca valor de reserva: número inventado exibido como cotação do dia é
    pior que cotação nenhuma."""
    def cai(*_a, **_k):
        raise OSError("sem rede")

    monkeypatch.setattr(precos.urllib.request, "urlopen", cai)
    assert precos.buscar_precos() == []


def test_descricao_diz_praca_uf_e_tipo():
    """A tela precisa dizer de onde veio o número: porto e terminal não são
    preço de porteira."""
    achado = precos.preferida(precos.extrair_precos(PAGINA))
    assert precos.descricao(achado) == "Barcarena (PA), porto"
