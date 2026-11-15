# -*- coding: utf-8 -*-
"""Janela de plantio da soja: ZARC e calendário de semeadura, de fontes oficiais.

- Calendário de semeadura e vazio sanitário: a portaria mais nova da SDA/MAPA
  (em novembro de 2026, a nº 1.579, de 9 de abril de 2026, DOU de 10/04/2026,
  safra 2026/2027). Lida da página do Diário Oficial, que traz a tabela em HTML. No Pará e no Maranhão o estado se divide em
  regiões, definidas por listas de municípios nas notas de rodapé; cada nome é
  conferido contra a lista oficial do IBGE, e um nome que não bate faz a coleta
  falhar em vez de gravar uma região errada.
- ZARC: a tábua de risco do Zoneamento Agrícola de Risco Climático, publicada pelo
  Ministério da Agricultura como dado aberto (licença Creative Commons Atribuição)
  no catálogo dados.agricultura.gov.br. Para cada município, grupo de cultivar
  (Grupo I, II e III) e classe de água disponível no solo (AD1 a AD6), o risco
  de plantar em cada um dos 36 decêndios do ano: 20, 30 ou 40%, ou 0 quando o
  decêndio não é indicado.

Saída, em pesquisa/dados/plantio/:
- calendario_soja_<safra>.json: vazio sanitário e semeadura por estado e região,
  com os municípios de cada região pelo código do IBGE;
- zarc_soja_<safra>.csv: uma linha por município, grupo e solo, com os 36 riscos
  numa sequência de dígitos (0, 2, 3 ou 4, de 0%, 20%, 30% ou 40%);
- fontes_plantio.json: de onde veio cada coisa e quando foi lida.

A safra troca sozinha. Toda semana a coleta procura no Diário Oficial a portaria
mais nova da SDA/MAPA com o calendário de semeadura da soja, e no catálogo do
Ministério as safras da tábua do ZARC.
- Portaria de uma safra mais nova que a em uso: o calendário passa para ela na
  mesma coleta. A tábua do ZARC acompanha a safra do calendário; enquanto a da
  safra nova não sai (em 2026, a portaria saiu em abril e a tábua, em julho),
  segue a da safra anterior, e a API diz isso junto da fonte do ZARC.
- Outra portaria da mesma safra, mais nova que a em uso: a coleta tenta ler nela
  o calendário inteiro. Se a página não o traz (uma alteração das datas de um
  estado, por exemplo), segue na em uso e grava um aviso, que o workflow
  transforma em issue para alguém conferir.
- Os arquivos das safras anteriores ficam; a API usa os da mais nova.
Sem a busca do Diário Oficial (fora do ar ou com formato novo), segue a safra em
uso, lida de fontes_plantio.json, ou a portaria abaixo. Uma portaria de safra
nova que não se deixe ler faz a coleta falhar, como qualquer leitura errada, e
nada é gravado. Quando nada muda, os arquivos ficam como estão, inclusive a data
de fontes_plantio.json: a coleta semanal não abre PR à toa.

A verificação de certificado fica sempre ligada.

Uso:  python coleta_plantio.py [--saida DIR] [--descobre] [--aviso ARQUIVO]
      --descobre só mostra a portaria e as safras encontradas, sem gravar;
      --aviso grava ali o aviso de uma portaria da mesma safra que não se leu
      (primeira linha, o título da issue; o resto, o texto).
"""
import argparse
import csv
import html as html_mod
import io
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

UA = {"User-Agent": "AgroInteligencia-Dissertacao/1.0 (UFPA; pesquisa academica)"}
ESTADOS = ("PA", "MT", "MA", "TO", "RO")
# A portaria de partida, usada quando ainda não há fontes_plantio.json e a busca
# no Diário Oficial não responde. A safra em uso fica em fontes_plantio.json.
SAFRA = "2026/2027"
DOU = "https://www.in.gov.br/web/dou/-/portaria-sda/mapa-n-1.579-de-9-de-abril-de-2026-698696654"
PORTARIA = "Portaria SDA/MAPA nº 1.579, de 9 de abril de 2026"
BUSCA_DOU = "https://www.in.gov.br/consulta/-/buscar/dou"
PAGINA_DOU = "https://www.in.gov.br/web/dou/-/"
# A busca aceita uma frase entre aspas sozinha: a frase com outra palavra
# ("calendário de semeadura" soja), duas frases, + ou AND devolvem zero atos
# (conferido no Actions em 14/11/2026, execuções 43650528112 e 43650823721).
FRASE_DOU = '"calendário de semeadura"'
ATOS_POR_PAGINA = 50
SAFRA_NO_TEXTO = re.compile(r"safra\s+(\d{4})\s*/\s*(\d{4}|\d{2})\b", re.I)
TITULO_PORTARIA = re.compile(
    r"PORTARIA\s+SDA\s*/\s*MAPA\s+N[º°ºO.]*\s*([\d.]+)\s*,?\s+DE\s+(\d{1,2})\s*º?\s+DE\s+([A-ZÇÃ]+)\s+DE\s+(\d{4})", re.I)
CKAN = ("https://dados.agricultura.gov.br/api/3/action/package_show"
        "?id=tabua-de-risco-zoneamento-agricola-de-risco-climatico")
IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
# A mesma lista aberta que gera_municipios.py e monta_base_estados.py usam, com
# o código do IBGE de cada município: a reserva quando a API do IBGE não
# responde ao Actions (14/11/2026, tempo esgotado em 60 s).
KELVINS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
CODIGO_UF = {"PA": 15, "MT": 51, "MA": 21, "TO": 17, "RO": 11}
RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "pesquisa" / "dados" / "plantio"

MESES = {"janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
DATA = re.compile(r"(\d{1,2})\s*º?\s+de\s+([a-zçã]+)\s+de\s+(\d{4})", re.I)
REGIAO = re.compile(r"Região\s+([IVX]+)\s*(\d{1,2})\s*:\s*(.+?)(?=Região\s+[IVX]+\s*\d|$)")
CODIGO_RISCO = {"0": "0", "20": "2", "30": "3", "40": "4"}
DO_MUNICIPIO = re.compile(r"(?:pertencentes?\s+ao|do)\s+município\s+de\s+(.+)$")
# Grafias do anexo que não batem com a lista do IBGE, conferidas uma a uma. Um
# nome novo que não bata continua fazendo a coleta falhar.
GRAFIAS = {
    # Região II do Maranhão: o anexo escreve "Lagoa da Pedra"; o município é Lago
    # da Pedra (IBGE 2105708, que planta soja na PAM), o único do estado com nome
    # parecido.
    ("MA", "lagoadapedra"): "Lago da Pedra",
}


def normaliza(nome: str) -> str:
    """Para comparar nomes: sem acento, sem espaço, sem apóstrofo, minúsculas."""
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def datas(trecho: str) -> list[str]:
    """'22 de junho de 2026 a 20 de setembro de 2026' -> ['2026-06-22', '2026-09-20']."""
    saida = []
    for dia, mes, ano in DATA.findall(trecho):
        m = MESES.get(mes.lower())
        if m is None:
            raise ValueError(f"mês desconhecido: {mes!r} em {trecho!r}")
        saida.append(date(int(ano), m, int(dia)).isoformat())
    return saida


def periodos(celula: str) -> list[dict]:
    """Uma célula da tabela: um período só ou, com regiões, um por região.

    Devolve [{"regiao": "I" | None, "nota": "5" | None, "inicio": ..., "fim": ...}].
    """
    regioes = REGIAO.findall(celula)
    if not regioes:
        d = datas(celula)
        if len(d) != 2:
            raise ValueError(f"esperava duas datas em {celula!r}")
        return [{"regiao": None, "nota": None, "inicio": d[0], "fim": d[1]}]
    saida = []
    for numeral, nota, trecho in regioes:
        d = datas(trecho)
        if len(d) != 2:
            raise ValueError(f"esperava duas datas na região {numeral} de {celula!r}")
        saida.append({"regiao": numeral, "nota": nota, "inicio": d[0], "fim": d[1]})
    return saida


def linhas_da_tabela(pagina: str) -> dict[str, tuple[str, str]]:
    """UF -> (célula do vazio sanitário, célula do calendário de semeadura)."""
    linhas = {}
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", pagina):
        celulas = [html_mod.unescape(re.sub(r"<[^>]+>|\s+", " ", c)).strip()
                   for c in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", tr)]
        if len(celulas) == 3 and re.fullmatch(r"[A-Z]{2}", celulas[0]) and re.search(r"\d", celulas[1]):
            linhas[celulas[0]] = (celulas[1], celulas[2])
    return linhas


def notas_de_rodape(texto: str) -> dict[str, str]:
    """As notas do anexo: número -> texto até o ponto final.

    No texto da página o número vem colado ao primeiro nome ('5Alto Parnaíba'),
    o que o distingue das datas e dos números de região ('Região I5:').
    """
    notas = {}
    for m in re.finditer(r"(?<![\d\wº])(\d{1,2})(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç])", texto):
        fim = texto.find(".", m.end())
        if fim < 0:
            continue
        notas.setdefault(m.group(1), texto[m.end():fim].strip())
    return notas


def municipios_da_nota(nota: str) -> tuple[list[str], dict[str, str], str | None]:
    """'A, B (exceto ...) e C' -> (['A', 'B', 'C'], {'B': 'exceto ...'}, distritos).

    O parêntese depois de um nome ("Altamira (exceto os distritos de ...)") e a
    menção a distritos de outro município ("além dos distritos de ..., do
    município de ...") saem da lista antes de separá-la, porque também têm
    vírgulas e "e".
    """
    distritos = None
    m = re.search(r",?\s*além d[oa]s? distritos? .*$", nota)
    if m:
        distritos = m.group(0).lstrip(", ").strip()
        nota = nota[:m.start()]
    excecoes: dict[str, str] = {}

    def tira_parentese(mp: re.Match) -> str:
        antes = mp.group(1)
        excecoes[re.split(r"\s+e\s+", antes.strip())[-1]] = mp.group(2).strip()
        return antes.rstrip()

    nota = re.sub(r"([^,()]+?)\s*\(([^()]*)\)", tira_parentese, nota)
    partes = [p.strip() for p in nota.split(",") if p.strip()]
    if partes and " e " in partes[-1]:
        ultimo = partes.pop()
        partes += [p.strip() for p in ultimo.split(" e ") if p.strip()]
    return partes, excecoes, distritos


def codigo_ibge(uf: str, nome: str, ibge: dict[str, tuple[int, str]]) -> tuple[int, str] | None:
    """(código, nome no IBGE) de um nome do anexo, com as grafias conferidas; None se não bate."""
    return ibge.get(normaliza(GRAFIAS.get((uf, normaliza(nome)), nome)))


def fora_das_regioes(uf: str, ibge: dict[str, tuple[int, str]], regioes: list[dict],
                     textos: list[str]) -> list[str]:
    """Os municípios do estado que não entraram em região nenhuma.

    Se o nome aparece no texto das notas do estado, a leitura perdeu o nome: é
    problema, e a coleta falha. Se não aparece, a portaria não o lista: fica um
    aviso no log, e o aplicativo diz que não há calendário para ele.
    """
    cobertos = {c for r in regioes for c in (r["municipios"] or [])}
    corrido = normaliza(" ".join(textos))
    problemas = []
    for chave, (cod, nome) in sorted(ibge.items(), key=lambda x: x[1][1]):
        if cod in cobertos:
            continue
        if chave in corrido:
            problemas.append(f"{uf}: {nome} ({cod}) aparece nas notas, mas não entrou em região nenhuma")
        else:
            print(f"::warning::{uf}: {nome} ({cod}) não está em região nenhuma da portaria; "
                  "o aplicativo diz que não há calendário para ele")
    return problemas


def municipios_ibge(uf: str) -> dict[str, tuple[int, str]]:
    """Nome normalizado -> (código do IBGE, nome) de todos os municípios do estado."""
    try:
        r = requests.get(IBGE.format(uf=uf), headers=UA, timeout=20)
        r.raise_for_status()
        return {normaliza(m["nome"]): (int(m["id"]), m["nome"]) for m in r.json()}
    except requests.RequestException as e:
        print(f"API do IBGE indisponível ({type(e).__name__}); usando a lista de municípios do kelvins")
    r = requests.get(KELVINS, headers=UA, timeout=90)
    r.raise_for_status()
    r.encoding = "utf-8"
    import io
    return {normaliza(row["nome"]): (int(row["codigo_ibge"]), row["nome"])
            for row in csv.DictReader(io.StringIO(r.text)) if int(row["codigo_uf"]) == CODIGO_UF[uf]}


# ── a safra: a portaria mais nova do Diário Oficial e as tábuas do ZARC ──────

def texto_da_pagina(pagina: str) -> str:
    return html_mod.unescape(re.sub(r"\s+", " ", re.sub(r"(?is)<[^>]+>", " ", pagina)))


def safras_no_texto(texto: str) -> list[str]:
    """'safra 2027/2028' ou 'safra 2027/28' -> ['2027/2028'], sem repetir, em ordem."""
    vistas = []
    for a, b in SAFRA_NO_TEXTO.findall(texto):
        fim = b if len(b) == 4 else a[:2] + b
        if int(fim) == int(a) + 1 and f"{a}/{fim}" not in vistas:
            vistas.append(f"{a}/{fim}")
    return vistas


def nome_da_portaria(titulo: str) -> str:
    """'PORTARIA SDA/MAPA Nº 1.579, DE 9 DE ABRIL DE 2026' -> 'Portaria SDA/MAPA nº 1.579, de 9 de abril de 2026'."""
    m = TITULO_PORTARIA.search(titulo or "")
    if not m:
        return " ".join((titulo or "").split())
    numero, dia, mes, ano = m.groups()
    return f"Portaria SDA/MAPA nº {numero}, de {int(dia)} de {mes.lower()} de {ano}"


def resultados_da_busca(pagina: str) -> list[dict]:
    """Os atos que a busca do Diário Oficial devolve, do JSON que a página traz embutido."""
    m = re.search(r'<script[^>]*id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params"[^>]*>(.*?)</script>',
                  pagina, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(1)).get("jsonArray") or []
    except json.JSONDecodeError:
        return []


def candidatas(resultados: list[dict]) -> list[dict]:
    """As portarias da SDA/MAPA entre os atos da busca, as mais novas antes.

    A frase do calendário também aparece nas portarias do ZARC, que são da
    SPA/MAPA, e em calendários de outras culturas: quem decide é a página
    inteira (portaria_mais_nova). O título pode vir com o destaque da busca em
    HTML, que sai aqui.
    """
    saida = []
    for r in resultados:
        # O destaque fica no meio das palavras ("<span>SDA</span>/MAPA"): sai sem deixar espaço.
        titulo = " ".join(html_mod.unescape(re.sub(r"<[^>]+>", "", r.get("title") or r.get("titulo") or "")).split())
        if not TITULO_PORTARIA.search(titulo) or not r.get("urlTitle"):
            continue
        try:
            publicada = datetime.strptime(r.get("pubDate", ""), "%d/%m/%Y").date()
        except ValueError:
            continue
        saida.append({"titulo": titulo, "url": PAGINA_DOU + r["urlTitle"], "publicada": publicada})
    return sorted(saida, key=lambda c: c["publicada"], reverse=True)


def busca_no_dou(q: str, de: date, ate: date, paginas: int = 6) -> list[dict]:
    """Os atos que a busca do Diário Oficial acha entre as duas datas, do mais novo ao mais antigo.

    Cada página traz até ATOS_POR_PAGINA atos; a seguinte começa depois do
    último desta (score, classPK e displayDateSortable dele), como a própria
    página da busca faz. Para quando uma página não traz ato novo.
    """
    params = {"q": q, "s": "todos", "exactDate": "personalizado", "sortType": "0",
              "publishFrom": de.strftime("%d-%m-%Y"), "publishTo": ate.strftime("%d-%m-%Y"),
              "delta": str(ATOS_POR_PAGINA)}
    atos, vistos = [], set()
    for pagina in range(1, paginas + 1):
        r = requests.get(BUSCA_DOU, headers=UA, timeout=120, params=params)
        r.raise_for_status()
        lidos = resultados_da_busca(r.text)
        novos = [a for a in lidos if a.get("urlTitle") not in vistos]
        if not novos:
            break
        vistos.update(a.get("urlTitle") for a in novos)
        atos += novos
        u = lidos[-1]
        params.update({"currentPage": str(pagina), "newPage": str(pagina + 1), "score": str(u.get("score", 0)),
                       "id": str(u.get("classPK", "")), "displayDate": str(u.get("displayDateSortable", ""))})
    return atos


def portaria_mais_nova(hoje: date | None = None) -> dict | None:
    """A portaria mais nova do calendário de semeadura da soja no último ano, com a safra que ela fixa; None se não achar."""
    hoje = hoje or date.today()
    atos = busca_no_dou(FRASE_DOU, hoje - timedelta(days=364), hoje)
    cands = candidatas(atos)
    # O que a busca achou fica no log: é por aqui que se vê um formato novo do DOU.
    print(f"::group::busca no Diário Oficial: {len(atos)} atos com {FRASE_DOU} no último ano, "
          f"{len(cands)} portarias da SDA/MAPA")
    for c in cands:
        print(f"- {c['publicada']:%d/%m/%Y} {c['titulo']}: {c['url']}")
    achada = None
    for c in cands[:8]:
        pagina = requests.get(c["url"], headers=UA, timeout=120)
        pagina.raise_for_status()
        texto = texto_da_pagina(pagina.text)
        safras = safras_no_texto(texto)
        da_soja = "CALENDÁRIO DE SEMEADURA" in texto.upper() and "SOJA" in texto.upper()
        print(f"  {nome_da_portaria(c['titulo'])}: safras no texto {', '.join(safras) or 'nenhuma'}; "
              + ("calendário da soja" if da_soja else "não é o calendário da soja"))
        if safras and da_soja:
            achada = {"safra": max(safras), "fonte": nome_da_portaria(c["titulo"]), "url": c["url"]}
            break
    print("::endgroup::")
    return achada


def data_da_portaria(nome: str) -> date | None:
    """'Portaria SDA/MAPA nº 1.579, de 9 de abril de 2026' -> 9/4/2026."""
    m = DATA.search(nome or "")
    if not m or m.group(2).lower() not in MESES:
        return None
    try:
        return date(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None


def safra_em_uso(saida: Path) -> dict:
    """A safra, a portaria e o endereço da última coleta (fontes_plantio.json), ou os de partida."""
    try:
        f = json.loads((saida / "fontes_plantio.json").read_text(encoding="utf-8"))
        return {"safra": f["safra"], "fonte": f["calendario"]["fonte"], "url": f["calendario"]["url"]}
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return {"safra": SAFRA, "fonte": PORTARIA, "url": DOU}


def safras_do_zarc(recursos: list[dict]) -> list[str]:
    """As safras das tábuas do ZARC no catálogo ("... 2026/2027 ..." no nome), da mais antiga à mais nova."""
    safras = set()
    for x in recursos:
        for a, b in re.findall(r"\b(\d{4})/(\d{4})\b", x.get("name") or ""):
            if int(b) == int(a) + 1:
                safras.add(f"{a}/{b}")
    return sorted(safras)


def escolhe_calendario(atual: dict, nova: dict | None) -> tuple[dict, bool]:
    """A portaria de onde ler o calendário, e se ela é outra da mesma safra da em uso.

    Uma portaria de safra mais nova vale logo. Outra da mesma safra, de data
    posterior à em uso, pode trazer o calendário inteiro de novo ou só alterar
    um estado: grava() tenta lê-la inteira e, se não der, segue na em uso.
    """
    if not nova or nova["url"] == atual["url"]:
        return atual, False
    if nova["safra"] > atual["safra"]:
        return nova, False
    d_nova, d_atual = data_da_portaria(nova["fonte"]), data_da_portaria(atual["fonte"])
    if nova["safra"] == atual["safra"] and d_nova and d_atual and d_nova > d_atual:
        return nova, True
    return atual, False


def tabua_para(safra: str, safras_zarc: list[str]) -> str:
    """A tábua do ZARC que acompanha o calendário: a da mesma safra ou, enquanto ela não sai, a mais nova anterior."""
    anteriores = [s for s in safras_zarc if s <= safra]
    if not anteriores:
        raise SystemExit(f"nenhuma tábua do ZARC da safra {safra} ou anterior no catálogo: {safras_zarc}")
    tabua = max(anteriores)
    if tabua != safra:
        print(f"::notice::A tábua do ZARC da safra {safra} ainda não saiu; segue a da {tabua}, "
              "e a API diz isso junto da fonte do ZARC.")
    return tabua


def le_calendario(url: str = DOU) -> tuple[dict, list[str]]:
    """O calendário de cada estado na página da portaria, e o que não bateu na leitura."""
    r = requests.get(url, headers=UA, timeout=120)
    r.raise_for_status()
    pagina = r.text
    texto = html_mod.unescape(re.sub(r"\s+", " ", re.sub(r"(?is)<[^>]+>", " ", pagina)))
    # as notas ficam depois da tabela; antes dela o texto não tem listas
    notas = notas_de_rodape(texto[texto.find("CALENDÁRIO DE SEMEADURA"):])
    # As notas dos estados com regiões, por inteiro, para quem conferir a leitura.
    for uf, celulas in linhas_da_tabela(pagina).items():
        if uf in ESTADOS and "Região" in celulas[0]:
            print(f"::group::notas do anexo para {uf}")
            for p in periodos(celulas[0]):
                print(f"Região {p['regiao']} (nota {p['nota']}): {notas.get(p['nota'], '(sem nota)')}")
            print("::endgroup::")
    tabela = linhas_da_tabela(pagina)
    saida = {}
    problemas = []
    for uf in ESTADOS:
        if uf not in tabela:
            problemas.append(f"{uf}: sem linha na tabela")
            continue
        vazio, semeadura = (periodos(c) for c in tabela[uf])
        if len(vazio) != len(semeadura):
            problemas.append(f"{uf}: {len(vazio)} períodos de vazio e {len(semeadura)} de semeadura")
            continue
        ibge = municipios_ibge(uf) if vazio[0]["regiao"] else {}

        def codigo(nome: str, regiao: str) -> int | None:
            achado = codigo_ibge(uf, nome, ibge)
            if achado is None:
                problemas.append(f"{uf} região {regiao}: {nome!r} não está na lista do IBGE")
                return None
            if normaliza(achado[1]) != normaliza(nome):
                print(f"{uf} região {regiao}: {nome!r} do anexo lido como {achado[1]} ({achado[0]})")
            return achado[0]

        regioes, onde = [], {}
        for v, s in zip(vazio, semeadura):
            reg = {"regiao": v["regiao"], "vazio": [v["inicio"], v["fim"]],
                   "semeadura": [s["inicio"], s["fim"]], "municipios": None, "excecoes": {}, "distritos": []}
            if v["regiao"]:
                nota = notas.get(v["nota"], "")
                if not nota:
                    problemas.append(f"{uf} região {v['regiao']}: sem a nota {v['nota']}")
                if "demais" in nota.lower():
                    reg["municipios"] = "demais"
                else:
                    nomes, excecoes, distritos = municipios_da_nota(nota)
                    codigos = [c for c in (codigo(n, v["regiao"]) for n in nomes) if c is not None]
                    for c in codigos:
                        if c in onde:
                            problemas.append(f"{uf}: o município {c} está nas regiões {onde[c]} e {v['regiao']}")
                        onde[c] = v["regiao"]
                    reg["municipios"] = sorted(codigos)
                    for nome, texto in excecoes.items():
                        c = codigo(nome, v["regiao"])
                        if c is not None:
                            reg["excecoes"][str(c)] = texto
                    if distritos:
                        m = DO_MUNICIPIO.search(distritos)
                        c = codigo(m.group(1).strip(), v["regiao"]) if m else None
                        if m is None:
                            problemas.append(f"{uf} região {v['regiao']}: distritos sem o município: {distritos!r}")
                        elif c is not None:
                            reg["distritos"].append({"municipio": c, "texto": distritos})
            regioes.append(reg)
        for reg in regioes:
            if reg["municipios"] == "demais":
                reg["municipios"] = sorted({c for c, _ in ibge.values()} - set(onde))
        if ibge:
            problemas += fora_das_regioes(uf, ibge, regioes, [notas.get(v["nota"], "") for v in vazio])
        saida[uf] = regioes
    return saida, problemas


def calendario(url: str = DOU) -> dict:
    """O calendário da portaria; qualquer leitura que não bate faz a coleta falhar, sem gravar nada."""
    saida, problemas = le_calendario(url)
    if problemas:
        for p in problemas:
            print("::error::" + p)
        raise SystemExit("calendário com problemas; nada foi gravado")
    return saida


def recursos_do_zarc() -> list[dict]:
    """Os arquivos da tábua de risco do ZARC no catálogo do Ministério, um por safra."""
    r = requests.get(CKAN, headers=UA, timeout=60)
    r.raise_for_status()
    return r.json()["result"]["resources"]


def zarc(recursos: list[dict], safra: str = SAFRA) -> tuple[list[dict], dict]:
    alvo = next(x for x in recursos if safra in (x.get("name") or ""))
    linhas, portarias = [], {}
    with requests.get(alvo["url"], headers=UA, timeout=600, stream=True) as resp:
        resp.raise_for_status()
        cab = None
        for bruto in resp.iter_lines():
            campos = [c.strip().strip('"') for c in bruto.decode("utf-8", "replace").split(";")]
            if cab is None:
                cab = [c.lstrip("﻿") for c in campos]
                continue
            reg = dict(zip(cab, campos))
            if reg.get("Nome_cultura", "").lower() != "soja" or reg.get("UF") not in ESTADOS:
                continue
            if reg.get("Cod_Outros_Manejos") not in ("1", ""):  # só sequeiro
                continue
            riscos = "".join(CODIGO_RISCO[reg[f"dec{i}"]] for i in range(1, 37))
            linhas.append({"uf": reg["UF"], "geocodigo": int(reg["geocodigo"]), "municipio": reg["municipio"],
                           "ciclo": int(reg["Cod_Ciclo"]), "solo": int(reg["Cod_Solo"]), "riscos": riscos})
            portarias[reg["UF"]] = reg["Portaria"]
    linhas.sort(key=lambda x: (x["uf"], x["geocodigo"], x["ciclo"], x["solo"]))
    if not linhas or set(portarias) != set(ESTADOS):
        raise SystemExit(f"ZARC sem soja em todos os estados: {sorted(portarias)}")
    return linhas, {"recurso": alvo["url"], "portarias": portarias}


def descobre(saida: Path) -> dict:
    """O que a coleta lê nesta rodada (portaria e tábua do ZARC), com o que se achou impresso no log."""
    atual = safra_em_uso(saida)
    recursos = recursos_do_zarc()
    safras_zarc = safras_do_zarc(recursos)
    try:
        nova = portaria_mais_nova()
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"::warning::A busca no Diário Oficial falhou ({type(e).__name__}: {e}); a coleta segue na safra em uso.")
        nova = None
    print(f"Safra em uso: {atual['safra']} ({atual['fonte']})")
    print("Portaria mais nova no Diário Oficial: "
          + (f"{nova['fonte']}, safra {nova['safra']}, {nova['url']}" if nova else "não encontrada"))
    print(f"Tábuas do ZARC no catálogo: {', '.join(safras_zarc) or 'nenhuma'}")
    alvo, mesma_safra = escolhe_calendario(atual, nova)
    if alvo is not atual:
        print(f"::notice::Portaria nova: {alvo['fonte']}, safra {alvo['safra']}"
              + ("; é da mesma safra da em uso, e a coleta tenta ler nela o calendário inteiro." if mesma_safra
                 else "; o calendário passa para ela."))
    return {"atual": atual, "alvo": alvo, "mesma_safra": mesma_safra,
            "tabua": tabua_para(alvo["safra"], safras_zarc), "recursos": recursos}


def texto_do_aviso(atual: dict, nova: dict, problemas: list[str]) -> str:
    """A issue de uma portaria da mesma safra sem o calendário inteiro: o título na primeira linha, o texto depois."""
    estados = ", ".join(ESTADOS[:-1]) + " ou " + ESTADOS[-1]
    linhas = [
        f"Calendário de semeadura: conferir a {nova['fonte']}",
        f"A busca no Diário Oficial achou a [{nova['fonte']}]({nova['url']}), da safra {nova['safra']} e "
        f"posterior à portaria em uso ([{atual['fonte']}]({atual['url']})). A página dela não traz o calendário "
        "inteiro dos estados do produto, e a coleta seguiu na portaria em uso.",
        "",
        f"Pode ser uma alteração das datas ou das regiões de algum estado ({estados}), que o produto ainda não "
        "mostra. Confira o texto; se ela mudar algo, o coletor (`software/automacao_github/coleta_plantio.py`) "
        "precisa aprender a ler a alteração.",
        "",
        "O que não bateu na leitura:",
    ]
    return "\n".join(linhas + [f"- {p}" for p in problemas]) + "\n"


def _igual(arquivo: Path, texto: str) -> bool:
    try:
        with open(arquivo, encoding="utf-8", newline="") as f:
            return f.read() == texto
    except OSError:
        return False


def grava(saida: Path, aviso: Path | None = None) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    plano = descobre(saida)
    atual, alvo = plano["atual"], plano["alvo"]
    if plano["mesma_safra"]:
        cal, problemas = le_calendario(alvo["url"])
        if problemas:
            for p in problemas:
                print("::warning::" + p)
            print(f"::warning::A {alvo['fonte']} não traz o calendário inteiro; a coleta segue na {atual['fonte']}.")
            if aviso:
                aviso.write_text(texto_do_aviso(atual, alvo, problemas), encoding="utf-8")
            alvo = atual
            cal = calendario(atual["url"])
    else:
        cal = calendario(alvo["url"])
    safra, portaria, url, tabua = alvo["safra"], alvo["fonte"], alvo["url"], plano["tabua"]
    linhas, meta = zarc(plano["recursos"], tabua)
    # Os três arquivos ficam prontos antes de gravar qualquer um: uma falha no
    # meio não deixa o calendário de uma safra com uma tábua que não a escolhida.
    texto_cal = json.dumps({"safra": safra, "fonte": portaria, "url": url, "estados": cal},
                           ensure_ascii=False, indent=1) + "\n"
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["uf", "geocodigo", "municipio", "ciclo", "solo", "riscos"])
    w.writeheader()
    w.writerows(linhas)
    texto_zarc = buf.getvalue()
    fontes = {
        "safra": safra,
        "calendario": {"fonte": portaria, "url": url},
        # A safra da tábua pode ser a anterior à do calendário, enquanto a nova não sai.
        "zarc": {"safra": tabua,
                 "fonte": "Tábua de risco do ZARC, Ministério da Agricultura (dados abertos, "
                          "licença Creative Commons Atribuição)",
                 "url": meta["recurso"], "portarias": meta["portarias"],
                 "ciclos": {"20": "Grupo I", "21": "Grupo II", "22": "Grupo III"},
                 "solos": {str(c): f"AD{c - 10}" for c in range(11, 17)}},
    }
    arq_cal = saida / f"calendario_soja_{safra.replace('/', '_')}.json"
    arq_zarc = saida / f"zarc_soja_{tabua.replace('/', '_')}.csv"
    arq_fontes = saida / "fontes_plantio.json"
    try:
        anterior = json.loads(arq_fontes.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        anterior = {}
    # A data só muda quando algo muda: sem isso, cada coleta semanal abriria um
    # PR só com a data nova.
    nada_mudou = (_igual(arq_cal, texto_cal) and _igual(arq_zarc, texto_zarc)
                  and {k: v for k, v in anterior.items() if k != "lido_em"} == fontes)
    fontes["lido_em"] = anterior["lido_em"] if nada_mudou and anterior.get("lido_em") else date.today().isoformat()
    for arquivo, texto in ((arq_cal, texto_cal), (arq_zarc, texto_zarc),
                           (arq_fontes, json.dumps(fontes, ensure_ascii=False, indent=1) + "\n")):
        with open(arquivo, "w", encoding="utf-8", newline="") as f:
            f.write(texto)
    for uf, regs in cal.items():
        for reg in regs:
            n = len(reg["municipios"]) if isinstance(reg["municipios"], list) else "todos"
            extra = [f"exceção em {c}: {t}" for c, t in reg["excecoes"].items()]
            extra += [f"distritos de {d['municipio']}: {d['texto']}" for d in reg["distritos"]]
            print(f"{uf} região {reg['regiao'] or '-'}: vazio {reg['vazio']}, semeadura {reg['semeadura']}, "
                  f"{n} municípios" + "".join("; " + e for e in extra))
    print(f"ZARC da safra {tabua}: {len(linhas)} linhas; portarias {meta['portarias']}")
    print("Nada mudou nas fontes." if nada_mudou else f"Gravado em {saida} (lido em {fontes['lido_em']}).")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path, default=SAIDA)
    ap.add_argument("--descobre", action="store_true", help="só mostra a portaria e as safras encontradas")
    ap.add_argument("--aviso", type=Path, help="onde gravar o aviso de uma portaria da mesma safra que não se leu")
    args = ap.parse_args(argv)
    if args.descobre:
        plano = descobre(args.saida)
        print(f"A coleta leria: {plano['alvo']['fonte']} (safra {plano['alvo']['safra']}) "
              f"e a tábua do ZARC da safra {plano['tabua']}")
        return 0
    grava(args.saida, args.aviso)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
