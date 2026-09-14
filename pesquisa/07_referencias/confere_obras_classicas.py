# -*- coding: utf-8 -*-
"""
Confere os metadados das obras clássicas que entram nas subseções 2.3 e 2.4.3.

O acervo da dissertação — 41 referências — não tinha nenhum livro. As duas
lacunas de citação que restaram depois da revisão (os fundamentos de IA, no
parágrafo de abertura da subseção 2.3, e a obra de origem da Regressão por
Vetores de Suporte, na 2.4.3) só se resolvem com bibliografia nova, e a maior
parte dela é livro. Citar edição errada de livro é erro que a banca encontra
folheando, e escrever de memória o ano de uma edição é exatamente como se
comete.

Por isso este script não confia em memória: resolve na Crossref o que tem DOI
e consulta a Open Library o que é livro, imprimindo o que cada base devolve.
Ele não aprova nem reprova nada sozinho — imprime lado a lado para o autor
decidir, porque a pergunta "qual edição você tem em mãos" nenhuma API responde.

De quebra, resolve uma divergência interna do próprio acervo: o mesmo trabalho
do e-Science 2018 aparece com duas autorias diferentes na lista de referências
e no Apêndice B.

Roda no GitHub Actions: o ambiente de desenvolvimento não alcança
api.crossref.org, openlibrary.org nem googleapis.com, todos negados por
política de rede.

Uso:  python confere_obras_classicas.py
"""
import json
import sys
import time

import requests

CROSSREF = 'https://api.crossref.org/works'
OPENLIB = 'https://openlibrary.org/search.json'
# A Crossref não indexa os proceedings do NIPS dos anos 1990 — a primeira
# rodada deste script devolveu cinco capítulos de livro alheios no lugar do
# artigo procurado. A OpenAlex indexa, e a revisão sistemática desta pesquisa
# já a utiliza.
OPENALEX = 'https://api.openalex.org/works'
ESPERA = 1.0

# Trabalhos com DOI: a Crossref responde com o registro do próprio editor.
POR_DOI = [
    ('Smola; Schölkopf — tutorial de SVR (o que descreve margem e kernel)',
     '10.1023/B:STCO.0000035301.49549.88'),
    ('Cunha et al. OU Oliveira et al. — e-Science 2018, divergência do acervo',
     '10.1109/escience.2018.00131'),
]

# Trabalhos sem DOI confiável: busca por título na Crossref.
POR_TITULO = []

# Trabalhos que a Crossref não alcança.
POR_OPENALEX = [
    ('Drucker et al. — o artigo que propõe a SVR', 'Support vector regression machines'),
]

# Livros: a Open Library é a base aberta que cataloga edições. Interessa o ano
# da primeira edição e as edições subsequentes, porque é nisso que a citação
# erra.
LIVROS = [
    # Sem os dois-pontos e sem o subtítulo: com o título completo a Open
    # Library não devolveu nada na primeira rodada.
    ('Russell; Norvig — manual canônico de IA',
     'Artificial intelligence', 'Norvig'),
    ('Mitchell — manual canônico de Aprendizado de Máquina',
     'Machine Learning', 'Mitchell'),
    ('Vapnik — a teoria por trás das máquinas de vetores de suporte',
     'The Nature of Statistical Learning Theory', 'Vapnik'),
    ('Goodfellow; Bengio; Courville — manual canônico de Aprendizado Profundo',
     'Deep Learning', 'Goodfellow'),
    ('Hastie; Tibshirani; Friedman — alternativa estatística ao Mitchell',
     'The Elements of Statistical Learning', 'Hastie'),
]


def pede(url, **params):
    try:
        r = requests.get(url, params=params, timeout=40,
                         headers={'User-Agent': 'dissertacao-soja-ia/1.0'})
    except requests.RequestException as e:
        return None, f'falhou: {e}'
    if r.status_code != 200:
        return None, f'HTTP {r.status_code}'
    try:
        return r.json(), None
    except json.JSONDecodeError:
        return None, 'resposta não é JSON'


def autores(item):
    nomes = []
    for a in item.get('author', []):
        sobre = a.get('family') or a.get('name') or ''
        dado = a.get('given', '')
        nomes.append(f"{sobre}, {dado}".strip(', '))
    return '; '.join(nomes) if nomes else '(sem autoria no registro)'


def ano(item):
    for campo in ('published-print', 'published-online', 'issued', 'created'):
        partes = item.get(campo, {}).get('date-parts', [[None]])
        if partes and partes[0] and partes[0][0]:
            return partes[0][0]
    return '?'


def mostra_crossref(rotulo, item):
    print(f'  título    : {(item.get("title") or ["?"])[0]}')
    print(f'  autoria   : {autores(item)}')
    print(f'  ano       : {ano(item)}')
    print(f'  veículo   : {(item.get("container-title") or ["(sem veículo)"])[0]}')
    vol, num, pag = item.get('volume'), item.get('issue'), item.get('page')
    print(f'  v./n./p.  : {vol or "-"} / {num or "-"} / {pag or "-"}')
    print(f'  tipo      : {item.get("type", "?")}')
    print(f'  DOI       : {item.get("DOI", "?")}')
    print(f'  editora   : {item.get("publisher", "?")}')


def mostra_openalex(obra):
    aut = '; '.join(a['author'].get('display_name', '?')
                    for a in obra.get('authorships', []))
    loc = (obra.get('primary_location') or {}).get('source') or {}
    print(f'  título    : {obra.get("display_name", "?")}')
    print(f'  autoria   : {aut or "(sem autoria no registro)"}')
    print(f'  ano       : {obra.get("publication_year", "?")}')
    print(f'  veículo   : {loc.get("display_name", "(sem veículo)")}')
    print(f'  tipo      : {obra.get("type", "?")}')
    bib = obra.get('biblio') or {}
    print(f'  v./n./p.  : {bib.get("volume") or "-"} / {bib.get("issue") or "-"} / '
          f'{bib.get("first_page") or "-"}-{bib.get("last_page") or "-"}')
    print(f'  DOI       : {obra.get("doi") or "(sem DOI)"}')
    print(f'  citações  : {obra.get("cited_by_count", "?")}')


def main():
    falhas = 0

    print('=' * 78)
    print('COM DOI — resolvidos na Crossref')
    print('=' * 78)
    for rotulo, doi in POR_DOI:
        print(f'\n{rotulo}\n  consulta  : {doi}')
        dados, erro = pede(f'{CROSSREF}/{doi}')
        time.sleep(ESPERA)
        if erro:
            print(f'  ERRO      : {erro}')
            falhas += 1
            continue
        mostra_crossref(rotulo, dados['message'])

    print('\n' + '=' * 78)
    print('SEM DOI CONHECIDO — busca por título na Crossref')
    print('=' * 78)
    for rotulo, titulo in POR_TITULO:
        print(f'\n{rotulo}\n  consulta  : "{titulo}"')
        dados, erro = pede(CROSSREF, **{'query.bibliographic': titulo, 'rows': 5})
        time.sleep(ESPERA)
        if erro:
            print(f'  ERRO      : {erro}')
            falhas += 1
            continue
        itens = dados['message']['items']
        if not itens:
            print('  nada encontrado')
            falhas += 1
            continue
        for i, item in enumerate(itens, 1):
            print(f'  --- candidato {i} ---')
            mostra_crossref(rotulo, item)

    print('\n' + '=' * 78)
    print('FORA DA CROSSREF — OpenAlex')
    print('=' * 78)
    for rotulo, titulo in POR_OPENALEX:
        print(f'\n{rotulo}\n  consulta  : "{titulo}"')
        dados, erro = pede(OPENALEX, search=titulo, per_page=5,
                           mailto='mayconlimasan@gmail.com')
        time.sleep(ESPERA)
        if erro:
            print(f'  ERRO      : {erro}')
            falhas += 1
            continue
        obras = dados.get('results', [])
        if not obras:
            print('  nada encontrado')
            falhas += 1
            continue
        for i, obra in enumerate(obras, 1):
            print(f'  --- candidato {i} ---')
            mostra_openalex(obra)

    print('\n' + '=' * 78)
    print('LIVROS — Open Library')
    print('=' * 78)
    for rotulo, titulo, sobrenome in LIVROS:
        print(f'\n{rotulo}\n  consulta  : "{titulo}" + autor {sobrenome}')
        dados, erro = pede(OPENLIB, title=titulo, author=sobrenome, limit=4,
                           fields='title,author_name,first_publish_year,publisher,'
                                  'publish_year,isbn,number_of_pages_median')
        time.sleep(ESPERA)
        if erro:
            print(f'  ERRO      : {erro}')
            falhas += 1
            continue
        docs = dados.get('docs', [])
        if not docs:
            print('  nada encontrado')
            falhas += 1
            continue
        for i, doc in enumerate(docs, 1):
            anos = sorted({a for a in doc.get('publish_year', []) if a})
            print(f'  --- candidato {i} ---')
            print(f'  título    : {doc.get("title", "?")}')
            print(f'  autoria   : {"; ".join(doc.get("author_name", []) or ["?"])}')
            print(f'  1ª edição : {doc.get("first_publish_year", "?")}')
            print(f'  anos      : {", ".join(str(a) for a in anos[:24])}'
                  f'{" …" if len(anos) > 24 else ""}')
            eds = doc.get('publisher', []) or []
            print(f'  editoras  : {"; ".join(sorted(set(eds))[:10])}')

    print('\n' + '=' * 78)
    print(f'consultas que falharam: {falhas}')
    print('Nada aqui é decisão automática. O autor escolhe a edição que tem em mãos.')
    print('=' * 78)
    return 1 if falhas else 0


if __name__ == '__main__':
    sys.exit(main())
