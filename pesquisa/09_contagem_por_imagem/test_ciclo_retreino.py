"""Passos de ciclo_retreino.py que não precisam de modelo nem de foto: talhões, colheita e o portão do modo automático."""
import argparse
import json
import zipfile

import pytest

import ciclo_retreino as ciclo


def talhao(nome, colhido=None, contador=None, atualizado="2027-03-01T10:00:00-03:00"):
    ponto = {"plantas": 14, "metrosDeLinha": 1.0, "arrancadas": 5, "vagens": 200}
    if contador is not None:
        ponto["vagensDoContador"] = contador
    return {"talhao": nome, "atualizado_em": atualizado, "espacamento_m": 0.45, "graos_por_vagem": 2.2,
            "peso_mil_graos_g": 150.0, "area_ha": 10.0, "pontos": [ponto],
            "colheita_kg_ha": colhido}


def test_conta_igual_a_do_app():
    # 14 plantas em 1 m a 0,45 m = 31,1 plantas/m²; 40 vagens/planta; 2,2 grãos; 150 g: 4.106,7 kg/ha.
    assert ciclo.kg_ha_do_talhao(talhao("a")) == pytest.approx(14 / 0.45 * 40 * 2.2 * 150 / 100)
    assert ciclo.kg_ha_do_talhao(talhao("a", contador=180), contador=True) == pytest.approx(14 / 0.45 * 36 * 2.2 * 150 / 100)
    assert ciclo.kg_ha_do_talhao({**talhao("a"), "espacamento_m": 0}) is None


def test_junta_leva_os_talhoes_e_o_mais_novo_vence(tmp_path):
    def zip_com(nome, talhoes):
        z = tmp_path / nome
        with zipfile.ZipFile(z, "w") as arq:
            arq.writestr("LEIAME.txt", "x")
            arq.writestr(ciclo.TALHOES, json.dumps({"talhoes": talhoes}))
        return z

    base = tmp_path / "base"
    ciclo.junta([zip_com("1.zip", [talhao("a"), talhao("b")])], "Fazenda", base)
    ciclo.junta([zip_com("2.zip", [talhao("a", colhido=3600.0, atualizado="2027-05-01T10:00:00-03:00")])],
                "Fazenda", base)
    t = json.loads((base / ciclo.TALHOES).read_text())
    assert set(t) == {"Fazenda|a", "Fazenda|b"}
    assert t["Fazenda|a"]["colheita_kg_ha"] == 3600.0
    # talhoes.json não é foto: não entra na base de imagens nem vira recusa.
    assert json.loads((base / "anotacoes.json").read_text()) == {}


def test_compara_com_a_colheita():
    r = ciclo.compara_colheita([talhao("a", colhido=3800.0, contador=180), talhao("b", colhido=4000.0),
                                talhao("c")])
    assert r["talhoes_com_colheita"] == 2
    assert r["produtor"]["talhoes"] == 2 and r["contador"]["talhoes"] == 1
    est = 14 / 0.45 * 40 * 2.2 * 150 / 100
    assert r["produtor"]["vies_relativo"] == pytest.approx(((est - 3800) / 3800 + (est - 4000) / 4000) / 2, abs=1e-4)


def args_publica(tmp_path, medicao=None, modo=True):
    v1, v2 = tmp_path / "v1.tflite", tmp_path / "v2.tflite"
    v1.write_bytes(b"1" * 200_000)
    v2.write_bytes(b"2" * 200_000)
    anuncio = tmp_path / "anuncio.json"
    anuncio.write_text(json.dumps({"versao": 1}))
    return argparse.Namespace(versao=2, commit="a" * 40, pasta="celular_v2", v1=str(v1), v2=str(v2), nota="n",
                              app_minimo=23, anuncio=str(anuncio), modo_automatico=modo, medicao=medicao,
                              erro_maximo=0.10, fotos_minimas=30)


def medicao(tmp_path, fotos=40, erro=0.07, sha=None):
    import hashlib
    sha = sha or {v: hashlib.sha256(bytes([ord(str(i))]) * 200_000).hexdigest() for i, v in ((1, "v1"), (2, "v2"))}
    m = tmp_path / "mede_teste.json"
    m.write_text(json.dumps({"parte": "teste", "sha256": sha,
                             "contagem_v1": {"fotos": fotos, "erro_relativo_medio": erro}}))
    return str(m)


def test_publica_sem_modo_automatico_escreve_false(tmp_path):
    a = args_publica(tmp_path, modo=False)
    ciclo.publica(a)
    assert json.loads(open(a.anuncio).read())["modo_automatico"] is False


def test_modo_automatico_so_com_medicao_boa_dos_mesmos_modelos(tmp_path):
    with pytest.raises(SystemExit, match="precisa de --medicao"):
        ciclo.publica(args_publica(tmp_path))
    with pytest.raises(SystemExit, match="fotos de teste"):
        ciclo.publica(args_publica(tmp_path, medicao(tmp_path, fotos=10)))
    with pytest.raises(SystemExit, match="acima de"):
        ciclo.publica(args_publica(tmp_path, medicao(tmp_path, erro=0.2)))
    with pytest.raises(SystemExit, match="não é do v1"):
        ciclo.publica(args_publica(tmp_path, medicao(tmp_path, sha={"v1": "0" * 64, "v2": "0" * 64})))
    a = args_publica(tmp_path, medicao(tmp_path))
    ciclo.publica(a)
    assert json.loads(open(a.anuncio).read())["modo_automatico"] is True
