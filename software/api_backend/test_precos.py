# -*- coding: utf-8 -*-
"""Testes dos avisos de idade do levantamento e dos componentes do custo.

O preço é o parâmetro que dirige quase toda a margem exibida pelo produto, e o
padrão vem do levantamento da CONAB, bimestral. O que é testado aqui é o
produto avisar quando o levantamento envelhece e o custo fechar com a soma dos
componentes. Os testes da cotação física da Notícias Agrícolas saíram com a
fonte, em 14/11/2026 (o site passou a barrar acesso automático).

Rode com:  python -m pytest software -q
"""
import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import financas  # noqa: E402


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

def test_componentes_do_custo_somam_o_custo_operacional():
    """Na produtividade e no preço de referência, área + transporte + CESSR dão
    de volta o custo operacional por hectare da CONAB: os componentes só
    redistribuem o custo, não o mudam."""
    lev = financas.LEVANTAMENTO
    c = lev.get("custo_por_componente")
    assert c, "o levantamento em uso tem o custo aberto por item"
    prod = lev["produtividade_referencia_sc_ha"]
    soma = c["area_ha"] + (c["transporte_saca"] + c["taxa_receita"] * lev["preco_recebido_saca"]) * prod
    assert abs(soma - lev["custo_operacional_ha"]) < 1.0
    # Quase tudo é por hectare: o que anda com a produção é transporte e CESSR.
    assert c["area_ha"] > 0.9 * lev["custo_operacional_ha"]
