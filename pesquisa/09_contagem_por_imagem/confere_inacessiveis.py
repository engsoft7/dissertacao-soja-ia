# -*- coding: utf-8 -*-
"""
Segunda tentativa nos 38 trabalhos cujo texto a varredura não conseguiu ler
(varre_literatura.py, execução de 24/10/2026): MDPI, Elsevier, IEEE, Wiley,
SSRN e outros que recusam o leitor automático.

Para cada DOI tenta, nesta ordem:
1. o PDF aberto que o OpenAlex indica (best_oa_location e demais locais),
   lido com pypdf;
2. a página da editora com cabeçalhos de navegador;
3. variantes conhecidas da MDPI (/htm) e do Springer.
Do texto obtido, extrai a declaração de disponibilidade de dados e os links
de repositório, e consulta a licença de cada link como em varre_literatura.py.
O que continuar fechado fica marcado para a conferência por busca na web.

Uso:  python confere_inacessiveis.py
"""
import io
import json
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from varre_literatura import IGNORAR, LINKS, NEGADO, PEDIDO, SECAO, licenca_do_link, texto_limpo  # noqa: E402

NAVEGADOR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}

DOIS = """
10.3390/agronomy16050536
10.5281/zenodo.18898643
10.13031/aea.16563
10.1002/agj2.70303
10.3390/agriculture16192169
10.3390/agriculture15070796
10.3390/agriculture15060617
10.3390/agronomy15040791
10.3390/agriculture15050528
10.1109/tgrs.2025.3578800
10.3390/ai6070135
10.1016/j.atech.2025.101750
10.3390/rs17152688
10.1051/shsconf/202521601015
10.3390/electronics15010080
10.1016/j.compag.2024.108861
10.3390/agriculture14081423
10.3390/agronomy14112526
10.3390/agriculture14081347
10.3390/agriculture14020208
10.1111/pbr.13255
10.1109/icftic64248.2024.10913429
10.2139/ssrn.4822316
10.3390/agronomy13020541
10.3390/agronomy13041154
10.3390/agronomy13061507
10.1016/j.simpa.2023.100591
10.2139/ssrn.4639580
10.1016/j.compag.2022.106870
10.3390/agronomy12123209
10.1109/cvprw56347.2022.00173
10.1002/essoar.10510406.1
10.1590/2317-1545v43248996
10.1007/s11694-021-01124-0
10.1002/essoar.10508407.1
10.1109/access.2019.2916931
10.18517/ijaseit.8.4.6513
""".split()


def baixa(url):
    try:
        r = requests.get(url, headers=NAVEGADOR, timeout=40, allow_redirects=True)
        return r if r.status_code == 200 and len(r.content) > 3000 else None
    except requests.RequestException:
        return None


def texto_de(r):
    tipo = r.headers.get("content-type", "")
    if "pdf" in tipo or r.content[:4] == b"%PDF":
        try:
            from pypdf import PdfReader
            return " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages), "pdf"
        except Exception as e:
            return "", f"pdf ilegível ({type(e).__name__})"
    return texto_limpo(r.text), "html"


def candidatos(doi, w):
    urls = []
    for loc in ([w.get("best_oa_location")] if w.get("best_oa_location") else []) + (w.get("locations") or []):
        for campo in ("pdf_url", "landing_page_url"):
            u = (loc or {}).get(campo)
            if u and u not in urls:
                urls.append(u)
    urls.append(f"https://doi.org/{doi}")
    if doi.startswith("10.3390/"):
        for u in list(urls):
            if "mdpi.com" in u and not u.endswith("/htm"):
                urls.append(u.rstrip("/").removesuffix("/pdf") + "/htm")
    if doi.startswith("10.1007/"):
        urls.append(f"https://link.springer.com/content/pdf/{doi}.pdf")
    return urls


def main():
    resumo = []
    for doi in DOIS:
        r = requests.get(f"https://api.openalex.org/works/doi:{doi}", timeout=30)
        w = r.json() if r.status_code == 200 else {}
        titulo = (w.get("title") or "")[:110]
        print(f"\n--- {doi} | {titulo}")
        print(f"    acesso aberto: {(w.get('open_access') or {}).get('oa_status')}")
        texto, origem = "", ""
        for u in candidatos(doi, w):
            resp = baixa(u)
            if resp is None:
                print(f"    × {u}")
                continue
            t, tipo = texto_de(resp)
            if len(t) > 4000:
                texto, origem = t, f"{tipo}: {u}"
                break
            print(f"    × {u} ({tipo}, {len(t)} caracteres)")
            time.sleep(0.5)
        if not texto:
            print("    FECHADO: nenhum texto completo obtido")
            resumo.append((doi, titulo, "fechado", "", []))
            continue
        m = SECAO.search(texto)
        decl = re.sub(r"\s+", " ", texto[m.start(): m.start() + 600]) if m else ""
        links = sorted({l.rstrip(".,;") for l in LINKS.findall(texto) if not IGNORAR.search(l)})
        if links:
            classe = "link"
        elif decl and NEGADO.search(decl):
            classe = "não disponível"
        elif decl and PEDIDO.search(decl):
            classe = "sob pedido"
        elif decl:
            classe = "declaração sem link"
        else:
            classe = "sem declaração"
        print(f"    lido por {origem} | {classe}")
        if decl:
            print(f"    declaração: {decl[:450]}")
        lics = []
        for l in links[:6]:
            lic = licenca_do_link(l)
            lics.append(f"{l} [{lic}]")
            print(f"    dados: {l} → {lic}")
        resumo.append((doi, titulo, classe, decl[:300], lics))
        time.sleep(0.5)

    print("\n===== Resumo =====")
    cont = {}
    for _, _, c, _, _ in resumo:
        cont[c] = cont.get(c, 0) + 1
    print(json.dumps(cont, ensure_ascii=False))
    for doi, titulo, c, decl, lics in resumo:
        print(f"{c:20s} | {doi} | {titulo[:80]}")
        for l in lics:
            print(f"{'':20s}   {l}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
