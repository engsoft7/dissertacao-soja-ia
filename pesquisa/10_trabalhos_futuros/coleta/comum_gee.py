# -*- coding: utf-8 -*-
"""Peças comuns às coletas no Earth Engine desta pasta.

A autenticação, a coleção do MapBiomas e o pareamento de nomes são os da
rotina do produto (software/automacao_github/coleta_gee_safra.py), importados
de lá para que as coletas novas meçam do mesmo jeito que a base da dissertação.
"""
import os
import sys
import time
import unicodedata
import re

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, '..', '..', '..'))
DADOS = os.path.join(AQUI, '..', 'dados')
sys.path.insert(0, os.path.join(REPO, 'software', 'automacao_github'))
from coleta_gee_safra import COLL_ID, CLASSE_SOJA, conecta_gee  # noqa: E402,F401

# Nome do estado no GAUL 2015 (ADM1_NAME, sem acento ou com, conforme o GAUL) -> sigla
UFS = {'para': 'PA', 'tocantins': 'TO', 'maranhao': 'MA', 'rondonia': 'RO', 'mato grosso': 'MT',
       'goias': 'GO', 'minas gerais': 'MG', 'parana': 'PR', 'rio grande do sul': 'RS',
       'mato grosso do sul': 'MS', 'bahia': 'BA'}


def chave(s):
    """Nome sem acento, minúsculo e só com letras e espaços (pareia GAUL, IBGE e von Bloh)."""
    s = unicodedata.normalize('NFKD', str(s).replace('_', ' '))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r'[^a-z\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def reduz_em_lotes(ee, img, munis, reducer, scale, tamanho=12, tileScale=16):
    """reduceRegions em lotes de municípios, cada lote com novas tentativas.

    De uma vez só, municípios grandes (Altamira, Balsas, os do norte de Mato
    Grosso) estouravam o tempo de computação do Earth Engine e derrubavam a
    coleta inteira do estado.
    """
    nomes = munis.aggregate_array('ADM2_NAME').getInfo()

    def reduz(lista, escala):
        lote = munis.filter(ee.Filter.inList('ADM2_NAME', lista))
        return img.reduceRegions(collection=lote, reducer=reducer, scale=escala,
                                 tileScale=tileScale).getInfo()['features']

    feicoes = []
    for i in range(0, len(nomes), tamanho):
        lista = nomes[i:i + tamanho]
        try:
            feicoes += tenta(reduz, lista, scale)
            continue
        except Exception as e:  # lote pesado demais: um município por vez
            print(f'  lote {lista[0]}..{lista[-1]} falhou ({type(e).__name__}); um município por vez', flush=True)
        for nome in lista:
            # Município sozinho que ainda estoura o tempo vai a uma escala mais grossa:
            # a média sob a máscara muda pouco, e perder o município seria pior.
            for escala in (scale, scale * 2, scale * 4):
                try:
                    feicoes += tenta(reduz, [nome], escala, tentativas=2)
                    if escala != scale:
                        print(f'  {nome}: reduzido a {escala} m', flush=True)
                    break
                except Exception as e:
                    print(f'  {nome}: falhou a {escala} m ({type(e).__name__})', flush=True)
            else:
                print(f'  {nome}: fica sem valor nesta redução', flush=True)
    return feicoes


def tenta(f, *a, tentativas=4, **k):
    for i in range(tentativas):
        try:
            return f(*a, **k)
        except Exception as e:  # o Earth Engine devolve erros transitórios variados
            if i == tentativas - 1:
                raise
            print(f'  {getattr(f, "__name__", "chamada")}: {type(e).__name__}: {str(e)[:150]}; nova tentativa',
                  flush=True)
            time.sleep(20 * (i + 1))


def municipios_gaul(ee, siglas):
    """FeatureCollection dos municípios do GAUL nos estados pedidos, com a sigla em 'UF'."""
    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
    nomes = gaul.aggregate_array('ADM1_NAME').distinct().getInfo()
    escolhidos = {n: UFS[chave(n)] for n in nomes if chave(n) in UFS and UFS[chave(n)] in siglas}
    faltam = set(siglas) - set(escolhidos.values())
    assert not faltam, f'estados não achados no GAUL: {faltam}'
    fc = gaul.filter(ee.Filter.inList('ADM1_NAME', list(escolhidos)))
    return fc.map(lambda f: f.set('UF', ee.Dictionary(escolhidos).get(f.get('ADM1_NAME')))), escolhidos


def mascara_soja(ee, ano):
    """Máscara de soja do MapBiomas no ano, ou na mais recente publicada antes dele."""
    mb = (ee.ImageCollection('projects/mapbiomas-public/assets/brazil/lulc/v1')
          .filter(ee.Filter.eq('collection_id', COLL_ID)))
    anos = sorted(mb.aggregate_array('year').distinct().getInfo())
    am = max(a for a in anos if a <= ano) if any(a <= ano for a in anos) else min(anos)
    return mb.filter(ee.Filter.eq('year', am)).mosaic().select('classification').eq(CLASSE_SOJA), am
