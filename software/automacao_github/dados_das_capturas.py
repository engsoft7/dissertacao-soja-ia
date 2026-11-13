"""Grava as respostas reais da API para as capturas de tela do aplicativo.

As capturas (CapturasDeTelaTest) desenhavam as telas com uma série inventada,
boa para conferir o leiaute mas imprópria para mostrar o produto a alguém: o
histórico de Paragominas que aparecia não era o de Paragominas. Este script
sobe a API no próprio processo, sem servidor nem rede para o Render, pede as
mesmas rotas que o aplicativo pede e grava cada resposta em JSON na pasta que
o teste lê. A rota de mercado consulta o Yahoo Finance; quando ele não
responde, o arquivo não é gravado e o teste volta aos dados de exemplo só
naquela tela.

Grava também as respostas de um município de cada um dos outros estados
(previsao_MT.json, financas_MT.json, municipios_MT.json e assim por diante),
para as capturas das mesmas telas fora do Pará.

Uso: python software/automacao_github/dados_das_capturas.py [município]
"""
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "software" / "aplicativo_mobile" / "app" / "build" / "dados_capturas"

sys.path.insert(0, str(RAIZ / "software" / "api_backend"))

# Um município de cada estado que não o Pará: o de mais soja, ou a praça.
OUTROS_ESTADOS = {"MT": "Sorriso", "MA": "Balsas", "TO": "Porto Nacional", "RO": "Vilhena"}


def grava_outros_estados(cliente) -> None:
    """As rotas que o aplicativo pede com ?uf=, de um município por estado."""
    # Os outros estados treinam depois do Pará; até lá a API responde 503.
    for _ in range(300):
        estados = cliente.get("/api/estados").json()["estados"]
        if all(e["carregado"] for e in estados):
            break
        time.sleep(1)
    disponiveis = {e["uf"] for e in estados if e["carregado"]}
    for uf, municipio in OUTROS_ESTADOS.items():
        rotas = {"previsao": f"/api/previsao/{municipio}", "financas": f"/api/financas/{municipio}",
                 "municipios": "/api/municipios?com_sedes=true"}
        for nome, rota in rotas.items():
            alvo = DESTINO / f"{nome}_{uf}.json"
            r = cliente.get(rota, params={"uf": uf}) if uf in disponiveis else None
            if r is None or r.status_code != 200:
                print(f"{nome} de {uf}: sem dados, a captura fica de fora")
                alvo.unlink(missing_ok=True)
                continue
            alvo.write_text(json.dumps(r.json(), ensure_ascii=False), encoding="utf-8")
            print(f"{nome} de {uf}: gravado")


def main(municipio: str = "Paragominas") -> None:
    from fastapi.testclient import TestClient
    import api

    DESTINO.mkdir(parents=True, exist_ok=True)
    with TestClient(api.app) as cliente:
        rotas = {
            "previsao": f"/api/previsao/{municipio}",
            "financas": f"/api/financas/{municipio}",
            "mercado": "/api/mercado?periodo=1mo",
        }
        # Avisos do INMET para a sede de Paragominas (os outros municípios
        # usariam o próprio geocódigo; a tela das capturas é a de Paragominas).
        if municipio == "Paragominas":
            rotas["avisos"] = "/api/avisos?lat=-3.00212&lon=-47.3527&geocode=1505502"
        for nome, rota in rotas.items():
            resposta = cliente.get(rota)
            dados = resposta.json() if resposta.status_code == 200 else None
            if nome == "mercado" and dados and not dados.get("cotacao"):
                dados = None
            if nome == "avisos" and dados and not dados.get("disponivel"):
                dados = None
            if dados is None:
                print(f"{nome}: sem dados ({resposta.status_code}), a captura usa o exemplo")
                (DESTINO / f"{nome}.json").unlink(missing_ok=True)
                continue
            (DESTINO / f"{nome}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            print(f"{nome}: gravado")
        grava_outros_estados(cliente)


def grava_tempo(lat: float = -3.0, lon: float = -47.35) -> None:
    """A previsão do Open-Meteo, como o aplicativo a pede (Tempo.kt), para a tela Tempo.

    O aplicativo vai direto ao Open-Meteo, sem a API; o script faz o mesmo.
    """
    import requests
    params = {
        "latitude": lat, "longitude": lon, "past_days": 7, "forecast_days": 7, "timezone": "auto",
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,"
                   "wind_speed_10m,wind_gusts_10m,wind_direction_10m,is_day",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,"
                  "wind_speed_10m,wind_gusts_10m,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,"
                 "et0_fao_evapotranspiration,uv_index_max,sunrise,sunset",
    }
    alvo = DESTINO / "tempo.json"
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=30)
        r.raise_for_status()
        alvo.write_text(r.text, encoding="utf-8")
        print("tempo: gravado")
    except Exception as e:  # rede, limite de requisições
        alvo.unlink(missing_ok=True)
        print(f"tempo: sem dados ({type(e).__name__}), a captura usa o exemplo")


if __name__ == "__main__":
    main(*sys.argv[1:2])
    grava_tempo()
