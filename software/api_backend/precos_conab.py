# -*- coding: utf-8 -*-
"""Preço da soja em grão recebido pelo produtor, média do mês no estado, da CONAB.

O workflow precos-conab.yml coleta todo dia os preços agropecuários que a CONAB
publica abertos e grava a soja dos cinco estados do produto em
pesquisa/dados/conab/precos_soja_mensal_uf.csv (ver
software/automacao_github/coleta_precos_conab.py). Este módulo só lê esse
arquivo: a API não depende do portal da CONAB estar no ar, e um mês novo chega
pelo merge automático da coleta, sem mexer no código.

Vai à tela Mercado do aplicativo e ao painel como referência oficial, ao lado
da cotação do dia da Agrolink: é preço de porteira, sem frete até o porto, e é
a média do mês. O mês vai sempre junto, para a tela não passar o número de um
mês passado por preço de hoje. O preço padrão da simulação continua o do
levantamento de custos (financas.py), que é da mesma praça do custo.
"""
from __future__ import annotations

import csv
import threading
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "conab" / "precos_soja_mensal_uf.csv"
FONTE = "CONAB, preço da soja em grão recebido pelo produtor, média do mês no estado"
URL = "https://portaldeinformacoes.conab.gov.br/download-arquivos.html"
PRECO_MIN, PRECO_MAX = 40.0, 400.0

_cache: dict = {}
_trava = threading.Lock()


def _linhas(arquivo: Path) -> list[dict]:
    """O CSV inteiro, relido só quando o arquivo muda (o merge da coleta troca o arquivo no servidor)."""
    try:
        marca = arquivo.stat().st_mtime_ns
    except OSError:
        return []
    with _trava:
        if _cache.get("chave") == (str(arquivo), marca):
            return _cache["linhas"]
    try:
        with arquivo.open(encoding="utf-8", newline="") as f:
            linhas = list(csv.DictReader(f))
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        print(f"[precos_conab] {arquivo}: {type(e).__name__}: {e}", flush=True)
        return []
    with _trava:
        _cache.update(chave=(str(arquivo), marca), linhas=linhas)
    return linhas


def mensal(uf: str, arquivo: Path | None = None) -> dict | None:
    """O mês mais recente da CONAB no estado, ou None quando não há.

    {"uf": "PA", "mes": "2026-10", "preco_saca": 133.8, "fonte": ..., "url": ...}
    """
    meses = []
    for l in _linhas(arquivo or ARQUIVO):
        if l.get("uf") != uf:
            continue
        try:
            ano, mes, preco = int(l["ano"]), int(l["mes"]), float(l["preco_saca"])
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= mes <= 12 and PRECO_MIN <= preco <= PRECO_MAX:
            meses.append((ano, mes, preco))
    if not meses:
        return None
    ano, mes, preco = max(meses)
    return {"uf": uf, "mes": f"{ano:04d}-{mes:02d}", "preco_saca": round(preco, 2), "fonte": FONTE, "url": URL}
