# -*- coding: utf-8 -*-
"""
Confere as referências do artigo contra o registro oficial na Crossref.

O ambiente de desenvolvimento não alcança api.crossref.org, então a conferência
roda no GitHub Actions, que tem rede. Cada referência é procurada pelo título e
o script imprime o que a editora depositou: autores, ano, periódico, volume,
número de artigo e DOI. A comparação com o manuscrito é feita à vista, porque é
nela que estão os erros que importam — um coautor a mais ou a menos não é
detectável por similaridade de string sem produzir falso negativo.

O que motivou o script: seis referências do manuscrito tiveram a lista de
autores escrita por extenso a partir de "et al.", e listas de autores são
justamente o campo que nenhuma outra fonte do repositório verifica.

Uso:  python confere_referencias.py            # todas
      python confere_referencias.py --faltantes # só as que faltam conferir
"""
import os
import sys
import time

import requests

API = 'https://api.crossref.org/works'
MAILTO = os.environ.get('CROSSREF_MAILTO', '')   # polite pool; opcional

# (rótulo, título para busca, o que o manuscrito afirma)
REFERENCIAS = [
    ('Funk 2015',
     'The climate hazards infrared precipitation with stations: a new environmental '
     'record for monitoring extremes',
     'Sci. Data 2, 150066'),
    ('Munoz-Sabater 2021',
     'ERA5-Land: a state-of-the-art global reanalysis dataset for land applications',
     'Earth Syst. Sci. Data 13, 4349-4383'),
    ('Souza 2020',
     'Reconstructing three decades of land use and land cover changes in Brazilian '
     'biomes with Landsat archive and Earth Engine',
     'Remote Sens. 12, 2735', '10.3390/rs12172735'),
    ('Maimaitijiang 2020',
     'Soybean yield prediction from UAV using multimodal data fusion and deep learning',
     'Remote Sens. Environ. 237, 111599'),
    ('Schwalbert 2020',
     'Satellite-based soybean yield forecast: integrating machine learning and weather '
     'data for improving crop yield prediction in southern Brazil',
     'Agric. For. Meteorol. 284, 107886'),
    ('Fathi 2025',
     'MHRA-MS-3D-ResNet-BiLSTM: a multi-head-residual attention-based multi-stream deep '
     'learning model for soybean yield prediction',
     'Remote Sens. 17, 107 (ano em dúvida: triagem diz 2024)'),
    ('Ingole 2025',
     'A hybrid model for soybean yield prediction integrating convolutional neural '
     'networks, recurrent neural networks, and graph convolutional networks',
     'Computation 13, 4 (ano em dúvida: triagem diz 2024)'),
]

# Já conferidas contra a dissertação ou contra a triagem da revisão sistemática.
JA_CONFERIDAS = [
    ('van Klompenburg 2020',
     'Crop yield prediction using machine learning: a systematic literature review',
     'Comput. Electron. Agric. 177, 105709', '10.1016/j.compag.2020.105709'),
    ('Leukel 2023',
     'Machine learning technology for early prediction of grain yield at the field '
     'scale: a systematic review', 'Comput. Electron. Agric. 207, 107721'),
    ('Khaki 2019', 'Crop yield prediction using deep neural networks',
     'Front. Plant Sci. 10, 621'),
    ('Khaki 2020', 'A CNN-RNN framework for crop yield prediction',
     'Front. Plant Sci. 10, 1750'),
    ('You 2017', 'Deep Gaussian process for crop yield prediction based on remote '
     'sensing data', 'AAAI 31, 4559-4566'),
    ('Sun 2019', 'County-level soybean yield prediction using deep CNN-LSTM model',
     'Sensors 19, 4363'),
    ('Richetti 2018', 'Using phenology-based enhanced vegetation index and machine '
     'learning for soybean yield estimation in Parana State Brazil',
     'J. Appl. Remote Sens. 12, 026029'),
    ('Barbosa dos Santos 2021', 'Estimation and forecasting of soybean yield using '
     'artificial neural networks', 'Agron. J. 113, 3193-3209'),
    ('von Bloh 2023', 'Machine learning for soybean yield forecasting in Brazil',
     'Agric. For. Meteorol. 341, 109670'),
    ('Li 2024', 'Global de-trending significantly improves the accuracy of '
     'XGBoost-based county-level maize and soybean yield prediction',
     'GIsci. Remote Sens. 61, 2349341'),
    ('Wang 2024', 'Satellite-based soybean yield prediction in Argentina: a comparison '
     'between panel regression and deep learning methods',
     'Comput. Electron. Agric. 221, 108978'),
    ('Fu 2025', 'Prediction of soybean yield at the county scale based on multi-source '
     'remote sensing data and deep learning models', 'Agriculture 15, 1337'),
    ('Breiman 2001', 'Random forests', 'Mach. Learn. 45, 5-32',
     '10.1023/A:1010933404324'),
    ('Chen 2016', 'XGBoost: a scalable tree boosting system', 'ACM SIGKDD, 785-794'),
]


def busca(titulo, doi=None, tentativas=3):
    """Registro da Crossref: por DOI quando há um, senão pelo título.

    Títulos genéricos — "Random forests", ou o do Souza et al. (2020), que
    descreve um tema comum a muitos trabalhos — devolvem casamento falso na
    busca bibliográfica. Nesses casos o DOI é declarado em REFERENCIAS e a
    consulta passa a ser exata.
    """
    if doi:
        for n in range(tentativas):
            try:
                r = requests.get(f'{API}/{doi}', timeout=60)
                r.raise_for_status()
                return r.json()['message']
            except Exception as erro:
                if n == tentativas - 1:
                    print(f'    ERRO no DOI {doi}: {erro}')
                    return None
                time.sleep(2 ** n)
    p = {'query.bibliographic': titulo, 'rows': 1}
    if MAILTO:
        p['mailto'] = MAILTO
    for n in range(tentativas):
        try:
            r = requests.get(API, params=p, timeout=60)
            r.raise_for_status()
            itens = r.json()['message']['items']
            return itens[0] if itens else None
        except Exception as erro:
            if n == tentativas - 1:
                print(f'    ERRO: {erro}')
                return None
            time.sleep(2 ** n)
    return None


def autores(m):
    saida = []
    for a in m.get('author', []):
        fam = a.get('family', '').strip()
        dado = a.get('given', '').strip()
        iniciais = ''.join(f'{p[0]}.' for p in dado.replace('-', ' ').split() if p)
        saida.append(f'{fam}, {iniciais}' if fam else a.get('name', '?'))
    return saida


def ano(m):
    for campo in ('published-print', 'published-online', 'issued', 'created'):
        d = m.get(campo, {}).get('date-parts', [[None]])[0][0]
        if d:
            return d, campo
    return None, '—'


def relata(rotulo, titulo, afirmado, doi=None):
    print(f'\n{"─" * 76}\n{rotulo}   |   manuscrito afirma: {afirmado}')
    if doi:
        print(f'    (consulta por DOI: {doi})')
    m = busca(titulo, doi)
    if not m:
        print('    NÃO ENCONTRADO na Crossref')
        return False
    a, campo = ano(m)
    print(f'    título   : {(m.get("title") or ["?"])[0][:100]}')
    print(f'    periódico: {(m.get("container-title") or ["?"])[0]}')
    vol = m.get('volume', '—')
    art = m.get('article-number') or m.get('page', '—')
    print(f'    volume {vol} | artigo/páginas {art} | ano {a} (de {campo})')
    for c in ('published-print', 'published-online'):
        d = m.get(c, {}).get('date-parts', [[None]])[0]
        if d and d[0]:
            print(f'      {c}: {"-".join(str(x) for x in d)}')
    print(f'    DOI      : {m.get("DOI","—")}')
    aut = autores(m)
    print(f'    autores ({len(aut)}): ' + '; '.join(aut))
    return True


def main():
    so_faltantes = '--faltantes' in sys.argv
    lista = REFERENCIAS if so_faltantes else REFERENCIAS + JA_CONFERIDAS
    print(f'Conferindo {len(lista)} referências na Crossref'
          f'{" (só as faltantes)" if so_faltantes else ""}')
    achadas = 0
    for entrada in lista:
        achadas += relata(*entrada)
        time.sleep(1)
    print(f'\n{"─" * 76}\n{achadas} de {len(lista)} encontradas na Crossref.')
    print('Compare as listas de autores acima com as do manuscrito.')
    return 0 if achadas == len(lista) else 1


if __name__ == '__main__':
    sys.exit(main())
