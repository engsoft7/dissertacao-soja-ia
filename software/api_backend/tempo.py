# -*- coding: utf-8 -*-
"""Previsão do tempo e janela de pulverização, para o painel web.

Porta para Python das contas do aplicativo (aplicativo_mobile/.../TempoCalculo.kt),
com as mesmas regras e os mesmos limites, para o painel mostrar o que o
aplicativo mostra. A previsão vem do Open-Meteo (https://open-meteo.com, dados
sob CC BY 4.0, gratuito para uso não comercial), com cache de meia hora por
ponto.

A janela de pulverização segue a Embrapa Soja (Adegas e Gazziero, 2020,
Tecnologias de produção de soja, cap. 12, p. 285-289): até 30 °C, umidade
relativa acima de 60%, vento de 3 a 8 km/h (até 10 km/h só com ponta
antideriva) e sem chuva logo depois. O vento da previsão, a 10 m, é reduzido a
2 m pelo perfil logarítmico da FAO-56 (Allen et al., 1998, eq. 47). Chuva na
hora: 0,1 mm ou mais, ou chance de 50% ou mais (limites do aplicativo, e não
da Embrapa), conferida na hora e nas 2 seguintes.

A previsão do tempo serve às operações do dia; não entra na estimativa de
produtividade, que usa o clima observado das safras.
"""
from __future__ import annotations

import math
import threading
import time
from datetime import date, datetime, timedelta

import requests

URL = "https://api.open-meteo.com/v1/forecast"
ATUAL = ("temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,"
         "wind_speed_10m,wind_gusts_10m,wind_direction_10m,is_day")
HORARIO = ("temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,"
           "wind_speed_10m,wind_gusts_10m,weather_code")
DIARIO = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
          "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,et0_fao_evapotranspiration,"
          "uv_index_max,sunrise,sunset")
VALIDADE_S = 30 * 60

TEMPERATURA_MAXIMA, TEMPERATURA_MINIMA, UMIDADE_MINIMA = 30.0, 10.0, 60.0
VENTO_MINIMO, VENTO_IDEAL_MAXIMO, VENTO_MAXIMO_ANTIDERIVA = 3.0, 8.0, 10.0
CHUVA_MINIMA_MM, CHANCE_DE_CHUVA, HORAS_SEM_CHUVA = 0.1, 50.0, 2
BOA, ATENCAO, EVITAR = "boa", "atenção", "evitar"
_cache, _trava = {}, threading.Lock()


def vento_a_2m(vento_10m: float) -> float:
    """FAO-56, eq. 47: u2 = uz · 4,87 / ln(67,8 z − 5,42), z = 10 m."""
    return vento_10m * 4.87 / math.log(67.8 * 10 - 5.42)


def avalia_hora(temp, umidade, vento_10m, chuva_na_hora: bool, chuva_logo: bool) -> tuple[str, list[str]]:
    """Nível da hora e os motivos, do mais grave ao mais leve (como avaliaHora no app)."""
    evitar, atencao = [], []
    vento = None if vento_10m is None else vento_a_2m(vento_10m)
    if chuva_na_hora:
        evitar.append("chuva prevista nesta hora")
    if temp is not None and temp > TEMPERATURA_MAXIMA:
        evitar.append("temperatura acima de 30 °C")
    if umidade is not None and umidade < UMIDADE_MINIMA:
        evitar.append("umidade abaixo de 60%")
    if vento is not None and vento > VENTO_MAXIMO_ANTIDERIVA:
        evitar.append("vento acima de 10 km/h")
    if vento is not None and VENTO_IDEAL_MAXIMO < vento <= VENTO_MAXIMO_ANTIDERIVA:
        atencao.append("vento entre 8 e 10 km/h: só com ponta antideriva")
    if vento is not None and vento < VENTO_MINIMO:
        atencao.append("vento abaixo de 3 km/h: gotas finas ficam no ar")
    if temp is not None and temp < TEMPERATURA_MINIMA:
        atencao.append("temperatura abaixo de 10 °C")
    if not chuva_na_hora and chuva_logo:
        atencao.append(f"chuva prevista nas {HORAS_SEM_CHUVA} horas seguintes")
    if temp is None or umidade is None or vento is None:
        atencao.append("previsão incompleta para esta hora")
    nivel = EVITAR if evitar else ATENCAO if atencao else BOA
    return nivel, evitar + atencao


def horas_de_pulverizacao(h: dict, agora: datetime, quantas: int = 24) -> list[dict]:
    """Avaliação de cada hora a partir da hora em curso."""
    horas = [datetime.fromisoformat(t) for t in h["time"]]
    inicio_hora = agora.replace(minute=0, second=0, microsecond=0)
    ini = next((i for i, t in enumerate(horas) if t >= inicio_hora), None)
    if ini is None:
        return []
    chance = h.get("precipitation_probability") or [None] * len(horas)

    def chove(i):
        if i >= len(horas):
            return False
        return (h["precipitation"][i] or 0) >= CHUVA_MINIMA_MM or (chance[i] or 0) >= CHANCE_DE_CHUVA

    saida = []
    for i in range(ini, min(len(horas), ini + quantas)):
        t, ur, v = h["temperature_2m"][i], h["relative_humidity_2m"][i], h["wind_speed_10m"][i]
        nivel, motivos = avalia_hora(t, ur, v, chove(i), any(chove(i + k) for k in range(1, HORAS_SEM_CHUVA + 1)))
        saida.append({"hora": horas[i], "nivel": nivel, "motivos": motivos, "temperatura": t, "umidade": ur,
                      "vento_2m": None if v is None else vento_a_2m(v), "chance_chuva": chance[i]})
    return saida


def proxima_janela(horas: list[dict], minimo: int = 2):
    """Primeira sequência de pelo menos `minimo` horas boas: (início, fim), fim exclusivo."""
    i = 0
    while i < len(horas):
        if horas[i]["nivel"] != BOA:
            i += 1
            continue
        j = i
        while j + 1 < len(horas) and horas[j + 1]["nivel"] == BOA:
            j += 1
        if j - i + 1 >= minimo:
            return horas[i]["hora"], horas[j]["hora"] + timedelta(hours=1)
        i = j + 1
    return None


def balanco_chuva(d: dict, hoje: date) -> dict:
    """Chuva e evapotranspiração de referência dos dias passados, e a chuva prevista de hoje em diante."""
    dias = [date.fromisoformat(t) for t in d["time"]]
    chuva, et0 = d.get("precipitation_sum") or [], d.get("et0_fao_evapotranspiration") or []
    passados = [i for i, x in enumerate(dias) if x < hoje]
    adiante = [i for i, x in enumerate(dias) if x >= hoje]
    soma = lambda s, idx: sum((s[i] or 0) for i in idx if i < len(s))
    return {"chuva_passada": soma(chuva, passados), "et0_passada": soma(et0, passados),
            "dias_passados": len(passados), "chuva_prevista": soma(chuva, adiante), "dias_previstos": len(adiante)}


DESCRICAO = {0: "Céu limpo", 1: "Predomínio de sol", 2: "Parcialmente nublado", 3: "Nublado", 45: "Nevoeiro",
             48: "Nevoeiro", 51: "Garoa fraca", 53: "Garoa", 55: "Garoa forte", 56: "Garoa congelante",
             57: "Garoa congelante", 61: "Chuva fraca", 63: "Chuva moderada", 65: "Chuva forte",
             66: "Chuva congelante", 67: "Chuva congelante", 71: "Neve", 73: "Neve", 75: "Neve", 77: "Neve",
             80: "Pancadas de chuva fracas", 81: "Pancadas de chuva", 82: "Pancadas de chuva fortes",
             85: "Pancadas de neve", 86: "Pancadas de neve", 95: "Trovoada", 96: "Trovoada com granizo",
             97: "Trovoada forte", 99: "Trovoada com granizo"}


def descricao_tempo(codigo) -> str:
    return DESCRICAO.get(codigo, "Sem descrição")


def direcao_vento(graus) -> str:
    if graus is None:
        return ""
    return ["N", "NE", "L", "SE", "S", "SO", "O", "NO"][round((graus % 360) / 45.0) % 8]


def categoria_uv(uv):
    if uv is None:
        return None
    u = round(uv)
    return "baixo" if u <= 2 else "moderado" if u <= 5 else "alto" if u <= 7 else "muito alto" if u <= 10 else "extremo"


def previsao(lat: float, lon: float) -> dict | None:
    """Resposta do Open-Meteo para o ponto (arredondado a 0,01°), com cache de meia hora."""
    chave = (round(lat, 2), round(lon, 2))
    with _trava:
        guardado = _cache.get(chave)
        if guardado and time.time() - guardado[0] < VALIDADE_S:
            return guardado[1]
    try:
        r = requests.get(URL, timeout=20, params={
            "latitude": chave[0], "longitude": chave[1], "current": ATUAL, "hourly": HORARIO, "daily": DIARIO,
            "past_days": 7, "forecast_days": 7, "timezone": "auto"})
        r.raise_for_status()
        dados = r.json()
    except Exception as e:  # rede, limite de requisições
        print(f"[tempo] previsão indisponível: {type(e).__name__}: {e}", flush=True)
        return guardado[1] if guardado else None
    with _trava:
        _cache[chave] = (time.time(), dados)
    return dados
