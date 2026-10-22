# -*- coding: utf-8 -*-
"""Testes do registro automático do DOI (registra_doi.py)."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import registra_doi as r  # noqa: E402

COMANDO = (r"LC_ALL=C find . \( -name '*.py' -o -name '*.kt' -o -name '*.kts' \) "
           r"-not -path './.git/*' -not -path '*/build/*' -not -path '*__pycache__*' "
           r"-not -path '*/.gradle/*' | LC_ALL=C sort | xargs sha256sum | sha256sum")


def test_resumo_igual_ao_comando_do_registro(tmp_path):
    """O resumo em Python tem de dar o mesmo valor do comando da seção 9.1."""
    arquivos = {"a.py": "x = 1\n", "B.kt": "fun f() = 1\n", "app/build.gradle.kts": "plugins {}\n",
                "app/build/gerado.kt": "ignorar\n", "pkg/__pycache__/m.py": "ignorar\n",
                "z/.gradle/x.kts": "ignorar\n", "leia.md": "fora\n", "pkg/Ção.py": "y = 2\nz = 3\n"}
    for nome, conteudo in arquivos.items():
        p = tmp_path / nome
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(conteudo, encoding="utf-8")
    esperado = subprocess.run(COMANDO, shell=True, cwd=tmp_path, capture_output=True, text=True).stdout.split()[0]
    n, linhas, sha = r.resumo(tmp_path)
    assert (n, linhas, sha) == (4, 5, esperado)


def test_le_a_linha_da_tabela():
    texto = r.REGISTRO.read_text(encoding="utf-8")
    assert r.resumo_registrado(texto, "v2.4.6") == (
        99, 18438, "c96b5a6c643a2d15dd8187f7835418ea04bd9672c9856c0f8338e848bfd28444")
    assert r.resumo_registrado(texto, "v9.9.9") is None


PREPARADO = """Texto anterior.

O resumo criptográfico da `v9.9.9` foi calculado sobre o commit de merge
`abc1234`. A preparação da versão altera apenas este `REGISTRO_INPI.md` e o
`CITATION.cff`, de modo que o valor deve se manter na etiqueta; convém
conferi-lo sobre uma cópia limpa dela depois de etiquetar.

## 12. Referências

- **DOI da `v9.9.8`:** 10.5281/zenodo.1
- **DOI da versão mais recente (`v9.9.9`):** a preencher após a publicação do Release
"""


def test_registra_troca_o_a_preencher_e_a_conferencia():
    novo = r.registra(PREPARADO, "v9.9.9", "10.5281/zenodo.99", "def5678", "23/10/2026")
    assert "- **DOI da versão mais recente (`v9.9.9`):** 10.5281/zenodo.99" in novo
    assert "a preencher" not in novo
    corrido = " ".join(novo.split())
    assert "Conferido depois de etiquetar, sobre uma cópia limpa da `v9.9.9` (commit `def5678`)" in corrido
    assert "O DOI de versão desta etiqueta é 10.5281/zenodo.99" in corrido
    assert "deve se manter" not in corrido
    assert novo.startswith("Texto anterior.\n\n")
    assert all(len(l) <= 80 for l in novo.split("\n\n")[1].splitlines())


def test_registro_sem_a_preparacao_nao_e_editado():
    with pytest.raises(ValueError):
        r.registra(PREPARADO, "v9.9.7", "10.5281/zenodo.99", "def5678", "23/10/2026")


def test_acha_o_doi_pela_versao():
    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"hits": {"hits": [
                {"metadata": {"version": "v2.4.6"}, "doi": "10.5281/zenodo.23575177"},
                {"metadata": {"version": "v2.4.7"}, "pids": {"doi": {"identifier": "10.5281/zenodo.42"}}},
            ]}}

    class Sessao:
        def get(self, *a, **k):
            return Resposta()

    assert r.doi_da_versao("v2.4.7", Sessao()) == "10.5281/zenodo.42"
    assert r.doi_da_versao("v2.4.8", Sessao()) is None


# ── versão nova, sem preparação manual ───────────────────────────────────────

MUD = {"A": ["software/x/novo.py"], "M": ["software/x/a.kt", "software/x/b.py"], "D": []}
RESUMO = (103, 19000, "f" * 64)


def _nova(texto, titulo="v9.9.9 — Tela nova no aplicativo"):
    return r.registra_nova(texto, "v9.9.9", r.ultima_registrada(texto), RESUMO, "abc1234",
                           "10.5281/zenodo.77", "24/10/2026", titulo, MUD)


def test_versao_nova_ganha_linha_texto_e_referencia():
    texto = r.REGISTRO.read_text(encoding="utf-8")
    anterior = r.ultima_registrada(texto)
    novo = _nova(texto)
    # linha na tabela, logo abaixo da versão anterior, e o script a reconhece
    linhas = novo.splitlines()
    i = next(k for k, l in enumerate(linhas) if l.startswith(f"| Tag `{anterior}`"))
    assert linhas[i + 1] == ("| Tag `v9.9.9` (24/10/2026) — tela nova no aplicativo | 103 | 19.000 | `"
                             + "f" * 64 + "` |")
    assert r.resumo_registrado(novo, "v9.9.9") == (103, 19000, "f" * 64)
    assert r.ultima_registrada(novo) == "v9.9.9"
    # texto da versão antes do parágrafo de referência
    corrido = " ".join(novo.split())
    assert (f"Em relação à `{anterior}`, entra 1 arquivo-fonte (`software/x/novo.py`); "
            "mudam 2 (`software/x/a.kt` e `software/x/b.py`).") in corrido
    assert "O DOI de versão desta etiqueta é 10.5281/zenodo.77" in corrido
    assert corrido.index("A `v9.9.9` foi registrada") < corrido.index(" ".join(r.ANCORA_TEXTO.split()))
    # referências: a anterior deixa de ser a "mais recente"
    assert "- **DOI da versão mais recente (`v9.9.9`):** 10.5281/zenodo.77" in novo
    assert f"- **DOI da versão mais recente (`{anterior}`)" not in novo
    assert f"- **DOI da `{anterior}`:**" in novo
    # o resto do documento não muda
    assert len(novo.splitlines()) > len(texto.splitlines())
    assert novo.replace("\n", "").count("10.5281/zenodo.21286115") == texto.replace("\n", "").count("10.5281/zenodo.21286115")


def test_versao_nova_sem_mudanca_de_codigo():
    texto = r.REGISTRO.read_text(encoding="utf-8")
    novo = r.registra_nova(texto, "v9.9.9", r.ultima_registrada(texto), RESUMO, "abc1234",
                           "10.5281/zenodo.77", "24/10/2026", "", {"A": [], "M": [], "D": []})
    assert "Nenhum arquivo-fonte muda em relação à" in " ".join(novo.split())
    assert "registrada na publicação do Release | 103 |" in novo


def test_citacao_ganha_versao_e_data():
    cff = 'cff-version: 1.2.0\nversion: "2.4.7"\ndate-released: "2026-10-22"\n'
    assert r.atualiza_citacao(cff, "v2.4.8", "24/10/2026") == \
        'cff-version: 1.2.0\nversion: "2.4.8"\ndate-released: "2026-10-24"\n'
