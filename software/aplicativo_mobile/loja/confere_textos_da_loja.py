# -*- coding: utf-8 -*-
"""
Confere textos_da_loja.txt antes de colar no Play Console.

O Google Play recusou a ficha por "declarações enganosas": o app usa dados de
órgãos públicos (IBGE, INMET, CONAB, Embrapa, NOAA) e a descrição precisa trazer
links claros e funcionando para as fontes oficiais, além do aviso de que o app
não é do governo. Este script verifica:

  - os limites do Play Console: nome até 30 caracteres, breve descrição até 80
    e descrição completa até 4.000;
  - que o aviso de não afiliação está na descrição completa;
  - que cada link abre (resposta 2xx ou 3xx), com até três tentativas.

Roda no Actions (confere-links-loja.yml), que tem acesso livre à internet.
Uso:  python confere_textos_da_loja.py [arquivo]
      python confere_textos_da_loja.py --links URL [URL ...]   # só testa endereços candidatos
"""
import os
import re
import sys
import time
import urllib.error
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
LIMITES = {'NOME DO APP': 30, 'BREVE DESCRIÇÃO': 80, 'DESCRIÇÃO COMPLETA': 4000}
NAVEGADOR = ('Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) '
             'Chrome/126.0 Mobile Safari/537.36')


def secoes(texto):
    partes, atual = {}, None
    for linha in texto.splitlines():
        if linha.strip() in LIMITES:
            atual = linha.strip(); partes[atual] = []
        elif atual:
            partes[atual].append(linha)
    return {k: '\n'.join(v).strip() for k, v in partes.items()}


def abre(url):
    """Código HTTP final, ou a mensagem de erro."""
    ultimo = None
    for tentativa in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': NAVEGADOR, 'Accept-Language': 'pt-BR,pt;q=0.9'})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.status, r.geturl()
        except urllib.error.HTTPError as e:
            ultimo = (e.code, url)
            if e.code < 500 and e.code != 429: return ultimo
        except Exception as e:  # noqa: BLE001 - tempo esgotado, DNS, TLS
            ultimo = (f'{type(e).__name__}: {e}', url)
        time.sleep(5 * (tentativa + 1))
    return ultimo


def main(caminho):
    texto = open(caminho, encoding='utf-8').read()
    s = secoes(texto)
    problemas = []
    for nome, limite in LIMITES.items():
        n = len(s.get(nome, ''))
        print(f'{nome}: {n}/{limite} caracteres')
        if not n or n > limite: problemas.append(f'{nome} com {n} caracteres (limite {limite})')
    if 'NÃO é um aplicativo do governo' not in s.get('DESCRIÇÃO COMPLETA', ''):
        problemas.append('falta o aviso de não afiliação ao governo na descrição completa')
    urls = list(dict.fromkeys(re.findall(r'https?://[^\s)]+', texto)))
    print(f'\n{len(urls)} links:')
    for url in urls:
        codigo, final = abre(url)
        ok = isinstance(codigo, int) and codigo < 400
        print(f'  {"OK " if ok else "ERRO"} {codigo}  {url}' + (f'  -> {final}' if ok and final != url else ''))
        if not ok: problemas.append(f'{url}: {codigo}')
    if problemas:
        print('\nProblemas:'); [print('  -', p) for p in problemas]
        sys.exit(1)
    print('\nTudo certo: limites respeitados, aviso presente e todos os links abrem.')


def testa_links(urls):
    for url in urls:
        codigo, final = abre(url)
        ok = isinstance(codigo, int) and codigo < 400
        print(f'{"OK " if ok else "ERRO"} {codigo}  {url}' + (f'  -> {final}' if ok and final != url else ''), flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--links':
        testa_links(sys.argv[2:]); sys.exit(0)
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, 'textos_da_loja.txt'))
