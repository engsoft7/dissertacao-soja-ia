# -*- coding: utf-8 -*-
"""
Variáveis por fase da soja, a partir das séries coletadas no Earth Engine.

As fases não são datas fixas no calendário. No Pará, o sul planta em outubro e
novembro e o nordeste (Paragominas) em janeiro, de modo que uma janela fixa
mediria fases diferentes em municípios diferentes. A âncora é o pico de EVI
sob a máscara de soja, município a município e safra a safra, que na soja
cai entre a formação e o enchimento das vagens (R3-R5). As janelas, fixadas
antes de olhar o alvo:

  floração e formação de vagens (R1-R4)   pico - 20 dias até pico + 10
  enchimento de grãos (R5-R6)             pico + 11 até pico + 45

Em cada fase: chuva, maior veranico (dias seguidos com menos de 1 mm), calor
acumulado acima de 30 °C na máxima, déficit de pressão de vapor na hora mais
quente, umidade do solo em duas camadas e temperatura da superfície (MODIS).
O Atlântico entra como médias de dezembro a março do ano de colheita.
"""
import os

import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(RAIZ, 'dados')
FASES = {'flor': (-20, 10), 'ench': (11, 45)}

FAMILIAS = {
    'Estresse na floração e no enchimento': [f'{v}_{f}' for f in FASES for v in ('chuva', 'veranico', 'calor30', 'vpd')],
    'Umidade do solo por fase': [f'{v}_{f}' for f in FASES for v in ('sw1', 'sw2')],
    'Temperatura da superfície (MODIS)': [f'lst_{f}' for f in FASES],
    'Fenologia (pico de EVI)': ['dias_ate_pico', 'evi_pico'],
    'Atlântico tropical': ['grad_atl', 'tna', 'tsa'],
}


def _es(t):
    """Pressão de saturação do vapor (kPa), Tetens, t em °C."""
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def _maior_sequencia(seco):
    m = c = 0
    for s in seco:
        c = c + 1 if s else 0
        m = max(m, c)
    return m


def safra_de(datas):
    """Safra (ano de colheita) de cada data: outubro a dezembro contam para o ano seguinte."""
    return datas.dt.year + (datas.dt.month >= 10).astype(int)


def pico_evi():
    v = pd.read_csv(os.path.join(DADOS, 'gee_vegetacao_16d.csv'), parse_dates=['data'])
    v['safra'] = safra_de(v.data)
    v = v[(v.data.dt.month >= 11) | (v.data.dt.month <= 5)].dropna(subset=['evi'])
    out = []
    for (cod, s), g in v.sort_values('data').groupby(['cod_ibge7', 'safra']):
        if len(g) < 6:
            continue
        evi = g.evi.rolling(3, center=True, min_periods=1).mean().values / 1e4
        i = int(np.argmax(evi))
        pico = g.data.iloc[i] + pd.Timedelta(days=8)        # meio do composto de 16 dias
        out.append({'cod_ibge7': cod, 'safra': s, 'pico': pico, 'evi_pico': evi[i],
                    'dias_ate_pico': (pico - pd.Timestamp(s - 1, 10, 1)).days})
    return pd.DataFrame(out)


def variaveis_por_fase():
    """Uma linha por município (cod_ibge7) e safra."""
    pico = pico_evi()
    c = pd.read_csv(os.path.join(DADOS, 'gee_clima_diario.csv.gz'), parse_dates=['data'])
    c['tmax'] = c.tmax_k - 273.15
    c['tdew'] = c.tdew_k - 273.15
    c['vpd'] = (_es(c.tmax) - _es(c.tdew)).clip(lower=0)
    c['calor30'] = (c.tmax - 30).clip(lower=0)
    lst = pd.read_csv(os.path.join(DADOS, 'gee_lst_8d.csv'), parse_dates=['data'])
    lst['lst'] = lst.lst_dia * 0.02 - 273.15
    cg, lg = dict(tuple(c.groupby('cod_ibge7'))), dict(tuple(lst.groupby('cod_ibge7')))
    linhas = []
    for r in pico.itertuples():
        reg = {'cod_ibge7': r.cod_ibge7, 'ano': r.safra, 'evi_pico': r.evi_pico, 'dias_ate_pico': r.dias_ate_pico}
        cm, lm = cg.get(r.cod_ibge7), lg.get(r.cod_ibge7)
        for f, (a, b) in FASES.items():
            ini, fim = r.pico + pd.Timedelta(days=a), r.pico + pd.Timedelta(days=b)
            d = cm[(cm.data >= ini) & (cm.data <= fim)] if cm is not None else cm
            if d is None or len(d) < (b - a) * 0.9:
                continue
            reg.update({f'chuva_{f}': d.precip_mm.sum(), f'veranico_{f}': _maior_sequencia(d.precip_mm < 1),
                        f'calor30_{f}': d.calor30.sum(), f'vpd_{f}': d.vpd.mean(),
                        f'sw1_{f}': d.sw1.mean(), f'sw2_{f}': d.sw2.mean()})
            if lm is not None:
                # composto de 8 dias: entra se o meio dele cai na fase
                meio = lm.data + pd.Timedelta(days=4)
                reg[f'lst_{f}'] = lm[(meio >= ini) & (meio <= fim)].lst.mean()
        linhas.append(reg)
    return pd.DataFrame(linhas)


def atlantico():
    """TNA, TSA e o gradiente TNA - TSA, médias de dezembro a março da safra."""
    a = pd.read_csv(os.path.join(DADOS, 'atlantico_tna_tsa.csv'))
    a['safra'] = a.ano + (a.mes == 12).astype(int)
    a = a[a.mes.isin([12, 1, 2, 3])].groupby('safra')[['tna', 'tsa']]
    a = a.mean()[a.size() == 4]                     # só safras com os quatro meses
    a['grad_atl'] = a.tna - a.tsa
    return a.rename_axis('ano').reset_index()


def acrescenta(df):
    """Junta à base (municipio, ano, cod_ibge7, ...) as variáveis de todas as famílias."""
    out = df.merge(variaveis_por_fase(), on=['cod_ibge7', 'ano'], how='left')
    return out.merge(atlantico(), on='ano', how='left')
