# -*- coding: utf-8 -*-
"""Preço da soja recebido pelo produtor, por semana e por município, da CONAB.

Substitui a Notícias Agrícolas, que desde 12/11/2026 exige um desafio do
Cloudflare e barra acesso automático (issue #187). A CONAB publica os preços
agropecuários que levanta toda semana no Portal de Informações Agropecuárias,
como arquivo aberto.

Modo diagnóstico (--diagnostico): lista os arquivos de preço do portal e mostra
o cabeçalho, linhas de soja dos cinco estados do produto e os valores de cada
coluna, para conferir o formato antes de gravar qualquer coisa.
"""
import argparse
import collections
import re
import sys
import urllib.parse

import requests

PORTAL = "https://portaldeinformacoes.conab.gov.br/download-arquivos.html"
PASTA = "https://portaldeinformacoes.conab.gov.br/downloads/arquivos/"
CANDIDATOS = ["PrecosSemanalMunicipio.txt", "PrecosSemanalUF.txt",
              "PrecosMensalMunicipio.txt", "PrecosMensalUF.txt"]
UA = {"User-Agent": "AgroInteligencia-Dissertacao/1.0 (UFPA; pesquisa academica)"}
ESTADOS = {"PA", "MT", "MA", "TO", "RO"}
MAX_BYTES = 400_000_000


def links_do_portal() -> list[str]:
    r = requests.get(PORTAL, headers=UA, timeout=60)
    print(f"portal: HTTP {r.status_code}, {len(r.content)} bytes")
    hrefs = re.findall(r'href="([^"]+)"', r.text)
    arquivos = sorted({urllib.parse.urljoin(PORTAL, h) for h in hrefs
                       if re.search(r"\.(txt|csv|zip|xlsx?)$", h, re.I)})
    for a in arquivos:
        print("  arquivo:", a)
    return arquivos


def diagnostica(url: str) -> None:
    print(f"\n== {url}")
    try:
        r = requests.get(url, headers=UA, timeout=120, stream=True)
    except Exception as e:  # noqa: BLE001
        print("  falhou:", type(e).__name__, e)
        return
    print(f"  HTTP {r.status_code}; tipo {r.headers.get('Content-Type')}; "
          f"tamanho {r.headers.get('Content-Length')}")
    if r.status_code != 200:
        return
    cabecalho, n, lidos = None, 0, 0
    amostras, produtos, colunas = [], collections.Counter(), collections.defaultdict(collections.Counter)
    for bruto in r.iter_lines():
        lidos += len(bruto) + 1
        if lidos > MAX_BYTES:
            print("  parei no limite de bytes")
            break
        linha = bruto.decode("utf-8", "replace") if b"\xc3" in bruto else bruto.decode("latin-1")
        if cabecalho is None:
            cabecalho = linha
            sep = ";" if linha.count(";") >= linha.count(",") else ","
            nomes = [c.strip() for c in linha.split(sep)]
            print("  separador:", repr(sep))
            for i, c in enumerate(nomes):
                print(f"  coluna {i}: {c}")
            continue
        n += 1
        if "SOJA" not in linha.upper():
            continue
        campos = [c.strip() for c in linha.split(sep)]
        if not (ESTADOS & {c.upper() for c in campos}):
            continue
        produtos[" | ".join(c for c in campos if "SOJA" in c.upper())] += 1
        for i, c in enumerate(campos):
            colunas[i][c] += 1
        if len(amostras) < 12:
            amostras.append(linha)
    print(f"  linhas: {n}; bytes lidos: {lidos}")
    print("  produtos com soja nos cinco estados:", produtos.most_common(10))
    for linha in amostras:
        print("  amostra:", linha[:300])
    for i, cont in sorted(colunas.items()):
        print(f"  coluna {i}: {len(cont)} valores; ex.: {cont.most_common(6)}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diagnostico", action="store_true")
    args = ap.parse_args(argv)
    if args.diagnostico:
        try:
            achados = links_do_portal()
        except Exception as e:  # noqa: BLE001
            print("portal falhou:", type(e).__name__, e)
            achados = []
        urls = [u for u in achados if re.search(r"pre[cç]o", u, re.I)] or [PASTA + c for c in CANDIDATOS]
        for c in CANDIDATOS:
            if PASTA + c not in urls:
                urls.append(PASTA + c)
        for u in urls:
            diagnostica(u)
        return 0
    print("use --diagnostico por enquanto")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
