# -*- coding: utf-8 -*-
"""
Robustez e desempenho da API em produção, do jeito que o aplicativo a usa.

    python teste_api.py <pasta de saída>

1. Espera a API servir a versão da main (a safra de Pau D'Arco que a correção
   de 06/11/2026 trouxe), até 20 min depois do merge.
2. Tempo de resposta e tamanho de cada rota que o app chama, nos 38 municípios,
   e se a resposta vem comprimida.
3. Entradas que o app não manda, mas que um cliente qualquer pode mandar:
   município inexistente, nome enorme, caracteres especiais, coordenadas fora
   do lugar, corpo inválido. Nada disso pode virar erro 500 nem refletir HTML.
4. Requisições simultâneas, como 30 celulares abrindo o app juntos.
5. Hosts externos que a página do mapa carrega (para a política de privacidade).

Grava api.json e api.md na pasta de saída. A variável AUDITORIA_API troca a
instância conferida.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import requests

API = (os.environ.get("AUDITORIA_API") or "https://agrointeligencia-api.onrender.com").rstrip("/")
SAIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("teste_api")
SAIDA.mkdir(parents=True, exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = "AgroInteligencia-teste-premium/1.0"

verificacoes: list[dict] = []
medidas: dict = {}


def verifica(item: str, ok: bool, detalhe: str = "") -> None:
    verificacoes.append({"item": item, "ok": bool(ok), "detalhe": detalhe})
    print(("ok    " if ok else "FALHA ") + item + (f" ({detalhe})" if detalhe else ""), flush=True)


def pede(metodo: str, rota: str, **kw):
    t0 = time.perf_counter()
    try:
        r = S.request(metodo, API + rota, timeout=kw.pop("timeout", 90), **kw)
        return r, (time.perf_counter() - t0) * 1000
    except requests.RequestException as e:
        return e, (time.perf_counter() - t0) * 1000


def status(r) -> str:
    return str(r.status_code) if isinstance(r, requests.Response) else type(r).__name__


def p(v: list[float], q: float) -> float:
    v = sorted(v)
    return round(v[min(len(v) - 1, int(q * len(v)))], 0) if v else float("nan")


def espera_versao(minutos: int = 20) -> bool:
    fim = time.time() + minutos * 60
    while time.time() < fim:
        r, _ = pede("GET", "/api/previsao/" + quote("Pau D'Arco"))
        if isinstance(r, requests.Response) and r.ok:
            proj = [h["ano"] for h in r.json()["historico"] if h["rendimento_real"] == 0]
            if proj and proj[0] == 2026:
                return True
        time.sleep(30)
    return False


def main() -> None:
    r, ms = pede("GET", "/api/ping", timeout=180)
    medidas["ping_inicial_ms"] = round(ms)
    verifica("API responde", isinstance(r, requests.Response) and r.ok, f"{status(r)} em {ms:.0f} ms")
    verifica("API serve a correção da main (Pau D'Arco projeta 2026–2028)", espera_versao())

    municipios = pede("GET", "/api/municipios")[0].json()
    if isinstance(municipios, dict):
        municipios = next(v for v in municipios.values() if isinstance(v, list))
    nomes = [m if isinstance(m, str) else (m.get("nome") or m.get("municipio")) for m in municipios]
    verifica("lista com os 38 municípios", len(nomes) == 38, str(len(nomes)))

    # Tempo e tamanho por rota. Duas passadas: a primeira aquece o cache.
    rotas = {"previsao": [f"/api/previsao/{quote(n)}" for n in nomes],
             "financas": [f"/api/financas/{quote(n)}" for n in nomes],
             "municipios": ["/api/municipios"] * 5, "kpis_economia": ["/api/kpis_economia"] * 5,
             "mercado 1d": ["/api/mercado?periodo=1d"] * 5, "mercado 1mo": ["/api/mercado?periodo=1mo"] * 3,
             "contador": ["/api/contador"] * 5,
             "avisos (geocode)": ["/api/avisos?geocode=1505502"] * 3,
             "avisos (lat/lon)": ["/api/avisos?lat=-2.99&lon=-47.35"] * 3,
             "mapa/render": [f"/api/mapa/render?theme=light&municipio={quote(n)}" for n in nomes[:5]]}
    medidas["rotas"] = {}
    for nome, lista in rotas.items():
        for r_ in lista[:2]:
            pede("GET", r_)
        tempos, tamanhos, comprimido, erros = [], [], 0, 0
        for r_ in lista:
            r, ms = pede("GET", r_, headers={"Accept-Encoding": "gzip"})
            if not (isinstance(r, requests.Response) and r.ok):
                erros += 1
                continue
            tempos.append(ms)
            tamanhos.append(len(r.content))
            comprimido += r.headers.get("Content-Encoding", "") in ("gzip", "br")
        medidas["rotas"][nome] = {"n": len(lista), "erros": erros, "p50_ms": p(tempos, .5), "p95_ms": p(tempos, .95),
                                 "kb_medio": round(statistics.mean(tamanhos) / 1024, 1) if tamanhos else None,
                                 "comprimido": f"{comprimido}/{len(tempos)}"}
        verifica(f"{nome}: sem erro", erros == 0, f"{erros} de {len(lista)}")

    # Entradas fora do que o app manda.
    estranhos = [
        ("município inexistente", "GET", "/api/previsao/Nenhures", {}, {404}),
        ("nome com 5.000 letras", "GET", "/api/previsao/" + "a" * 5000, {}, {404, 414}),
        # O firewall do Render barra cara de injeção de SQL antes da API (403).
        ("aspas e ponto e vírgula", "GET", "/api/previsao/" + quote("x'; DROP TABLE x;--"), {}, {403, 404}),
        ("caminho com ../", "GET", "/api/previsao/" + quote("../../etc/passwd", safe=""), {}, {404}),
        ("emoji", "GET", "/api/previsao/" + quote("🌱"), {}, {404}),
        ("finanças de município inexistente", "GET", "/api/financas/Nenhures", {}, {404, 200}),
        ("avisos sem parâmetros", "GET", "/api/avisos", {}, {400, 422}),
        ("avisos com lat não numérica", "GET", "/api/avisos?lat=abc&lon=1", {}, {422}),
        ("avisos fora da Terra", "GET", "/api/avisos?lat=999&lon=999", {}, {200, 400, 422}),
        ("avisos com geocode estranho", "GET", "/api/avisos?geocode=" + quote("<script>"), {}, {200, 400, 404, 422}),
        ("mercado com período inválido", "GET", "/api/mercado?periodo=zzz", {}, {200, 400, 422}),
        ("simulação sem corpo", "POST", "/api/simulacao", {}, {422}),
        ("simulação com tipos errados", "POST", "/api/simulacao", {"json": {"municipio": 1, "precip_factor": "x"}}, {422}),
        ("simulação com fator enorme", "POST", "/api/simulacao",
         {"json": {"municipio": "Paragominas", "precip_factor": 1e9, "temp_offset": 1e9}}, {200, 400, 422}),
        ("simulação de município inexistente", "POST", "/api/simulacao",
         {"json": {"municipio": "Nenhures", "precip_factor": 1, "temp_offset": 0}}, {404}),
        ("rota inexistente", "GET", "/api/nada", {}, {404}),
    ]
    medidas["entradas_estranhas"] = []
    for nome, metodo, rota, kw, esperado in estranhos:
        r, ms = pede(metodo, rota, **kw)
        st = status(r)
        corpo = r.text[:300] if isinstance(r, requests.Response) else ""
        medidas["entradas_estranhas"].append({"caso": nome, "status": st, "ms": round(ms)})
        ok = st.isdigit() and int(st) in esperado
        verifica(f"entrada estranha: {nome}", ok, f"HTTP {st}" + ("" if ok else f": {corpo[:120]}"))

    # A página do mapa não pode devolver HTML que veio da URL.
    carga = "<script>alert(1)</script>"
    r, _ = pede("GET", "/api/mapa/render?theme=" + quote(carga) + "&municipio=" + quote(carga))
    refletiu = isinstance(r, requests.Response) and carga in r.text
    verifica("mapa não reflete HTML vindo da URL", not refletiu, status(r))

    # 30 celulares ao mesmo tempo.
    alvo = [f"/api/previsao/{quote(n)}" for n in nomes[:30]]
    t0 = time.perf_counter()
    with ThreadPoolExecutor(30) as ex:
        resp = list(ex.map(lambda r_: pede("GET", r_), alvo))
    total = (time.perf_counter() - t0) * 1000
    erros = sum(1 for r, _ in resp if not (isinstance(r, requests.Response) and r.ok))
    tempos = [ms for _, ms in resp]
    medidas["simultaneas_30"] = {"erros": erros, "total_ms": round(total), "p50_ms": p(tempos, .5),
                                 "p95_ms": p(tempos, .95), "max_ms": round(max(tempos))}
    verifica("30 requisições simultâneas sem erro", erros == 0, f"p95 {p(tempos, .95):.0f} ms")

    # Cabeçalhos.
    r, _ = pede("GET", "/api/ping", headers={"Origin": "https://exemplo.org"})
    medidas["cabecalhos_ping"] = {k: v for k, v in r.headers.items()
                                  if k.lower().startswith(("access-control", "strict-transport", "x-", "server", "content-security"))}
    try:
        sem_tls = requests.get(API.replace("https://", "http://") + "/api/ping", timeout=60, allow_redirects=False)
        verifica("HTTP sem criptografia redireciona para HTTPS", sem_tls.status_code in (301, 302, 307, 308),
                 str(sem_tls.status_code))
    except requests.RequestException as e:
        verifica("HTTP sem criptografia redireciona para HTTPS", True, f"recusado ({type(e).__name__})")

    # Hosts externos da página do mapa.
    r, _ = pede("GET", "/api/mapa/render?theme=light&municipio=Paragominas")
    hosts = sorted(set(re.findall(r"https?://([a-zA-Z0-9.{}-]+)", r.text))) if isinstance(r, requests.Response) else []
    medidas["mapa_hosts_externos"] = hosts


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        verifica("roteiro completo", False, f"{type(e).__name__}: {e}")
    (SAIDA / "api.json").write_text(json.dumps({"api": API, "verificacoes": verificacoes, "medidas": medidas},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    linhas = [f"# API em produção: robustez e desempenho ({API})", "",
              "| Verificação | Resultado | Detalhe |", "|---|---|---|"]
    linhas += [f"| {v['item']} | {'ok' if v['ok'] else '**falha**'} | {v['detalhe']} |" for v in verificacoes]
    linhas += ["", "## Rotas (duas passadas de aquecimento antes)", "",
               "| Rota | n | erros | p50 (ms) | p95 (ms) | KB | comprimido |", "|---|---|---|---|---|---|---|"]
    for nome, d in medidas.get("rotas", {}).items():
        linhas.append(f"| {nome} | {d['n']} | {d['erros']} | {d['p50_ms']} | {d['p95_ms']} | {d['kb_medio']} | {d['comprimido']} |")
    linhas += ["", "## Outras medidas", "", "```", json.dumps({k: v for k, v in medidas.items() if k != "rotas"},
                                                              ensure_ascii=False, indent=1), "```"]
    (SAIDA / "api.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
