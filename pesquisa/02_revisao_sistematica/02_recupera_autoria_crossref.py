# -*- coding: utf-8 -*-
"""
Recupera a autoria real de cada estudo incluido na revisao sistematica,
consultando a base Crossref a partir do DOI, e formata as referencias
segundo a ABNT NBR 6023.

Entrada: estudos_triados.csv  (coluna 'doi' e coluna 'DECISAO' == 'S')
Saidas : estudos_com_autoria.csv  e  referencias_abnt.txt

Nenhuma autoria e inferida ou preenchida manualmente: todos os campos
provem do registro oficial depositado pela editora na Crossref.
"""

# !pip install requests pandas -q

import requests, pandas as pd, time

EMAIL = "seu-email@exemplo.com"     # a Crossref pede identificacao (polite pool)
ENTRADA = "estudos_triados.csv"


def busca_crossref(doi):
    """Retorna metadados oficiais do DOI, ou None se nao encontrado."""
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}",
                         params={"mailto": EMAIL}, timeout=30)
        if r.status_code != 200:
            return None
        m = r.json()["message"]
    except Exception:
        return None

    autores = []
    for a in (m.get("author") or []):
        fam = (a.get("family") or "").strip()
        giv = (a.get("given") or "").strip()
        if fam:
            iniciais = " ".join(p[0].upper() + "." for p in giv.split() if p)
            autores.append(f"{fam.upper()}, {iniciais}")

    return {
        "autores_completo": "; ".join(autores),
        "n_autores": len(autores),
        "primeiro_sobrenome": autores[0].split(",")[0] if autores else "",
        "periodico": (m.get("container-title") or [""])[0],
        "volume": m.get("volume", ""),
        "pagina": m.get("page", ""),
        "ano_cr": (m.get("issued", {}).get("date-parts", [[None]])[0][0]),
    }


def citacao_abnt(r):
    """Citacao no corpo do texto: (SOBRENOME et al., ano)."""
    if not r.primeiro_sobrenome:
        return ""
    if r.n_autores == 1:
        return f"({r.primeiro_sobrenome}, {int(r.ano)})"
    if r.n_autores <= 3:
        nomes = "; ".join(a.split(",")[0] for a in r.autores_completo.split("; "))
        return f"({nomes}, {int(r.ano)})"
    return f"({r.primeiro_sobrenome} et al., {int(r.ano)})"


def referencia_abnt(r):
    """Referencia completa (NBR 6023)."""
    if not r.autores_completo:
        return ""
    vol = f", v. {r.volume}" if r.volume else ""
    pag = f", p. {r.pagina}" if r.pagina else ""
    return (f"{r.autores_completo}. {r.titulo}. "
            f"{r.periodico}{vol}{pag}, {int(r.ano)}. DOI: {r.doi}.")


if __name__ == "__main__":
    d = pd.read_csv(ENTRADA)
    if "DECISAO" in d.columns:
        d = d[d.DECISAO == "S"]
    d = d.sort_values("citacoes", ascending=False)

    linhas = []
    for i, r in d.iterrows():
        info = busca_crossref(r.doi)
        if info is None:
            print(f"  FALHOU: {r.doi}")
            info = {"autores_completo": "", "n_autores": 0, "primeiro_sobrenome": "",
                    "periodico": r.get("fonte", ""), "volume": "", "pagina": "",
                    "ano_cr": r.ano}
        else:
            print(f"  {info['primeiro_sobrenome']} ({info['ano_cr']})")
        linhas.append({**r.to_dict(), **info})
        time.sleep(0.4)      # cortesia com a API

    out = pd.DataFrame(linhas)
    out["citacao_abnt"] = out.apply(citacao_abnt, axis=1)
    out["referencia_abnt"] = out.apply(referencia_abnt, axis=1)

    print(f"\nCom autoria: {(out.n_autores > 0).sum()} de {len(out)}")
    out.to_csv("estudos_com_autoria.csv", index=False)

    refs = sorted(x for x in out.referencia_abnt if x)
    with open("referencias_abnt.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(refs))
    print("Gerados: estudos_com_autoria.csv e referencias_abnt.txt")
