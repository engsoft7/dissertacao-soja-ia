# -*- coding: utf-8 -*-
"""
Resolve cada DOI da lista de referências e compara com o que a editora depositou.

Diferente de confere_referencias.py, que busca sete referências pelo título e
deixa a comparação a olho, este parte do arquivo que foi submetido — o
Manuscript.docx — extrai todos os DOIs impressos e resolve um a um na Crossref,
confrontando ano, periódico, volume, número de artigo ou páginas e sobrenome do
primeiro autor. O que o script não consegue decidir sozinho ele imprime lado a
lado, em vez de aprovar por semelhança de string.

Roda no GitHub Actions: o ambiente de desenvolvimento não alcança
api.crossref.org nem doi.org, ambos negados por política de rede.

Uso:  python confere_doi_referencias.py
"""
import os
import re
import sys
import time
import unicodedata

import requests
from docx import Document

RAIZ = os.path.dirname(os.path.abspath(__file__))
DOCX = os.path.join(RAIZ, 'saida', 'Manuscript.docx')
API = 'https://api.crossref.org/works/'
MAILTO = os.environ.get('CROSSREF_MAILTO', '')
# O DOI do próprio depósito no Zenodo não está na Crossref: o Zenodo registra na
# DataCite. Resolver lá seria outra API e outro formato; fica declarado aqui em
# vez de aparecer como falha.
DATACITE = ('10.5281/zenodo.22739059',)


def sem_acento(t):
    return ''.join(c for c in unicodedata.normalize('NFD', t)
                   if unicodedata.category(c) != 'Mn').lower()


def referencias_do_docx(caminho):
    """Os parágrafos da seção References, na ordem em que foram submetidos."""
    d = Document(caminho)
    textos, dentro = [], False
    for p in d.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        if t == 'References':
            dentro = True
            continue
        if dentro:
            textos.append(t)
    return textos


def consulta(doi):
    url = API + requests.utils.quote(doi)
    cab = {'User-Agent': f'dissertacao-soja-ia/1.0 (mailto:{MAILTO})' if MAILTO
           else 'dissertacao-soja-ia/1.0'}
    r = requests.get(url, headers=cab, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()['message']


def ano_depositado(m):
    """O ano de impressão quando existe; senão o da publicação online."""
    for campo in ('published-print', 'published-online', 'issued', 'created'):
        parte = m.get(campo, {}).get('date-parts', [[None]])[0]
        if parte and parte[0]:
            return int(parte[0]), campo
    return None, None


def main():
    refs = referencias_do_docx(DOCX)
    print(f'{len(refs)} referências lidas de {os.path.basename(DOCX)}\n')

    problemas, sem_doi, checadas = [], [], 0
    for texto in refs:
        achado = re.search(r'https?://doi\.org/(\S+?)\.?$', texto)
        rotulo = texto[:60].rstrip() + '…'
        if not achado:
            sem_doi.append(rotulo)
            print(f'—  {rotulo}\n   sem DOI impresso\n')
            continue
        doi = achado.group(1).rstrip('.')
        if doi in DATACITE:
            print(f'—  {rotulo}\n   {doi} — registrado na DataCite (Zenodo), '
                  f'fora do escopo da Crossref\n')
            continue

        try:
            m = consulta(doi)
        except Exception as erro:
            problemas.append((rotulo, f'falha na consulta: {erro}'))
            print(f'!  {rotulo}\n   {doi} — {erro}\n')
            continue
        if m is None:
            problemas.append((rotulo, 'DOI não existe na Crossref'))
            print(f'X  {rotulo}\n   {doi} — NÃO ENCONTRADO\n')
            continue

        checadas += 1
        titulo = (m.get('title') or [''])[0]
        revista = (m.get('container-title') or [''])[0]
        ano, campo = ano_depositado(m)
        volume = m.get('volume', '')
        artigo = m.get('article-number', '') or m.get('page', '')
        autores = m.get('author', []) or []
        primeiro = autores[0].get('family', '') if autores else ''

        # o que o manuscrito afirma, extraído do próprio texto da referência
        divergencias = []
        anos_no_texto = re.findall(r'\b(19|20)(\d{2})\b', texto[:120])
        ano_texto = int(f'{anos_no_texto[0][0]}{anos_no_texto[0][1]}') if anos_no_texto else None
        if ano_texto and ano and ano_texto != ano:
            outro = m.get('published-online', {}).get('date-parts', [[None]])[0][0]
            if ano_texto != outro:
                divergencias.append(f'ano: manuscrito {ano_texto}, depósito {ano} ({campo})')
        if volume and volume not in texto:
            divergencias.append(f'volume {volume} não aparece no texto da referência')
        if artigo and artigo.split('-')[0] not in texto.replace('–', '-'):
            divergencias.append(f'página/artigo {artigo} não aparece no texto')
        if primeiro and sem_acento(primeiro).split()[-1] not in sem_acento(texto):
            divergencias.append(f'primeiro autor depositado: {primeiro}')

        marca = 'ok' if not divergencias else '??'
        print(f'{marca}  {rotulo}')
        print(f'    {doi}')
        print(f'    {primeiro} et al. ({ano}, {campo}) — {revista} {volume}, {artigo}')
        print(f'    {titulo[:95]}')
        for d in divergencias:
            print(f'    >> {d}')
        print()
        if divergencias:
            problemas.append((rotulo, '; '.join(divergencias)))
        time.sleep(0.4)

    print('=' * 72)
    print(f'{checadas} DOIs resolvidos na Crossref')
    if sem_doi:
        print(f'{len(sem_doi)} referência(s) sem DOI impresso:')
        for r in sem_doi:
            print(f'  - {r}')
    if problemas:
        print(f'\n{len(problemas)} ponto(s) a conferir a olho:')
        for r, p in problemas:
            print(f'  - {r}\n      {p}')
        return 1
    print('Nenhuma divergência automática entre o manuscrito e o registro da editora.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
