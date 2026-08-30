# -*- coding: utf-8 -*-
"""
Compara os cenários COM e SEM máscara de soja isolando o efeito da máscara.

Substitui 01_compara_mascara_e_baseline.py, cujo desenho confundia três coisas:
a máscara, a inclusão de log_area como preditora e a mudança de amostra
(sem máscara: 493 registros, 44 municípios, 2001-2023;
 com máscara: 415 registros, 38 municípios, 2001-2024).
Como o baseline não usa nenhuma variável ambiental, o RMSE dele deveria ser
idêntico nos dois cenários; na versão anterior ia de 427 para 416 kg/ha, o que
mostrava que a diferença vinha da amostra, e não da máscara.

Aqui a comparação roda sobre os registros município-safra presentes nas duas
bases, com o mesmo conjunto de variáveis. Gera a Tabela 5 e a Figura 5 da
dissertação. O desempenho na base completa (Tabela 6) sai de
02_desempenho_base_completa.py.

Uso:  python 01_compara_mascara_controlada.py
"""
import json
import os
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from xgboost import XGBRegressor

SEED = 42
MIN_MUN_POR_SAFRA = 4
DADOS = '../dados'
SAIDA = 'results'

FEATURES = ['NDVI_mean', 'NDVI_max', 'EVI_mean', 'EVI_max', 'precip_total',
            'etp_total', 'balanco_hidrico', 'temp_mean', 'temp_max', 'srad_mean']
MODELOS = ['Random Forest', 'XGBoost', 'SVR', 'MLP']
PRECISA_ESCALA = {'SVR', 'MLP'}

np.random.seed(SEED)


def constroi(nome):
    if nome == 'Random Forest':
        return RandomForestRegressor(n_estimators=300, max_depth=10, min_samples_leaf=4,
                                     n_jobs=-1, random_state=SEED)
    if nome == 'XGBoost':
        return XGBRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                            subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
                            tree_method='hist', n_jobs=-1, verbosity=0, random_state=SEED)
    if nome == 'SVR':
        return SVR(C=10, gamma='scale')
    if nome == 'MLP':
        return MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-2, max_iter=800,
                            early_stopping=True, random_state=SEED)
    raise ValueError(nome)


def carrega():
    """Devolve as duas bases restritas aos registros município-safra comuns."""
    sem = pd.read_csv(f'{DADOS}/soja_para_sem_mascara_2001_2023.csv')
    com = pd.read_csv(f'{DADOS}/soja_para_mascarado_2001_2024.csv')
    for df in (sem, com):
        df['balanco_hidrico'] = df.precip_total - df.etp_total

    chave = ['municipio', 'ano']
    comuns = sem[chave].merge(com[chave], on=chave)

    def prepara(df):
        return (df.merge(comuns, on=chave)
                  .dropna(subset=FEATURES + ['rendimento_kg_ha'])
                  .sort_values(chave)
                  .reset_index(drop=True))

    return prepara(sem), prepara(com)


def avalia(df):
    """Validação leave-one-year-out. Os modelos preveem o resíduo sobre o baseline."""
    y = df.rendimento_kg_ha.values.astype(float)
    anos, mun, X = df.ano.values, df.municipio.values, df[FEATURES].values
    safras = [a for a in sorted(set(anos)) if (anos == a).sum() >= MIN_MUN_POR_SAFRA]

    obs = {m: [] for m in MODELOS}
    prev = {m: [] for m in MODELOS}
    obs_base, prev_base = [], []

    for safra in safras:
        tr, te = anos != safra, anos == safra

        # baseline: média histórica do município + tendência tecnológica
        lin = LinearRegression().fit(anos[tr].reshape(-1, 1), y[tr])
        incl, ano_medio = lin.coef_[0], anos[tr].mean()
        media_mun = pd.Series(y[tr]).groupby(mun[tr]).mean()
        media_geral = y[tr].mean()

        def baseline(mask):
            return np.array([media_mun.get(mun[k], media_geral) + incl * (anos[k] - ano_medio)
                             for k in np.where(mask)[0]])

        b_tr, b_te = baseline(tr), baseline(te)
        obs_base += list(y[te])
        prev_base += list(b_te)

        residuo = y[tr] - b_tr
        esc = StandardScaler().fit(X[tr])
        X_tr, X_te = esc.transform(X[tr]), esc.transform(X[te])

        for nome in MODELOS:
            m = constroi(nome)
            if nome in PRECISA_ESCALA:
                m.fit(X_tr, residuo)
                pred = m.predict(X_te)
            else:
                m.fit(X[tr], residuo)
                pred = m.predict(X[te])
            obs[nome] += list(y[te])
            prev[nome] += list(b_te + pred)

    def metricas(o, p):
        o, p = np.array(o), np.array(p)
        return {'RMSE': round(float(np.sqrt(mean_squared_error(o, p))), 1),
                'MAE': round(float(mean_absolute_error(o, p)), 1),
                'R2': round(float(r2_score(o, p)), 3),
                'rRMSE_%': round(float(np.sqrt(mean_squared_error(o, p)) / y.mean() * 100), 1)}

    res = {'Baseline (sem clima)': metricas(obs_base, prev_base)}
    for nome in MODELOS:
        res[nome] = metricas(obs[nome], prev[nome])
    return res


def figura(sem, com, caminho):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    CLARO, ESCURO, VERM = '#3A7CBE', '#1F4E79', '#C00000'
    x, w = np.arange(len(MODELOS)), 0.38
    fig, ax = plt.subplots(1, 2, figsize=(13.5, 4.6), dpi=200)

    for eixo, chave, rotulo, titulo in (
            (ax[0], 'RMSE', 'RMSE (kg/ha)', '(a) Erro por modelo'),
            (ax[1], 'R2', 'R² (agregado)', '(b) Nenhum modelo supera a baseline')):
        eixo.bar(x - w / 2, [sem[m][chave] for m in MODELOS], w, color=CLARO, label='Município inteiro')
        eixo.bar(x + w / 2, [com[m][chave] for m in MODELOS], w, color=ESCURO, label='Máscara de soja')
        base = sem['Baseline (sem clima)'][chave]
        eixo.axhline(base, color=VERM, ls='--', lw=2,
                     label=f'Baseline ({base})' if chave == 'R2' else 'Baseline (sem clima), idêntico nos dois')
        eixo.set_ylabel(rotulo, fontsize=11)
        eixo.set_title(titulo, fontsize=13)
        eixo.legend(fontsize=8.5, loc='upper right')
        eixo.set_xticks(x)
        eixo.set_xticklabels(MODELOS, rotation=20, ha='right', fontsize=10)
        eixo.grid(axis='y', alpha=0.3)
        eixo.set_axisbelow(True)
        for lado in ('top', 'right'):
            eixo.spines[lado].set_visible(False)

    ax[0].set_ylim(390, 445)
    ax[1].set_ylim(0, 0.30)
    fig.tight_layout()
    fig.savefig(caminho, bbox_inches='tight')
    plt.close(fig)


def main():
    os.makedirs(SAIDA, exist_ok=True)
    sem, com = carrega()

    print(f'Registros comuns às duas bases: {len(sem)}')
    print(f'{sem.municipio.nunique()} municípios | safras {sem.ano.min()}-{sem.ano.max()} '
          f'| produtividade média {sem.rendimento_kg_ha.mean():.0f} kg/ha\n')

    resultados = {}
    for rotulo, base in (('SEM MASCARA (municipio inteiro)', sem),
                         ('COM MASCARA (pixels de soja)', com)):
        resultados[rotulo] = avalia(base)
        print(f'===== {rotulo} =====')
        for nome, m in resultados[rotulo].items():
            print(f"  {nome:22s} RMSE={m['RMSE']:6.0f}  MAE={m['MAE']:6.0f}  "
                  f"R2={m['R2']:+.3f}  rRMSE={m['rRMSE_%']:.1f}%")
        print()

    b_sem = resultados['SEM MASCARA (municipio inteiro)']['Baseline (sem clima)']['RMSE']
    b_com = resultados['COM MASCARA (pixels de soja)']['Baseline (sem clima)']['RMSE']
    assert abs(b_sem - b_com) < 0.5, (
        f'O baseline deveria ser idêntico nos dois cenários ({b_sem} vs {b_com}). '
        'Se divergir, as amostras não estão pareadas e a comparação volta a ser confundida.')
    print(f'Verificação: baseline idêntico nos dois cenários ({b_sem:.0f} kg/ha). '
          'A diferença observada decorre apenas da máscara.\n')

    with open(f'{SAIDA}/comparacao_controlada.json', 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    figura(resultados['SEM MASCARA (municipio inteiro)'],
           resultados['COM MASCARA (pixels de soja)'],
           f'{SAIDA}/fig_pa_mascara_controlada.png')
    print(f'Saídas em {SAIDA}/: comparacao_controlada.json, fig_pa_mascara_controlada.png')


if __name__ == '__main__':
    main()
