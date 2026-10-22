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
