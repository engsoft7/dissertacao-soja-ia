# -*- coding: utf-8 -*-
"""
Resolve na Crossref o ano de publicação dos 53 estudos incluídos na revisão.

Existe porque os três registros do mesmo fato discordam entre si. A distribuição
por ano dos estudos incluídos aparece em três lugares — no parágrafo de síntese
da subseção 3.5, no Apêndice B da dissertação e neste repositório, em
referencias_53_estudos_abnt.txt e em estudos_triados.csv — e os três dão
números diferentes para as safras recentes:

    texto da síntese   2022:5  2023:9   2024:15  2025:7
    Apêndice B         2022:4  2023:10  2024:15  2025:7
    repositório        2022:5  2023:10  2024:16  2025:5

Somam 53 nos três casos, de modo que nenhum perdeu estudo: o que muda é o ano
atribuído a quatro deles. Discordância assim não se resolve escolhendo a versão
mais simpática — resolve-se perguntando a quem publicou.

O script pergunta. Para cada DOI imprime a data impressa e a data on-line que a
editora depositou, porque são elas que produzem a divergência: um artigo que sai
on-line em dezembro e entra no fascículo de janeiro tem dois anos igualmente
verdadeiros, e a norma pede o do fascículo.

Roda no GitHub Actions: o ambiente de desenvolvimento não alcança
api.crossref.org, negada por política de rede.

Uso:  python 04_confere_anos_crossref.py
"""
import collections
import os
import re
import sys
import time

import requests

RAIZ = os.path.dirname(os.path.abspath(__file__))
FONTE = os.path.join(RAIZ, 'referencias_53_estudos_abnt.txt')
API = 'https://api.crossref.org/works/'
ESPERA = 0.4

# Como cada registro conta os mesmos 53 estudos.
SERIES = {
    'texto da síntese': {2018: 3, 2019: 3, 2020: 3, 2021: 8, 2022: 5,
                         2023: 9, 2024: 15, 2025: 7},
    'Apêndice B': {2018: 3, 2019: 3, 2020: 3, 2021: 8, 2022: 4,
                   2023: 10, 2024: 15, 2025: 7},
}
# O do repositório não se escreve à mão: lê-se do arquivo, para que a tabela
# acuse sozinha se alguém reintroduzir um ano errado.


# DOIs cujo ano é disputado entre os três registros e que, por isso, valem
# detalhe mesmo quando o repositório acerta. Os dois da MDPI estão aqui porque
# o número do volume sugere um ano e a data depositada pode sugerir outro:
# Remote Sensing v. 17 e Computation v. 13 são volumes de 2025, ainda que o
# artigo tenha saído nos últimos dias de 2024.
DETALHAR = (
    '10.3390/rs17010107',
    '10.3390/computation13010004',
    '10.1002/agj2.21473',
    '10.1109/jstars.2022.3223423',
)


def doi_de(linha):
    m = re.search(r'10\.\d{4,9}/[^\s,;]+', linha)
    return m.group(0).rstrip('.').lower() if m else None


def ano_abnt(linha):
    """O ano como está impresso na referência, antes do DOI."""
    antes = linha.split('DOI:')[0]
    anos = re.findall(r'\b(?:19|20)\d{2}[ab]?\b', antes)
    return int(re.sub(r'[ab]$', '', anos[-1])) if anos else None


def parte_ano(item, campo):
    partes = (item.get(campo) or {}).get('date-parts', [[None]])
    return partes[0][0] if partes and partes[0] else None


def coerencia_volume_ano(linhas):
    """Confere se o ano impresso é coerente com o volume, periódico a periódico.

    Foi isto que desempatou os dois artigos da MDPI, que a Crossref não decide e
    cuja página responde 403 a quem consulta de um servidor. Periódico sério
    incrementa o volume uma vez por ano, e a própria bibliografia deste trabalho
    fixa a escala: Remote Sensing v. 13 em 2021, v. 14 em 2022, v. 15 em 2023 —
    logo v. 17 é 2025, e não 2024, que é apenas a data em que o artigo apareceu
    on-line, nos últimos dias de dezembro, já dentro do volume seguinte.

    A checagem não depende de saber o calendário de nenhuma editora: deriva a
    escala das próprias referências e aponta quem destoa dela.
    """
    import collections
    por_revista = collections.defaultdict(list)
    for l in linhas:
        if 'DOI:' not in l or ', v. ' not in l:
            continue
        revista = l.split(', v. ')[0].split('. ')[-1].strip()
        v = re.search(r',\s*v\.\s*(\d+)', l)
        a = re.search(r',\s*((?:19|20)\d{2})[ab]?\s*\.\s*DOI', l)
        if v and a:
            por_revista[revista].append((int(v.group(1)), int(a.group(1)),
                                         doi_de(l)))

    print('Coerência entre volume e ano, periódico a periódico:')
    print('-' * 78)
    incoerentes = 0
    for revista, itens in sorted(por_revista.items()):
        if len(itens) < 2:
            continue
        # a escala: quanto vale volume - ano nesse periódico, pelo voto da maioria
        desloc = collections.Counter(v - a for v, a, _ in itens)
        base, quantos = desloc.most_common(1)[0]
        if quantos < 2:
            continue
        fora = [(v, a, d) for v, a, d in itens if v - a != base]
        marca = 'ok' if not fora else f'{len(fora)} fora da escala'
        print(f'  {revista[:56]:56s} {len(itens):>2} itens  {marca}')
        for v, a, dd in fora:
            incoerentes += 1
            print(f'       v. {v} impresso como {a}; pela escala seria {v - base}')
            print(f'       {dd}')
    print(f'  total incoerente: {incoerentes}\n')
    return incoerentes


def confere_mdpi(doi):
    """Pergunta à MDPI o ano que ela própria imprime na citação do artigo.

    A Crossref não decide o caso dos dois artigos da MDPI. Ela traz apenas a
    data on-line, dezembro de 2024, enquanto o número do volume — Remote
    Sensing v. 17 e Computation v. 13 — é o do volume de 2025. A MDPI publica
    nos últimos dias de dezembro dentro do volume do ano seguinte, e a norma
    pede o ano do fascículo, não o do depósito.

    Quem desempata é a própria editora: a página do artigo imprime a citação
    completa, no formato "Remote Sens. 2025, 17(1), 107". É esse ano que o
    leitor vê e que a banca confere.
    """
    try:
        r = requests.get(f'https://doi.org/{doi}', timeout=40, allow_redirects=True,
                         headers={'User-Agent': 'Mozilla/5.0 (compatible; '
                                                'dissertacao-soja-ia/1.0)'})
    except requests.RequestException as e:
        return None, f'falhou: {e}'
    if r.status_code != 200:
        return None, f'HTTP {r.status_code}'
    # A citação aparece em <meta name="citation_date"> e no texto da página.
    m = re.search(r'name="citation_(?:date|publication_date)"\s+content="(\d{4})',
                  r.text)
    if m:
        return int(m.group(1)), 'meta citation_date'
    m = re.search(r'\b(?:Remote Sens|Computation)\.\s+(\d{4}),', r.text)
    if m:
        return int(m.group(1)), 'linha de citação da página'
    return None, 'não encontrei o ano na página'


def main():
    linhas = [l.strip() for l in open(FONTE, encoding='utf-8') if l.strip()]
    print(f'referências no arquivo: {len(linhas)}\n')

    coerencia_volume_ano(linhas)

    SERIES['repositório'] = collections.Counter(
        a for a in (ano_abnt(l) for l in linhas) if a)

    resolvidos, falhas = {}, []
    for linha in linhas:
        doi = doi_de(linha)
        if not doi:
            falhas.append(('sem DOI', linha[:70]))
            continue
        try:
            r = requests.get(API + doi, timeout=40,
                             headers={'User-Agent': 'dissertacao-soja-ia/1.0'})
        except requests.RequestException as e:
            falhas.append((doi, f'falhou: {e}'))
            time.sleep(ESPERA)
            continue
        time.sleep(ESPERA)
        if r.status_code != 200:
            falhas.append((doi, f'HTTP {r.status_code}'))
            continue
        item = r.json()['message']
        resolvidos[doi] = {
            'impresso': parte_ano(item, 'published-print'),
            'online': parte_ano(item, 'published-online'),
            'issued': parte_ano(item, 'issued'),
            'veiculo': (item.get('container-title') or ['?'])[0],
            'volume': item.get('volume'),
            'abnt': ano_abnt(linha),
        }

    # O ano da norma é o do fascículo; on-line só quando não há fascículo.
    def ano_final(d):
        return d['impresso'] or d['online'] or d['issued']

    # A primeira versão deste script só listava os DOIs em que a data impressa e
    # a on-line caíam em anos diferentes, e por isso explicava apenas parte da
    # divergência: um ano trocado por outro motivo — registro sem data impressa,
    # ou ano simplesmente errado no arquivo — passava sem aparecer. O que
    # interessa é comparar cada DOI com o ano que está impresso na referência.
    print('DOIs em que o ano do repositório difere do que a editora depositou:')
    print('-' * 78)
    divergentes = 0
    for doi, d in sorted(resolvidos.items()):
        if ano_final(d) != d['abnt']:
            divergentes += 1
            print(f'  {doi}')
            print(f'     no repositório: {d["abnt"]}   ->   Crossref: {ano_final(d)}')
            print(f'     fascículo: {d["impresso"] or "-"}   on-line: '
                  f'{d["online"] or "-"}   issued: {d["issued"] or "-"}')
            print(f'     {d["veiculo"][:70]}')
    print(f'  total: {divergentes}\n')

    crossref = collections.Counter(ano_final(d) for d in resolvidos.values())
    print('DOIs disputados, com tudo o que a editora depositou:')
    print('-' * 78)
    for doi in DETALHAR:
        d = resolvidos.get(doi)
        if not d:
            print(f'  {doi}  não resolvido')
            continue
        print(f'  {doi}')
        print(f'     fascículo: {d["impresso"] or "-"}   on-line: {d["online"] or "-"}'
              f'   issued: {d["issued"] or "-"}   volume: {d.get("volume") or "-"}')
        print(f'     no repositório: {d["abnt"]}   ->   adotado: {ano_final(d)}')
        print(f'     {d["veiculo"][:70]}')
    print()

    print('O que a MDPI imprime na página dos dois artigos:')
    print('-' * 78)
    mdpi = {}
    for doi in DETALHAR:
        if not doi.startswith('10.3390/'):
            continue
        ano, origem = confere_mdpi(doi)
        mdpi[doi] = ano
        time.sleep(ESPERA)
        dep = resolvidos.get(doi, {})
        print(f'  {doi}')
        print(f'     Crossref: {ano_final(dep) if dep else "?"}   '
              f'MDPI: {ano if ano else "—"}  ({origem})')
    print()

    print('=' * 78)
    print('DISTRIBUIÇÃO POR ANO')
    print('=' * 78)
    anos = sorted(set(crossref) | {a for s in SERIES.values() for a in s})
    cab = 'ano   ' + ''.join(f'{n[:16]:>18s}' for n in SERIES) + f'{"Crossref":>18s}'
    print(cab)
    print('-' * len(cab))
    for a in anos:
        linha = f'{a}  '
        for nome in SERIES:
            linha += f'{SERIES[nome].get(a, 0):>18d}'
        linha += f'{crossref.get(a, 0):>18d}'
        print(linha)
    linha = 'total '
    for nome in SERIES:
        linha += f'{sum(SERIES[nome].values()):>18d}'
    linha += f'{sum(crossref.values()):>18d}'
    print('-' * len(cab))
    print(linha)

    print('\nquantos anos cada registro acerta, tomando a Crossref por referência:')
    for nome, s in SERIES.items():
        iguais = sum(1 for a in anos if s.get(a, 0) == crossref.get(a, 0))
        print(f'  {nome:18s} {iguais} de {len(anos)}')

    if falhas:
        print(f'\nnão resolvidos: {len(falhas)}')
        for doi, motivo in falhas:
            print(f'  {doi}  {motivo}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
