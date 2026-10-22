# -*- coding: utf-8 -*-
"""Cotação da soja em Chicago ao longo do dia, em reais por saca, para a tela
Mercado do aplicativo.

Fonte: o gráfico do Yahoo Finance para o contrato mais próximo da soja na CBOT
(ZS=F, em centavos de dólar por bushel) e para o câmbio (BRL=X). É a mesma
fonte que o produto já usava para a cotação de bolsa. Não é tempo real: a CBOT
chega com atraso de 10 a 15 minutos, e a tela declara isso. Cotação em tempo
real exige licença paga de dados de mercado (CME ou B3).

A conversão de cada vela usa o câmbio do mesmo instante (o último publicado até
ali), e não o de agora: senão a variação do dólar ao longo do período
apareceria como se fosse do preço da soja.

    R$/saca = (centavos/bushel / 100) x 2,20462 bushels por saca x R$/US$

A saca tem 60 kg e o bushel de soja, 27,2155 kg.
"""
import bisect
import threading
import time

import requests

BUSHELS_POR_SACA = 60 / 27.2155
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}"
# período exibido -> granularidade das velas
PERIODOS = {"1d": "5m", "5d": "15m", "1mo": "60m", "6mo": "1d"}
VALIDADE_S = 120
_cache, _trava = {}, threading.Lock()


def _serie(resposta):
    """(instantes, abertura, máxima, mínima, fechamento, meta) de uma resposta do Yahoo."""
    r = resposta["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    return (r.get("timestamp") or [], q.get("open") or [], q.get("high") or [],
            q.get("low") or [], q.get("close") or [], r.get("meta") or {})


def velas_em_reais(soja, cambio):
    """Velas da soja convertidas para R$/saca, com o câmbio de cada instante.

    Velas sem preço (o Yahoo devolve None em minutos sem negócio) são
    descartadas. Antes do primeiro câmbio publicado no período vale o primeiro.
    """
    ts, ab, mx, mn, fe, _ = _serie(soja)
    tc, _, _, _, fc, meta_c = _serie(cambio)
    pares = [(t, c) for t, c in zip(tc, fc) if c]
    if not pares:
        reserva = meta_c.get("regularMarketPrice")
        if not reserva:
            return []
        pares = [(0, float(reserva))]
    instantes = [t for t, _ in pares]
    velas = []
    for t, o, h, l, c in zip(ts, ab, mx, mn, fe):
        if None in (o, h, l, c):
            continue
        i = max(bisect.bisect_right(instantes, t) - 1, 0)
        k = BUSHELS_POR_SACA * pares[i][1] / 100
        velas.append({"t": int(t), "o": round(o * k, 2), "h": round(h * k, 2),
                      "l": round(l * k, 2), "c": round(c * k, 2)})
    return velas


def resumo(soja, cambio, periodo):
    velas = velas_em_reais(soja, cambio)
    meta = _serie(soja)[5]
    meta_c = _serie(cambio)[5]
    if not velas:
        return None
    ultima, primeira = velas[-1], velas[0]
    return {
        "simbolo": "ZS=F",
        "fonte": "Yahoo Finance: soja na CBOT (contrato mais próximo) e dólar comercial",
        "periodo": periodo,
        "intervalo": PERIODOS[periodo],
        "atraso_min": int(meta.get("exchangeDataDelayedBy") or 10),
        "atualizado_em": int(meta.get("regularMarketTime") or ultima["t"]),
        "ultimo_brl_saca": ultima["c"],
        "ultimo_usd_bushel": round(float(meta.get("regularMarketPrice") or 0) / 100, 4) or None,
        "cambio": round(float(meta_c.get("regularMarketPrice") or 0), 4) or None,
        "variacao_periodo_pct": round((ultima["c"] / primeira["o"] - 1) * 100, 2),
        "maxima_periodo": max(v["h"] for v in velas),
        "minima_periodo": min(v["l"] for v in velas),
        "velas": velas,
    }


def _baixa(simbolo, periodo):
    r = requests.get(URL.format(simbolo=simbolo),
                     params={"range": periodo, "interval": PERIODOS[periodo]},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    r.raise_for_status()
    return r.json()


def cotacao(periodo="1d"):
    """Resumo do período, com cache curto para não sobrecarregar a fonte.

    Devolve None quando a fonte não responde; o cliente diz que a cotação está
    indisponível, em vez de exibir um número inventado.
    """
    if periodo not in PERIODOS:
        raise ValueError(f"período inválido: {periodo}")
    with _trava:
        guardado = _cache.get(periodo)
        if guardado and time.time() - guardado[0] < VALIDADE_S:
            return guardado[1]
    try:
        dados = resumo(_baixa("ZS=F", periodo), _baixa("BRL=X", periodo), periodo)
    except Exception as e:  # rede, formato, limite de requisições
        print(f"[mercado] cotação indisponível: {type(e).__name__}: {e}", flush=True)
        dados = None
    if dados is None:
        # a última leitura boa, se houver, com o horário dela: o cliente mostra
        # a hora da cotação, e o usuário vê que ela não é de agora
        return guardado[1] if guardado else None
    with _trava:
        _cache[periodo] = (time.time(), dados)
    return dados
