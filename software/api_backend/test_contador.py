"""O anúncio do contador (contador_modelo.json) aponta para os arquivos certos."""
import hashlib
import json
import re
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
ASSETS = AQUI.parent / "aplicativo_mobile" / "app" / "src" / "main" / "assets"
ENDERECO = re.compile(r"https://raw\.githubusercontent\.com/engsoft7/dissertacao-soja-ia/[0-9a-f]{40}/[A-Za-z0-9_./-]+")


def manifesto():
    return json.loads((AQUI / "contador_modelo.json").read_text(encoding="utf-8"))


def test_anuncio_tem_o_que_o_aplicativo_exige():
    m = manifesto()
    assert isinstance(m["versao"], int) and m["versao"] >= 1
    assert set(m["arquivos"]) == {"contador_vagens_v1.tflite", "contador_vagens_v2.tflite"}
    for nome, a in m["arquivos"].items():
        assert ENDERECO.fullmatch(a["url"]) and ".." not in a["url"], nome
        assert a["url"].endswith("/" + nome)
        assert re.fullmatch(r"[0-9a-f]{64}", a["sha256"])
        assert 100_000 <= a["bytes"] <= 50_000_000


def test_versao_1_e_a_dos_assets():
    """Enquanto o anúncio for a versão 1, ele descreve os modelos que vêm no aplicativo."""
    m = manifesto()
    if m["versao"] != 1:
        return
    for nome, a in m["arquivos"].items():
        dados = (ASSETS / nome).read_bytes()
        assert hashlib.sha256(dados).hexdigest() == a["sha256"], nome
        assert len(dados) == a["bytes"], nome


def test_endpoint_devolve_o_anuncio():
    pytest.importorskip("fastapi")   # o job de testes do Python não instala a API inteira
    import api
    assert api.get_contador() == manifesto()
