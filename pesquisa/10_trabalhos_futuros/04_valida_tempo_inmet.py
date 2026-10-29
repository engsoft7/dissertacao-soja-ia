# -*- coding: utf-8 -*-
"""
A previsão do tempo e a janela de pulverização do aplicativo contra o que as
estações automáticas do INMET mediram no Pará, na safra 2025/26.

O aplicativo (Tempo.kt e TempoCalculo.kt) classifica cada hora como boa, de
atenção ou a evitar para pulverizar, pela previsão do Open-Meteo e pelos
critérios da Embrapa Soja (Adegas e Gazziero, 2020). A classificação nunca
foi comparada com o tempo que de fato fez. Aqui:

  observado  dados horários das estações automáticas do INMET em municípios da
             base (arquivos anuais abertos em portal.inmet.gov.br/dadoshistoricos):
             temperatura, umidade, vento a 10 m e chuva
  previsto   o arquivo de previsões do Open-Meteo (Historical Forecast API), as
             mesmas variáveis e os mesmos modelos que o aplicativo consulta,
             nas coordenadas de cada estação

no período de 1º de novembro de 2025 a 30 de abril de 2026, o ciclo da soja.
O arquivo do Open-Meteo junta as primeiras horas de cada rodada dos modelos:
mede a previsão de curto prazo, a mais favorável, e não a de dias à frente.

Mede-se: o erro de temperatura, umidade e vento; o acerto da chuva por hora e
por dia; e a concordância da janela de pulverização (as mesmas regras do
aplicativo, portadas de TempoCalculo.kt), com a matriz de confusão, o kappa
de Cohen e, o número que mais importa ao produtor, quantas horas previstas como
boas foram, no medido, horas a evitar.

Uso:   python 04_valida_tempo_inmet.py
Saída: valida_tempo_inmet.json
"""
import io
import json
import math
import os
import re
import sys
import time
import unicodedata
import zipfile

import numpy as np
import pandas as pd
import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, '..', '..'))
INICIO, FIM = '2025-11-01', '2026-04-30'
ANOS = (2025, 2026)
URL_INMET = 'https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip'
URL_OM = 'https://historical-forecast-api.open-meteo.com/v1/forecast'

# Regras do aplicativo (TempoCalculo.kt)
T_MAX, T_MIN, UR_MIN, V_MIN, V_IDEAL, V_ANTIDERIVA = 30.0, 10.0, 60.0, 3.0, 8.0, 10.0
CHUVA_MM, CHANCE, HORAS_SEM_CHUVA = 0.1, 50.0, 2
FATOR_2M = 4.87 / math.log(67.8 * 10 - 5.42)


def chave(s):
    s = unicodedata.normalize('NFKD', str(s))
    return re.sub(r'[^a-z]', '', ''.join(c for c in s if not unicodedata.combining(c)).lower())


def avalia(t, ur, v10, chuva_hora, chuva_logo):
    """0 boa, 1 atenção, 2 evitar — como avaliaHora em TempoCalculo.kt."""
    if any(x is None or (isinstance(x, float) and math.isnan(x)) for x in (t, ur, v10)):
        return np.nan
    v = v10 * FATOR_2M
    if chuva_hora or t > T_MAX or ur < UR_MIN or v > V_ANTIDERIVA:
        return 2
    if V_IDEAL < v <= V_ANTIDERIVA or v < V_MIN or t < T_MIN or chuva_logo:
        return 1
    return 0


def classifica(df, chove):
    c = chove.values
    logo = np.array([c[i + 1:i + 1 + HORAS_SEM_CHUVA].any() for i in range(len(c))])
    return np.array([avalia(t, u, v, a, b) for t, u, v, a, b in zip(df.t, df.ur, df.v10, c, logo)])


def estacoes_inmet():
    """Leituras horárias das estações do INMET em municípios da base do Pará."""
    base = pd.read_csv(os.path.join(REPO, 'pesquisa', 'dados', 'municipios_para.csv'))
    alvo = {chave(m): m for m in base.municipio}
    lidas = {}
    for ano in ANOS:
        r = requests.get(URL_INMET.format(ano=ano), timeout=600, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        for nome in z.namelist():
            m = re.search(r'_PA_(A\d{3})_(.+?)_\d{2}-\d{2}-\d{4}_A_', os.path.basename(nome))
            if not m or chave(m.group(2)) not in alvo:
                continue
            texto = z.read(nome).decode('latin-1')
            linhas = texto.splitlines()
            meta = {l.split(';')[0].strip(': ').upper(): l.split(';')[1].replace(',', '.') for l in linhas[:8]}
            df = pd.read_csv(io.StringIO('\n'.join(linhas[8:])), sep=';', decimal=',', na_values=['-9999', ''])
            col = {c: c.upper() for c in df.columns}
            achar = lambda *ps: next(c for c, u in col.items() if all(p in u for p in ps))
            d = pd.DataFrame({
                'hora': pd.to_datetime(df[achar('DATA')].astype(str).str.replace('-', '/') + ' ' +
                                       df[achar('HORA')].astype(str).str[:4], format='%Y/%m/%d %H%M'),
                'chuva': df[achar('PRECIPITA')], 't': df[achar('BULBO SECO')],
                'ur': df[achar('UMIDADE RELATIVA DO AR, HORARIA')], 'v10': df[achar('VENTO, VELOCIDADE')] * 3.6,
            })
            cod = m.group(1)
            ant = lidas.get(cod, {'municipio': alvo[chave(m.group(2))], 'lat': float(meta['LATITUDE']),
                                  'lon': float(meta['LONGITUDE']), 'dados': []})
            ant['dados'].append(d)
            lidas[cod] = ant
    for cod, e in lidas.items():
        d = pd.concat(e['dados']).drop_duplicates('hora').set_index('hora').sort_index()
        e['dados'] = d.loc[INICIO:FIM + ' 23:00']
    return lidas


def previsao(lat, lon):
    """Mês a mês e com novas tentativas: o arquivo do Open-Meteo demora a
    responder o semestre inteiro de uma vez e cortou a primeira execução."""
    partes = []
    for ini in pd.date_range(INICIO, FIM, freq='MS'):
        fim = min(ini + pd.offsets.MonthEnd(0), pd.Timestamp(FIM))
        for tentativa in range(4):
            try:
                r = requests.get(URL_OM, timeout=180, params={
                    'latitude': lat, 'longitude': lon, 'start_date': ini.strftime('%Y-%m-%d'),
                    'end_date': fim.strftime('%Y-%m-%d'), 'timezone': 'UTC',
                    'hourly': 'temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,'
                              'precipitation_probability'})
                r.raise_for_status()
                break
            except requests.RequestException:
                if tentativa == 3:
                    raise
                time.sleep(20 * (tentativa + 1))
        h = r.json()['hourly']
        partes.append(pd.DataFrame({'hora': pd.to_datetime(h['time']), 't': h['temperature_2m'],
                                    'ur': h['relative_humidity_2m'], 'v10': h['wind_speed_10m'],
                                    'chuva': h['precipitation'],
                                    'chance': h.get('precipitation_probability') or [None] * len(h['time'])}))
    return pd.concat(partes).drop_duplicates('hora').set_index('hora').sort_index()


def kappa(a, b, k=3):
    m = np.zeros((k, k))
    for x, y in zip(a, b):
        m[int(x), int(y)] += 1
    n = m.sum()
    po = np.trace(m) / n
    pe = (m.sum(0) * m.sum(1)).sum() / n ** 2
    return m, (po - pe) / (1 - pe) if pe < 1 else np.nan


def main():
    est = estacoes_inmet()
    print(f'{len(est)} estações do INMET em municípios da base: '
          f'{[(c, e["municipio"]) for c, e in est.items()]}', flush=True)
    resultados, todos_o, todos_p = {}, [], []
    for cod, e in est.items():
        obs = e['dados'].dropna(subset=['t', 'ur', 'v10'])
        if len(obs) < 24 * 30:
            print(f'  {cod}: só {len(obs)} horas completas; fica de fora', flush=True)
            continue
        prev = previsao(e['lat'], e['lon'])
        j = obs.join(prev, lsuffix='_o', rsuffix='_p', how='inner').dropna(subset=['t_p', 'ur_p', 'v10_p'])
        j = j.asfreq('h')
        chove_o = j.chuva_o.fillna(0) >= CHUVA_MM
        tem_chance = j.chance.notna().any()
        chove_p = (j.chuva_p.fillna(0) >= CHUVA_MM) | ((j.chance.fillna(0) >= CHANCE) if tem_chance else False)
        cls_o = classifica(j.rename(columns={'t_o': 't', 'ur_o': 'ur', 'v10_o': 'v10'}), chove_o)
        cls_p = classifica(j.rename(columns={'t_p': 't', 'ur_p': 'ur', 'v10_p': 'v10'}), chove_p)
        ok = ~np.isnan(cls_o) & ~np.isnan(cls_p)
        o, p = cls_o[ok].astype(int), cls_p[ok].astype(int)
        mat, kap = kappa(p, o)
        d = j.dropna(subset=['t_o', 't_p'])
        dia = j[['chuva_o', 'chuva_p']].resample('D').sum(min_count=20).dropna()
        ch_o, ch_p = dia.chuva_o >= 1, dia.chuva_p >= 1
        resultados[cod] = {
            'municipio': e['municipio'], 'horas': int(ok.sum()),
            'erro_medio_absoluto': {'temperatura_C': round(float((d.t_p - d.t_o).abs().mean()), 2),
                                    'umidade_pct': round(float((d.ur_p - d.ur_o).abs().mean()), 1),
                                    'vento_10m_kmh': round(float((d.v10_p - d.v10_o).abs().mean()), 1)},
            'vies': {'temperatura_C': round(float((d.t_p - d.t_o).mean()), 2),
                     'umidade_pct': round(float((d.ur_p - d.ur_o).mean()), 1),
                     'vento_10m_kmh': round(float((d.v10_p - d.v10_o).mean()), 1)},
            'chuva_por_dia_1mm': {'dias': int(len(dia)), 'acerto_dos_dias_com_chuva': round(float((ch_p & ch_o).sum() / max(ch_o.sum(), 1)), 3),
                                  'alarmes_falsos': round(float((ch_p & ~ch_o).sum() / max(ch_p.sum(), 1)), 3)},
            'janela': {'acerto': round(float((o == p).mean()), 3), 'kappa': round(float(kap), 3),
                       'matriz_prevista_x_medida': mat.astype(int).tolist(),
                       'boa_prevista_que_era_evitar': round(float(mat[0, 2] / max(mat[0].sum(), 1)), 3),
                       'boa_prevista_que_era_boa': round(float(mat[0, 0] / max(mat[0].sum(), 1)), 3)},
            'chance_de_chuva_no_arquivo': bool(tem_chance),
        }
        todos_o.append(o); todos_p.append(p)
        print(f'  {cod} {e["municipio"]}: {resultados[cod]["janela"]}', flush=True)
    o, p = np.concatenate(todos_o), np.concatenate(todos_p)
    mat, kap = kappa(p, o)
    saida = {
        'nota': ('Janela de pulverização e previsão do Open-Meteo (arquivo de previsões de curto prazo) contra '
                 f'as estações automáticas do INMET em municípios da base, {INICIO} a {FIM}. '
                 'Classes: 0 boa, 1 atenção, 2 evitar; matriz com linhas = prevista, colunas = medida.'),
        'estacoes': resultados,
        'geral': {'horas': int(len(o)), 'acerto': round(float((o == p).mean()), 3), 'kappa': round(float(kap), 3),
                  'matriz_prevista_x_medida': mat.astype(int).tolist(),
                  'boa_prevista_que_era_evitar': round(float(mat[0, 2] / max(mat[0].sum(), 1)), 3),
                  'boa_prevista_que_era_boa': round(float(mat[0, 0] / max(mat[0].sum(), 1)), 3),
                  'proporcao_medida': {k: round(float((o == i).mean()), 3) for i, k in enumerate(('boa', 'atencao', 'evitar'))}},
    }
    with open(os.path.join(AQUI, 'valida_tempo_inmet.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    print(json.dumps(saida['geral'], indent=1, ensure_ascii=False))


if __name__ == '__main__':
    sys.exit(main())
