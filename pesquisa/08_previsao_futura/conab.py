# -*- coding: utf-8 -*-
"""
Leitura das planilhas de safra da CONAB (soja, por UF).

  SojaSerieHist.xls                         série histórica, uma aba por
                                            variável (área, produtividade,
                                            produção), safras 1976/77 em diante
  site_previsao_de_safra-por_produto-*.xlsx levantamento mensal, aba "Soja",
                                            safra anterior e safra corrente

A safra "2024/25" é colhida em 2025 e corresponde ao ano 2025 da PAM.
"""
import os
import re

import pandas as pd

UFS = {'RO', 'AC', 'AM', 'RR', 'PA', 'AP', 'TO', 'MA', 'PI', 'CE', 'RN', 'PB', 'PE', 'AL', 'SE', 'BA',
       'MG', 'ES', 'RJ', 'SP', 'PR', 'SC', 'RS', 'MS', 'MT', 'GO', 'DF'}
MESES = {m: i for i, m in enumerate(['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out',
                                     'nov', 'dez'], 1)}
ABAS = {'Área': 'area_mil_ha', 'Produtividade': 'produtividade_kg_ha', 'Produção': 'producao_mil_t'}


def ano_colheita(safra):
    m = re.search(r'(\d{2}|\d{4})/(\d{2})', str(safra))
    if not m:
        return None
    a = int(m.group(1))
    return (a if a > 1900 else 2000 + a) + 1


def serie_historica(caminho):
    """Uma linha por UF e ano de colheita, com área, produtividade e produção."""
    partes = []
    for aba, col in ABAS.items():
        d = pd.read_excel(caminho, sheet_name=aba, header=None)
        cab = d.index[d[0].astype(str).str.strip() == 'REGIÃO/UF'][0]
        anos = [ano_colheita(s) for s in d.loc[cab]]
        linhas = d.loc[cab + 1:]
        linhas = linhas[linhas[0].astype(str).str.strip().isin(UFS)]
        for _, r in linhas.iterrows():
            for j, a in enumerate(anos):
                if a is not None:
                    partes.append({'uf': str(r[0]).strip(), 'ano': a, 'variavel': col,
                                   'valor': pd.to_numeric(r[j], errors='coerce'),
                                   'previsao': 'Previs' in str(d.loc[cab, j])})
    t = pd.DataFrame(partes)
    larga = t.pivot_table(index=['uf', 'ano'], columns='variavel', values='valor').reset_index()
    prev = t.groupby('ano').previsao.any()
    larga['previsao'] = larga.ano.map(prev)
    larga.columns.name = None
    return larga


def levantamento(caminho):
    """Aba Soja de um levantamento mensal: UF x safra, com a data de divulgação."""
    nome = os.path.basename(caminho)
    m = re.search(r'-(\w{3})-(\d{4})\.xlsx?$', nome)
    divulgado = f'{m.group(2)}-{MESES[m.group(1).lower()]:02d}' if m else None
    d = pd.read_excel(caminho, sheet_name='Soja', header=None)
    cab = d.index[d[0].astype(str).str.strip() == 'REGIÃO/UF'][0]
    safras = d.loc[cab + 1]
    grupos, atual = {}, None
    for j in range(1, d.shape[1]):
        titulo = str(d.loc[cab, j])
        if titulo != 'nan':
            atual = next((c for k, c in ABAS.items() if k.upper() in titulo.upper()), None)
        if atual and ano_colheita(safras[j]):
            grupos[j] = (atual, ano_colheita(safras[j]))
    linhas = []
    for _, r in d.loc[cab + 2:].iterrows():
        uf = str(r[0]).strip()
        if uf not in UFS:
            continue
        reg = {}
        for j, (col, ano) in grupos.items():
            reg.setdefault(ano, {})[col] = pd.to_numeric(r[j], errors='coerce')
        linhas += [{'divulgado': divulgado, 'uf': uf, 'ano': a, **v} for a, v in reg.items()]
    return pd.DataFrame(linhas)
