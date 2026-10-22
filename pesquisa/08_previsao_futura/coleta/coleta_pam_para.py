# -*- coding: utf-8 -*-
"""
PAM (SIDRA, tabela 5457) da soja: municípios do Pará e unidades da federação.

Baixa rendimento, quantidade produzida, valor, área colhida e área plantada de
todos os anos publicados, inclusive os posteriores à base da dissertação. Os
nomes das variáveis são lidos da própria resposta da API, e não presumidos
pelo código, para que o rótulo de cada coluna seja o do IBGE.

Roda no GitHub Actions (o SIDRA não é alcançável de todo ambiente).

Uso:  python coleta_pam_para.py
Saída: ../dados/pam_para_municipios.csv, ../dados/pam_uf.csv, ../dados/pam_coleta.json
"""
import json
import os
import sys
import time
from datetime import date

import pandas as pd
import requests

SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dados')
VARIAVEIS = '112,214,215,216,8331'
URLS = {
    'municipios': ('https://apisidra.ibge.gov.br/values/t/5457/n6/in%20n3%2015'
                   f'/v/{VARIAVEIS}/p/all/c782/40124?formato=json'),
    'uf': f'https://apisidra.ibge.gov.br/values/t/5457/n3/all/v/{VARIAVEIS}/p/all/c782/40124?formato=json',
}
ROTULOS = [('Rendimento', 'rendimento_kg_ha'), ('Quantidade produzida', 'producao_t'),
           ('Valor', 'valor_mil_reais'), ('colhida', 'area_colhida_ha'), ('plantada', 'area_plantada_ha')]


def baixa(url, tentativas=4, espera=30):
    for i in range(1, tentativas + 1):
        try:
            r = requests.get(url, timeout=180)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            print(f'  SIDRA: {type(e).__name__} (tentativa {i}/{tentativas})', flush=True)
            if i == tentativas:
                raise
            time.sleep(espera)


def tabela(dados):
    """Converte a resposta do SIDRA em tabela larga, uma coluna por variável."""
    cab, linhas = dados[0], dados[1:]
    nomes = {cab[k]: k[:-1] for k in cab if k.endswith('N') and k.startswith('D')}
    terr = next(v for k, v in nomes.items() if k in ('Município', 'Unidade da Federação'))
    var, ano = nomes['Variável'], nomes['Ano']
    df = pd.DataFrame(linhas)
    longa = pd.DataFrame({'cod': pd.to_numeric(df[terr + 'C']), 'nome': df[terr + 'N'],
                          'ano': pd.to_numeric(df[ano + 'C']), 'variavel': df[var + 'N'],
                          'unidade': df['MN'], 'valor_bruto': df['V']})
    # "-" é zero absoluto; "..", "..." e "X" são dado inexistente ou sigiloso
    longa['valor'] = pd.to_numeric(longa.valor_bruto.replace('-', '0'), errors='coerce')
    rotulo = {}
    for v in longa.variavel.unique():
        achado = [c for chave, c in ROTULOS if chave.lower() in v.lower()]
        if not achado:
            sys.exit(f'variável sem rótulo: {v}')
        rotulo[v] = achado[0]
    unidades = longa.groupby('variavel').unidade.first().to_dict()
    longa['coluna'] = longa.variavel.map(rotulo)
    larga = longa.pivot_table(index=['cod', 'nome', 'ano'], columns='coluna', values='valor',
                              aggfunc='first').reset_index()
    larga.columns.name = None
    return larga, {rotulo[v]: {'nome_ibge': v, 'unidade': unidades[v]} for v in rotulo}


def main():
    os.makedirs(SAIDA, exist_ok=True)
    meta = {'fonte': 'IBGE, PAM, SIDRA tabela 5457, produto soja (c782/40124)',
            'coletado_em': date.today().isoformat(), 'urls': URLS}
    for chave, url in URLS.items():
        print(f'{chave}: {url}', flush=True)
        larga, variaveis = tabela(baixa(url))
        larga = larga[larga.ano >= 2001]
        cod = 'cod_ibge7' if chave == 'municipios' else 'uf_cod'
        larga = larga.rename(columns={'cod': cod, 'nome': 'municipio' if chave == 'municipios' else 'uf'})
        arq = 'pam_para_municipios.csv' if chave == 'municipios' else 'pam_uf.csv'
        larga.sort_values([cod, 'ano']).to_csv(os.path.join(SAIDA, arq), index=False)
        com_soja = larga[larga.get('producao_t', 0) > 0]
        meta[chave] = {'arquivo': arq, 'variaveis': variaveis, 'anos': [int(larga.ano.min()), int(larga.ano.max())],
                       'registros_com_producao': int(len(com_soja))}
        print(f'  {len(larga)} linhas, anos {larga.ano.min()}-{larga.ano.max()}, '
              f'{len(com_soja)} com produção', flush=True)
        for a in sorted(larga.ano.unique())[-3:]:
            s = larga[larga.ano == a]
            print(f'  {a}: produção {s.producao_t.sum():,.0f} t, área colhida {s.area_colhida_ha.sum():,.0f} ha, '
                  f'plantada {s.area_plantada_ha.sum():,.0f} ha', flush=True)
    with open(os.path.join(SAIDA, 'pam_coleta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
