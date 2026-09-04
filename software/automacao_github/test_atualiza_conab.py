# -*- coding: utf-8 -*-
"""Testes do coletor de custos da CONAB.

O que é exercitado aqui é a parte que decide o que entra na base do produto:
reconhecer a planilha, acrescentar levantamento sem apagar história, relatar
revisão de valor já publicado e não sujar o diff com mudança de formato. O
download em si não é testado — depende do portal da CONAB estar no ar e do
endereço configurado, e é justamente por isso que existe o modo --testar.

Rode com:  python -m pytest software -q
"""
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import atualiza_conab as coletor  # noqa: E402

ORIGINAIS = RAIZ / "pesquisa" / "dados" / "conab"


@pytest.fixture
def conab(tmp_path, monkeypatch):
    """Cópia descartável da pasta de dados, para os testes gravarem à vontade."""
    destino = tmp_path / "conab"
    shutil.copytree(ORIGINAIS, destino)
    monkeypatch.setattr(coletor, "CONAB", destino)
    return destino


def test_reconhece_as_planilhas_do_portal():
    """Cada arquivo já versionado tem que ser identificado como ele mesmo.

    A identificação é pelo cabeçalho, e não pelo nome, porque o portal exporta
    tudo como "dados.csv" — o usuário não deve ter que renomear nada.
    """
    for nome in coletor.PLANILHAS:
        texto = (ORIGINAIS / nome).read_text(encoding="utf-8")
        assert coletor.identificar(texto)[0] == nome


def test_recusa_o_que_nao_e_planilha_da_conab():
    """Portal fora do ar devolve HTML com status 200. Gravar isso apagaria a
    base — a recusa é o comportamento certo."""
    with pytest.raises(coletor.ConteudoInesperado):
        coletor.identificar("<!doctype html><html><body>Erro</body></html>")


def test_ida_e_volta_nao_altera_o_arquivo(conab):
    """Reescrever sem mudança nenhuma tem que produzir bytes idênticos.

    Se o formato mudasse na volta (aspas em todas as colunas, por exemplo), o
    diff do PR mensal viria com o arquivo inteiro alterado e a mudança real do
    levantamento ficaria invisível na revisão.
    """
    for nome in coletor.PLANILHAS:
        texto = (conab / nome).read_text(encoding="utf-8")
        _, mudancas = coletor.aplicar(texto)
        assert mudancas == [], f"{nome} acusou mudança sem haver"
        assert (conab / nome).read_text(encoding="utf-8") == texto


def test_levantamento_novo_entra_sem_apagar_a_serie(conab):
    """A série histórica é acumulada, não substituída."""
    arquivo = conab / "serie_pedro_afonso_to.csv"
    antes = arquivo.read_text(encoding="utf-8")
    novo = antes + '"JUL-2026";9.4;25.3;86.1;121.5;71.04;35.4;10.1\n'

    nome, mudancas = coletor.aplicar(novo)
    assert nome == "serie_pedro_afonso_to.csv"
    assert mudancas == ["levantamento novo: JUL-2026"]

    depois = arquivo.read_text(encoding="utf-8")
    assert "MAR-2023" in depois, "a série perdeu o começo"
    assert depois.count("\n") == antes.count("\n") + 1


def test_revisao_de_valor_publicado_e_relatada(conab):
    """A CONAB revisa levantamento já publicado, e o painel cita esses números.

    Uma revisão pode entrar — mas nunca calada: tem que aparecer no relato que
    vira corpo do PR, para a conferência humana ver o que mudou.
    """
    arquivo = conab / "serie_pedro_afonso_to.csv"
    revisado = arquivo.read_text(encoding="utf-8").replace(
        '"MAR-2026";9.12;24.91;85.03;105.09', '"MAR-2026";9.12;24.91;85.03;111.4')

    _, mudancas = coletor.aplicar(revisado)
    assert len(mudancas) == 1
    assert "revisão em MAR-2026" in mudancas[0]
    assert "105.09" in mudancas[0] and "111.4" in mudancas[0]


def test_simular_nao_grava(conab):
    arquivo = conab / "serie_pedro_afonso_to.csv"
    antes = arquivo.read_text(encoding="utf-8")
    _, mudancas = coletor.aplicar(
        antes + '"JUL-2026";9.4;25.3;86.1;121.5;71.04;35.4;10.1\n', simular=True)
    assert mudancas, "a simulação tem que dizer o que mudaria"
    assert arquivo.read_text(encoding="utf-8") == antes


def test_defasagem_e_contada_em_meses():
    """A única verificação que funciona sem rede: quantos meses o levantamento
    em uso tem. É o que permite avisar que provavelmente há um mais recente."""
    rotulo, meses = coletor.meses_de_defasagem()
    assert rotulo == "MAR-2026"
    assert meses >= 0

# ── descoberta automática da fonte ───────────────────────────────────────────

BASE = "https://portaldeinformacoes.conab.gov.br/custos-de-producao.html"


def test_links_ignoram_estaticos_e_a_propria_pagina():
    """Numa página de painéis, a maioria dos links é imagem, script e folha de
    estilo. E a própria página casa com "custo" no caminho: sem excluí-la, ela
    viraria candidata de si mesma."""
    html = ('<a href="/downloads/arquivos/CustoProducao.csv">b</a>'
            '<img src="logo.png"><link href="a.css"><script src="app.js">'
            '<a href="/custos-de-producao.html">a própria página</a>'
            '<a href="https://outro.gov.br/serie.xlsx">x</a>')
    achados = coletor._links_de_html(html, BASE)
    assert achados == [
        "https://portaldeinformacoes.conab.gov.br/downloads/arquivos/CustoProducao.csv",
        "https://outro.gov.br/serie.xlsx",
    ]


def test_url_explicita_vem_primeiro_e_nao_repete(monkeypatch):
    """Quem configurou a variável sabe mais sobre o portal que a heurística."""
    monkeypatch.setattr(coletor, "_candidatas_do_catalogo",
                        lambda: ["https://a/1.csv", "https://b/2.csv"])
    monkeypatch.setattr(coletor, "_candidatas_do_portal",
                        lambda: ["https://b/2.csv", "https://c/3.csv"])
    achados = coletor.descobrir_fontes("https://b/2.csv")
    assert achados[0] == "https://b/2.csv"
    assert achados == ["https://b/2.csv", "https://a/1.csv", "https://c/3.csv"]


def test_descoberta_tem_teto(monkeypatch):
    """Uma página cheia de links não pode virar varredura."""
    monkeypatch.setattr(coletor, "_candidatas_do_catalogo", lambda: [])
    monkeypatch.setattr(coletor, "_candidatas_do_portal",
                        lambda: [f"https://x/{i}.csv" for i in range(50)])
    assert len(coletor.descobrir_fontes()) == coletor.MAX_CANDIDATAS


def test_candidata_errada_e_descartada_e_a_certa_fica(monkeypatch):
    """O que torna a descoberta segura não é acertar a URL: é recusar tudo o
    que não tenha o cabeçalho de uma planilha da CONAB. Portal fora do ar
    devolve HTML com status 200, e gravá-lo apagaria a base."""
    planilha = (ORIGINAIS / "serie_pedro_afonso_to.csv").read_text(encoding="utf-8")
    paginas = {
        "https://x/erro.html": "<!doctype html><body>Erro 500</body>",
        "https://x/outra.csv": "coluna;outra\n1;2\n",
        "https://x/serie.csv": planilha,
    }
    monkeypatch.setattr(coletor, "_candidatas_do_catalogo", lambda: [])
    monkeypatch.setattr(coletor, "_candidatas_do_portal", lambda: list(paginas))
    monkeypatch.setattr(coletor, "baixar", lambda u, tempo=30: paginas[u])

    achadas, relato = coletor.coletar()
    assert len(achadas) == 1
    assert achadas[0] == planilha
    assert sum("não é planilha da CONAB" in l for l in relato) == 2


def test_fonte_fora_do_ar_nao_derruba_a_coleta(monkeypatch):
    """Uma candidata que não baixa é relatada e a próxima segue."""
    planilha = (ORIGINAIS / "custo_producao_por_uf.csv").read_text(encoding="utf-8")

    def baixar(url, tempo=30):
        if url.endswith("morta.csv"):
            raise OSError("connection reset")
        return planilha

    monkeypatch.setattr(coletor, "_candidatas_do_catalogo", lambda: [])
    monkeypatch.setattr(coletor, "_candidatas_do_portal",
                        lambda: ["https://x/morta.csv", "https://x/viva.csv"])
    monkeypatch.setattr(coletor, "baixar", baixar)

    achadas, relato = coletor.coletar()
    assert len(achadas) == 1
    assert any("não baixou" in l for l in relato)
