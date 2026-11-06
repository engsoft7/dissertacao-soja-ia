#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auditoria_numeros.py

Auditoria dos números do aplicativo: o que a API em produção entrega para os
38 municípios, comparado com a fonte de cada número, lida aqui por conta
própria (sem o código da API).

  produtividade  IBGE, PAM (SIDRA, tabela 1612, variável 112, soja)
  praças do PA   Agrolink, páginas regionais de cada praça
  Chicago        Yahoo Finance (ZS=F em centavos de dólar por bushel, BRL=X)
  custo          levantamento da CONAB versionado em pesquisa/dados/conab
  avisos         INMET, avisos ativos (geocódigo do município)

Grava, em <saída>/api/, as respostas da API (o AuditoriaTest do aplicativo as
lê para conferir as telas com o código do próprio app) e, em <saída>/,
fontes.json e fontes.md com cada conferência: ok, divergente ou sem fonte.

Roda no Actions (auditoria-app.yml): o ambiente de desenvolvimento não alcança
nenhuma dessas fontes.

Uso: python software/automacao_github/auditoria_numeros.py [saída]
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[2]
API = "https://agrointeligencia-api.onrender.com"
SAIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "software/aplicativo_mobile/app/build/auditoria"
CABECALHO = {"User-Agent": "Mozilla/5.0 (auditoria AgroInteligencia)"}
BELEM = timezone(timedelta(hours=-3))
BUSHEL_POR_SACA = 60 / 27.2155     # saca de 60 kg em bushels de soja (27,2155 kg)
TEMPO_KOTLIN = RAIZ / "software/aplicativo_mobile/app/src/main/java/com/agrointeligencia/app/Tempo.kt"

conferencias: list[dict] = []


def registra(grupo, item, situacao, app=None, fonte=None, nota=""):
    conferencias.append({"grupo": grupo, "item": item, "situacao": situacao,
                         "app": app, "fonte": fonte, "nota": nota})


def pega(url, json_=True, tentativas=3, espera=90, **k):
    for i in range(tentativas):
        try:
            r = requests.get(url, headers=CABECALHO, timeout=espera, **k)
            r.raise_for_status()
            return r.json() if json_ else r.text
        except Exception as e:  # noqa: BLE001 - fonte fora do ar vira "sem fonte"
            if i == tentativas - 1:
                print(f"  falhou: {url} ({type(e).__name__}: {str(e)[:120]})", flush=True)
                return None
            time.sleep(10 * (i + 1))


def sedes() -> dict:
    """Sedes municipais do app (Tempo.kt): nome -> (lat, lon, geocódigo)."""
    t = TEMPO_KOTLIN.read_text(encoding="utf-8")
    return {n: (float(la), float(lo), g) for n, la, lo, g in
            re.findall(r'"([^"]+)" to LugarTempo\("[^"]+", (-?[\d.]+), (-?[\d.]+), "(\d{7})"\)', t)}


# ── API ──────────────────────────────────────────────────────────────────────
def api(rota):
    return pega(API + rota)


def baixa_api(municipios):
    destino = SAIDA / "api"
    destino.mkdir(parents=True, exist_ok=True)
    respostas = {"mercado": api("/api/mercado?periodo=1mo")}
    (destino / "mercado.json").write_text(json.dumps(respostas["mercado"], ensure_ascii=False), encoding="utf-8")
    for m in municipios:
        for rota in ("previsao", "financas"):
            r = api(f"/api/{rota}/{requests.utils.quote(m)}")
            respostas[(rota, m)] = r
            if r is not None:
                (destino / f"{rota}_{m}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    return respostas


# ── IBGE ─────────────────────────────────────────────────────────────────────
def pam_sidra(codigos):
    url = (f"https://apisidra.ibge.gov.br/values/t/1612/n6/{','.join(codigos)}"
           f"/v/112/p/all/c81/2713")
    linhas = pega(url, espera=120)
    if not linhas:
        return None
    cab = linhas[0]
    dim = {v: k[:-1] for k, v in cab.items() if k.endswith("N")}   # 'Município' -> 'D1'
    kmun = next(d for n, d in dim.items() if n.startswith("Munic"))
    kano = dim["Ano"]
    pam = {}
    for l in linhas[1:]:
        v = l["V"]
        if re.fullmatch(r"\d+(\.\d+)?", v or ""):
            pam[(l[kmun + "C"], int(l[kano + "C"]))] = float(v)
    return pam


def confere_pam(respostas, sede):
    codigos = sorted({g for _, _, g in sede.values()})
    pam = pam_sidra(codigos)
    if pam is None:
        registra("Produtividade (IBGE)", "SIDRA 1612", "sem fonte", nota="SIDRA não respondeu")
        return
    divergentes, conferidos = [], 0
    for m, (_, _, g) in sede.items():
        prev = respostas.get(("previsao", m))
        if not prev:
            continue
        for h in prev["historico"]:
            if h["rendimento_real"] <= 0:
                continue
            oficial = pam.get((g, h["ano"]))
            conferidos += 1
            if oficial is None:
                divergentes.append(f"{m} {h['ano']}: app {h['rendimento_real']:.0f}, sem valor no SIDRA")
            elif abs(oficial - h["rendimento_real"]) > 0.5:
                divergentes.append(f"{m} {h['ano']}: app {h['rendimento_real']:.0f}, IBGE {oficial:.0f}")
        # safra publicada pelo IBGE e ausente no app
        anos_app = {h["ano"] for h in prev["historico"] if h["rendimento_real"] > 0}
        for (gg, ano), v in pam.items():
            if gg == g and ano >= 2001 and ano not in anos_app and v > 0:
                divergentes.append(f"{m} {ano}: IBGE {v:.0f}, ausente no app")
    registra("Produtividade (IBGE)", f"{conferidos} safras município a município",
             "ok" if not divergentes else "divergente", nota=f"{len(divergentes)}: " + "; ".join(divergentes))


# ── Agrolink ─────────────────────────────────────────────────────────────────
def pracas_agrolink():
    achadas = {}
    for cidade in ("barcarena", "redencao", "paragominas", "parauapebas"):
        html = pega(f"https://www.agrolink.com.br/regional/pa/{cidade}/cotacoes", json_=False)
        if not html:
            continue
        html = html.replace('\\"', '"')
        for obj in re.findall(r"\{[^{}]*\}", html):
            if '"uf":"PA"' not in obj or not re.search(r'"produto":"Soja em Gr[^"]*60Kg"', obj):
                continue
            c = re.search(r'"cidade":"([^"]+)"', obj); p = re.search(r'"preco":([\d.]+)', obj)
            ms = re.search(r'"atualizacaoMs":(\d+)', obj)
            if c and p and ms:
                dia = datetime.fromtimestamp(int(ms.group(1)) / 1000, tz=BELEM).strftime("%Y-%m-%d")
                atual = achadas.get(c.group(1))
                if atual is None or dia > atual[1]:
                    achadas[c.group(1)] = (float(p.group(1)), dia)
    return achadas


def confere_pracas(mercado):
    fonte = pracas_agrolink()
    app = {p["praca"]: (p["valor"], p["data"]) for p in (mercado or {}).get("pracas_para") or []}
    if not fonte:
        registra("Praças do Pará (Agrolink)", "páginas regionais", "sem fonte")
        return
    for praca in sorted(set(fonte) | set(app)):
        a, f = app.get(praca), fonte.get(praca)
        if a is None or f is None:
            registra("Praças do Pará (Agrolink)", praca, "divergente", a, f,
                     "só no app" if f is None else "só na fonte")
        else:
            ok = abs(a[0] - f[0]) < 0.005 and a[1] == f[1]
            registra("Praças do Pará (Agrolink)", praca, "ok" if ok else "divergente",
                     f"R$ {a[0]:.2f} em {a[1]}", f"R$ {f[0]:.2f} em {f[1]}",
                     "" if ok else "a API guarda as praças por 2 h; refazer se a fonte mudou há pouco")


# ── Chicago ──────────────────────────────────────────────────────────────────
def yahoo(simbolo):
    j = pega(f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?range=1d&interval=5m")
    try:
        return j["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except Exception:  # noqa: BLE001
        return None


def confere_chicago(mercado):
    c = (mercado or {}).get("cotacao")
    zs, brl = yahoo("ZS=F"), yahoo("BRL=X")
    if not c or zs is None or brl is None:
        registra("Chicago (CBOT)", "cotação", "sem fonte", nota="API ou Yahoo sem resposta")
        return
    fonte = zs / 100 * BUSHEL_POR_SACA * brl
    dif = c["ultimo_brl_saca"] / fonte - 1
    registra("Chicago (CBOT)", "R$/saca", "ok" if abs(dif) < 0.015 else "divergente",
             f"R$ {c['ultimo_brl_saca']:.2f}", f"R$ {fonte:.2f}",
             f"diferença {dif * 100:+.2f}% (as duas leituras têm minutos de distância)")
    if c.get("ultimo_usd_bushel") and c.get("cambio"):
        conta = c["ultimo_usd_bushel"] * BUSHEL_POR_SACA * c["cambio"]
        registra("Chicago (CBOT)", "conversão da própria API", "ok" if abs(conta - c["ultimo_brl_saca"]) < 0.05
                 else "divergente", f"R$ {c['ultimo_brl_saca']:.2f}", f"R$ {conta:.2f}",
                 "US$/bushel × 2,2046 bushels/saca × câmbio")
    p = (mercado or {}).get("para") or {}
    if p.get("estimado_brl_saca") is not None:
        conta = c["ultimo_brl_saca"] + p["base_brl_saca"]
        registra("Média do Pará estimada", "Chicago + base", "ok" if abs(conta - p["estimado_brl_saca"]) < 0.05
                 else "divergente", f"R$ {p['estimado_brl_saca']:.2f}", f"R$ {conta:.2f}",
                 f"base de {p['mes_base']}: R$ {p['base_brl_saca']:+.2f}")


# ── CONAB ────────────────────────────────────────────────────────────────────
def confere_conab(respostas, municipios):
    lev = json.loads((RAIZ / "pesquisa/dados/conab/levantamento_atual.json").read_text(encoding="utf-8"))
    comp = lev.get("custo_por_componente") or {}
    fin = next((respostas.get(("financas", m)) for m in municipios if respostas.get(("financas", m))), None)
    if not fin:
        registra("Custo e preço (CONAB)", "financas", "sem fonte", nota="API sem resposta")
        return
    pares = [("custo_ha", lev["custo_operacional_ha"]), ("soja_preco_saca", lev["preco_recebido_saca"]),
             ("custo_area_ha", comp.get("area_ha")), ("custo_transporte_saca", comp.get("transporte_saca")),
             ("taxa_cessr", comp.get("taxa_receita"))]
    for campo, esperado in pares:
        v = fin.get(campo)
        ok = v is not None and esperado is not None and abs(v - esperado) < 1e-6
        registra("Custo e preço (CONAB)", campo, "ok" if ok else "divergente", v, esperado,
                 f"levantamento {lev['levantamento']} de {lev['praca']}")
    # O levantamento versionado contra a série do portal da CONAB (CSV baixado do portal).
    serie = (RAIZ / "pesquisa/dados/conab/serie_pedro_afonso_to.csv").read_text(encoding="utf-8").splitlines()
    ult = next((l for l in serie if l.startswith(f'"{lev["levantamento"]}"')), None)
    if ult:
        c = ult.split(";")
        fixo, variavel, preco = float(c[2]), float(c[3]), float(c[4])
        registra("Custo e preço (CONAB)", "levantamento × série do portal", "ok" if abs(preco - lev["preco_recebido_saca"]) < 0.005
                 and abs((fixo + variavel) * lev["produtividade_referencia_sc_ha"] - lev["custo_operacional_ha"]) < 1 else "divergente",
                 f"R$ {lev['preco_recebido_saca']:.2f}/sc; R$ {lev['custo_operacional_ha']:.2f}/ha",
                 f"R$ {preco:.2f}/sc; ({fixo} + {variavel}) × {lev['produtividade_referencia_sc_ha']:.0f} sc")
    if None not in (fin.get("custo_area_ha"), fin.get("custo_transporte_saca"), fin.get("taxa_cessr")):
        ref = lev["produtividade_referencia_sc_ha"]
        conta = fin["custo_area_ha"] + (fin["custo_transporte_saca"] + fin["taxa_cessr"] * fin["soja_preco_saca"]) * ref
        registra("Custo e preço (CONAB)", f"componentes somam o custo da CONAB ({ref:.0f} sc/ha)",
                 "ok" if abs(conta - fin["custo_ha"]) < 1 else "divergente",
                 f"R$ {conta:.2f}", f"R$ {fin['custo_ha']:.2f}")
    iguais = {json.dumps({k: f.get(k) for k in ("custo_ha", "soja_preco_saca")}) for m in municipios
              if (f := respostas.get(("financas", m)))}
    registra("Custo e preço (CONAB)", "mesmo levantamento nos 38 municípios", "ok" if len(iguais) == 1 else "divergente",
             nota=f"{len(iguais)} combinação(ões) de custo e preço")
    meses = fin.get("defasagem_meses")
    registra("Custo e preço (CONAB)", "idade do levantamento", "ok" if meses is not None and meses <= 12 else "verificar",
             meses, lev["levantamento"], "meses desde o levantamento; o app avisa o produtor")


# ── INMET ────────────────────────────────────────────────────────────────────
def confere_avisos(sede):
    ativos = pega("https://apiprevmet3.inmet.gov.br/avisos/ativos")
    if ativos is None:
        registra("Avisos (INMET)", "avisos ativos", "sem fonte")
        return
    todos = {}
    for k in ("hoje", "futuro"):
        for a in (ativos.get(k) or []) if isinstance(ativos, dict) else []:
            if str(a.get("encerrado")).lower() != "true":
                todos.setdefault(a.get("id"), a)
    for m in ("Paragominas", "Redenção", "Santarém", "Dom Eliseu", "Novo Progresso", "Altamira"):
        lat, lon, g = sede[m]
        r = api(f"/api/avisos?lat={lat}&lon={lon}&geocode={g}")
        no_app = {str(a["id"]) for a in (r or {}).get("avisos") or []}
        pelo_geocodigo = {str(i) for i, a in todos.items() if g in (a.get("geocodes") or "").split(",")}
        falta = pelo_geocodigo - no_app
        # A API também acha o aviso pelo polígono: a mais no app é esperado; a menos, não.
        registra("Avisos (INMET)", m, "ok" if not falta else "divergente", len(no_app), len(pelo_geocodigo),
                 (f"{len(no_app - pelo_geocodigo)} a mais pelo polígono do aviso" if no_app - pelo_geocodigo else "")
                 + (f"; faltam no app: {sorted(falta)}" if falta else ""))


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    print("acordando a API...", flush=True)
    pega(API + "/api/ping", espera=120)
    lista = (api("/api/municipios") or {}).get("municipios") or []
    sede = sedes()
    registra("Municípios", "lista da API × sedes do app", "ok" if set(lista) == set(sede) else "divergente",
             len(lista), len(sede), "; ".join(sorted(set(lista) ^ set(sede))))
    respostas = baixa_api(lista)
    faltam = [m for m in lista for r in ("previsao", "financas") if respostas.get((r, m)) is None]
    registra("API", "respostas dos 38 municípios", "ok" if not faltam else "divergente", nota="; ".join(faltam))
    confere_pam(respostas, {m: sede[m] for m in lista if m in sede})
    confere_pracas(respostas["mercado"])
    confere_chicago(respostas["mercado"])
    confere_conab(respostas, lista)
    confere_avisos(sede)

    agora = datetime.now(BELEM).strftime("%d/%m/%Y %H:%M")
    (SAIDA / "fontes.json").write_text(json.dumps({"em": agora, "conferencias": conferencias},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    linhas = [f"# Auditoria dos números: API × fontes ({agora}, horário de Belém)", "",
              "| Grupo | Item | Situação | App | Fonte | Nota |", "|---|---|---|---|---|---|"]
    for c in conferencias:
        linhas.append("| " + " | ".join(str(c[k] if c[k] is not None else "") .replace("|", "/")
                                         for k in ("grupo", "item", "situacao", "app", "fonte", "nota")) + " |")
    (SAIDA / "fontes.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    ruins = [c for c in conferencias if c["situacao"] != "ok"]
    print(f"{len(conferencias)} conferências, {len(ruins)} fora do ok", flush=True)
    for c in ruins:
        print(" ", c["grupo"], "|", c["item"], "|", c["situacao"], "|", c["nota"][:200], flush=True)


if __name__ == "__main__":
    main()
