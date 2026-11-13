# -*- coding: utf-8 -*-
"""
Data de semeadura estimada por satélite, como variável no protocolo da Tabela 6.

A dissertação deixa como trabalho futuro o manejo: data de semeadura e
cultivar. Não há registro público de nenhum dos dois por município. A data,
porém, deixa marca na curva de vegetação: a soja semeada mais cedo começa a
ficar verde mais cedo. Aqui ela é estimada da série de 16 dias do MODIS sobre a
máscara de soja (gee_vegetacao_16d.csv, de 08_previsao_futura/coleta), safra a
safra, em cada município do Pará:

  início do verdor  o primeiro dia em que o NDVI suavizado passa de 20% da
                    subida entre o mínimo antes do pico e o pico (o limiar
                    usual em fenologia por satélite, como no TIMESAT),
                    interpolado entre as duas imagens de 16 dias;
  semeadura         o início do verdor menos 20 dias, o tempo típico da
                    semeadura até a soja cobrir o solo o bastante para o
                    MODIS (250 m) a ver; serve só para ler o calendário, e a
                    conta abaixo não depende desse número;
  dias até o pico   do início do verdor ao NDVI máximo.

Safras sem subida nítida (pico menos de 0,1 de NDVI acima do mínimo) ficam sem
data. A conferência de plausibilidade compara o sul do Pará, que semeia de
outubro a dezembro, com o nordeste, que semeia de dezembro a fevereiro.

Depois, a Tabela 6 refeita com e sem as duas variáveis (início do verdor e dias
até o pico), nos mesmos registros, com o ganho sobre a referência, IC95 por
reamostragem de safras e p corrigido por Holm entre os quatro modelos.

Uso:   python 07_data_semeadura.py            (fenologia e Tabela 6, ~40 min)
       python 07_data_semeadura.py fenologia  (só as datas, segundos)
Saída: data_semeadura.json e dados/fenologia_para.csv
"""
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
PESQUISA = os.path.abspath(os.path.join(AQUI, '..'))
PARA = os.path.join(PESQUISA, '04_analise_para')
SERIE = os.path.join(PESQUISA, '08_previsao_futura', 'dados', 'gee_vegetacao_16d.csv')
MUNICIPIOS = os.path.join(PESQUISA, 'dados', 'municipios_para.csv')
sys.path.insert(0, os.path.join(PESQUISA, '08_previsao_futura'))

ORCAMENTO = {'Random Forest': 9, 'XGBoost': 15, 'SVR': 15, 'MLP': 15}
FENOLOGIA = ['inicio_verdor_dias', 'dias_ate_pico']
LIMIAR = 0.20          # fração da subida que marca o início do verdor
AMPLITUDE_MIN = 1000   # 0,1 de NDVI na escala do MODIS (x10000)
VERDOR_MENOS_SEMEADURA = 20


def fenologia_da_safra(datas: pd.Series, ndvi: pd.Series, inicio: pd.Timestamp) -> dict | None:
    """Início do verdor, pico e semeadura estimada de uma safra (datas em dias desde 1º/set)."""
    s = pd.Series(ndvi.values, index=pd.DatetimeIndex(datas.values)).sort_index()
    if len(s) < 8:
        return None
    suave = s.rolling(3, center=True, min_periods=1).median()
    i_pico = int(np.argmax(suave.values))
    if i_pico < 2:
        return None
    i_min = int(np.argmin(suave.values[: i_pico + 1]))
    base, pico = float(suave.values[i_min]), float(suave.values[i_pico])
    if pico - base < AMPLITUDE_MIN:
        return None
    alvo = base + LIMIAR * (pico - base)
    for i in range(i_min + 1, i_pico + 1):
        if suave.values[i] >= alvo:
            v0, v1 = suave.values[i - 1], suave.values[i]
            t0, t1 = suave.index[i - 1], suave.index[i]
            frac = 0.0 if v1 == v0 else (alvo - v0) / (v1 - v0)
            verdor = t0 + (t1 - t0) * float(frac)
            dia = (verdor - inicio).days
            pico_dia = (suave.index[i_pico] - inicio).days
            return {'inicio_verdor_dias': dia, 'semeadura_dias': dia - VERDOR_MENOS_SEMEADURA,
                    'pico_dias': pico_dia, 'dias_ate_pico': pico_dia - dia,
                    'ndvi_base': base / 1e4, 'ndvi_pico': pico / 1e4}
    return None


def fenologia() -> pd.DataFrame:
    v = pd.read_csv(SERIE, parse_dates=['data'])
    # Safra pelo ano da colheita, como o IBGE: de outubro de Y-1 a junho de Y.
    v['ano'] = np.where(v.data.dt.month >= 8, v.data.dt.year + 1, v.data.dt.year)
    linhas = []
    for (cod, ano), g in v.groupby(['cod_ibge7', 'ano']):
        f = fenologia_da_safra(g.data, g.ndvi, pd.Timestamp(year=int(ano) - 1, month=9, day=1))
        if f:
            linhas.append({'cod_ibge7': int(cod), 'ano': int(ano), **f})
    return pd.DataFrame(linhas)


def holm(ps: dict) -> dict:
    """p corrigido por Holm entre os modelos."""
    ordem = sorted(ps, key=ps.get)
    m, acum, saida = len(ordem), 0.0, {}
    for i, k in enumerate(ordem):
        acum = max(acum, min(1.0, (m - i) * ps[k]))
        saida[k] = acum
    return saida


def dia_e_mes(dias: float) -> str:
    d = pd.Timestamp('2001-09-01') + pd.Timedelta(days=float(dias))
    return d.strftime('%d/%m')


def plausibilidade(fen: pd.DataFrame) -> dict:
    muni = pd.read_csv(MUNICIPIOS)
    f = fen.merge(muni[['cod_ibge7', 'municipio', 'latitude']], on='cod_ibge7')
    sul, nordeste = f[f.latitude < -7], f[f.latitude > -4]
    resumo = {}
    for nome, g in (('sul (latitude abaixo de -7)', sul), ('nordeste (acima de -4)', nordeste), ('todos', f)):
        q = g.semeadura_dias.quantile([0.25, 0.5, 0.75])
        resumo[nome] = {'safras': int(len(g)), 'municipios': int(g.cod_ibge7.nunique()),
                        'semeadura_mediana': dia_e_mes(q[0.5]),
                        'semeadura_quartis': [dia_e_mes(q[0.25]), dia_e_mes(q[0.75])],
                        'dias_ate_pico_mediana': float(g.dias_ate_pico.median())}
    por_municipio = (f.groupby('municipio').semeadura_dias.median().sort_values()
                     .map(dia_e_mes).to_dict())
    return {'por_regiao': resumo, 'semeadura_mediana_por_municipio': por_municipio}


def busca():
    spec = importlib.util.spec_from_file_location('busca', os.path.join(PARA, '03_busca_hiperparametros.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.DADOS = os.path.join(PESQUISA, 'dados')
    return m


def avalia(m, df, ref, y, anos, safras):
    from comum import ganho_sobre_referencia
    preve_original, externas = m.preve, {}

    def preve_e_guarda(nome, cfg, X, y_, anos_, mun_, tr, te):
        p = preve_original(nome, cfg, X, y_, anos_, mun_, tr, te)
        if np.array_equal(tr, ~te):
            externas[int(anos_[te][0])] = p
        return p

    m.preve = preve_e_guarda
    saida = {}
    obs = np.concatenate([y[anos == ty] for ty in safras])
    pref = np.concatenate([ref[ty] for ty in safras])
    aa = np.concatenate([anos[anos == ty] for ty in safras])
    for nome, n in ORCAMENTO.items():
        externas.clear()
        r = m.avalia_modelo(nome, n, df)
        prev = np.concatenate([externas[ty] for ty in safras])
        g = ganho_sobre_referencia(obs, prev, pref, aa)
        saida[nome] = {**{k: r[k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%')},
                       'ganho_sobre_referencia': g['ganho'], 'IC95': g['IC95'], 'p_unilateral': g['p_unilateral']}
        print(f'  {nome}: {saida[nome]}', flush=True)
    m.preve = preve_original
    for k, p in holm({k: v['p_unilateral'] for k, v in saida.items()}).items():
        saida[k]['p_holm'] = p
    return saida


def main():
    fen = fenologia()
    os.makedirs(os.path.join(AQUI, 'dados'), exist_ok=True)
    fen.round(4).to_csv(os.path.join(AQUI, 'dados', 'fenologia_para.csv'), index=False)
    saida = {
        'nota': ('Início do verdor por município-safra na série de NDVI de 16 dias do MODIS sobre a máscara de '
                 f'soja: primeiro dia acima de {int(LIMIAR * 100)}% da subida até o pico (NDVI suavizado pela '
                 f'mediana de 3 imagens). Semeadura estimada = verdor menos {VERDOR_MENOS_SEMEADURA} dias. '
                 'Datas em dias desde 1º de setembro do ano anterior à colheita.'),
        'safras_com_data': int(len(fen)),
        'plausibilidade': plausibilidade(fen),
    }
    print(json.dumps(saida['plausibilidade']['por_regiao'], ensure_ascii=False, indent=1), flush=True)
    if len(sys.argv) > 1 and sys.argv[1] == 'fenologia':
        print(f'{len(fen)} safras com data')
        return

    m = busca()
    df = m.carrega().merge(fen[['cod_ibge7', 'ano'] + FENOLOGIA], on=['cod_ibge7', 'ano'], how='left')
    df = df[df[FENOLOGIA].notna().all(axis=1)].reset_index(drop=True)
    y, anos, mun, _, safras = m._matrizes(df)
    ref = {ty: m.referencia(y, anos, mun, anos != ty, anos == ty) for ty in safras}
    base = list(m.FEATURES)
    print(f'{len(df)} registros com data de verdor. Sem a fenologia:', flush=True)
    sem = avalia(m, df, ref, y, anos, safras)
    m.FEATURES = base + FENOLOGIA
    print('Com a fenologia:', flush=True)
    com = avalia(m, df, ref, y, anos, safras)
    m.FEATURES = base
    saida.update({
        'variaveis': FENOLOGIA,
        'registros': int(len(df)), 'municipios': int(df.municipio.nunique()),
        'sem_fenologia': sem, 'com_fenologia': com,
    })
    with open(os.path.join(AQUI, 'data_semeadura.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
