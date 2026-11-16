# -*- coding: utf-8 -*-
"""envia_play.py: as notas cabem no limite do Play, sem a chave nada é enviado, e
uma recusa da loja vira uma explicação no log, sem confirmar a edição. A ficha da
loja sai de textos_da_loja.txt e só é gravada quando pedido."""
from pathlib import Path

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

    FICHAS = [{"language": "pt-BR", "title": "AgroInteligência", "shortDescription": "Curta",
               "fullDescription": "Linha 1\nLinha 2", "video": "https://youtu.be/x"}]

    def __init__(self, faixas_recusadas=(), pacote_recusado=None, ficha_recusada=None):
        self.faixas_recusadas, self.pacote_recusado = dict(faixas_recusadas), pacote_recusado
        self.ficha_recusada = ficha_recusada
        self.feitas, self.corpo, self.recurso = [], None, None

    def edits(self): return self
    def bundles(self): return self

    def tracks(self):
        self.recurso = "tracks"
        return self

    def listings(self):
        self.recurso = "listings"
        return self

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
    def list(self, **k):
        if self.recurso == "listings":
            return self._faz("listings.list", {"listings": self.FICHAS})
        return self._faz("list", {"tracks": self.FAIXAS})

    def patch(self, **k):
        self.corpo = k["body"]
        return self._faz("listings.patch:" + k["language"], erro=self.ficha_recusada)

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


def test_faixa_em_uso_e_a_mais_alta_com_versao_lancada():
    """As faixas do app em 15/11/2026: produção e teste aberto vazios, teste fechado na 28 e interno na 22."""
    def faixa(nome, *versoes):
        return {"track": nome, "releases": [{"versionCodes": [v], "status": s} for v, s in versoes]}
    hoje = [faixa("production"), faixa("beta"), faixa("alpha", ("28", "completed")), faixa("internal", ("22", "completed"))]
    assert envia_play.faixa_em_uso(hoje) == "alpha"
    # Depois da primeira versão de produção, lançada pelo Play Console, as novas vão para lá.
    assert envia_play.faixa_em_uso(hoje[1:] + [faixa("production", ("33", "inProgress"))]) == "production"
    # Um rascunho em produção não puxa o envio para a produção.
    assert envia_play.faixa_em_uso([faixa("production", ("33", "draft")), faixa("alpha", ("28", "completed"))]) == "alpha"
    # Faixa de nome próprio é teste fechado: empata com a alpha, e a alpha leva; ganha do teste interno.
    assert envia_play.faixa_em_uso([faixa("Testadores", ("30", "completed")), faixa("alpha", ("28", "completed"))]) == "alpha"
    assert envia_play.faixa_em_uso([faixa("Testadores", ("30", "completed")), faixa("internal", ("22", "completed"))]) == "Testadores"
    assert envia_play.faixa_em_uso([faixa("production"), {"track": "internal"}]) is None


def test_sem_faixa_pedida_o_envio_vai_para_a_faixa_em_uso(monkeypatch, capsys):
    api = Api()
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.delenv("PLAY_FAIXA", raising=False)
    monkeypatch.setattr(envia_play, "cliente", lambda credencial: api)
    monkeypatch.setattr(envia_play, "_arquivo", lambda aab: aab)
    assert envia_play.main(["app.aab", "App 2.9.0"]) == 0
    assert api.feitas == ["insert", "list", "delete", "insert", "upload", "update:alpha", "commit"]
    saida = capsys.readouterr().out
    assert "Faixa de envio: alpha (teste fechado), a mais alta em que o app já tem versão." in saida
    # A variável PLAY_FAIXA, quando existe, manda.
    api = Api()
    monkeypatch.setattr(envia_play, "cliente", lambda credencial: api)
    monkeypatch.setenv("PLAY_FAIXA", "internal")
    assert envia_play.main(["app.aab", "App 2.9.0"]) == 0
    assert api.feitas == ["insert", "upload", "update:internal", "commit"]


def test_app_sem_versao_em_faixa_nenhuma_nao_envia(monkeypatch, capsys):
    api = Api()
    api.FAIXAS = [{"track": "production"}, {"track": "internal", "releases": [{"versionCodes": ["1"], "status": "draft"}]}]
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.delenv("PLAY_FAIXA", raising=False)
    monkeypatch.setattr(envia_play, "cliente", lambda credencial: api)
    assert envia_play.main(["app.aab", "notas"]) == 1
    assert "upload" not in api.feitas
    assert "a primeira é lançada pelo Play Console" in capsys.readouterr().out


def test_listar_as_faixas_nao_muda_nada(monkeypatch, capsys):
    api = Api()
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.setattr(envia_play, "cliente", lambda credencial: api)
    assert envia_play.main(["--faixas"]) == 0
    assert api.feitas == ["insert", "list", "delete"]
    saida = capsys.readouterr().out
    assert "production (produção): sem versão" in saida and "alpha (teste fechado): versão 31 (completed)" in saida


# ── a ficha da loja, que vem de textos_da_loja.txt ──────────────────────────

TEXTOS = Path(__file__).resolve().parents[1] / "aplicativo_mobile" / "loja" / "textos_da_loja.txt"


def _textos(tmp_path, nome="AgroInteligência", curta="Curta", completa="Linha 1\nLinha 2"):
    arquivo = tmp_path / "textos.txt"
    arquivo.write_text(f"NOME DO APP\n{nome}\n\nBREVE DESCRIÇÃO\n{curta}\n\nDESCRIÇÃO COMPLETA\n{completa}\n",
                       encoding="utf-8")
    return arquivo


def test_ficha_do_arquivo_de_verdade():
    ficha = envia_play.ficha_do_arquivo(TEXTOS)
    assert ficha["title"] == "AgroInteligência"
    assert 0 < len(ficha["shortDescription"]) <= 80
    # A descrição completa vai até o fim do arquivo, com as fontes e o aviso de não afiliação.
    assert "NÃO é um aplicativo do governo" in ficha["fullDescription"]
    assert "FONTES OFICIAIS" in ficha["fullDescription"]
    assert ficha["fullDescription"].endswith("politica-de-privacidade/")
    assert len(ficha["fullDescription"]) <= 4000


def test_ficha_do_arquivo_recusa_secao_faltando_ou_longa(tmp_path):
    import pytest
    arquivo = tmp_path / "sem_curta.txt"
    arquivo.write_text("NOME DO APP\nAgro\n\nDESCRIÇÃO COMPLETA\nTexto\n", encoding="utf-8")
    with pytest.raises(ValueError, match="BREVE DESCRIÇÃO"):
        envia_play.ficha_do_arquivo(arquivo)
    with pytest.raises(ValueError, match="NOME DO APP"):
        envia_play.ficha_do_arquivo(_textos(tmp_path, nome="x" * 31))


def test_ficha_igual_nao_muda_nada(tmp_path, capsys):
    api = Api()
    assert envia_play.ficha(api, _textos(tmp_path), aplica=True) == 0
    assert api.feitas == ["insert", "listings.list", "delete"]
    assert "já está igual" in capsys.readouterr().out


def test_ficha_conferida_mostra_o_que_muda_e_nao_grava(tmp_path, capsys):
    api = Api()
    assert envia_play.ficha(api, _textos(tmp_path, completa="Linha 1\nLinha nova")) == 0
    assert api.feitas == ["insert", "listings.list", "delete"]
    saida = capsys.readouterr().out
    assert "-Linha 2" in saida and "+Linha nova" in saida and "Linha 1" not in saida.split("@@")[-1]
    assert "nada mudou na loja" in saida


def test_ficha_aplicada_grava_so_os_textos(tmp_path, capsys):
    api = Api()
    assert envia_play.ficha(api, _textos(tmp_path, curta="Nova curta"), aplica=True) == 0
    assert api.feitas == ["insert", "listings.list", "listings.patch:pt-BR", "commit"]
    # Só o nome e as descrições: o vídeo não vai no corpo e fica como está.
    assert api.corpo == {"title": "AgroInteligência", "shortDescription": "Nova curta",
                         "fullDescription": "Linha 1\nLinha 2", "language": "pt-BR"}
    assert "atualizada" in capsys.readouterr().out


def test_ficha_recusada_ou_sem_portugues(tmp_path, capsys):
    api = Api(ficha_recusada=Recusa(403, "The caller does not have permission"))
    assert envia_play.ficha(api, _textos(tmp_path, curta="Nova"), aplica=True) == 1
    assert "commit" not in api.feitas and api.feitas[-1] == "delete"
    assert "recusou a ficha (403: The caller does not have permission)" in capsys.readouterr().out
    api = Api()
    api.FICHAS = [{"language": "en-US", "title": "AgroIntelligence"}]
    assert envia_play.ficha(api, _textos(tmp_path), aplica=True) == 1
    assert "não tem ficha em pt-BR" in capsys.readouterr().out


def test_ficha_pela_linha_de_comando(tmp_path, monkeypatch):
    api = Api()
    monkeypatch.setenv("PLAY_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.setattr(envia_play, "cliente", lambda credencial: api)
    assert envia_play.main(["--ficha", str(_textos(tmp_path, curta="Outra"))]) == 0
    assert "commit" not in api.feitas
    assert envia_play.main(["--ficha", str(_textos(tmp_path, curta="Outra")), "--aplica"]) == 0
    assert api.feitas[-1] == "commit"
