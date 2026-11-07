"""Mato Grosso e Maranhão na API (estados.py): mesmas rotas, com ?uf=, e o Pará sem mudar.

Precisa da API inteira (FastAPI, scikit-learn, folium): o job de testes do
Python não a instala, e o teste fica de fora lá; roda onde ela está instalada.
"""
import time

import pytest

import estados


def test_custo_da_conab_por_praca():
    lev = estados.levantamento_da_praca("SORRISO-MT", "Sorriso (MT)", "MAR-2026", "março de 2026")
    # 72,46 + 11,20 = 83,66/sc; 3.600 kg/ha são 60 sc/ha.
    assert lev["custo_operacional_saca"] == pytest.approx(83.66)
    assert lev["custo_operacional_ha"] == pytest.approx(83.66 * 60)
    assert lev["preco_recebido_saca"] == pytest.approx(103.9)
    balsas = estados.levantamento_da_praca("BALSAS-MA", "Balsas (MA)", "MAR-2026", "março de 2026")
    assert balsas["produtividade_referencia_sc_ha"] == pytest.approx(52.0)


def test_praca_mais_perto_da_sede():
    mt = estados.ESTADOS["MT"]
    assert estados.praca_conab(mt, (-13.0, -55.9))[1] == "Sorriso (MT)"           # Lucas do Rio Verde
    assert estados.praca_conab(mt, (-15.9, -54.9))[1] == "Primavera do Leste (MT)"  # Campo Verde
    assert estados.praca_conab(estados.ESTADOS["PA"], (-3.0, -47.0)) is None
    assert estados.estado(None).uf == "PA" and estados.estado("mt").uf == "MT" and estados.estado("SP") is None


@pytest.fixture(scope="module")
def cliente():
    pytest.importorskip("fastapi")
    pytest.importorskip("sklearn")
    pytest.importorskip("folium")
    import requests
    from fastapi.testclient import TestClient

    original = requests.get
    requests.get = lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("sem rede no teste"))
    import api
    with TestClient(api.app) as c:
        for _ in range(300):
            if all(e["carregado"] for e in c.get("/api/estados").json()["estados"]):
                break
            time.sleep(1)
        yield c
    requests.get = original


def test_estados_e_municipios(cliente):
    e = {x["uf"]: x for x in cliente.get("/api/estados").json()["estados"]}
    assert set(e) >= {"PA", "MT", "MA"} and e["MT"]["municipios"] > 100
    assert "uf" not in cliente.get("/api/municipios").json()        # o aplicativo antigo recebe o mesmo de antes
    mt = cliente.get("/api/municipios", params={"uf": "MT", "com_sedes": True}).json()
    assert "Sorriso" in mt["municipios"] and mt["uf"] == "MT"
    sorriso = next(s for s in mt["sedes"] if s["nome"] == "Sorriso")
    assert sorriso["cod_ibge7"] == 5107925 and -13 < sorriso["latitude"] < -12
    assert cliente.get("/api/municipios", params={"uf": "SP"}).status_code == 404


def test_previsao_financas_simulacao_e_mapa(cliente):
    p = cliente.get("/api/previsao/Sorriso", params={"uf": "MT"}).json()
    assert p["uf"] == "MT" and p["validacao"]["municipios"] > 100
    futuras = [h for h in p["historico"] if h["rendimento_real"] == 0]
    assert len(futuras) == 3 and all(2500 < h["rendimento_predito"] < 5000 for h in futuras)
    assert cliente.get("/api/previsao/Sorriso").status_code == 404   # sem estado, só o Pará
    f = cliente.get("/api/financas/Sorriso", params={"uf": "MT"}).json()
    assert f["fonte_preco"].startswith("CONAB, Sorriso (MT)") and f["custo_ha"] == pytest.approx(83.66 * 60)
    assert cliente.get("/api/financas/Balsas", params={"uf": "MA"}).json()["fonte_preco"].startswith("CONAB, Balsas")
    s = cliente.post("/api/simulacao", json={"municipio": "Balsas", "uf": "MA", "precip_factor": 0.8,
                                             "temp_offset": 1.0, "ano": 2027}).json()
    assert s["ano"] == 2027 and s["estimativa_kg_ha"] > 0
    html = cliente.get("/api/mapa/render", params={"uf": "MT", "municipio": "Sorriso"}).text
    assert "leaflet" in html.lower() and "Sorriso" in html
    m = cliente.get("/api/mercado", params={"uf": "MA"}).json()
    assert m["uf"] == "MA" and m["para"] is None and m["conab_fonte"].startswith("CONAB, Balsas")


def test_textos_da_praca_em_reais():
    t = estados.levantamento_da_praca("SORRISO-MT", "Sorriso (MT)", "MAR-2026", "março de 2026")["textos"]
    assert "R$ 83,66/sc, convertido para R$ 5.019,60/ha" in t["nota_custo"]
    assert "(3.600 kg/ha, 60 sc/ha)" in t["nota_custo"]
    assert t["nota_preco"].startswith("R$ 103,90/sc")
    assert estados.ESTADOS["MT"].no == "em Mato Grosso" and estados.ESTADOS["MA"].do == "do Maranhão"
