# -*- coding: utf-8 -*-
"""
Procura bases públicas de imagens de soja (vagens e plantas) e confere a
licença de cada uma, para o treino da contagem automática da Estimativa no
campo do aplicativo.

Só imagem com licença que permita uso num aplicativo gratuito com citação
(CC0, CC BY, CC BY-SA, MIT, Apache) pode entrar no treino sem pedir
autorização. "Sem licença declarada" quer dizer todos os direitos reservados:
precisa de autorização dos autores.

Consulta:
- repositórios no GitHub (API: licença do repositório e trechos do README
  sobre dados e licença);
- páginas de bases no Kaggle e no Roboflow Universe (texto de licença);
- artigos no arXiv (licença do artigo e links de dados no texto completo);
- buscas por "soybean pod" e afins no Zenodo, Figshare, Hugging Face e
  Wikimedia Commons, com a licença de cada resultado.

Não baixa imagens: só lê metadados e imprime o que cada fonte respondeu.
Roda no GitHub Actions, porque o ambiente de desenvolvimento não alcança
esses sites (negados pela política de rede).

Uso:  python confere_bases_de_imagens.py
"""
import json
import os
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) dissertacao-soja-ia/1.0"}
GH = {"Accept": "application/vnd.github+json", **UA}
if os.environ.get("GITHUB_TOKEN"):
    GH["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"

REPOS = [
    "JiangGuo921/soybean-pod-dataset",
    "JiajiaLi04/Soybean-Pod-Counting-from-UAV-Images",
    "Boatsure/PodNet",
    "UTokyo-FieldPhenomics-Lab/P2PNet-Soy",
    "eliezersflores/SoyCult",
]
PAGINAS = {
    "Kaggle SoybeanNet (página)": "https://www.kaggle.com/datasets/jiajiali/uav-based-soybean-pod-images",
    "Kaggle SoybeanNet (API)": "https://www.kaggle.com/api/v1/datasets/view/jiajiali/uav-based-soybean-pod-images",
    "Roboflow soybean_instance_segmentation": "https://universe.roboflow.com/prakhar-patidar/soybean_instance_segmentation-raqpm",
    "Roboflow soybean (image annotation)": "https://universe.roboflow.com/image-annotation-epo3y/soybean-uijee",
    "Roboflow busca 'soybean pod'": "https://universe.roboflow.com/search?q=soybean%20pod",
    "Roboflow busca 'pod'": "https://universe.roboflow.com/search?q=class%3Apod",
    "MDPI SPCN (BeanCount-1500)": "https://www.mdpi.com/2077-0472/14/8/1347",
}
ARXIV = {
    "GrowingSoy": "2406.00313",
    "SoybeanNet": "2310.10861",
    "Vagens em campo e laboratório": "2502.15286",
}
TERMOS = ["soybean pod", "soybean pods", "soybean plant counting", "soybean stand count", "soybean seedling"]

LICENCA = re.compile(
    r"(CC[ -]?BY(?:[ -](?:SA|NC|ND|NC-SA|NC-ND))*(?:[ -]\d\.\d)?|CC0|Creative Commons[^<\"]{0,60}|"
    r"public domain|MIT License|Apache(?:[ -]License)?[ -]2\.0|GPL-?\d|ODbL|"
    r"creativecommons\.org/(?:licenses|publicdomain)/[a-z\-]+/\d\.\d)", re.I)


def get(url, **kw):
    try:
        return requests.get(url, headers=kw.pop("headers", UA), timeout=30, **kw)
    except requests.RequestException as e:
        print(f"    sem resposta: {type(e).__name__}")
        return None


def cod(r):
    # Response com erro HTTP é falso em contexto booleano; por isso "is None".
    return "-" if r is None else r.status_code


def licencas_no_texto(texto, limite=8):
    vistos = []
    for m in LICENCA.finditer(texto):
        s = re.sub(r"\s+", " ", m.group(0)).strip()
        if s.lower() not in [v.lower() for v in vistos]:
            vistos.append(s)
        if len(vistos) >= limite:
            break
    return vistos


def trechos(texto, palavras, largura=160, limite=6):
    saida = []
    for p in palavras:
        for m in re.finditer(p, texto, re.I):
            a, b = max(0, m.start() - largura), min(len(texto), m.end() + largura)
            saida.append(re.sub(r"\s+", " ", texto[a:b]))
            if len(saida) >= limite:
                return saida
    return saida


def texto_limpo(html):
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", html)


def repos():
    print("\n===== GitHub =====")
    linhas = []
    for nome in REPOS:
        print(f"\n--- {nome}")
        r = get(f"https://api.github.com/repos/{nome}", headers=GH)
        if r is None or r.status_code != 200:
            print(f"    HTTP {cod(r)}")
            linhas.append((nome, "repositório não respondeu"))
            continue
        d = r.json()
        lic = (d.get("license") or {}).get("spdx_id") or "nenhuma declarada"
        print(f"    licença do repositório: {lic}; tamanho {d.get('size')} KB; atualizado {d.get('pushed_at')}")
        rd = get(f"https://api.github.com/repos/{nome}/readme", headers={**GH, "Accept": "application/vnd.github.raw"})
        if rd is not None and rd.status_code == 200:
            for t in trechos(rd.text, [r"licen[cs]e", r"dataset", r"download", r"terms", r"cite"], limite=8):
                print(f"    README: …{t}…")
            achadas = licencas_no_texto(rd.text)
            if achadas:
                print(f"    licenças citadas no README: {achadas}")
        linhas.append((nome, f"repositório: {lic}"))
    busca = get("https://api.github.com/search/repositories", headers=GH,
                params={"q": "soy-segmentation-ds OR growingsoy in:name,description,readme", "per_page": 10})
    if busca is not None and busca.status_code == 200:
        print("\n--- busca GrowingSoy no GitHub")
        for it in busca.json().get("items", []):
            print(f"    {it['full_name']}  licença: {(it.get('license') or {}).get('spdx_id')}  {it.get('description')}")
    return linhas


def paginas():
    print("\n===== Kaggle, Roboflow, MDPI =====")
    for nome, url in PAGINAS.items():
        print(f"\n--- {nome}\n    {url}")
        r = get(url)
        if r is None:
            continue
        print(f"    HTTP {r.status_code}, {len(r.text)} caracteres")
        if r.status_code != 200:
            continue
        if "api/v1" in url:
            try:
                d = r.json()
                print("    licenças:", d.get("licenses") or d.get("licenseName"), "| título:", d.get("title"))
                continue
            except ValueError:
                pass
        t = texto_limpo(r.text)
        print(f"    licenças no texto: {licencas_no_texto(r.text + t)}")
        for tr in trechos(t, [r"Data Availability", r"License", r"soybean pod", r"\bpods?\b"], limite=6):
            print(f"    …{tr}…")


def arxiv():
    print("\n===== arXiv =====")
    for nome, ident in ARXIV.items():
        print(f"\n--- {nome} ({ident})")
        r = get(f"https://arxiv.org/abs/{ident}")
        if r is not None and r.status_code == 200:
            print(f"    licença do artigo: {licencas_no_texto(r.text, 3)}")
        h = get(f"https://arxiv.org/html/{ident}")
        if h is None or h.status_code != 200:
            print(f"    texto completo em HTML: HTTP {cod(h)}")
            continue
        t = texto_limpo(h.text)
        links = sorted(set(re.findall(r"https?://(?:github\.com|www\.kaggle\.com|zenodo\.org|figshare\.com|"
                                      r"pan\.baidu\.com|drive\.google\.com|universe\.roboflow\.com|"
                                      r"huggingface\.co)[^\s\"'<>)]*", h.text)))
        print(f"    links de dados no texto: {links[:12]}")
        for tr in trechos(t, [r"Data Availability", r"available at", r"publicly available", r"licen[cs]e"], limite=6):
            print(f"    …{tr}…")


def zenodo():
    print("\n===== Zenodo =====")
    for termo in TERMOS:
        r = get("https://zenodo.org/api/records", params={"q": f'"{termo}"', "type": "dataset", "size": 10})
        if r is None or r.status_code != 200:
            print(f"  {termo}: HTTP {cod(r)}")
            continue
        for h in r.json().get("hits", {}).get("hits", []):
            md = h.get("metadata", {})
            lic = (md.get("license") or {}).get("id")
            print(f"  [{termo}] {md.get('title','')[:100]} | licença {lic} | {h.get('links', {}).get('self_html')}")


def figshare():
    print("\n===== Figshare =====")
    for termo in TERMOS:
        try:
            r = requests.post("https://api.figshare.com/v2/articles/search", headers=UA, timeout=30,
                              json={"search_for": f'"{termo}"', "item_type": 3, "page_size": 10})
        except requests.RequestException as e:
            print(f"  {termo}: sem resposta ({type(e).__name__})")
            continue
        if r.status_code != 200:
            print(f"  {termo}: HTTP {r.status_code}")
            continue
        for it in r.json():
            d = get(f"https://api.figshare.com/v2/articles/{it['id']}")
            lic = d.json().get("license", {}).get("name") if d is not None and d.status_code == 200 else "?"
            print(f"  [{termo}] {it.get('title','')[:100]} | licença {lic} | {it.get('url_public_html')}")


def huggingface():
    print("\n===== Hugging Face =====")
    for termo in ["soybean", "soy pod", "pod counting"]:
        r = get("https://huggingface.co/api/datasets", params={"search": termo, "limit": 30, "full": "true"})
        if r is None or r.status_code != 200:
            print(f"  {termo}: HTTP {cod(r)}")
            continue
        for d in r.json():
            lic = [t for t in d.get("tags", []) if t.startswith("license:")]
            print(f"  [{termo}] {d.get('id')} | {lic or 'sem licença'}")


def commons():
    print("\n===== Wikimedia Commons =====")
    r = get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": "soybean pods OR \"Glycine max\" pod", "gsrlimit": 50,
        "prop": "imageinfo", "iiprop": "extmetadata|size"})
    if r is None or r.status_code != 200:
        print(f"  HTTP {cod(r)}")
        return
    paginas = r.json().get("query", {}).get("pages", {}).values()
    contagem = {}
    for p in paginas:
        ii = (p.get("imageinfo") or [{}])[0]
        lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "?")
        contagem[lic] = contagem.get(lic, 0) + 1
        print(f"  {p.get('title')} | {lic} | {ii.get('width')}x{ii.get('height')}")
    print(f"  total por licença: {json.dumps(contagem, ensure_ascii=False)}")


ABERTAS_HF = [
    "Project-AgML/YOLOPOD_Soyabean_Pod_Counting_Dataset",
    "Project-AgML/mtl_plotcounter_soybean_detection",
    "pspawar71/SOYBEAN_UAV_RGB",
    "lisawen/soybean_dataset",
]


def detalhes_abertas():
    """O que há dentro das bases de licença aberta achadas na primeira rodada."""
    print("\n===== Bases abertas: conteúdo =====")
    for nome in ABERTAS_HF:
        print(f"\n--- Hugging Face {nome}")
        r = get(f"https://huggingface.co/api/datasets/{nome}")
        if r is None or r.status_code != 200:
            print(f"    HTTP {cod(r)}")
            continue
        d = r.json()
        arquivos = [s_["rfilename"] for s_ in d.get("siblings", [])]
        print(f"    licença: {[t for t in d.get('tags', []) if t.startswith('license:')]}; "
              f"{len(arquivos)} arquivos; exemplos: {arquivos[:8]}")
        rd = get(f"https://huggingface.co/datasets/{nome}/raw/main/README.md")
        if rd is not None and rd.status_code == 200:
            print("    README: " + re.sub(r"\s+", " ", rd.text)[:1800])
    print("\n--- Zenodo 18898644 (SP-YOLO)")
    r = get("https://zenodo.org/api/records/18898644")
    if r is not None and r.status_code == 200:
        md = r.json().get("metadata", {})
        print(f"    {md.get('title')} | licença {(md.get('license') or {}).get('id')} | {md.get('publication_date')}")
        print("    descrição: " + re.sub(r"\s+", " ", texto_limpo(md.get("description") or ""))[:1800])
        for f in r.json().get("files", [])[:20]:
            print(f"    arquivo: {f.get('key')} ({(f.get('size') or 0) / 1e6:.1f} MB)")
    else:
        print(f"    HTTP {cod(r)}")
    print("\n--- GitHub raulsteinmetz/soy-segmentation-ds (GrowingSoy)")
    rd = get("https://api.github.com/repos/raulsteinmetz/soy-segmentation-ds/readme",
             headers={**GH, "Accept": "application/vnd.github.raw"})
    if rd is not None and rd.status_code == 200:
        print("    README: " + re.sub(r"\s+", " ", rd.text)[:1800])
    arv = get("https://api.github.com/repos/raulsteinmetz/soy-segmentation-ds/git/trees/HEAD?recursive=1", headers=GH)
    if arv is not None and arv.status_code == 200:
        itens = arv.json().get("tree", [])
        ext = {}
        for it in itens:
            if it.get("type") == "blob":
                e = it["path"].rsplit(".", 1)[-1].lower()
                ext[e] = ext.get(e, 0) + 1
        print(f"    arquivos por extensão: {ext}")


def main():
    linhas = repos()
    for etapa in (detalhes_abertas, paginas, arxiv, zenodo, figshare, huggingface, commons):
        try:
            etapa()
        except Exception as e:  # uma fonte fora do ar não esconde as outras
            print(f"\n!! {etapa.__name__} falhou: {type(e).__name__}: {e}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("## Licenças dos repositórios de imagens de soja\n\n| Repositório | Licença |\n|---|---|\n")
            for nome, lic in linhas:
                f.write(f"| {nome} | {lic} |\n")
            f.write("\nO detalhe de cada fonte está no log do passo.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
