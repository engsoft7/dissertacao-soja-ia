# -*- coding: utf-8 -*-
"""
Confere a projeção registrada para 2025 contra a PAM 2025.

Item 1 de TRABALHOS_FUTUROS.md. A projeção de 03_previsao_producao_para.py foi
feita em 22/10/2026, com a PAM até 2024, e gravada em previsao_producao_para.json
antes de a PAM 2025 ser baixada. Este script não refaz aquela projeção: lê o
registro, recalcula os componentes (área e produtividade) com as mesmas funções
e a mesma série até 2024, confere que reproduzem o valor registrado e só então
compara com a safra 2025 publicada, calculada do mesmo jeito (soma, por
município, de rendimento x a área da série usada no 03).

Também registra, para conferência futura, a projeção feita com origem em 2025,
e faz o primeiro teste fora da amostra na escala municipal: modelos treinados
com 2001-2024 (a base da dissertação) prevendo a safra 2025 da base do painel,
cujas variáveis ambientais a rotina de atualização coletou depois.

Requer ../dados/pam_para_municipios.csv (coleta/coleta_pam_para.py, no Actions).

Uso:  python 06_confere_projecao_2025.py
Saída: confere_projecao_2025.json
"""
import importlib.util
import json
import os
from datetime import date

import numpy as np
import pandas as pd

from comum import RAIZ

PAM = os.path.join(RAIZ, 'dados', 'pam_para_municipios.csv')
COLETA = os.path.join(RAIZ, 'dados', 'pam_coleta.json')


def modulo():
    spec = importlib.util.spec_from_file_location('p03', os.path.join(RAIZ, '03_previsao_producao_para.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def area_da_serie_antiga(pam, antiga, coleta):
    """Qual área da PAM nova é a 'area_plantada_ha' da série usada no 03.

    O 03 lê pam_soja_municipios.csv, que guarda a variável 216 do SIDRA com o
    nome area_plantada_ha. Em vez de presumir o que é a 216, escolhe-se a
    coluna da coleta cujos totais de 2001-2024 batem com a série antiga, e o
    nome que o IBGE dá a ela vem da própria resposta da API.
    """
    difs = {}
    for col in ('area_colhida_ha', 'area_plantada_ha'):
        tot = pam[pam.ano <= 2024].groupby('ano')[col].sum()
        difs[col] = float((tot / antiga.area - 1).abs().max())
    col = min(difs, key=difs.get)
    return col, coleta['municipios']['variaveis'][col]['nome_ibge'], difs


def serie(pam, col_area):
    p = pam.dropna(subset=['rendimento_kg_ha', col_area])
    p = p[(p[col_area] > 0) & (p.rendimento_kg_ha > 0)]
    p = p.assign(prod_t=p.rendimento_kg_ha * p[col_area] / 1000)
    s = p.groupby('ano').agg(area=(col_area, 'sum'), producao=('prod_t', 'sum'),
                             producao_ibge=('producao_t', 'sum'), municipios=('cod_ibge7', 'nunique'))
    s['rendimento'] = s.producao / s.area * 1000
    return s


def municipal_2025():
    """Referência, SVR e MLP (configurações de 02) treinados em 2001-2024, testados em 2025."""
    from comum import AMBIENTAIS, DADOS, carrega_base_para, metricas, referencia
    painel = pd.read_csv(os.path.join(DADOS, 'soja_para_painel.csv'))
    alvo = painel[painel.ano == 2025].copy()
    if alvo.empty:
        return {'situacao': 'a base do painel ainda não tem 2025'}
    alvo['balanco_hidrico'] = alvo.precip_total - alvo.etp_total
    alvo['log_area'] = np.log1p(alvo.soy_area_ha)
    alvo = alvo.dropna(subset=AMBIENTAIS + ['rendimento_kg_ha'])
    treino = carrega_base_para()
    spec = importlib.util.spec_from_file_location('p02', os.path.join(RAIZ, '02_previsao_rendimento_para.py'))
    p02 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p02)
    r_te, r_tr = referencia(treino, alvo), referencia(treino, treino)
    obs = alvo.rendimento_kg_ha.values
    out = {'municipios': int(len(alvo)), 'Referência': metricas(obs, r_te)}
    rng = np.random.default_rng(42)
    for nome in ('SVR', 'MLP'):
        mdl = p02.AMBIENTAL[nome]().fit(treino[AMBIENTAIS].values, treino.rendimento_kg_ha.values - r_tr)
        prev = r_te + mdl.predict(alvo[AMBIENTAIS].values)
        em, er = (obs - prev) ** 2, (obs - r_te) ** 2
        boot = [1 - em[i].sum() / er[i].sum() for i in (rng.integers(0, len(obs), len(obs)) for _ in range(2000))]
        out[nome] = {**metricas(obs, prev), 'ganho_sobre_referencia': round(float(1 - em.sum() / er.sum()), 3),
                     'IC95_municipios': [round(float(x), 3) for x in np.percentile(boot, [2.5, 97.5])]}
    out['ressalva'] = 'uma safra só: o intervalo reamostra municípios, não safras'
    return out


def main():
    m = modulo()
    with open(os.path.join(RAIZ, 'previsao_producao_para.json'), encoding='utf-8') as f:
        registro = json.load(f)
    with open(COLETA, encoding='utf-8') as f:
        coleta = json.load(f)
    nome = registro['melhor_no_retroteste']
    reg25 = registro['projecao'][nome]['2025']

    # 1. o registro se reproduz com a série antiga
    antiga = m.serie_estadual()
    na, nr = nome.split(' x ')
    area25 = m.AREA[na](antiga.area, 1)
    rend25 = m.REND[nr](antiga.rendimento, 1)
    assert round(area25 * rend25 / 1000) == reg25['central_t'], 'o registro não se reproduz'

    # 2. a série nova, até 2024, é a mesma? (o IBGE revisa safras passadas)
    pam = pd.read_csv(PAM)
    col, nome_ibge, difs = area_da_serie_antiga(pam, antiga, coleta)
    nova = serie(pam, col)
    comum = antiga.index.intersection(nova.index)
    revisao = (nova.loc[comum, 'producao'] / antiga.loc[comum, 'producao'] - 1) * 100
    if 2025 not in nova.index:
        raise SystemExit('a PAM coletada ainda não traz 2025')
    o = nova.loc[2025]

    lo, hi = reg25['faixa80_t']
    saida = {
        'registro': {'modelo': nome, 'feito_em': '2026-10-22', 'central_t': reg25['central_t'], 'faixa80_t': [lo, hi],
                     'area_ha': round(area25), 'rendimento_kg_ha': round(rend25)},
        'area_usada': {'coluna': col, 'variavel_ibge': nome_ibge,
                       'maior_diferenca_relativa_2001_2024': {k: round(v, 4) for k, v in difs.items()}},
        'revisao_2001_2024_%': {'max_abs': round(float(revisao.abs().max()), 2),
                                'anos_com_revisao': [int(a) for a in revisao.index[revisao.abs() > 0.01]]},
        'observado_2025': {'producao_t': round(o.producao), 'producao_ibge_t': round(o.producao_ibge),
                           'area_ha': round(o.area), 'rendimento_kg_ha': round(o.rendimento),
                           'municipios': int(o.municipios)},
    }
    erro = reg25['central_t'] / o.producao - 1
    saida['resultado'] = {
        'dentro_da_faixa_80': bool(lo <= o.producao <= hi),
        'erro_producao_%': round(erro * 100, 1),
        'erro_area_%': round((area25 / o.area - 1) * 100, 1),
        'erro_rendimento_%': round((rend25 / o.rendimento - 1) * 100, 1),
        # posição no retroteste: que fração dos erros a 1 safra foi maior que este
        'erros_maiores_no_retroteste_%': None,
    }
    d = m.retroteste(antiga)
    e1 = d[(d.tipo == 'produção') & (d.modelo == nome) & (d.h == 1)].erro_rel.abs()
    saida['resultado']['erros_maiores_no_retroteste_%'] = round(float((e1 > abs(erro)).mean() * 100), 1)

    # 3. novo registro, com origem em 2025 e a série nova
    s = nova[['area', 'producao', 'rendimento']]
    m.ORIGENS = range(2010, 2025)
    d2 = m.retroteste(s)
    proj = {}
    for h in (1, 2, 3):
        c = m.AREA[na](s.area, h) * m.REND[nr](s.rendimento, h) / 1000
        e = d2[(d2.tipo == 'produção') & (d2.modelo == nome) & (d2.h == h)].erro_rel
        a, b = np.percentile(e, [10, 90])
        proj[str(2025 + h)] = {'central_t': round(c), 'faixa80_t': [round(c / (1 + b)), round(c / (1 + a))]}
    saida['novo_registro_origem_2025'] = {'modelo': nome, 'feito_em': date.today().isoformat(), 'projecao': proj}
    saida['municipal_2025'] = municipal_2025()

    with open(os.path.join(RAIZ, 'confere_projecao_2025.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    print(json.dumps(saida, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
