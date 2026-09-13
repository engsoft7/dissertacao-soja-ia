# -*- coding: utf-8 -*-
"""
A repetição do rendimento é coerente com a área declarada na mesma pesquisa?

O diagnóstico afirma que safras consecutivas com rendimento idêntico indicam
valor não medido. Falta a essa afirmação uma referência independente: alguém
pode responder que a lavoura simplesmente rendeu o mesmo nos dois anos.

A própria PAM oferece a referência. Ela publica a área plantada (variável 216)
ao lado do rendimento (112), levantadas na mesma consulta municipal mas
registradas em campos distintos. Isso permite uma checagem de coerência interna
que não depende de nenhuma fonte externa:

  - se o informante repetiu o registro inteiro, a área também repete;
  - se a área mudou muito e o rendimento ficou idêntico **ao quilograma**, a
    produção teria de ter variado na exata proporção da área, o que é um
    acidente improvável de se repetir milhares de vezes.

O segundo caso é o que interessa. Um município cuja área de soja cresceu
metade e que declara o mesmo rendimento, dígito por dígito, não está
descrevendo uma medição.

Esta é a validação que a base do Pará não consegue dar: lá são 377 pares e o
sinal de satélite, uma vez controlada a área, não distingue os grupos
(06_repeticao_e_sinal_espectral.py registra esse resultado nulo). Aqui são
46.536 pares e a referência é a própria pesquisa.

Uso:  python 09_coerencia_interna.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

RAIZ = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(RAIZ, 'pam_soja_municipios.csv')
SAIDA = os.path.join(RAIZ, 'coerencia_interna.json')

LIMIARES = (10, 25, 50)


def formata_p(valor):
    """Guardar 0.0 num campo de valor-p mente: o valor é pequeno, não nulo.

    Com qui-quadrado na casa dos milhares o valor-p cai abaixo do menor float
    representável e o Python devolve 0.0. Registrar isso como zero sugeriria
    impossibilidade em vez de improbabilidade extrema.
    """
    return float(f'{valor:.3g}') if valor > 0 else '<1e-300'


def tabela_de_pares(df):
    """Um registro por par de safras consecutivas, com rendimento e área.

    Consecutivo é adjacente na série do município, a mesma definição de
    07_repeticao_27_estados.py — as duas contagens precisam coincidir.
    """
    d = df.sort_values(['cod_ibge7', 'ano']).copy()
    g = d.groupby('cod_ibge7')
    d['rend_ant'] = g.rendimento_kg_ha.shift()
    d['area_ant'] = g.area_plantada_ha.shift()
    p = d[d.rend_ant.notna()].copy()
    p['rend_repetiu'] = p.rendimento_kg_ha == p.rend_ant
    p['area_repetiu'] = p.area_plantada_ha == p.area_ant
    p['var_area'] = ((p.area_plantada_ha - p.area_ant).abs()
                     / p.area_ant.replace(0, np.nan) * 100)
    return p


def analisa(p):
    rep, nao = p[p.rend_repetiu], p[~p.rend_repetiu]

    # 1. o registro inteiro foi carregado?
    tabela = np.array([[int(rep.area_repetiu.sum()), int((~rep.area_repetiu).sum())],
                       [int(nao.area_repetiu.sum()), int((~nao.area_repetiu).sum())]])
    qui, p_qui = stats.chi2_contingency(tabela)[:2]

    # 2. entre os que repetiram o rendimento mas mudaram a área, quanto mudou?
    m = rep[~rep.area_repetiu]
    u, p_u = stats.mannwhitneyu(m.var_area.dropna(), nao.var_area.dropna(),
                                alternative='two-sided')

    r = {
        'pares': int(len(p)),
        'rendimento_repetiu': int(rep.shape[0]),
        'taxa_repeticao': round(float(p.rend_repetiu.mean() * 100), 1),
        'area_tambem_repetiu': {
            'quando_rendimento_repetiu_%': round(float(rep.area_repetiu.mean() * 100), 1),
            'quando_rendimento_mudou_%': round(float(nao.area_repetiu.mean() * 100), 1),
            'razao': round(float(rep.area_repetiu.mean() / nao.area_repetiu.mean()), 2),
            'qui_quadrado': round(float(qui), 1),
            'p': formata_p(p_qui),
        },
        'rendimento_repetiu_area_mudou': {
            'pares': int(len(m)),
            'fracao_dos_repetidos_%': round(float(len(m) / len(rep) * 100), 1),
            'variacao_mediana_da_area_%': round(float(m.var_area.median()), 1),
            'variacao_mediana_quando_rendimento_mudou_%': round(
                float(nao.var_area.median()), 1),
            'p_mannwhitney': formata_p(p_u),
        },
    }
    for lim in LIMIARES:
        r['rendimento_repetiu_area_mudou'][f'area_variou_mais_de_{lim}%'] = {
            'pares': int((m.var_area > lim).sum()),
            'fracao_%': round(float((m.var_area > lim).mean() * 100), 1),
        }
    return r


def imprime(r):
    a, b = r['area_tambem_repetiu'], r['rendimento_repetiu_area_mudou']
    print(f'{r["pares"]:,} pares de safras consecutivas; '
          f'{r["rendimento_repetiu"]:,} com rendimento idêntico ({r["taxa_repeticao"]}%)')
    print(f'\n{"─" * 70}\nO registro inteiro foi carregado?')
    print(f'  área também idêntica, quando o rendimento repetiu : '
          f'{a["quando_rendimento_repetiu_%"]:.1f}%')
    print(f'  área também idêntica, quando o rendimento mudou   : '
          f'{a["quando_rendimento_mudou_%"]:.1f}%')
    print(f'  razão {a["razao"]}×   qui-quadrado {a["qui_quadrado"]}   p {a["p"]}')

    print(f'\n{"─" * 70}\nE quando o rendimento repetiu mas a área mudou?')
    print(f'  {b["pares"]:,} pares, {b["fracao_dos_repetidos_%"]}% dos repetidos')
    print(f'  variação mediana da área                  : '
          f'{b["variacao_mediana_da_area_%"]:.1f}%')
    print(f'  a mesma mediana quando o rendimento mudou : '
          f'{b["variacao_mediana_quando_rendimento_mudou_%"]:.1f}%')
    print(f'  Mann-Whitney p {b["p_mannwhitney"]}')
    for lim in LIMIARES:
        v = b[f'area_variou_mais_de_{lim}%']
        print(f'    área variou mais de {lim:2d}%: {v["fracao_%"]:5.1f}%  '
              f'({v["pares"]:,} pares)')
    print('─' * 70)
    print('A área plantada move-se quase três vezes mais justamente quando o')
    print('rendimento fica idêntico ao quilograma. Rendimento é produção dividida')
    print('por área: para que os dois fatos coexistam por acidente, a produção')
    print('teria de acompanhar a área na proporção exata, milhares de vezes.')


def main():
    df = pd.read_csv(CSV)
    p = tabela_de_pares(df)
    r = analisa(p)
    imprime(r)
    r['fonte'] = 'IBGE/SIDRA, tabela 5457, variáveis 112 e 216, soja em grão'
    with open(SAIDA, 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    print(f'\ngravado em {os.path.basename(SAIDA)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
