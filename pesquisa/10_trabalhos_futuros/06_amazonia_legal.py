# -*- coding: utf-8 -*-
"""
O protocolo da Tabela 6 em Tocantins, Maranhão, Rondônia e Mato Grosso.

A base do Pará tem 415 registros, pouco para revelar ganhos pequenos sobre o
modelo de referência, e a dissertação aponta a extensão aos demais estados da
Amazônia Legal. As variáveis vêm de coleta/coleta_amazonia_legal.py (a mesma
conta da base paraense, só muda o estado) e a produtividade da PAM
(03_analise_nacional/pam_soja_municipios.csv), pareadas pelo nome do município
dentro do estado.

Entra o registro (município, safra) com produtividade e área plantada na PAM,
soja na máscara do MapBiomas daquele ano e as onze variáveis completas, o
mesmo critério que deu os 415 registros do Pará. Para cada estado, e para os
cinco juntos (com o Pará da dissertação), roda-se o protocolo da Tabela 6 sem
mudar nada: leave-one-year-out com busca aninhada, mesmos orçamentos e semente,
modelos ajustados ao resíduo sobre a média do município mais a tendência. O
critério é o ganho sobre esse modelo de referência, com IC95 por reamostragem
de safras.

Pergunta: com mais registros, o clima e a vegetação medidos por satélite
passam a explicar a produtividade municipal além da média do município?

Uso:   python 06_amazonia_legal.py [TO MA RO MT]
Saída: amazonia_legal.json
"""
import importlib.util
import json
import os
import re
import sys
import unicodedata

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
PESQUISA = os.path.abspath(os.path.join(AQUI, '..'))
PARA = os.path.join(PESQUISA, '04_analise_para')
sys.path.insert(0, os.path.join(PESQUISA, '08_previsao_futura'))
from comum import ganho_sobre_referencia  # noqa: E402

ORCAMENTO = {'Random Forest': 9, 'XGBoost': 15, 'SVR': 15, 'MLP': 15}


def chave(s):
    s = unicodedata.normalize('NFKD', str(s))
    return re.sub(r'[^a-z]', '', ''.join(c for c in s if not unicodedata.combining(c)).lower())


def busca():
    spec = importlib.util.spec_from_file_location('busca', os.path.join(PARA, '03_busca_hiperparametros.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.DADOS = os.path.join(PESQUISA, 'dados')
    return m


def base_do_estado(uf, m):
    """Registros do estado no formato da base do Pará."""
    g = pd.read_csv(os.path.join(AQUI, 'dados', f'amazonia_legal_{uf}.csv'))
    pam = pd.read_csv(os.path.join(PESQUISA, '03_analise_nacional', 'pam_soja_municipios.csv'))
    pam = pam[(pam.uf == uf) & (pam.area_plantada_ha > 0) & (pam.rendimento_kg_ha > 0)].copy()
    pam['k'] = pam.nome.str.replace(r'\s+-\s+[A-Z]{2}$', '', regex=True).map(chave)
    g['k'] = g.municipio_gaul.map(chave)
    nomes = pam.groupby('k').nome.first()
    df = g.merge(pam[['k', 'ano', 'rendimento_kg_ha', 'cod_ibge7']], on=['k', 'ano'], how='inner')
    df['municipio'] = df.k.map(nomes).fillna(df.municipio_gaul + f' - {uf}')
    df['balanco_hidrico'] = df.precip_total - df.etp_total
    df['log_area'] = np.log1p(df.soy_area_ha)
    df = df[df.soy_area_ha > 0].dropna(subset=m.FEATURES + ['rendimento_kg_ha'])
    pareados = g.k.nunique(), int(g.k.isin(set(pam.k)).groupby(g.k).first().sum())
    return df.sort_values(['municipio', 'ano']).reset_index(drop=True), pareados


def avalia(m, df, rotulo):
    y, anos, mun, _, safras = m._matrizes(df)
    ref = {ty: m.referencia(y, anos, mun, anos != ty, anos == ty) for ty in safras}
    obs = np.concatenate([y[anos == ty] for ty in safras])
    pref = np.concatenate([ref[ty] for ty in safras])
    aa = np.concatenate([anos[anos == ty] for ty in safras])
    preve_original, externas = m.preve, {}

    def preve_e_guarda(nome, cfg, X, y_, anos_, mun_, tr, te):
        p = preve_original(nome, cfg, X, y_, anos_, mun_, tr, te)
        if np.array_equal(tr, ~te):          # avaliação externa: treino = todas as outras safras
            externas[int(anos_[te][0])] = p
        return p

    m.preve = preve_e_guarda
    saida = {'registros': int(len(df)), 'municipios': int(df.municipio.nunique()),
             'safras_avaliadas': [int(a) for a in safras], 'referencia': m.avalia_baseline(df), 'modelos': {}}
    print(f'{rotulo}: {saida["registros"]} registros, {saida["municipios"]} municípios; '
          f'referência {saida["referencia"]}', flush=True)
    for nome, n in ORCAMENTO.items():
        externas.clear()
        r = m.avalia_modelo(nome, n, df)
        prev = np.concatenate([externas[ty] for ty in safras])
        g = ganho_sobre_referencia(obs, prev, pref, aa)
        saida['modelos'][nome] = {**{k: r[k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%', 'segundos')},
                                  'ganho_sobre_referencia': g['ganho'], 'IC95': g['IC95'],
                                  'p_unilateral': g['p_unilateral']}
        print(f'  {nome}: {saida["modelos"][nome]}', flush=True)
    m.preve = preve_original
    return saida


def main(ufs):
    m = busca()
    saida = {'nota': ('Protocolo da Tabela 6 (04_analise_para/03_busca_hiperparametros.py) por estado e com os '
                      'cinco estados juntos. Ganho = 1 - MSE(modelo)/MSE(referência), IC95 por reamostragem de '
                      'safras.'), 'estados': {}}
    bases = {'PA': m.carrega()}
    for uf in ufs:
        df, (n_gaul, n_par) = base_do_estado(uf, m)
        bases[uf] = df
        saida['estados'][uf] = {'municipios_gaul': n_gaul, 'municipios_com_pam': n_par}
        saida['estados'][uf].update(avalia(m, df, uf))
    junto = pd.concat([b.assign(municipio=b.municipio + ('' if uf != 'PA' else ' - PA'))
                       for uf, b in bases.items()], ignore_index=True)
    saida['cinco_estados'] = avalia(m, junto, 'cinco estados')
    with open(os.path.join(AQUI, 'amazonia_legal.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False, default=float)


if __name__ == '__main__':
    main(sys.argv[1:] or ['TO', 'MA', 'RO', 'MT'])
