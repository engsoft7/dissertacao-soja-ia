# -*- coding: utf-8 -*-
"""
Confere, uma a uma, as listas de referências da dissertação e dos dois artigos.

As listas estão em listas_de_referencias.json, copiadas dos documentos como
estão no Google Drive: a lista principal da dissertação, o Apêndice B (os 53
estudos da revisão sistemática) e as referências dos artigos do ERAD e do
ERAMIA. Para cada referência:

- com DOI impresso: resolve o DOI na Crossref e confere ano, primeiro autor e
  título contra o texto da referência;
- sem DOI: procura a obra na Crossref pelo texto da referência e, achando com
  título e ano compatíveis, informa o DOI que poderia ser impresso;
- de órgão público ou página na web (IBGE, CONAB, NASA, MapBiomas, Receita,
  Agrolink): confere se o endereço indicado responde.

Não altera nada: imprime o que cada base devolveu e um resumo por lista, e
escreve o resumo no relatório da execução. O que não consegue decidir ele
marca para conferência manual, em vez de aprovar por semelhança.

Roda no GitHub Actions: o ambiente de desenvolvimento não alcança
api.crossref.org nem os sites dos órgãos, negados por política de rede.

Uso:  python confere_listas.py
"""
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

AQUI = Path(__file__).resolve().parent
CROSSREF = "https://api.crossref.org/works"
MAILTO = os.environ.get("CROSSREF_MAILTO", "")
UA = {"User-Agent": "dissertacao-soja-ia/1.0" + (f" (mailto:{MAILTO})" if MAILTO else "")}
INSTITUCIONAIS = ("INSTITUTO BRASILEIRO", "COMPANHIA NACIONAL", "BRASIL.", "NATIONAL AERONAUTICS",
                  "MAPBIOMAS", "AGROLINK")
VAZIAS = {"the", "and", "for", "with", "from", "using", "uma", "para", "com", "dos", "das", "por"}


def sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn").lower()


def palavras(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", sem_acento(t)) if len(w) > 3 and w not in VAZIAS}


def anos(texto: str) -> set[int]:
    return {int(a) for a in re.findall(r"(?<!\d)(19[5-9]\d|20[0-3]\d)(?!\d)", texto)}


def doi_do_texto(texto: str) -> str | None:
    m = re.search(r"10\.\d{4,9}/[^\s,;]+", texto)
    return m.group(0).rstrip(".)") if m else None


def anos_depositados(m: dict) -> set[int]:
    saida = set()
    for campo in ("published-print", "published-online", "issued", "published"):
        parte = m.get(campo, {}).get("date-parts", [[None]])[0]
        if parte and parte[0]:
            saida.add(int(parte[0]))
    return saida


def cobertura_do_titulo(m: dict, texto: str) -> float:
    titulo = palavras((m.get("title") or [""])[0])
    return len(titulo & palavras(texto)) / len(titulo) if titulo else 0.0


def primeiro_autor_confere(m: dict, texto: str) -> bool | None:
    autores = m.get("author") or []
    if not autores or not autores[0].get("family"):
        return None
    familia = sem_acento(autores[0]["family"]).split()
    alvo = sem_acento(texto[:200])
    return any(parte in alvo for parte in familia if len(parte) > 2)


def get(url: str, **params):
    for tentativa in range(3):
        try:
            r = requests.get(url, params=params or None, headers=UA, timeout=30)
            if r.status_code in (429, 503):
                time.sleep(3 * (tentativa + 1))
                continue
            return r
        except requests.RequestException:
            time.sleep(3 * (tentativa + 1))
    return None


def confere_com_doi(texto: str, doi: str) -> tuple[str, str]:
    r = get(f"{CROSSREF}/{requests.utils.quote(doi)}")
    if r is None:
        return "?", f"{doi}: Crossref não respondeu"
    if r.status_code == 404:
        return "X", f"{doi}: DOI não existe na Crossref"
    m = r.json()["message"]
    problemas = []
    if not (anos(texto) & anos_depositados(m)):
        problemas.append(f"ano: texto {sorted(anos(texto))}, Crossref {sorted(anos_depositados(m))}")
    if primeiro_autor_confere(m, texto) is False:
        problemas.append(f"primeiro autor na Crossref: {m['author'][0].get('family')}")
    cob = cobertura_do_titulo(m, texto)
    if cob < 0.75:
        problemas.append(f"título confere {cob:.0%}: Crossref '{(m.get('title') or [''])[0][:90]}'")
    if problemas:
        return "??", f"{doi}: " + "; ".join(problemas)
    return "ok", doi


def procura_sem_doi(texto: str) -> tuple[str, str]:
    r = get(CROSSREF, **{"query.bibliographic": texto[:300], "rows": 5})
    if r is None or r.status_code != 200:
        return "?", "Crossref não respondeu à busca"
    melhor, nota = None, 0.0
    for m in r.json()["message"]["items"]:
        cob = cobertura_do_titulo(m, texto)
        if cob > nota:
            melhor, nota = m, cob
    if melhor and nota >= 0.8 and anos(texto) & anos_depositados(melhor):
        return "ok", f"sem DOI impresso; a Crossref tem a obra: {melhor.get('DOI')}"
    if melhor and nota >= 0.8:
        return "??", (f"sem DOI impresso; obra achada ({melhor.get('DOI')}) com ano "
                      f"{sorted(anos_depositados(melhor))}, texto diz {sorted(anos(texto))}")
    return "--", "sem DOI e não localizada na Crossref (livro ou anais antigos?): conferir à mão"


def confere_endereco(texto: str) -> tuple[str, str]:
    urls = re.findall(r"https?://[^\s]+", texto)
    if not urls:
        return "--", "referência institucional sem endereço: conferir à mão"
    url = urls[0].rstrip(".,;")
    r = get(url)
    if r is None:
        return "?", f"{url}: sem resposta"
    if r.status_code >= 400:
        return "X", f"{url}: HTTP {r.status_code}"
    return "ok", f"{url}: HTTP {r.status_code}"


def main() -> int:
    dados = json.loads((AQUI / "listas_de_referencias.json").read_text(encoding="utf-8"))
    resumo = []
    for nome, lista in dados["listas"].items():
        print(f"\n===== {nome}: {len(lista)} referências =====\n")
        contagem = {}
        for texto in lista:
            if texto.upper().startswith(INSTITUCIONAIS):
                marca, nota = confere_endereco(texto)
            elif (doi := doi_do_texto(texto)):
                marca, nota = confere_com_doi(texto, doi)
            else:
                marca, nota = procura_sem_doi(texto)
            contagem[marca] = contagem.get(marca, 0) + 1
            print(f"{marca:>2}  {texto[:110]}")
            print(f"    {nota}")
            time.sleep(0.3)
        resumo.append((nome, len(lista), contagem))

    linhas = ["| Lista | Referências | ok | divergência (??) | não existe (X) | conferir à mão (--) | sem resposta (?) |",
              "|---|---|---|---|---|---|---|"]
    for nome, n, c in resumo:
        linhas.append(f"| {nome} | {n} | {c.get('ok', 0)} | {c.get('??', 0)} | {c.get('X', 0)} "
                      f"| {c.get('--', 0)} | {c.get('?', 0)} |")
    print("\n" + "\n".join(linhas))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("## Conferência das listas de referências\n\n" + "\n".join(linhas) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
