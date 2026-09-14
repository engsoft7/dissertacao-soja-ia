# -*- coding: utf-8 -*-
"""
Procura um preprint deste trabalho no SSRN, pela Crossref.

O SSRN está bloqueado por política de rede tanto em papers.ssrn.com quanto em
api.ssrn.com, e raspar o site esbarraria na proteção antirrobô de todo jeito.
Não é preciso: preprint do SSRN recebe DOI 10.2139/ssrn.* e é depositado na
Crossref como "posted-content". Consultar a Crossref responde a mesma pergunta
com fonte melhor — o registro do próprio editor.

A pergunta que importa é se existe, público, um preprint com o título antigo,
o da submissão recusada pela Computers and Electronics in Agriculture. Se
existir, o que está no SSRN diverge do que foi declarado à European Journal of
Agronomy, e é melhor descobrir agora.

Uso:  python procura_preprint_ssrn.py
"""
import os
import sys
import time

import requests

API = 'https://api.crossref.org/works'
MAILTO = os.environ.get('CROSSREF_MAILTO', '')

TITULO_ATUAL = ('Value repetition in official crop statistics: a diagnostic of '
                'target-variable quality and its effect on the evaluation of '
                'machine learning yield models')
TITULO_ANTIGO = ('Machine learning crop yield prediction is bounded by '
                 'target-variable quality')
AUTOR = 'Maycon Lima dos Santos'


def busca(**params):
    # Os parâmetros de consulta da Crossref levam ponto — query.author,
    # query.bibliographic — então chegam aqui por dicionário desempacotado:
    # com ponto o Python não aceita palavra-chave, e trocar o ponto por
    # sublinhado faz a API devolver 400.
    cab = {'User-Agent': f'dissertacao-soja-ia/1.0 (mailto:{MAILTO})' if MAILTO
           else 'dissertacao-soja-ia/1.0'}
    r = requests.get(API, params={'rows': 20, **params}, headers=cab, timeout=40)
    r.raise_for_status()
    return r.json()['message']['items']


def relata(rotulo, itens, so_ssrn=False):
    print(f'\n── {rotulo} ──')
    achou = False
    for it in itens:
        doi = it.get('DOI', '')
        if so_ssrn and 'ssrn' not in doi.lower():
            continue
        achou = True
        titulo = (it.get('title') or [''])[0]
        autores = ', '.join(f"{a.get('given','')} {a.get('family','')}".strip()
                            for a in (it.get('author') or [])[:4])
        ano = (it.get('issued', {}).get('date-parts') or [[None]])[0][0]
        print(f'  {doi}')
        print(f'    [{it.get("type","")}] {ano} — {titulo[:90]}')
        print(f'    {autores or "(sem autores depositados)"}')
    if not achou:
        print('  nada' + (' com DOI do SSRN' if so_ssrn else ''))
    return achou


def main():
    print('Procurando preprint no SSRN pelo registro da Crossref\n')
    print('SSRN bloqueado por política de rede; a Crossref registra os')
    print('preprints do SSRN como posted-content sob 10.2139/ssrn.*\n')

    algum = False
    algum |= relata('DOIs do SSRN com o autor no nome',
                    busca(**{'query.author': AUTOR, 'filter': 'prefix:10.2139'}), so_ssrn=True)
    time.sleep(0.5)
    algum |= relata('DOIs do SSRN com o título atual',
                    busca(**{'query.bibliographic': TITULO_ATUAL,
                             'filter': 'prefix:10.2139'}), so_ssrn=True)
    time.sleep(0.5)
    algum |= relata('DOIs do SSRN com o título antigo (versão da COMPAG)',
                    busca(**{'query.bibliographic': TITULO_ANTIGO,
                             'filter': 'prefix:10.2139'}), so_ssrn=True)
    time.sleep(0.5)
    relata('qualquer registro com este autor, sem filtro de prefixo',
           busca(**{'query.author': AUTOR, 'query.bibliographic': 'soybean yield repetition'}))

    print('\n' + '=' * 72)
    if algum:
        print('HÁ registro do SSRN. Confira o título acima contra o submetido.')
        return 1
    print('Nenhum preprint do SSRN registrado na Crossref para este autor ou título.')
    print('Ressalva: o depósito na Crossref pode levar dias após a publicação no')
    print('SSRN, então isto não prova ausência — apenas que não há registro hoje.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
