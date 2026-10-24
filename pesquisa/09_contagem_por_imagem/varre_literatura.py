# -*- coding: utf-8 -*-
"""
Varredura da literatura sobre contagem de vagens, grãos e plantas de soja por
imagem, atrás dos trabalhos que publicaram os dados e em que termos.

1. Busca no OpenAlex (2015 em diante) com várias frases e guarda os trabalhos
   cujo título ou resumo fala de soja, de contagem ou detecção de vagens,
   grãos, plântulas ou estande, e de imagem (visão computacional, aprendizado
   profundo, drone, câmera).
2. Para cada trabalho, procura a declaração de disponibilidade de dados e os
   links de repositório no texto completo aberto: Europe PMC (XML), arXiv
   (HTML) e a página da editora, quando ela responde a robôs.
3. Classifica a disponibilidade (link público, sob pedido, não disponível,
   sem informação) e, para cada link de GitHub, Zenodo, Figshare, Hugging
   Face ou Kaggle, consulta a licença declarada no repositório.

Não baixa dados. Imprime o detalhe de cada trabalho e, no fim, uma tabela só
com os que têm link de dados, e escreve a mesma tabela no resumo da execução.
Roda no GitHub Actions (o ambiente de desenvolvimento não alcança essas APIs).

Uso:  python varre_literatura.py
"""
import json
import os
import re
import sys
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) dissertacao-soja-ia/1.0 (mailto:pesquisa@example.org)"}
GH = {"Accept": "application/vnd.github+json", **UA}
if os.environ.get("GITHUB_TOKEN"):
    GH["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"

FRASES = [
    "soybean pod counting", "soybean pod detection", "soybean pod image deep learning",
    "soybean pod phenotyping image", "soybean seed counting image", "soybean seed per pod image",
    "soybean plant counting image", "soybean stand count", "soybean seedling counting",
    "soybean emergence UAV counting", "soybean yield estimation pods image",
]
SOJA = re.compile(r"soy", re.I)
# Contar ou localizar o objeto: "pod counting", "detection of soybean pods",
# "seedling count", "stand count". Genética de componentes de rendimento
# (QTL, genes) fala de vagens e grãos sem nenhuma imagem, e fica de fora.
ALVO = re.compile(r"(pods?|seeds?|seedlings?|plants?|stand)\b[^.]{0,50}?(count|detect|segment|recogni|locali)|"
                  r"(count|detect|segment|recogni|locali)\w*[^.]{0,50}?\b(pods?|seeds?|seedlings?|plants?|stand)\b", re.I)
IMAGEM = re.compile(r"deep learning|image|imagery|machine vision|computer vision|yolo|\bcnn\b|convolution|"
                    r"\buav\b|drone|transformer|neural network|camera", re.I)
FORA = re.compile(r"\bQTL|\bgene\b|genes\b|transcript|genom|metabol|proteom|GWAS|marker", re.I)
LINKS = re.compile(r"https?://(?:www\.)?(?:github\.com|gitee\.com|zenodo\.org|doi\.org/10\.5281|figshare\.com|"
                   r"[a-z]+\.figshare\.com|huggingface\.co|kaggle\.com|universe\.roboflow\.com|data\.mendeley\.com|"
                   r"doi\.org/10\.17632|pan\.baidu\.com|drive\.google\.com|ieee-dataport\.org|datadryad\.org|"
                   r"osf\.io|scidb\.cn|doi\.org/10\.57760|aistudio\.baidu\.com|agdatacommons)[^\s\"'<>)\]]*", re.I)
SECAO = re.compile(r"(data availability|availability of data|data and code availability|data accessibility|"
                   r"code availability|dataset availability|supplementary data)", re.I)
PEDIDO = re.compile(r"reasonable request|upon request|on request|request to the corresponding|"
                    r"available from the corresponding|contact the (?:corresponding )?author", re.I)
NEGADO = re.compile(r"not publicly available|cannot be shared|are not available|confidential|privacy", re.I)
# Links que toda página da editora ou do arXiv carrega (scripts, menus, ajuda)
# e ferramentas de terceiros citadas no método: não são os dados do trabalho.
IGNORAR = re.compile(r"github\.com/(?:arXiv|brucemiller|ultralytics|pytorch|open-mmlab|facebookresearch|"
                     r"tensorflow|wkentaro|tzutalin|heartexlabs|HumanSignal|WongKinYiu|AlexeyAB|"
                     r"TencentYoutuResearch|cocodataset|newrelic|ncbi|PLOS)\b|"
                     r"(?:widgets|api|info)\.figshare\.com|figshare\.com/(?:terms|browse|search|authors|$)|"
                     r"figshare\.com/?$|scielo\.figshare\.com/?(?:$|bra-pat)|ndownloader|"
                     r"huggingface\.co/(?:docs|huggingface)|pan\.baidu\.com/?$|github\.com/?$", re.I)


def get(url, headers=None, **kw):
    for tentativa in range(3):
        try:
            r = requests.get(url, headers=headers or UA, timeout=30, **kw)
            if r.status_code in (429, 503):
                time.sleep(3 * (tentativa + 1))
                continue
            return r
        except requests.RequestException:
            time.sleep(2)
    return None


def resumo(w):
    inv = w.get("abstract_inverted_index") or {}
    pos = {}
    for palavra, lugares in inv.items():
        for p in lugares:
            pos[p] = palavra
    return " ".join(pos[i] for i in sorted(pos))


def busca_openalex():
    achados = {}
    for frase in FRASES:
        cursor = "*"
        for _ in range(2):  # até 400 por frase
            r = get("https://api.openalex.org/works", params={
                "search": frase, "filter": "from_publication_date:2015-01-01",
                "per-page": 200, "cursor": cursor,
                "select": "id,doi,title,publication_year,primary_location,best_oa_location,ids,"
                          "abstract_inverted_index,open_access,locations,cited_by_count"})
            if r is None or r.status_code != 200:
                print(f"  OpenAlex '{frase}': HTTP {'-' if r is None else r.status_code}")
                break
            d = r.json()
            for w in d.get("results", []):
                texto = (w.get("title") or "") + " " + resumo(w)
                if (SOJA.search(w.get("title") or "") and ALVO.search(texto) and IMAGEM.search(texto)
                        and not FORA.search(w.get("title") or "")):
                    achados[w["id"]] = w
            cursor = d.get("meta", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.2)
        print(f"  '{frase}': acumulado {len(achados)}")
    return list(achados.values())


def texto_limpo(html):
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def fontes_de_texto(w):
    """URLs de texto completo a tentar, da mais à menos legível por máquina."""
    urls = []
    pmcid = (w.get("ids") or {}).get("pmcid")
    if pmcid:
        n = pmcid.rstrip("/").split("/")[-1]
        urls.append(("europepmc", f"https://www.ebi.ac.uk/europepmc/webservices/rest/{n}/fullTextXML"))
    for loc in w.get("locations") or []:
        u = (loc.get("landing_page_url") or "")
        m = re.search(r"arxiv\.org/abs/([\d.]+)", u)
        if m:
            urls.append(("arxiv", f"https://arxiv.org/html/{m.group(1)}"))
    oa = (w.get("best_oa_location") or {}).get("landing_page_url")
    if oa:
        urls.append(("editora", oa))
    if w.get("doi"):
        urls.append(("doi", w["doi"]))
    vistos, saida = set(), []
    for tipo, u in urls:
        if u not in vistos:
            vistos.add(u)
            saida.append((tipo, u))
    return saida


def disponibilidade(w):
    links, declaracao, origem = set(), "", ""
    for tipo, url in fontes_de_texto(w):
        r = get(url)
        if r is None or r.status_code != 200 or len(r.text) < 2000:
            continue
        texto = texto_limpo(r.text)
        if len(texto) < 3000:  # página de bloqueio ou só resumo
            continue
        for l in LINKS.findall(r.text):
            l = l.rstrip(".,;")
            if not IGNORAR.search(l):
                links.add(l)
        m = SECAO.search(texto)
        if m:
            declaracao = texto[m.start(): m.start() + 600]
            # Links escritos na própria declaração valem mais que os do resto
            # da página: são os que o autor indicou como os dados.
            for l in LINKS.findall(declaracao):
                l = l.rstrip(".,;")
                if not IGNORAR.search(l):
                    links.add("★" + l)
        origem = tipo
        if declaracao or links:
            break
        time.sleep(0.3)
    if links:
        classe = "link público"
    elif declaracao and NEGADO.search(declaracao):
        classe = "não disponível"
    elif declaracao and PEDIDO.search(declaracao):
        classe = "sob pedido"
    elif declaracao:
        classe = "declaração sem link"
    elif origem:
        classe = "texto lido, sem declaração"
    else:
        classe = "texto completo inacessível"
    return classe, sorted(links), declaracao, origem


def licenca_do_link(l):
    try:
        m = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", l)
        if m:
            r = get(f"https://api.github.com/repos/{m.group(1)}/{m.group(2).removesuffix('.git')}", headers=GH)
            if r is not None and r.status_code == 200:
                return "GitHub: " + ((r.json().get("license") or {}).get("spdx_id") or "sem licença")
            return f"GitHub: HTTP {'-' if r is None else r.status_code}"
        m = re.search(r"zenodo\.org/(?:records?|record)/(\d+)|10\.5281/zenodo\.(\d+)", l)
        if m:
            r = get(f"https://zenodo.org/api/records/{m.group(1) or m.group(2)}")
            if r is not None and r.status_code == 200:
                return "Zenodo: " + str((r.json().get("metadata", {}).get("license") or {}).get("id"))
        m = re.search(r"huggingface\.co/datasets/([^/\s]+/[^/\s#?]+)", l)
        if m:
            r = get(f"https://huggingface.co/api/datasets/{m.group(1)}")
            if r is not None and r.status_code == 200:
                return "HF: " + str([t for t in r.json().get("tags", []) if t.startswith("license:")] or "sem licença")
        m = re.search(r"kaggle\.com/datasets/([^/\s]+/[^/\s#?]+)", l)
        if m:
            r = get(f"https://www.kaggle.com/api/v1/datasets/view/{m.group(1)}")
            if r is not None and r.status_code == 200:
                return "Kaggle: " + str(r.json().get("licenseName") or r.json().get("licenses"))
        m = re.search(r"figshare\.com/articles/(?:[^/]+/)*(\d{6,})", l)
        if m:
            r = get(f"https://api.figshare.com/v2/articles/{m.group(1)}")
            if r is not None and r.status_code == 200:
                return "Figshare: " + str(r.json().get("license", {}).get("name"))
    except Exception as e:  # um link estranho não derruba a varredura
        return f"erro: {type(e).__name__}"
    return "conferir à mão"


def main():
    print("===== Busca no OpenAlex =====")
    trabalhos = busca_openalex()
    trabalhos.sort(key=lambda w: (-(w.get("publication_year") or 0), -(w.get("cited_by_count") or 0)))
    print(f"\n{len(trabalhos)} trabalhos relevantes\n")

    linhas, contagem, porclasse = [], {}, {}
    for i, w in enumerate(trabalhos, 1):
        classe, links, declaracao, origem = disponibilidade(w)
        contagem[classe] = contagem.get(classe, 0) + 1
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        print(f"[{i}] {w.get('publication_year')} | {(w.get('title') or '')[:150]}")
        print(f"     {venue[:60]} | {w.get('doi')} | citado {w.get('cited_by_count')} | {classe} ({origem or '-'})")
        if declaracao:
            print(f"     declaração: {declaracao[:350]}")
        # Com e sem estrela é o mesmo link; fica a versão marcada.
        marcados = {l[1:] for l in links if l.startswith("★")}
        links = sorted(l for l in links if l.startswith("★") or l not in marcados)
        lics = []
        for l in links[:8]:
            lic = licenca_do_link(l.lstrip("★"))
            lics.append(f"{l} [{lic}]")
            print(f"     dados: {l}  →  {lic}")
        if links:
            linhas.append((w.get("publication_year"), (w.get("title") or "")[:90], w.get("doi") or "", lics))
        porclasse.setdefault(classe, []).append(f"{w.get('publication_year')} {(w.get('title') or '')[:100]} ({w.get('doi')})")
        time.sleep(0.2)

    print("\n===== Resumo =====")
    print(json.dumps(contagem, ensure_ascii=False))
    for classe, itens in porclasse.items():
        if classe == "link público":
            continue
        print(f"\n===== {classe} ({len(itens)}) =====")
        for it in itens:
            print("  " + it)
    print("\n===== Trabalhos com link de dados (★ = link escrito na declaração de dados) =====")
    tabela = ["| Ano | Trabalho | DOI | Dados e licença |", "|---|---|---|---|"]
    for ano, titulo, doi, lics in linhas:
        print(f"{ano} | {titulo} | {doi}")
        for l in lics:
            print(f"      {l}")
        tabela.append(f"| {ano} | {titulo} | {doi} | {'<br>'.join(lics)} |")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"## Literatura: {len(trabalhos)} trabalhos, disponibilidade dos dados\n\n")
            f.write(json.dumps(contagem, ensure_ascii=False) + "\n\n" + "\n".join(tabela) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
