"""Procura, nas fontes públicas, cotações físicas da soja em praças do Pará.

A página principal de cotações do Notícias Agrícolas, de onde precos.py lê o
físico do dia, não publica nenhuma praça do Pará (em 23/10/2026 trazia Sorriso,
Rondonópolis, Paranaguá e Rio Grande). Para estimar o preço no Pará ao longo do
dia é preciso de uma série do físico paraense, e este roteiro levanta onde ela
existe: subpáginas do Notícias Agrícolas, a Agrolink e os arquivos de preços
semanais e mensais da CONAB.

Só lê e relata. Roda no GitHub Actions, porque o ambiente de desenvolvimento
não alcança essas fontes.
"""
import io
import re
import sys
import zipfile

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
PARA = ("Barcarena", "Santarém", "Santarem", "Miritituba", "Itaituba", "Paragominas",
        "Redenção", "Redencao", "Dom Eliseu", "Ulianópolis", "Ulianopolis", "Marabá",
        "Maraba", "Rondon do Pará", "Santana do Araguaia", "Belterra", "Mojuí", "/PA", "(PA)", " PA ")

CONAB = "https://portaldeinformacoes.conab.gov.br/downloads/arquivos/"
CONAB_ARQUIVOS = ("PrecosSemanalMunicipio.txt", "PrecosSemanalUF.txt",
                  "PrecosMensalMunicipio.txt", "PrecosMensalUF.txt")


def baixa(url, **kw):
    r = requests.get(url, headers=UA, timeout=60, **kw)
    r.raise_for_status()
    return r


def trechos(texto, termos, largura=160, maximo=6):
    achados = []
    for t in termos:
        for m in re.finditer(re.escape(t), texto):
            a = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texto[max(0, m.start() - largura):m.end() + largura]))
            achados.append(a.strip())
            if len(achados) >= maximo:
                return achados
    return achados


def noticias_agricolas():
    print("\n== Notícias Agrícolas: subpáginas de /cotacoes/soja/")
    base = "https://www.noticiasagricolas.com.br"
    try:
        html = baixa(base + "/cotacoes/soja/").text
    except Exception as e:
        print("  indisponível:", e)
        return
    links = sorted(set(re.findall(r'href="(/cotacoes/soja/[^"#?]+)"', html)))
    print(f"  {len(links)} subpáginas")
    for link in links:
        try:
            pag = baixa(base + link).text
        except Exception as e:
            print(f"  {link}: erro {e}")
            continue
        achados = trechos(pag, PARA, maximo=3)
        datas = sorted(set(re.findall(r"\d{2}/\d{2}/\d{4}", pag)))[-3:]
        print(f"  {link}  datas={datas}  Pará={'SIM' if achados else 'não'}")
        for a in achados:
            print("     ·", a[:300])
    # Páginas com histórico costumam aceitar a data no caminho; registra o padrão dos links.
    hist = sorted(set(re.findall(r'href="(/cotacoes/soja/[^"]*\d{4}-\d{2}-\d{2}[^"]*)"', html)))[:5]
    print("  links com data:", hist)


def agrolink():
    print("\n== Agrolink")
    for url in ("https://www.agrolink.com.br/cotacoes/graos/soja/soja-em-grao-sc-60kg",
                "https://www.agrolink.com.br/cotacoes/historico/pa/soja-em-grao-sc-60kg"):
        try:
            pag = baixa(url).text
        except Exception as e:
            print(f"  {url}: erro {e}")
            continue
        achados = trechos(pag, PARA, maximo=6)
        print(f"  {url}: {len(pag)} bytes, Pará={'SIM' if achados else 'não'}")
        for a in achados:
            print("     ·", a[:300])


def conab():
    print("\n== CONAB: preços semanais e mensais")
    for nome in CONAB_ARQUIVOS:
        url = CONAB + nome
        try:
            r = baixa(url, stream=True)
            bruto = r.content
        except Exception as e:
            print(f"  {nome}: erro {e}")
            continue
        if bruto[:2] == b"PK":
            z = zipfile.ZipFile(io.BytesIO(bruto))
            bruto = z.read(z.namelist()[0])
        texto = bruto.decode("utf-8", errors="replace")
        linhas = texto.splitlines()
        print(f"  {nome}: {len(bruto)/1e6:.1f} MB, {len(linhas)} linhas")
        print("     cabeçalho:", linhas[0][:300])
        soja_pa = [l for l in linhas if "SOJA" in l.upper() and re.search(r"(^|[;,\t])\s*PA\s*([;,\t]|$)", l)]
        print(f"     linhas com SOJA e UF PA: {len(soja_pa)}")
        for l in soja_pa[:3] + soja_pa[-3:]:
            print("     ·", l[:300])
        produtos = sorted({c for l in linhas[1:20000] for c in l.split(";") if "SOJA" in c.upper()})[:10]
        print("     produtos com SOJA:", produtos)


if __name__ == "__main__":
    for etapa in (noticias_agricolas, agrolink, conab):
        try:
            etapa()
        except Exception as e:  # um diagnóstico não para no primeiro erro
            print(f"  {etapa.__name__} falhou: {type(e).__name__}: {e}")
    sys.exit(0)
