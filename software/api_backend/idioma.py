"""O idioma das frases que a API monta: português, o padrão, ou inglês.

O aplicativo (2.9.0 em diante) manda no cabeçalho Accept-Language o idioma em
que está, e o WebView do mapa manda o do aparelho; ?lang=en serve para conferir
no navegador. Vale o primeiro idioma que a API conhece, na ordem de preferência
do cabeçalho, como o Android faz com os textos do aplicativo: um aparelho em
espanhol com o inglês como segundo idioma recebe inglês; só em espanhol,
português. Sem cabeçalho, tudo sai em português, como no painel, que chama as
funções direto.

Só as frases mudam de idioma. Números, nomes de praça e de município e o que
vem pronto das fontes (os avisos do INMET, por exemplo) seguem como são.
"""
from __future__ import annotations

import re
from datetime import date

IDIOMAS = ("pt", "en")

_SIGLAS = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
           "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
_MESES_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
_CURTOS_EN = {"jan": "Jan", "fev": "Feb", "mar": "Mar", "abr": "Apr", "mai": "May", "jun": "Jun",
              "jul": "Jul", "ago": "Aug", "set": "Sep", "out": "Oct", "nov": "Nov", "dez": "Dec"}


def idioma(lang: str | None = None, accept_language: str | None = None) -> str:
    """"en" ou "pt": o parâmetro lang, se veio; senão, o primeiro idioma conhecido do Accept-Language."""
    if lang:
        pedido = lang.strip().lower()[:2]
        return pedido if pedido in IDIOMAS else "pt"
    if not accept_language:
        return "pt"
    preferidos = []
    for ordem, parte in enumerate(accept_language.split(",")):
        etiqueta, _, parametros = parte.strip().partition(";")
        peso = 1.0
        m = re.search(r"q\s*=\s*([0-9.]+)", parametros)
        if m:
            try:
                peso = float(m.group(1))
            except ValueError:
                peso = 0.0
        if etiqueta.strip() and peso > 0:
            preferidos.append((-peso, ordem, etiqueta.strip().lower()[:2]))
    for _, _, codigo in sorted(preferidos):
        if codigo in IDIOMAS:
            return codigo
    return "pt"


def mes_por_extenso_en(levantamento: str) -> str | None:
    """'MAR-2026', o rótulo da CONAB, para 'March 2026'; None se o rótulo não for lido."""
    sigla, _, ano = str(levantamento).partition("-")
    mes = _SIGLAS.get(sigla.upper())
    if mes is None or not ano.isdigit():
        return None
    return f"{_MESES_EN[mes - 1]} {ano}"


def periodo_curto_en(periodo: str) -> str:
    """'mar/2023 a mar/2026' para 'Mar/2023 to Mar/2026'."""
    t = re.sub(r"\b([a-z]{3})/(\d{4})", lambda m: f"{_CURTOS_EN.get(m.group(1), m.group(1))}/{m.group(2)}", periodo)
    return t.replace(" a ", " to ")


def data_en(iso: str) -> str:
    """'2026-08-01' para 'Aug 1, 2026'."""
    d = date.fromisoformat(iso)
    return f"{_MESES_EN[d.month - 1][:3]} {d.day}, {d.year}"


def reais_en(valor: float) -> str:
    """R$ no formato do inglês: 'R$ 5,277.12'."""
    return f"R$ {valor:,.2f}"


def ordinal_en(n: int) -> str:
    """2 para '2nd', 11 para '11th'."""
    if 10 <= n % 100 <= 20:
        sufixo = "th"
    else:
        sufixo = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{sufixo}"


def juntar_com_and(nomes: str) -> str:
    """'Cachoeira da Serra e Castelo de Sonhos' para '... and ...': só o último ' e ' da lista."""
    antes, sep, depois = nomes.rpartition(" e ")
    return f"{antes} and {depois}" if sep else nomes


def textos_en(lev: dict) -> dict:
    """A descrição do levantamento e a nota do preço em inglês, com os números de [lev].

    O levantamento do Pará (Pedro Afonso, TO) traz a série da praça, e a nota
    diz onde o preço está nela, com a mesma regra de gera_levantamento_conab.py;
    o dos outros estados (estados.levantamento_da_praca) não traz, e a nota diz
    só de onde o preço vem.
    """
    quando = mes_por_extenso_en(lev.get("levantamento", "")) or lev.get("levantamento_extenso", "")
    praca = lev.get("praca", "")
    preco = reais_en(float(lev["preco_recebido_saca"]))
    s = lev.get("serie")
    if s:
        n, pos = int(s["levantamentos"]), int(s["posicao_do_atual"])
        if n < 2:
            posicao = "the only survey available"
        elif pos == 1:
            posicao = f"the lowest of the {n} surveys"
        elif pos == n:
            posicao = f"the highest of the {n} surveys"
        else:
            posicao = f"the {ordinal_en(pos)} lowest of the {n} surveys"
        if n < 2:
            fecho = ""
        elif pos <= (n + 1) // 2:
            fecho = " Conservative scenario, not a price forecast."
        else:
            fecho = " Optimistic scenario: the series has been well below this."
        nota = (f"{preco}/bag is {posicao} at this location ({periodo_curto_en(s['periodo_curto'])}, "
                f"median {reais_en(float(s['mediana_saca']))}).{fecho}")
    else:
        nota = (f"{preco}/bag is the price received in {praca} in CONAB's {quando} survey. "
                "Reference scenario, not a price forecast.")
    return {"descricao": f"CONAB, {praca}, {quando}", "nota_preco": nota}
