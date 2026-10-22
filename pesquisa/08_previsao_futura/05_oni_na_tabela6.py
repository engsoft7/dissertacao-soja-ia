# -*- coding: utf-8 -*-
"""
O ONI como variável no protocolo da Tabela 6.

Item 2 de TRABALHOS_FUTUROS.md. Repete a avaliação da Tabela 6 (base completa
do Pará, leave-one-year-out com busca aninhada, mesmos orçamentos e semente)
acrescentando às onze variáveis ambientais o ONI de dezembro a março do ano de
colheita. As rotinas são as de 04_analise_para/03_busca_hiperparametros.py,
importadas e não recopiadas; só a lista de variáveis muda.

Hipótese: o ONI reduz o erro dos modelos em relação aos valores publicados na
Tabela 6. Critério: comparar RMSE e R² com e sem o ONI, modelo a modelo, e o
ganho de cada um sobre o modelo de referência (que não usa variáveis e não
muda), com intervalo de 95% por reamostragem de safras. Para isso as previsões
da avaliação externa são guardadas à medida que avalia_modelo as produz.

Uso:  python 05_oni_na_tabela6.py
Saída: oni_na_tabela6.json
"""
import importlib.util
import json
import os

import numpy as np

from comum import RAIZ, ganho_sobre_referencia, oni

PARA = os.path.join(RAIZ, '..', '04_analise_para')
ORCAMENTO = {'Random Forest': 9, 'XGBoost': 15, 'SVR': 15, 'MLP': 15}


def busca():
    spec = importlib.util.spec_from_file_location('busca', os.path.join(PARA, '03_busca_hiperparametros.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.DADOS = os.path.join(PARA, '..', 'dados')
    return m


def main():
    m = busca()
    djf, _ = oni()
    # carrega com a lista original (o ONI não está no CSV) e só depois acrescenta
    df = m.carrega()
    df['oni_djf'] = df.ano.map(djf)
    m.FEATURES = m.FEATURES + ['oni_djf']
    with open(os.path.join(PARA, 'resultados_busca_aninhada.json'), encoding='utf-8') as f:
        publicado = json.load(f)
    saida = {'variaveis': m.FEATURES, 'modelos': {}}
    y, anos, mun, _, safras = m._matrizes(df)
    # previsões do modelo de referência, safra a safra, como em avalia_baseline
    ref = {ty: m.referencia(y, anos, mun, anos != ty, anos == ty) for ty in safras}
    preve_original = m.preve
    externas = {}

    def preve_e_guarda(nome, cfg, X, y_, anos_, mun_, tr, te):
        p = preve_original(nome, cfg, X, y_, anos_, mun_, tr, te)
        if np.array_equal(tr, ~te):          # avaliação externa: treino = todas as outras safras
            externas[int(anos_[te][0])] = p
        return p

    m.preve = preve_e_guarda
    for nome, n in ORCAMENTO.items():
        externas.clear()
        r = m.avalia_modelo(nome, n, df)
        pub = publicado[nome]
        obs = np.concatenate([y[anos == ty] for ty in safras])
        prev = np.concatenate([externas[ty] for ty in safras])
        pref = np.concatenate([ref[ty] for ty in safras])
        aa = np.concatenate([anos[anos == ty] for ty in safras])
        g = ganho_sobre_referencia(obs, prev, pref, aa)
        saida['modelos'][nome] = {'com_oni': {k: r[k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%')},
                                  'tabela_6': {k: pub[k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%')},
                                  'ganho_com_oni_sobre_referencia': g['ganho'], 'IC95': g['IC95']}
        print(nome, saida['modelos'][nome], flush=True)
    saida['referencia_tabela_6'] = {k: publicado['Baseline (sem clima)'][k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%')}
    with open(os.path.join(RAIZ, 'oni_na_tabela6.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
