# ==========================================================================
#  REVISÃO SISTEMÁTICA DA LITERATURA — EXECUÇÃO REAL
#  Bases abertas: OpenAlex, Crossref, Semantic Scholar, arXiv
#  Gera: números reais do PRISMA + planilha de triagem para você ler
#  Rode no Google Colab.
# ==========================================================================

!pip install requests pandas -q

import requests, pandas as pd, time, re, unicodedata, json
from urllib.parse import quote

EMAIL = "mayconlimasan@gmail.com"   # OpenAlex pede um e-mail (polite pool, mais rápido)
ANO_INI, ANO_FIM = 2015, 2025

# ---------------- Strings de busca (as mesmas do Quadro 3) ----------------
QUERIES = [
    '("machine learning" OR "deep learning") AND ("yield prediction" OR "yield forecasting") AND (soybean OR crop)',
    '"crop yield prediction" AND "machine learning"',
    '"soybean yield" AND ("machine learning" OR "artificial intelligence")',
    '"yield forecasting" AND ("random forest" OR "neural network" OR "XGBoost")',
]

registros = []   # cada item: base, titulo, autores, ano, doi, abstract, fonte

# ---------------- 1. OpenAlex (maior base aberta, ~250M obras) ----------------
def abstract_from_inverted(inv):
    if not inv: return ""
    pos = {}
    for palavra, idxs in inv.items():
        for i in idxs: pos[i] = palavra
    return " ".join(pos[i] for i in sorted(pos))

print("=== OpenAlex ===")
for q in QUERIES:
    cursor = "*"
    n = 0
    while cursor:
        url = ("https://api.openalex.org/works"
               f"?search={quote(q)}"
               f"&filter=publication_year:{ANO_INI}-{ANO_FIM},type:article"
               f"&per-page=200&cursor={cursor}&mailto={EMAIL}")
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            print("  erro", r.status_code); break
        d = r.json()
        for w in d["results"]:
            registros.append({
                "base": "OpenAlex",
                "titulo": w.get("title") or "",
                "ano": w.get("publication_year"),
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                "abstract": abstract_from_inverted(w.get("abstract_inverted_index")),
                "fonte": (w.get("primary_location") or {}).get("source", {}).get("display_name", "") if w.get("primary_location") else "",
                "citacoes": w.get("cited_by_count", 0),
            })
            n += 1
        cursor = d["meta"].get("next_cursor")
        if n >= 600: break        # teto por query
        time.sleep(0.3)
    print(f"  query [{q[:45]}...] -> {n} registros")

# ---------------- 2. Crossref ----------------
print("\n=== Crossref ===")
for q in QUERIES:
    n = 0
    for offset in range(0, 400, 100):
        url = ("https://api.crossref.org/works"
               f"?query.bibliographic={quote(q)}"
               f"&filter=from-pub-date:{ANO_INI}-01-01,until-pub-date:{ANO_FIM}-12-31,type:journal-article"
               f"&rows=100&offset={offset}&mailto={EMAIL}")
        try:
            r = requests.get(url, timeout=60)
            items = r.json()["message"]["items"]
        except Exception as e:
            print("  erro:", e); break
        if not items: break
        for it in items:
            registros.append({
                "base": "Crossref",
                "titulo": (it.get("title") or [""])[0],
                "ano": (it.get("issued", {}).get("date-parts", [[None]])[0][0]),
                "doi": it.get("DOI", ""),
                "abstract": re.sub(r"<[^>]+>", "", it.get("abstract", "") or ""),
                "fonte": (it.get("container-title") or [""])[0],
                "citacoes": it.get("is-referenced-by-count", 0),
            })
            n += 1
        time.sleep(0.5)
    print(f"  query [{q[:45]}...] -> {n} registros")

# ---------------- 3. Semantic Scholar ----------------
print("\n=== Semantic Scholar ===")
for q in QUERIES:
    n = 0
    for offset in (0, 100, 200):
        url = ("https://api.semanticscholar.org/graph/v1/paper/search"
               f"?query={quote(q)}&offset={offset}&limit=100"
               f"&year={ANO_INI}-{ANO_FIM}"
               "&fields=title,year,abstract,externalIds,venue,citationCount")
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 429:
                time.sleep(5); continue
            data = r.json().get("data", [])
        except Exception as e:
            print("  erro:", e); break
        if not data: break
        for p in data:
            registros.append({
                "base": "SemanticScholar",
                "titulo": p.get("title") or "",
                "ano": p.get("year"),
                "doi": (p.get("externalIds") or {}).get("DOI", "") or "",
                "abstract": p.get("abstract") or "",
                "fonte": p.get("venue") or "",
                "citacoes": p.get("citationCount", 0),
            })
            n += 1
        time.sleep(3)   # essa API é sensível a rate limit
    print(f"  query [{q[:45]}...] -> {n} registros")

df = pd.DataFrame(registros)
N_IDENTIFICADOS = len(df)
print(f"\n>>> IDENTIFICAÇÃO: {N_IDENTIFICADOS} registros brutos")
print(df.base.value_counts().to_string())


# ---------------- 4. Remoção de duplicatas ----------------
def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).lower()
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t)

df["titulo_norm"] = df["titulo"].map(norm)
df["doi"] = df["doi"].str.lower().str.strip()

antes = len(df)
# dedup por DOI (quando existe) e depois por título normalizado
com_doi = df[df.doi != ""].drop_duplicates(subset="doi")
sem_doi = df[df.doi == ""]
df = pd.concat([com_doi, sem_doi]).drop_duplicates(subset="titulo_norm")
N_DUPLICATAS = antes - len(df)
print(f"\n>>> DUPLICATAS REMOVIDAS: {N_DUPLICATAS}")
print(f">>> APÓS DEDUPLICAÇÃO: {len(df)}")


# ---------------- 5. Exclusão automática (critérios objetivos) ----------------
# Critérios que NÃO exigem leitura: sem título, sem resumo, fora do escopo temático
df = df[df.titulo.str.len() > 10]
sem_resumo = (df.abstract.str.len() < 50).sum()
df_screen = df[df.abstract.str.len() >= 50].copy()

TERMOS_ML = r"machine learning|deep learning|random forest|xgboost|neural network|gradient boosting|support vector|artificial intelligence|lstm|cnn"
TERMOS_YIELD = r"yield|productivity|production"
TERMOS_CROP = r"crop|soybean|soy|maize|corn|wheat|agricultur"

m1 = df_screen.titulo.str.lower().str.contains(TERMOS_ML) | df_screen.abstract.str.lower().str.contains(TERMOS_ML)
m2 = df_screen.titulo.str.lower().str.contains(TERMOS_YIELD) | df_screen.abstract.str.lower().str.contains(TERMOS_YIELD)
m3 = df_screen.titulo.str.lower().str.contains(TERMOS_CROP) | df_screen.abstract.str.lower().str.contains(TERMOS_CROP)

df_screen["passa_filtro"] = m1 & m2 & m3
N_EXCLUIDOS_AUTO = (~df_screen.passa_filtro).sum() + sem_resumo
elegiveis = df_screen[df_screen.passa_filtro].copy()

print(f"\n>>> EXCLUÍDOS na triagem automática: {N_EXCLUIDOS_AUTO}")
print(f"    (sem resumo: {sem_resumo} | fora do escopo: {(~df_screen.passa_filtro).sum()})")
print(f">>> ELEGÍVEIS para leitura: {len(elegiveis)}")


# ---------------- 6. Planilha de triagem (VOCÊ decide a inclusão) ----------------
elegiveis = elegiveis.sort_values("citacoes", ascending=False)
elegiveis["INCLUIR_S_N"] = ""          # <- você preenche
elegiveis["MOTIVO_EXCLUSAO"] = ""      # <- você preenche
cols = ["INCLUIR_S_N","MOTIVO_EXCLUSAO","titulo","ano","fonte","citacoes","doi","abstract","base"]
elegiveis[cols].to_csv("triagem_rsl.csv", index=False)

# ---------------- 7. Números do PRISMA (reais) ----------------
prisma = {
    "identificacao": int(N_IDENTIFICADOS),
    "duplicatas_removidas": int(N_DUPLICATAS),
    "triados": int(N_IDENTIFICADOS - N_DUPLICATAS),
    "excluidos_triagem": int(N_EXCLUIDOS_AUTO),
    "elegiveis_leitura_integral": int(len(elegiveis)),
    "incluidos": "<< preencha após ler >>",
    "por_base": df.base.value_counts().to_dict(),
    "periodo": f"{ANO_INI}-{ANO_FIM}",
    "queries": QUERIES,
    "data_da_busca": time.strftime("%Y-%m-%d"),
}
json.dump(prisma, open("prisma_numeros.json","w"), indent=2, ensure_ascii=False)
print("\n" + "="*60)
print("NÚMEROS REAIS DO PRISMA:")
for k,v in prisma.items():
    if k not in ("queries",): print(f"  {k}: {v}")

from google.colab import files
files.download("triagem_rsl.csv")
files.download("prisma_numeros.json")
print("\nMe envie os DOIS arquivos.")
print("Depois abra triagem_rsl.csv, leia título+resumo e preencha INCLUIR_S_N (S/N).")
