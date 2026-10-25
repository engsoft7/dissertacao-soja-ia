# -*- coding: utf-8 -*-
"""Preço estimado da soja no Pará ao longo do dia: Chicago em reais + base do Pará.

Nenhuma fonte pública publica o físico paraense em tempo real. A Agrolink
publica a praça de Barcarena (PA) todo dia, mas o valor diário vem como imagem,
de propósito, e este módulo não tenta lê-lo. O que a Agrolink publica em texto
é a média mensal do estado, ao lado da média nacional, e é dela que sai a base:

    base do mês = média do Pará no mês − média de Chicago no mês, em R$/saca

Chicago em reais é a mesma conta de mercado.py (contrato mais próximo da CBOT
vezes o dólar do mesmo dia). A estimativa do Pará em cada instante é a cotação
de Chicago daquele instante somada à base do mês dele; nos meses ainda sem
média publicada vale a base do último mês publicado. É assim que tradings e
cooperativas cotam: a bolsa se move ao longo do dia e a base, devagar, com
frete, prêmio de porto e época da safra.

O mês corrente entra com a média parcial que a Agrolink publica até a véspera,
comparada com a média de Chicago nos mesmos dias de pregão do mês.

Fonte: https://www.agrolink.com.br/cotacoes/historico/pa/soja-em-grao-sc-60kg
"""
from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests

import mercado

URL_AGROLINK = "https://www.agrolink.com.br/cotacoes/historico/pa/soja-em-grao-sc-60kg"
FONTE = "Agrolink, média mensal do Pará (praça publicada: Barcarena)"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
# A média mensal muda uma vez por dia, no máximo; meio dia de cache basta e
# poupa a fonte.
VALIDADE_S = 12 * 3600
MESES = 24
PRECO_MIN, PRECO_MAX = 40.0, 400.0
_cache, _trava = {}, threading.Lock()


def le_historico(html: str) -> list[dict]:
    """Linhas 'M/AAAA | estadual | nacional' da tabela da Agrolink, do mais antigo ao mais novo."""
    linhas = []
    padrao = re.compile(
        r"<th[^>]*>\s*(\d{1,2})/(\d{4})\s*</th>\s*<td[^>]*>\s*([\d.]+,\d+)\s*</td>\s*"
        r"<td[^>]*>\s*([\d.]+,\d+)\s*</td>", re.DOTALL)
    for m in padrao.finditer(html):
        mes, ano = int(m.group(1)), int(m.group(2))
        para, nacional = (float(x.replace(".", "").replace(",", ".")) for x in m.group(3, 4))
        if 1 <= mes <= 12 and PRECO_MIN <= para <= PRECO_MAX:
            linhas.append({"mes": f"{ano:04d}-{mes:02d}", "para": round(para, 2),
                           "nacional": round(nacional, 2)})
    unicos = {l["mes"]: l for l in linhas}
    return [unicos[k] for k in sorted(unicos)]


def mes_de(t: int) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m")


def medias_mensais(velas: list[dict]) -> dict[str, float]:
    """Média dos fechamentos diários de Chicago em R$/saca, por mês."""
    por_mes = defaultdict(list)
    for v in velas:
        por_mes[mes_de(v["t"])].append(v["c"])
    return {m: round(sum(vs) / len(vs), 2) for m, vs in por_mes.items()}


def combina(historico: list[dict], chicago: dict[str, float]) -> list[dict]:
    """Meses que têm as duas médias, com a base de cada um."""
    serie = []
    for linha in historico:
        c = chicago.get(linha["mes"])
        if c is None:
            continue
        serie.append({**linha, "chicago": c, "base": round(linha["para"] - c, 2)})
    return serie[-MESES:]


def base_em(serie: list[dict], t: int) -> float | None:
    """Base do mês do instante t; antes da primeira média publicada, nenhuma."""
    mes = mes_de(t)
    anteriores = [s for s in serie if s["mes"] <= mes]
    return anteriores[-1]["base"] if anteriores else None


def estima(cotacao: dict | None, serie: list[dict]) -> dict | None:
    """Velas com a estimativa do Pará ('pa') e o resumo para a interface.

    Não altera a cotação recebida, que mercado.py guarda em cache.
    """
    if not serie:
        return None
    ultimo = serie[-1]
    saida = {
        "fonte": FONTE,
        "url": URL_AGROLINK,
        "mes_base": ultimo["mes"],
        "base_brl_saca": ultimo["base"],
        "meses": serie,
        "estimado_brl_saca": None,
        "velas_pa": [],
    }
    if cotacao and cotacao.get("velas"):
        velas = cotacao["velas"]
        pa = []
        for v in velas:
            b = base_em(serie, v["t"])
            pa.append(None if b is None else round(v["c"] + b, 2))
        saida["velas_pa"] = pa
        b_agora = base_em(serie, velas[-1]["t"])
        if b_agora is not None:
            saida["estimado_brl_saca"] = round(velas[-1]["c"] + b_agora, 2)
    return saida


def _baixa_agrolink() -> list[dict]:
    r = requests.get(URL_AGROLINK, headers=UA, timeout=15)
    r.raise_for_status()
    return le_historico(r.text)


def _baixa_chicago_diario() -> dict[str, float]:
    params = {"range": "2y", "interval": "1d"}
    soja, cambio = (requests.get(mercado.URL.format(simbolo=s), params=params,
                                 headers={"User-Agent": "Mozilla/5.0"}, timeout=15).json()
                    for s in ("ZS=F", "BRL=X"))
    return medias_mensais(mercado.velas_em_reais(soja, cambio))


def serie_mensal() -> list[dict]:
    """Série mensal Pará × Chicago com a base, com cache de meio dia.

    Quando a fonte falha, devolve a última leitura boa; sem nenhuma, lista vazia,
    e a interface omite a estimativa em vez de inventar uma base.
    """
    with _trava:
        guardado = _cache.get("serie")
        if guardado and time.time() - guardado[0] < VALIDADE_S:
            return guardado[1]
    try:
        serie = combina(_baixa_agrolink(), _baixa_chicago_diario())
    except Exception as e:  # rede, formato, limite de requisições
        print(f"[precos_para] série mensal indisponível: {type(e).__name__}: {e}", flush=True)
        serie = []
    if not serie:
        return guardado[1] if guardado else []
    with _trava:
        _cache["serie"] = (time.time(), serie)
    return serie


if __name__ == "__main__":  # diagnóstico manual e no GitHub Actions
    s = serie_mensal()
    if not s:
        print("::warning::série mensal do Pará indisponível")
        # Qual das duas pontas falhou: a tabela da Agrolink ou as médias de Chicago.
        try:
            r = requests.get(URL_AGROLINK, headers=UA, timeout=15)
            hist = le_historico(r.text)
            print(f"Agrolink: HTTP {r.status_code}, {len(r.text)} caracteres, {len(hist)} meses lidos; "
                  f"últimos: {hist[-3:]}")
            if not hist:
                i = r.text.find("/2026")
                print("trecho da página:", r.text[max(0, i - 600):i + 600] if i >= 0 else r.text[:1200])
        except Exception as e:
            print(f"Agrolink: {type(e).__name__}: {e}")
        try:
            ch = _baixa_chicago_diario()
            print(f"Chicago: {len(ch)} meses; últimos: {sorted(ch.items())[-3:]}")
        except Exception as e:
            print(f"Chicago: {type(e).__name__}: {e}")
        raise SystemExit(1)
    print(f"{len(s)} meses; fonte: {FONTE}")
    for linha in s:
        print(f"  {linha['mes']}  Pará {linha['para']:7.2f}  Chicago {linha['chicago']:7.2f}  base {linha['base']:+7.2f}")
    agora = estima(mercado.cotacao("1d"), s)
    print("\nPará estimado agora:", agora and agora["estimado_brl_saca"])
