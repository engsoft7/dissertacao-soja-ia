# -*- coding: utf-8 -*-
"""
Descobre o DOI que o Zenodo atribuiu à versão mais recente do depósito.

O Zenodo deposita a partir do evento de *release* do GitHub — não da criação da
etiqueta — e só então atribui o DOI de versão. Esse número precisa ser copiado
para o REGISTRO_INPI.md, que documenta cada versão do código-fonte para o
registro de programa de computador, e a alternativa a consultá-lo é digitá-lo à
mão a partir da página, que é como se troca um dígito de um identificador
permanente.

Parte do DOI de conceito, que é estável e resolve sempre para a versão mais
recente, e lista as versões que pendem dele em ordem decrescente. Imprime o DOI,
a versão declarada e a data de publicação de cada uma, para que a correspondência
entre etiqueta e DOI possa ser conferida a olho antes de entrar no documento.

Roda no GitHub Actions: o ambiente de desenvolvimento não alcança zenodo.org,
negado por política de rede.

Uso:  python consulta_doi_zenodo.py
"""
import sys

import requests

CONCEITO = '21285918'
API = 'https://zenodo.org/api/records'


def main():
    try:
        r = requests.get(API, timeout=40, headers={'User-Agent': 'dissertacao-soja-ia/1.0'},
                         params={'q': f'conceptrecid:{CONCEITO}',
                                 'all_versions': 'true',
                                 'size': 15,
                                 'sort': 'mostrecent'})
    except requests.RequestException as e:
        print(f'falhou: {e}')
        return 1
    if r.status_code != 200:
        print(f'HTTP {r.status_code}: {r.text[:300]}')
        return 1

    itens = r.json().get('hits', {}).get('hits', [])
    print(f'DOI de conceito: 10.5281/zenodo.{CONCEITO}')
    print(f'versões depositadas: {len(itens)}\n')
    if not itens:
        print('Nenhuma versão retornada. Se a release acabou de ser publicada, o')
        print('depósito pode ainda não ter sido processado — repita em alguns minutos.')
        return 1

    print(f'{"versão":<12} {"publicado":<12} {"DOI":<34} título')
    print('-' * 100)
    for it in itens:
        md = it.get('metadata', {})
        print(f'{str(md.get("version", "?")):<12} '
              f'{str(md.get("publication_date", "?")):<12} '
              f'{str(it.get("doi", "?")):<34} '
              f'{str(md.get("title", "?"))[:44]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
