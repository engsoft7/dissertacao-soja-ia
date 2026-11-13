# -*- coding: utf-8 -*-
"""
Por que a janela de pulverização prevista discorda da medida, critério a critério.

04_valida_tempo_inmet.py mediu que a janela calculada sobre a previsão do
Open-Meteo coincide com a calculada sobre o que as estações do INMET mediram
em 42% das horas, e que 10,6% das horas previstas como boas eram, no medido,
horas a evitar. Faltava saber de onde vem a discordância e se dá para
reduzi-la. Com as mesmas estações, o mesmo período e as mesmas regras:

  1. Cada critério sozinho (chuva na hora, temperatura acima de 30 °C, umidade
     abaixo de 60%, vento acima de 10 km/h, vento de 8 a 10 km/h, vento abaixo
     de 3 km/h): com que frequência o previsto e o medido o acionam, quanto do
     medido a previsão acerta e quanto do previsto é alarme falso.
  2. Substituição: a janela prevista é refeita trocando uma variável prevista
     de cada vez pela medida. O quanto a concordância sobe diz quanto da
     discordância vem daquela variável.
  3. Correção do vento, que a previsão superestima: (a) reta ajustada na
     própria estação de novembro a janeiro e aplicada de fevereiro a abril;
     (b) viés médio por hora do dia, no mesmo desenho; (c) reta ajustada na
     estação mais próxima e aplicada à estação, o que o aplicativo poderia
     fazer num lugar sem estação. Em cada caso, a concordância e a fração de
     horas boas que eram a evitar, antes e depois, nas mesmas horas.

Roda no Actions (o INMET e o Open-Meteo não respondem a todo ambiente).

Uso:   python 10_janela_por_criterio.py
Saída: janela_por_criterio.json
"""
import importlib.util
import json
import math
import os

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
CORTE = '2026-02-01'       # ajuste até 31/01, teste de 01/02 em diante


def carrega_validacao():
    spec = importlib.util.spec_from_file_location('valida', os.path.join(AQUI, '04_valida_tempo_inmet.py'))
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    return v


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def junta(v):
    """Uma tabela por estação: medido (_o) e previsto (_p), hora a hora."""
    tabelas = {}
    for cod, e in v.estacoes_inmet().items():
        obs = e['dados'].dropna(subset=['t', 'ur', 'v10'])
        if len(obs) < 24 * 30:
            continue
        prev = v.previsao(e['lat'], e['lon'])
        j = obs.join(prev, lsuffix='_o', rsuffix='_p', how='inner').dropna(subset=['t_p', 'ur_p', 'v10_p'])
        j = j.asfreq('h')
        j['chove_o'] = j.chuva_o.fillna(0) >= v.CHUVA_MM
        tem_chance = j.chance.notna().any()
        j['chove_p'] = (j.chuva_p.fillna(0) >= v.CHUVA_MM) | ((j.chance.fillna(0) >= v.CHANCE) if tem_chance else False)
        tabelas[cod] = {'municipio': e['municipio'], 'lat': e['lat'], 'lon': e['lon'], 'j': j}
        print(f'  {cod} {e["municipio"]}: {len(j)} horas', flush=True)
    return tabelas


def classe(v, j, t='t_p', ur='ur_p', v10='v10_p', chove='chove_p'):
    return v.classifica(pd.DataFrame({'t': j[t], 'ur': j[ur], 'v10': j[v10]}), j[chove])


def concordancia(v, prevista, medida):
    ok = ~np.isnan(prevista) & ~np.isnan(medida)
    p, o = prevista[ok].astype(int), medida[ok].astype(int)
    mat, kap = v.kappa(p, o)
    return {'horas': int(ok.sum()), 'acerto': round(float((p == o).mean()), 3), 'kappa': round(float(kap), 3),
            'boa_prevista_que_era_evitar': round(float(mat[0, 2] / max(mat[0].sum(), 1)), 3),
            'boa_prevista_que_era_boa': round(float(mat[0, 0] / max(mat[0].sum(), 1)), 3),
            'horas_previstas_boas': int(mat[0].sum())}


def criterios(v, j):
    """Cada critério como um sim ou não, no previsto e no medido."""
    f = v.FATOR_2M
    return {
        'chuva na hora': (j.chove_p, j.chove_o),
        'temperatura acima de 30 °C': (j.t_p > v.T_MAX, j.t_o > v.T_MAX),
        'umidade abaixo de 60%': (j.ur_p < v.UR_MIN, j.ur_o < v.UR_MIN),
        'vento acima de 10 km/h': (j.v10_p * f > v.V_ANTIDERIVA, j.v10_o * f > v.V_ANTIDERIVA),
        'vento de 8 a 10 km/h': ((j.v10_p * f > v.V_IDEAL) & (j.v10_p * f <= v.V_ANTIDERIVA),
                                 (j.v10_o * f > v.V_IDEAL) & (j.v10_o * f <= v.V_ANTIDERIVA)),
        'vento abaixo de 3 km/h': (j.v10_p * f < v.V_MIN, j.v10_o * f < v.V_MIN),
    }


def reta(x, y):
    ok = ~np.isnan(x) & ~np.isnan(y)
    b, a = np.polyfit(x[ok], y[ok], 1)
    return float(a), float(b)


def main():
    v = carrega_validacao()
    tab = junta(v)
    todos = pd.concat([t['j'].assign(estacao=c) for c, t in tab.items()])
    medida = np.concatenate([classe(v, t['j'], 't_o', 'ur_o', 'v10_o', 'chove_o') for t in tab.values()])
    prevista = np.concatenate([classe(v, t['j']) for t in tab.values()])
    saida = {'nota': ('Janela de pulverização do aplicativo (regras de TempoCalculo.kt) sobre a previsão de curto prazo '
                      f'do Open-Meteo e sobre o medido nas estações do INMET, {v.INICIO} a {v.FIM}. Concordância: '
                      'acerto e kappa de Cohen entre as três classes; vento a 10 m levado a 2 m como no aplicativo.'),
             'estacoes': {c: t['municipio'] for c, t in tab.items()},
             'como_esta': concordancia(v, prevista, medida)}

    # 1. cada critério sozinho
    saida['criterios'] = {}
    ok = todos[['t_o', 'ur_o', 'v10_o', 't_p', 'ur_p', 'v10_p']].notna().all(axis=1).values
    for nome, (p, o) in criterios(v, todos).items():
        p, o = p.values[ok].astype(bool), o.values[ok].astype(bool)
        saida['criterios'][nome] = {
            'medido_%': round(float(o.mean() * 100), 1), 'previsto_%': round(float(p.mean() * 100), 1),
            'acerto_do_medido_%': round(float((p & o).sum() / max(o.sum(), 1) * 100), 1),
            'alarme_falso_%': round(float((p & ~o).sum() / max(p.sum(), 1) * 100), 1)}

    # 2. uma variável medida no lugar da prevista
    saida['substituicao'] = {}
    for nome, troca in (('temperatura', {'t': 't_o'}), ('umidade', {'ur': 'ur_o'}), ('vento', {'v10': 'v10_o'}),
                        ('chuva', {'chove': 'chove_o'}),
                        ('vento e chuva', {'v10': 'v10_o', 'chove': 'chove_o'})):
        c = np.concatenate([classe(v, t['j'], **troca) for t in tab.values()])
        saida['substituicao'][nome] = concordancia(v, c, medida)

    # 3. correção do vento
    def avalia_correcao(corrige, so_teste):
        antes, depois, med = [], [], []
        for cod, t in tab.items():
            j = t['j'].loc[CORTE:] if so_teste else t['j']
            jc = j.assign(v10_c=np.clip(corrige(cod, j), 0, None))
            antes.append(classe(v, j)); depois.append(classe(v, jc, v10='v10_c'))
            med.append(classe(v, j, 't_o', 'ur_o', 'v10_o', 'chove_o'))
        med = np.concatenate(med)
        return {'antes': concordancia(v, np.concatenate(antes), med),
                'depois': concordancia(v, np.concatenate(depois), med)}

    retas_treino = {c: reta(t['j'].loc[:CORTE].v10_p.values, t['j'].loc[:CORTE].v10_o.values) for c, t in tab.items()}
    retas_tudo = {c: reta(t['j'].v10_p.values, t['j'].v10_o.values) for c, t in tab.items()}
    vies_hora = {c: (t['j'].loc[:CORTE].v10_p - t['j'].loc[:CORTE].v10_o).groupby(t['j'].loc[:CORTE].index.hour).mean()
                 for c, t in tab.items()}
    vizinha = {c: min((o for o in tab if o != c),
                      key=lambda o: km((tab[c]['lat'], tab[c]['lon']), (tab[o]['lat'], tab[o]['lon']))) for c in tab}
    saida['correcao_do_vento'] = {
        'reta da própria estação (ajuste nov-jan, teste fev-abr)': avalia_correcao(
            lambda c, j: retas_treino[c][0] + retas_treino[c][1] * j.v10_p.values, True),
        'viés por hora do dia da própria estação (ajuste nov-jan, teste fev-abr)': avalia_correcao(
            lambda c, j: j.v10_p.values - j.index.hour.map(vies_hora[c]).values, True),
        'reta da estação mais próxima (período inteiro)': avalia_correcao(
            lambda c, j: retas_tudo[vizinha[c]][0] + retas_tudo[vizinha[c]][1] * j.v10_p.values, False),
        'retas': {c: {'a_kmh': round(retas_tudo[c][0], 2), 'b': round(retas_tudo[c][1], 2), 'vizinha': vizinha[c],
                      'distancia_km': round(km((tab[c]['lat'], tab[c]['lon']),
                                               (tab[vizinha[c]]['lat'], tab[vizinha[c]]['lon'])))} for c in tab},
    }
    with open(os.path.join(AQUI, 'janela_por_criterio.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: saida[k] for k in ('como_esta', 'criterios', 'substituicao')}, indent=1, ensure_ascii=False))
    print(json.dumps({k: w for k, w in saida['correcao_do_vento'].items() if k != 'retas'}, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
