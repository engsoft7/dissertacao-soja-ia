# -*- coding: utf-8 -*-
"""envia_play.py, vídeo e imagens da ficha: --midia só lê; --imagens confere as
capturas da pasta contra os limites do Play, troca só o tipo que mudou e, numa
recusa da loja, não confirma a edição."""
import struct
import zlib
from pathlib import Path

import pytest

import envia_play


def png(caminho: Path, largura: int, altura: int) -> Path:
    """Um PNG mínimo, com o cabeçalho que dimensoes_png lê."""
    def bloco(tipo: bytes, dados: bytes) -> bytes:
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados))
    ihdr = struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0)
    caminho.write_bytes(b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", ihdr) + bloco(b"IEND", b"") + caminho.name.encode())
    return caminho


def pasta_da_loja(tmp_path: Path, capturas: int = 8, lado=(1080, 1920), destaque=(1024, 500)) -> Path:
    for i in range(1, capturas + 1):
        png(tmp_path / f"loja_{i}_tela.png", *lado)
    if destaque:
        png(tmp_path / "loja_destaque.png", *destaque)
    # Capturas de outros testes na mesma pasta não entram.
    png(tmp_path / "mercado_claro.png", 1233, 4200)
    return tmp_path


# ── uma API de mentira, com as chamadas encadeadas da de verdade ─────────────

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


class Fichas:
    def __init__(self, api):
        self.api = api

    def list(self, **k):
        return Chamada(lambda: {"listings": [{"language": "pt-BR", "video": self.api.video}]})


class Imagens:
    def __init__(self, api):
        self.api = api

    def list(self, imageType, **k):
        return Chamada(lambda: {"images": self.api.na_loja.get(imageType, [])})

    def deleteall(self, imageType, **k):
        return self.api.faz(f"deleteall {imageType}")

    def upload(self, imageType, media_body, **k):
        erro = Recusa(403, "imagem recusada") if self.api.recusa_upload else None
        return self.api.faz(f"upload {imageType} {media_body}", erro=erro)


class Api:
    def __init__(self, na_loja=None, video="", recusa_upload=False):
        self.na_loja, self.video, self.recusa_upload = na_loja or {}, video, recusa_upload
        self.feitas = []

    def faz(self, nome, resultado=None, erro=None):
        def f():
            if erro:
                raise erro
            self.feitas.append(nome)
            return resultado or {}
        return Chamada(f)

    def edits(self): return self
    def listings(self): return Fichas(self)
    def images(self): return Imagens(self)
    def insert(self, **k): return self.faz("insert", {"id": "e1"})
    def delete(self, **k): return self.faz("delete")
    def commit(self, **k): return self.faz("commit")


@pytest.fixture(autouse=True)
def sem_biblioteca_do_google(monkeypatch):
    monkeypatch.setattr(envia_play, "_imagem", lambda caminho: caminho.name)


def na_loja_igual(pasta: Path) -> dict:
    novas = envia_play.imagens_da_pasta(pasta)
    return {tipo: [{"url": "u", "sha256": envia_play._sha256(a)} for a in arquivos] for tipo, arquivos in novas.items()}


# ── o que a pasta precisa ter ────────────────────────────────────────────────

def test_dimensoes_do_png(tmp_path):
    assert envia_play.dimensoes_png(png(tmp_path / "a.png", 1080, 1920)) == (1080, 1920)
    (tmp_path / "b.png").write_bytes(b"\xff\xd8\xff\xe0 isto e um JPEG")
    with pytest.raises(ValueError, match="não é PNG"):
        envia_play.dimensoes_png(tmp_path / "b.png")


def test_pasta_boa_na_ordem_das_capturas(tmp_path):
    novas = envia_play.imagens_da_pasta(pasta_da_loja(tmp_path))
    assert [a.name for a in novas["phoneScreenshots"]] == [f"loja_{i}_tela.png" for i in range(1, 9)]
    assert [a.name for a in novas["featureGraphic"]] == ["loja_destaque.png"]


@pytest.mark.parametrize("args, motivo", [
    ({"capturas": 1}, "1 capturas de celular"),
    ({"lado": (1080, 2400)}, "mais comprida que 2 para 1"),
    ({"lado": (200, 400)}, "fora de 320 a 3840"),
    ({"lado": (4000, 4000)}, "fora de 320 a 3840"),
    ({"destaque": None}, "falta loja_destaque.png"),
    ({"destaque": (1024, 512)}, "e não 1024 x 500"),
])
def test_pasta_recusada(tmp_path, args, motivo):
    with pytest.raises(ValueError, match=motivo):
        envia_play.imagens_da_pasta(pasta_da_loja(tmp_path, **args))


# ── a loja ───────────────────────────────────────────────────────────────────

def test_imagens_iguais_nao_mudam_nada(tmp_path, capsys):
    pasta = pasta_da_loja(tmp_path)
    api = Api(na_loja=na_loja_igual(pasta))
    assert envia_play.envia_imagens(api, pasta, aplica=True) == 0
    assert api.feitas == ["insert", "delete"]
    assert "já são as da pasta" in capsys.readouterr().out


def test_conferencia_mostra_o_que_muda_e_nao_grava(tmp_path, capsys):
    pasta = pasta_da_loja(tmp_path)
    api = Api(na_loja={"phoneScreenshots": [{"url": "u", "sha256": "antiga"}] * 3})
    assert envia_play.envia_imagens(api, pasta) == 0
    saida = capsys.readouterr().out
    assert "capturas de celular: 3 na loja, 8 novas" in saida
    assert "imagem de destaque: 0 na loja, 1 novas" in saida
    assert "nada mudou na loja" in saida
    assert api.feitas == ["insert", "delete"]


def test_aplicada_troca_so_o_tipo_que_mudou(tmp_path, capsys):
    pasta = pasta_da_loja(tmp_path)
    na_loja = na_loja_igual(pasta)
    na_loja["phoneScreenshots"] = [{"url": "u", "sha256": "antiga"}]
    api = Api(na_loja=na_loja)
    assert envia_play.envia_imagens(api, pasta, aplica=True) == 0
    assert api.feitas == (["insert", "deleteall phoneScreenshots"]
                          + [f"upload phoneScreenshots loja_{i}_tela.png" for i in range(1, 9)] + ["commit"])
    assert "imagem de destaque: as mesmas da loja" in capsys.readouterr().out


def test_recusa_da_loja_nao_confirma(tmp_path, capsys):
    pasta = pasta_da_loja(tmp_path)
    api = Api(recusa_upload=True)
    assert envia_play.envia_imagens(api, pasta, aplica=True) == 1
    assert "commit" not in api.feitas and api.feitas[-1] == "delete"
    assert "recusou as imagens (403: imagem recusada)" in capsys.readouterr().out


def test_midia_mostra_o_video_e_as_imagens():
    api = Api(na_loja={"phoneScreenshots": [{"url": "https://a"}, {"url": "https://b"}],
                       "icon": [{"url": "https://i"}]}, video="https://youtu.be/x")
    linhas = envia_play.descreve_midia(envia_play.midia(api))
    assert linhas[0] == "Vídeo da ficha: https://youtu.be/x"
    assert "capturas de celular (phoneScreenshots): 2" in linhas and "  https://b" in linhas
    assert "ícone (icon): 1" in linhas
    assert api.feitas == ["insert", "delete"]


def test_midia_sem_video_nem_imagens():
    assert envia_play.descreve_midia(envia_play.midia(Api())) == ["Vídeo da ficha: nenhum", "Nenhuma imagem na ficha."]


def test_linha_de_comando(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PLAY_SERVICE_ACCOUNT_JSON", raising=False)
    assert envia_play.main(["--midia"]) == 0
    assert envia_play.main(["--imagens", str(pasta_da_loja(tmp_path))]) == 0
    assert "não configurado" in capsys.readouterr().out
    # A pasta é conferida antes de qualquer acesso à loja, com ou sem a chave.
    sem_destaque = tmp_path / "sem_destaque"
    sem_destaque.mkdir()
    with pytest.raises(ValueError, match="falta loja_destaque.png"):
        envia_play.main(["--imagens", str(pasta_da_loja(sem_destaque, destaque=None))])
