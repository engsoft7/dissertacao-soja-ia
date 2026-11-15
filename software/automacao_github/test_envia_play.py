# -*- coding: utf-8 -*-
"""envia_play.py: as notas cabem no limite do Play, e sem a chave nada é enviado."""
import envia_play


def test_notas_curtas_ficam_como_estao():
    assert envia_play.notas_da_versao("  App 2.9.0:\n janela de plantio ") == "App 2.9.0: janela de plantio"


def test_notas_longas_cortam_numa_palavra():
    longas = "palavra " * 100
    notas = envia_play.notas_da_versao(longas)
    assert len(notas) <= envia_play.LIMITE_NOTAS
    assert notas.endswith("palavra…")


def test_sem_chave_nao_envia(monkeypatch, capsys):
    monkeypatch.delenv("PLAY_SERVICE_ACCOUNT_JSON", raising=False)
    assert envia_play.main(["app-release.aab", "notas"]) == 0
    assert "não configurado" in capsys.readouterr().out
