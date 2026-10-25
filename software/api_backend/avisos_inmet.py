# -*- coding: utf-8 -*-
"""Avisos meteorológicos do INMET que atingem um ponto ou um município, para a
tela Tempo do aplicativo.

Fonte: https://apiprevmet3.inmet.gov.br/avisos/ativos, a mesma do Alert-AS
do INMET, com os avisos de hoje e dos próximos dias. Cada aviso traz o
polígono da área atingida (GeoJSON) e os geocódigos IBGE dos municípios.

A resposta inteira passa de 300 kB, quase tudo listas de municípios do país
inteiro. O aplicativo não a baixa: pede aqui só os avisos do lugar dele, pelo
município (geocódigo) ou pelo ponto do GPS, que pode estar longe da sede num
município do tamanho dos do Pará. O ponto vale quando cai dentro do polígono.

Quando o INMET não responde, devolve a última leitura boa; sem nenhuma,
"disponivel" vai falso e a tela diz que os avisos estão indisponíveis, em vez
de mostrar uma lista vazia como se não houvesse aviso.
"""
from __future__ import annotations

import ast
import json
import threading
import time

import requests

URL = "https://apiprevmet3.inmet.gov.br/avisos/ativos"
FONTE = "INMET, avisos meteorológicos (alertas.inmet.gov.br)"
VALIDADE_S = 30 * 60
# Do menos para o mais grave, como o INMET classifica.
SEVERIDADES = ("Perigo Potencial", "Perigo", "Grande Perigo")
_cache, _trava = {}, threading.Lock()


def aneis(poligono: str | dict) -> list[list[list[float]]]:
    """Anéis externos de um Polygon ou MultiPolygon, como listas de [lon, lat]."""
    g = json.loads(poligono) if isinstance(poligono, str) else poligono
    if g.get("type") == "Polygon":
        return [g["coordinates"][0]]
    if g.get("type") == "MultiPolygon":
        return [p[0] for p in g["coordinates"]]
    return []


def dentro(lon: float, lat: float, anel: list[list[float]]) -> bool:
    """Ponto no polígono pelo método do raio (par-ímpar)."""
    achou = False
    j = len(anel) - 1
    for i in range(len(anel)):
        xi, yi = anel[i][0], anel[i][1]
        xj, yj = anel[j][0], anel[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            achou = not achou
        j = i
    return achou


def atinge(aviso: dict, lat: float | None, lon: float | None, geocode: str | None) -> bool:
    if geocode and geocode in (aviso.get("geocodes") or "").split(","):
        return True
    if lat is None or lon is None:
        return False
    try:
        return any(dentro(lon, lat, a) for a in aneis(aviso.get("poligono") or "{}"))
    except (ValueError, KeyError, TypeError, IndexError):
        return False


def _lista(texto) -> list[str]:
    """Os campos de riscos e instruções vêm como texto de lista Python: "['...', '...']"."""
    if isinstance(texto, list):
        return [str(t).strip() for t in texto if str(t).strip()]
    try:
        valor = ast.literal_eval(texto or "[]")
        if isinstance(valor, (list, tuple)):
            return [str(t).strip() for t in valor if str(t).strip()]
    except (ValueError, SyntaxError):
        pass
    return [str(texto).strip()] if texto else []


def resume(aviso: dict) -> dict:
    return {
        "id": str(aviso.get("id")),
        "evento": aviso.get("descricao"),
        "severidade": aviso.get("severidade"),
        "nivel": SEVERIDADES.index(aviso["severidade"]) + 1 if aviso.get("severidade") in SEVERIDADES else None,
        "cor": aviso.get("aviso_cor"),
        "inicio": aviso.get("inicio"),
        "fim": aviso.get("fim"),
        "riscos": _lista(aviso.get("riscos")),
        "instrucoes": _lista(aviso.get("instrucoes")),
    }


def filtra(dados: dict, lat: float | None, lon: float | None, geocode: str | None) -> list[dict]:
    """Avisos de hoje e dos próximos dias que atingem o lugar, do mais cedo ao mais tarde."""
    vistos, saida = set(), []
    for chave in ("hoje", "futuro"):
        for aviso in dados.get(chave) or []:
            if str(aviso.get("encerrado")).lower() == "true" or aviso.get("id") in vistos:
                continue
            if atinge(aviso, lat, lon, geocode):
                vistos.add(aviso.get("id"))
                saida.append(resume(aviso))
    return sorted(saida, key=lambda a: (a["inicio"] or "", -(a["nivel"] or 0)))


def _baixa() -> dict:
    r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    dados = r.json()
    if not isinstance(dados, dict) or not ({"hoje", "futuro"} & dados.keys()):
        raise ValueError("formato inesperado da resposta do INMET")
    return dados


def avisos(lat: float | None = None, lon: float | None = None, geocode: str | None = None) -> dict:
    """Avisos do INMET para o lugar, com a lista inteira em cache por meia hora."""
    with _trava:
        guardado = _cache.get("ativos")
    if not guardado or time.time() - guardado[0] >= VALIDADE_S:
        try:
            guardado = (time.time(), _baixa())
            with _trava:
                _cache["ativos"] = guardado
        except Exception as e:  # rede, formato, limite de requisições
            print(f"[avisos_inmet] avisos indisponíveis: {type(e).__name__}: {e}", flush=True)
    if not guardado:
        return {"fonte": FONTE, "disponivel": False, "lido_em": None, "avisos": []}
    return {"fonte": FONTE, "disponivel": True, "lido_em": int(guardado[0]),
            "avisos": filtra(guardado[1], lat, lon, geocode)}


if __name__ == "__main__":  # diagnóstico manual e no GitHub Actions
    import sys
    dados = _baixa()
    print(f"INMET: {len(dados.get('hoje') or [])} avisos hoje, {len(dados.get('futuro') or [])} nos próximos dias")
    # Paragominas e Santarém: sede e geocódigo, para ver os dois caminhos.
    for nome, lat, lon, geo in (("Paragominas", -2.99, -47.35, "1505502"), ("Santarém", -2.44, -54.71, "1506807")):
        lista = filtra(dados, lat, lon, geo)
        print(f"{nome}: {len(lista)} aviso(s)")
        for a in lista:
            print(f"  {a['inicio']} a {a['fim']}  {a['evento']} ({a['severidade']})")
    sys.exit(0)
