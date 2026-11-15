# -*- coding: utf-8 -*-
"""envia_play.py: as notas cabem no limite do Play, sem a chave nada é enviado, e
uma recusa da loja vira uma explicação no log, sem confirmar a edição."""
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


# ── uma API de mentira, com as mesmas chamadas encadeadas da de verdade ──────

class Recusa(Exception):
    """Como o HttpError da biblioteca do Google: traz a resposta e o motivo."""

    def __init__(self, status, reason):
        super().__init__(reason)
        self.resp = type("Resposta", (), {"status": status})()
        self.reason = reason


class Chamada:
    def __init__(self, f):
        self.f = f

    def execute(self):
        return self.f()


class Api:
    FAIXAS = [{"track": "production", "releases": []},
              {"track": "alpha", "releases": [{"versionCodes": ["31"], "status": "completed"}]},
              {"track": "internal"}]

    def __init__(self, faixas_recusadas=(), pacote_recusado=None):
        self.faixas_recusadas, self.pacote_recusado = dict(faixas_recusadas), pacote_recusado
        self.feitas, self.corpo = [], None

    def edits(self): return self
    def bundles(self): return self
    def tracks(self): return self

    def _faz(self, nome, resultado=None, erro=None):
        def f():
            self.feitas.append(nome)
            if erro:
                raise erro
            return resultado
        return Chamada(f)

    def insert(self, **k): return self._faz("insert", {"id": "e1"})
    def delete(self, **k): return self._faz("delete")
    def commit(self, **k): return self._faz("commit")
    def list(self, **k): return self._faz("list", {"tracks": self.FAIXAS})

    def upload(self, **k):
        return self._faz("upload", {"versionCode": 32}, self.pacote_recusado)

    def update(self, **k):
        self.corpo = k["body"]
        return self._faz("update:" + k["track"], erro=self.faixas_recusadas.get(k["track"]))


def test_envio_que_da_certo_confirma_a_edicao(monkeypatch, capsys):
    monkeypatch.setattr(envia_play, "_arquivo", lambda aab: aab)
    api = Api()
    assert envia_play.envia(api, "app.aab", "App 2.9.0", "alpha") == 0
    assert api.feitas == ["insert", "upload", "update:alpha", "commit"]
    assert api.corpo["releases"][0]["versionCodes"] == ["32"]
    assert api.corpo["releases"][0]["releaseNotes"] == [{"language": "pt-BR", "text": "App 2.9.0"}]
    assert "Versão 32 enviada à faixa alpha" in capsys.readouterr().out


def test_producao_recusada_explica_e_nao_confirma(monkeypatch, capsys):
    """O caso de 15/11/2026: a chave valia, e a loja recusou a faixa de produção."""
    monkeypatch.setattr(envia_play, "_arquivo", lambda aab: aab)
    api = Api(faixas_recusadas={"production": Recusa(400, "Precondition check failed.")})
    assert envia_play.envia(api, "app.aab", "App 2.9.0", "production") == 1
    assert "commit" not in api.feitas
    saida = capsys.readouterr().out
    assert "::error::A Google Play recusou a versão 32 na faixa production (400: Precondition check failed.)" in saida
    assert "PLAY_FAIXA" in saida and "Nada mudou na loja" in saida
    # As faixas do app ajudam a escolher a certa.
    assert "Faixa do app na loja: alpha (teste fechado): versão 31 (completed)" in saida
    assert "Faixa do app na loja: internal (teste interno): sem versão" in saida


def test_pacote_recusado_e_app_em_rascunho(monkeypatch, capsys):
    monkeypatch.setattr(envia_play, "_arquivo", lambda aab: aab)
    api = Api(pacote_recusado=Recusa(403, "Version code 32 has already been used."))
    assert envia_play.envia(api, "app.aab", "notas", "alpha") == 1
    assert api.feitas == ["insert", "upload"]
    assert "recusou o pacote (403: Version code 32 has already been used.)" in capsys.readouterr().out
    api = Api(faixas_recusadas={"alpha": Recusa(400, "Only releases with status draft may be created on draft app.")})
    assert envia_play.envia(api, "app.aab", "notas", "alpha") == 1
    assert "a primeira é lançada pelo Play Console" in capsys.readouterr().out


def test_erro_que_nao_e_da_loja_nao_e_engolido(monkeypatch):
    import pytest
    monkeypatch.setattr(envia_play, "_arquivo", lambda aab: aab)
    api = Api(faixas_recusadas={"alpha": ConnectionError("rede")})
    with pytest.raises(ConnectionError):
        envia_play.envia(api, "app.aab", "notas", "alpha")


def test_listar_as_faixas_nao_muda_nada(monkeypatch, capsys):
    api = Api()
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.setattr(envia_play, "cliente", lambda credencial: api)
    assert envia_play.main(["--faixas"]) == 0
    assert api.feitas == ["insert", "list", "delete"]
    saida = capsys.readouterr().out
    assert "production (produção): sem versão" in saida and "alpha (teste fechado): versão 31 (completed)" in saida
