# -*- coding: utf-8 -*-
"""envia_play.py, vídeo e imagens da ficha: --midia só lê; --imagens confere as
capturas da pasta contra os limites do Play, troca só o tipo que mudou e, numa
recusa da loja, não confirma a edição."""
import struct
import zlib
from pathlib import Path

import pytest

import envia_play


def png(caminho: Path, largura: int, altura: int, cor: int = 2) -> Path:
    """Um PNG mínimo, com o cabeçalho que dimensoes_png lê; cor 2 é RGB, e 6, RGB com transparência."""
    def bloco(tipo: bytes, dados: bytes) -> bytes:
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados))
    ihdr = struct.pack(">IIBBBBB", largura, altura, 8, cor, 0, 0, 0)
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


def test_png_com_transparencia_e_recusado(tmp_path):
    pasta = pasta_da_loja(tmp_path)
    png(pasta / "loja_destaque.png", 1024, 500, cor=6)
    with pytest.raises(ValueError, match="loja_destaque.png: PNG com transparência"):
        envia_play.imagens_da_pasta(pasta)


def test_baixa_as_imagens_da_ficha(tmp_path, monkeypatch, capsys):
    """Cada imagem vai para a pasta no tamanho original ("=s0"), com a extensão do formato; sem o
    tamanho original, o endereço puro; o vídeo vai para video.txt."""
    respostas = {
        "https://a=s0": b"\x89PNG\r\n\x1a\n" + b"0" * 30,
        "https://b=s0": None,  # recusado: vale o endereço puro
        "https://b": b"\xff\xd8\xff\xe0" + b"0" * 30,
    }

    class Resposta:
        def __init__(self, dados): self.dados = dados
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return self.dados

    def abre(url, timeout):
        if respostas.get(url) is None:
            raise OSError("400")
        return Resposta(respostas[url])

    monkeypatch.setattr("urllib.request.urlopen", abre)
    m = {"video": "https://youtu.be/x", "imagens": {"phoneScreenshots": ["https://a"], "featureGraphic": ["https://b"]}}
    salvas = envia_play.baixa_imagens(m, tmp_path / "antes")
    assert [s.name for s in salvas] == ["phoneScreenshots_1.png", "featureGraphic_1.jpg"]
    assert (tmp_path / "antes" / "video.txt").read_text(encoding="utf-8") == "https://youtu.be/x\n"


# ── o vídeo da ficha, pela seção VÍDEO de textos_da_loja.txt ─────────────────

def _textos_com_video(tmp_path, video):
    real = Path(envia_play.__file__).resolve().parents[1] / "aplicativo_mobile" / "loja" / "textos_da_loja.txt"
    arquivo = tmp_path / "textos.txt"
    arquivo.write_text(f"VÍDEO\n{video}\n\n" + real.read_text(encoding="utf-8"), encoding="utf-8")
    return arquivo


def test_video_da_secao_entra_na_ficha_sem_mudar_os_textos(tmp_path):
    sem = envia_play.ficha_do_arquivo(Path(envia_play.__file__).resolve().parents[1] / "aplicativo_mobile" / "loja"
                                      / "textos_da_loja.txt")
    com = envia_play.ficha_do_arquivo(_textos_com_video(tmp_path, "https://youtu.be/AbCdEfGhIj0"))
    assert com["video"] == "https://youtu.be/AbCdEfGhIj0"
    assert {k: v for k, v in com.items() if k != "video"} == sem
    assert "video" not in sem


def test_video_que_nao_e_do_youtube_e_recusado(tmp_path):
    with pytest.raises(ValueError, match="endereço do YouTube"):
        envia_play.ficha_do_arquivo(_textos_com_video(tmp_path, "https://exemplo.com/video.mp4"))


def test_diferenca_do_video_so_com_a_secao():
    na_loja = {"title": "A", "shortDescription": "B", "fullDescription": "C", "video": "https://youtu.be/AbCdEfGhIj0"}
    assert envia_play.diferencas(na_loja, {"title": "A", "shortDescription": "B", "fullDescription": "C"}) == []
    novo = {**na_loja, "video": "https://youtu.be/ZyXwVuTsRq9"}
    assert any("ZyXwVuTsRq9" in linha for linha in envia_play.diferencas(na_loja, novo))
