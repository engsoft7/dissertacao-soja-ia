# -*- coding: utf-8 -*-
"""Janela de plantio da soja: ZARC e calendário de semeadura, de fontes oficiais.

- ZARC: a tábua de risco do Zoneamento Agrícola de Risco Climático, publicada
  pelo Ministério da Agricultura como dado aberto (licença Creative Commons
  Atribuição), uma por safra, no catálogo dados.agricultura.gov.br.
- Calendário de semeadura e vazio sanitário: Portaria SDA/MAPA nº 1.579, de 9
  de abril de 2026 (safra 2026/2027), e as normas estaduais que a detalham.

A verificação de certificado fica sempre ligada.

Modo diagnóstico (--diagnostico): mostra o que as fontes publicam, sem gravar.
"""
import argparse
import collections
import io
import json
import re
import sys

import requests

UA = {"User-Agent": "AgroInteligencia-Dissertacao/1.0 (UFPA; pesquisa academica)"}
CKAN = "https://dados.agricultura.gov.br/api/3/action/package_show?id=tabua-de-risco-zoneamento-agricola-de-risco-climatico"
ESTADOS = ("PA", "MT", "MA", "TO", "RO")
PORTARIA = [
    "https://www.embrapa.br/documents/1355202/1529289/20-+PORTARIA+SDA_MAPA+N%C2%BA+1579+DE+9+DE+ABRIL+DE+2026.pdf/030865a3-fcf0-a8e3-8047-797aac35c2bb",
    "https://www.abrasem.com.br/wp-content/uploads/2025/10/Portaria-SDA-n-1.579-DE-9-DE-ABRIL-DE-2026-Estabelece-os-periodos-de-vazio-sanitario-e-de-calendario-de-semeadura-de-soja-em-nivel-nacional.pdf",
]
DOU = "https://www.in.gov.br/web/dou/-/portaria-sda/mapa-n-1.579-de-9-de-abril-de-2026-698696654"
NORMAS_ESTADUAIS = {
    "RO": "https://rondonia.ro.gov.br/wp-content/uploads/2026/06/SEI_71685192_Instrucao_Normativa_4.pdf",
}
NOMES = {"PA": "PARÁ", "MT": "MATO GROSSO", "MA": "MARANHÃO", "TO": "TOCANTINS", "RO": "RONDÔNIA"}


def zarc_diagnostico() -> None:
    r = requests.get(CKAN, headers=UA, timeout=60)
    print(f"CKAN: HTTP {r.status_code}")
    recursos = r.json()["result"]["resources"]
    for rec in recursos:
        print(f"  recurso: {rec.get('name')!r} | {rec.get('format')} | {rec.get('size')} | {rec.get('url')}")
    alvo = next((x for x in recursos if "2026/2027" in (x.get("name") or "")), None)
    dic = next((x for x in recursos if "icion" in (x.get("name") or "").lower()), None)
    if dic:
        try:
            from pypdf import PdfReader
            pdf = requests.get(dic["url"], headers=UA, timeout=120).content
            texto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
            print("\n== dicionário de dados ==\n" + texto[:6000])
        except Exception as e:  # noqa: BLE001
            print("dicionário falhou:", type(e).__name__, e)
    if not alvo:
        print("sem recurso 2026/2027")
        return
    print(f"\n== tábua 2026/2027: {alvo['url']}")
    r = requests.get(alvo["url"], headers=UA, timeout=300, stream=True)
    print(f"  HTTP {r.status_code}; tamanho {r.headers.get('Content-Length')}")
    cab, sep, n, amostras = None, ";", 0, []
    por_uf, cont = collections.Counter(), collections.defaultdict(collections.Counter)
    municipios_alvo, valores_dec = [], collections.Counter()
    for bruto in r.iter_lines():
        linha = bruto.decode("utf-8", "replace")
        if cab is None:
            sep = ";" if linha.count(";") > linha.count(",") else ","
            cab = [c.strip().strip('"').lstrip("\ufeff") for c in linha.split(sep)]
            print("  colunas:", cab)
            continue
        n += 1
        campos = [c.strip().strip('"') for c in linha.split(sep)]
        reg = dict(zip(cab, campos))
        cultura = (reg.get("Nome_cultura") or reg.get("nome_cultura") or "").lower()
        uf = (reg.get("UF") or reg.get("uf") or "").upper()
        if "soja" not in cultura or uf not in ESTADOS:
            continue
        por_uf[uf] += 1
        for k, v in reg.items():
            if not k.lower().startswith("dec"):
                cont[k][v] += 1
            else:
                valores_dec[v] += 1
        if len(amostras) < 6:
            amostras.append(linha)
        if reg.get("municipio", "").upper() in ("PARAGOMINAS", "SORRISO") and len(municipios_alvo) < 60:
            municipios_alvo.append(" ".join(f"{k}={v}" for k, v in reg.items() if not k.startswith("dec"))
                                   + " | " + " ".join(reg.get(f"dec{i}", "") for i in range(1, 37)))
    print(f"  linhas: {n}; soja nos cinco estados por UF: {dict(por_uf)}")
    for a in amostras:
        print("  amostra:", a[:400])
    for k, c in cont.items():
        print(f"  {k}: {len(c)} valores; ex.: {c.most_common(8)}")
    print("  valores nas colunas dec:", valores_dec.most_common(12))
    for linha in municipios_alvo:
        print("  municipio:", linha[:500])


def texto_pdf(url: str) -> str:
    import pdfplumber
    pdf = requests.get(url, headers=UA, timeout=120).content
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        partes = []
        for p in doc.pages:
            partes.append(p.extract_text() or "")
            for t in p.extract_tables() or []:
                for linha in t:
                    partes.append(" | ".join((c or "").replace("\n", " ") for c in linha))
        return "\n".join(partes)


def dou_diagnostico() -> None:
    import html as html_mod
    r = requests.get(DOU, headers=UA, timeout=120)
    print(f"\n== DOU: HTTP {r.status_code}, {len(r.text)} caracteres")
    corpo = r.text
    i = corpo.find("ANEXO")
    corpo = corpo[i:] if i >= 0 else corpo
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", corpo):
        celulas = [html_mod.unescape(re.sub(r"<[^>]+>|\s+", " ", c)).strip()
                   for c in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", tr)]
        if celulas:
            print("  linha:", " || ".join(celulas)[:600])
    texto = html_mod.unescape(re.sub(r"\s+", " ", re.sub(r"(?is)<[^>]+>", " ", corpo)))
    for nome in ("Pará", "Maranhão", "Mato Grosso", "Tocantins", "Rondônia"):
        for m in re.finditer(nome, texto):
            print(f"  [{nome}] …{texto[max(0, m.start()-300):m.start()+300]}…")
    print("  notas:", texto[texto.find("1Abaíra") - 50:][:200] if "1Abaíra" in texto else "sem notas")
    j = texto.find("Pará") if False else -1
    # as notas de rodapé com listas de municípios (Pará e Maranhão têm regiões)
    for marca in re.finditer(r"(\d)([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:[ -][A-Za-záéíóúâêôãõçÁÉÍÓÚ]+)*,)", texto):
        trecho = texto[marca.start():marca.start() + 260]
        print(f"  nota {marca.group(1)}: {trecho}")


def calendario_diagnostico() -> None:
    try:
        dou_diagnostico()
    except Exception as e:  # noqa: BLE001
        print("DOU falhou:", type(e).__name__, e)
    for url in PORTARIA:
        print(f"\n== portaria: {url[:90]}")
        try:
            t = texto_pdf(url)
        except Exception as e:  # noqa: BLE001
            print("  falhou:", type(e).__name__, e)
            continue
        print(f"  {len(t)} caracteres")
        i = t.find("ANEXO")
        print(t[i:i + 9000])
        break  # a da Embrapa basta; a da Abrasem só se a primeira falhar
    for uf, url in NORMAS_ESTADUAIS.items():
        print(f"\n== norma estadual {uf}: {url}")
        try:
            t = texto_pdf(url)
            for m in re.finditer(r"(?i)(vazio sanit[áa]rio|calend[áa]rio de semeadura)[^.]{0,400}", t):
                print("  ", re.sub(r"\s+", " ", m.group(0))[:420])
        except Exception as e:  # noqa: BLE001
            print("  falhou:", type(e).__name__, e)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diagnostico", action="store_true")
    args = ap.parse_args(argv)
    if args.diagnostico:
        try:
            zarc_diagnostico()
        except Exception as e:  # noqa: BLE001
            print("ZARC falhou:", type(e).__name__, e)
        calendario_diagnostico()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
