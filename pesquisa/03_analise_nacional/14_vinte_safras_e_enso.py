# -*- coding: utf-8 -*-
"""
A janela de teste do estudo nacional, de cinco para vinte safras, contra o ENSO.

A subseção 5.4 nota que 2016, safra de El Niño forte, é a pior para os quatro
modelos, mas a janela de teste (2016-2020) tem um único evento intenso, e o
texto recomenda ampliá-la. Este script repete o protocolo da Tabela 3
(04_avalia_ajustado.py: mesmos modelos, hiperparâmetros e subamostras) com
cada uma das vinte safras de 2001 a 2020 deixada de fora, e cruza o desempenho
de cada safra com o Oceanic Niño Index de dezembro a fevereiro
(pesquisa/dados/eventos_enso.json).

Por safra: RMSE e R² dos quatro modelos e do modelo de referência (média do
município mais tendência, como em 08_previsao_futura/04_referencia_nacional.py),
e o ganho do modelo sobre a referência, 1 − MSE(modelo)/MSE(referência).
A associação com o ENSO é a correlação de Spearman entre o módulo do ONI e
cada medida, nas vinte safras.

Ressalva, que o resultado carrega: os hiperparâmetros foram escolhidos na
janela de 2001 a 2015, com as safras de 2014 e 2015 como validação interna.
As de 2016 a 2020 nunca entraram na busca; as de 2014 e 2015 orientaram a
escolha; as de 2001 a 2013 só serviram de treino dentro dela. Por isso o SVR
também roda com a configuração anterior à busca (01_treina_modelos.py), que
não viu nenhuma safra como validação, e as duas janelas são reportadas à parte.

Requer data/data_cast.csv (00_baixa_dados.py). Uso: python 14_vinte_safras_e_enso.py
Saída: vinte_safras_e_enso.json
"""
import importlib.util
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

warnings.filterwarnings('ignore')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..', '08_previsao_futura'))
from comum import ganho_sobre_referencia  # noqa: E402
ENSO = os.path.join(AQUI, '..', 'dados', 'eventos_enso.json')
SEM_AJUSTE = 'SVR sem ajuste'


def carrega_protocolo():
    spec = importlib.util.spec_from_file_location('avalia', os.path.join(AQUI, '04_avalia_ajustado.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def referencia(y, anos, cod, tr, te):
    b = np.polyfit(anos[tr], y[tr], 1)[0]
    media = pd.Series(y[tr]).groupby(cod[tr]).mean()
    return pd.Series(cod[te]).map(media).fillna(y[tr].mean()).values + b * (anos[te] - anos[tr].mean())


def main():
    cfg = carrega_protocolo()
    df = pd.read_csv(os.path.join(AQUI, 'data', 'data_cast.csv'))
    fora = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
    feat = [c for c in df.columns if c not in fora and df[c].dtype != 'object']
    X = df[feat].fillna(df[feat].median()).values
    y, tend = df.YIELD.values.astype(float), df.YIELD_TREND.values.astype(float)
    anom = df.YIELD_TREND_CORRECTED.values.astype(float)
    anos, cod = df.HARVESTED.values, df.CODE.values
    safras = [int(a) for a in sorted(set(anos))]
    modelos = dict(cfg.AJUSTADOS)
    modelos[SEM_AJUSTE] = SVR(C=10, epsilon=0.1, gamma='scale')
    with open(ENSO, encoding='utf-8') as f:
        enso = json.load(f)['historico_detalhado']

    por_safra = {}
    P = {nome: np.full(len(y), np.nan) for nome in modelos}
    R = np.full(len(y), np.nan)
    for ty in safras:
        te = anos == ty
        idx = np.random.RandomState(1000 + ty).choice(np.where(~te)[0], min(cfg.SUB, int((~te).sum())),
                                                      replace=False)
        ref = R[te] = referencia(y, anos, cod, ~te, te)
        linha = {'registros': int(te.sum()), 'oni_djf': enso[str(ty)]['oni_djf'],
                 'fase': enso[str(ty)]['classificacao'],
                 'Referência': {'RMSE': round(float(np.sqrt(mean_squared_error(y[te], ref))), 1),
                                'R2': round(float(r2_score(y[te], ref)), 3)}}
        for nome, base in modelos.items():
            xtr, xte, atr = X[idx], X[te], anom[idx]
            if 'SVR' in nome or nome == 'MLP':
                esc = StandardScaler().fit(xtr)
                xtr, xte = esc.transform(xtr), esc.transform(xte)
                if 'SVR' in nome:
                    xtr, atr = xtr[:cfg.SUB_SVR], atr[:cfg.SUB_SVR]
            p = P[nome][te] = clone(base).fit(xtr, atr).predict(xte) + tend[te]
            mse = mean_squared_error(y[te], p)
            linha[nome] = {'RMSE': round(float(np.sqrt(mse)), 1), 'R2': round(float(r2_score(y[te], p)), 3),
                           'ganho_sobre_referencia': round(float(1 - mse / mean_squared_error(y[te], ref)), 3)}
        por_safra[ty] = linha
        print(ty, f"ONI {linha['oni_djf']:+.2f}", f"ref {linha['Referência']['R2']:+.3f}",
              ' '.join(f"{k[:3]} {v['R2']:+.3f}" for k, v in linha.items() if isinstance(v, dict) and k != 'Referência'),
              flush=True)

    oni = np.array([abs(por_safra[a]['oni_djf']) for a in safras])
    nomes = list(modelos)

    def associacao(quais):
        k = np.array([a in quais for a in safras])
        saida = {}
        for nome in nomes + ['Referência']:
            medidas = ['R2', 'RMSE'] + (['ganho_sobre_referencia'] if nome != 'Referência' else [])
            saida[nome] = {}
            for med in medidas:
                v = np.array([por_safra[a][nome][med] for a in safras])
                rho, p = spearmanr(oni[k], v[k])
                saida[nome][med] = {'rho': round(float(rho), 2), 'p': round(float(p), 3)}
        return saida

    def conjunto(quais):
        """As safras reunidas, como na Tabela 3; IC95 do ganho por reamostragem de safras."""
        k = np.isin(anos, quais)
        s = {'safras': len(quais), 'registros': int(k.sum()),
             'Referência': {'RMSE': round(float(np.sqrt(mean_squared_error(y[k], R[k]))), 1),
                            'R2': round(float(r2_score(y[k], R[k])), 3)}}
        for nome in nomes:
            g = ganho_sobre_referencia(y[k], P[nome][k], R[k], anos[k])
            s[nome] = {'RMSE': round(float(np.sqrt(mean_squared_error(y[k], P[nome][k]))), 1),
                       'R2': round(float(r2_score(y[k], P[nome][k])), 3),
                       'ganho_sobre_referencia': g['ganho'], 'IC95': g['IC95'],
                       'safras_em_que_supera_a_referencia': int(sum(
                           por_safra[a][nome]['ganho_sobre_referencia'] > 0 for a in quais))}
        return s

    limpas = [a for a in safras if a not in (2014, 2015)]
    fortes = [a for a in safras if abs(por_safra[a]['oni_djf']) >= 1.5]
    saida = {
        'nota': ('Protocolo da Tabela 3 (04_avalia_ajustado.py) com cada safra de 2001 a 2020 deixada de fora. '
                 'Hiperparâmetros escolhidos em 2001-2015 com 2014 e 2015 como validação interna: só 2016-2020 '
                 f'ficaram fora da busca. "{SEM_AJUSTE}" usa a configuração anterior à busca. Ganho = '
                 '1 − MSE(modelo)/MSE(referência), referência = média do município + tendência. Associação: '
                 'Spearman entre |ONI de dezembro a fevereiro| e a medida da safra.'),
        'por_safra': por_safra,
        'conjunto': {'2001-2020': conjunto(safras), '2001-2015': conjunto([a for a in safras if a <= 2015]),
                     '2016-2020 (Tabela 3)': conjunto([a for a in safras if a >= 2016])},
        'associacao_com_modulo_do_oni': {'vinte safras': associacao(safras),
                                         'sem 2014 e 2015 (validação da busca)': associacao(limpas)},
        'safras_de_evento_forte_(|ONI|>=1.5)': fortes,
        'media_por_grupo': {
            nome: {med: {'evento forte': round(float(np.mean([por_safra[a][nome][med] for a in fortes])), 3),
                         'demais': round(float(np.mean([por_safra[a][nome][med] for a in safras if a not in fortes])), 3)}
                   for med in (['R2', 'RMSE'] + (['ganho_sobre_referencia'] if nome != 'Referência' else []))}
            for nome in nomes + ['Referência']},
        'pior_safra_por_R2': {nome: int(min(safras, key=lambda a: por_safra[a][nome]['R2'])) for nome in nomes},
    }
    with open(os.path.join(AQUI, 'vinte_safras_e_enso.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    print(json.dumps(saida['associacao_com_modulo_do_oni'], ensure_ascii=False, indent=1))
    print('fortes', fortes, json.dumps(saida['media_por_grupo'], ensure_ascii=False))
    print('pior safra', saida['pior_safra_por_R2'])
    print(json.dumps(saida['conjunto'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
