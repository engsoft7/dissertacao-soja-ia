# -*- coding: utf-8 -*-
"""A API não devolve ao cliente a mensagem interna de um erro, que pode trazer
caminhos e nomes de arquivos do servidor: ela vai só para o log, e o cliente
recebe um aviso curto (/api/previsao, /api/mapa/geo e /api/mapa/render)."""
import pandas as pd
import pytest

api = pytest.importorskip("api")

SEGREDO = "/srv/app/cache/modelo_PA.joblib corrompido"


class _Estado:
    uf = "PA"


class _Carregado:
    """O mínimo de EstadoCarregado que as rotas usam antes de chegar ao erro."""
    estado = _Estado()
    df = pd.DataFrame({"municipio": ["Paragominas"]})

    def nome_na_base(self, municipio):
        return municipio


def _falha(*a, **k):
    raise RuntimeError(SEGREDO)


def test_previsao(monkeypatch, capsys):
    monkeypatch.setattr(api.AppState, "df", pd.DataFrame({"municipio": ["Paragominas"]}))
    monkeypatch.setattr(api, "_estado_carregado", lambda uf: _Carregado())
    monkeypatch.setattr(api, "_historico_do_municipio", _falha)
    with pytest.raises(api.HTTPException) as erro:
        api.get_previsao("Paragominas")
    assert erro.value.status_code == 500 and SEGREDO not in str(erro.value.detail)
    assert SEGREDO in capsys.readouterr().out


def test_mapa_geo(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(api, "GEO_PARA", tmp_path / "nao_existe" / "para_geo.json")
    with pytest.raises(api.HTTPException) as erro:
        api.get_mapa_geo()
    assert erro.value.status_code == 500 and "nao_existe" not in str(erro.value.detail)
    assert "nao_existe" in capsys.readouterr().out


def test_mapa_render(monkeypatch, capsys):
    monkeypatch.setattr(api, "_estado_carregado", lambda uf: _Carregado())
    monkeypatch.setattr(api, "_generate_map_html_cached", _falha)
    resposta = api.render_mapa("Paragominas", "dark", None, None, None)
    assert resposta.status_code == 500 and SEGREDO.encode() not in resposta.body
    assert SEGREDO in capsys.readouterr().out
