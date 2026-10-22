# -*- coding: utf-8 -*-
"""
Previsão da produtividade de safras futuras no Pará, em janela crescente.

A dissertação mostrou, em leave-one-year-out, que as variáveis ambientais não
superam o modelo de referência (média do município + tendência). Isso deixa
duas perguntas que ela não respondeu e que este script testa:

  1. Antes da safra (antecedência h = 1, 2 ou 3 safras), sem clima nem satélite
     da safra prevista, o que prevê melhor: persistir o último valor, a média do
     município, a referência, tendências por município, ou um modelo que combine
     defasagens? O ONI de setembro-novembro, já conhecido no plantio, ajuda?
  2. Ao fim do ciclo (h = 0), com o clima e o satélite da própria safra, os
     modelos da dissertação passam a superar a referência quando treinados só
     com o passado? E o ONI de dezembro-março, acrescentado a eles?

Hipótese nula em todos os casos: ganho de habilidade nulo sobre a referência
(1 - MSE_modelo / MSE_referência = 0). O intervalo de 95% vem de reamostragem
de safras inteiras. Safras avaliadas: 2010 a 2024, cada uma prevista só com o
que se sabia antes dela. Também se reporta o subconjunto em que o valor da PAM
mudou em relação à safra anterior, onde a repetição não favorece a persistência.

Roda sobre duas bases: a da dissertação (38 municípios, com variáveis
ambientais) e todos os municípios paraenses da PAM (53, sem variáveis
ambientais), para os modelos que só usam o histórico.

Uso:  python 02_previsao_rendimento_para.py
Saída: previsao_rendimento_para.json
"""
import json
import os
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from comum import (ALVO, AMBIENTAIS, RAIZ, carrega_base_para, carrega_pam_para,
                   ganho_sobre_referencia, metricas, oni, referencia)

warnings.filterwarnings('ignore')
SEED = 42
SAFRAS = list(range(2010, 2025))
ONI_DJF, ONI_SON = oni()

# Configurações modais do Quadro 8 da dissertação (busca aninhada no Pará).
AMBIENTAL = {
    'MLP': lambda: make_pipeline(StandardScaler(), MLPRegressor(
        hidden_layer_sizes=(64, 32), alpha=1e-3, learning_rate_init=3e-3, max_iter=500,
        early_stopping=True, random_state=SEED)),
    'SVR': lambda: make_pipeline(StandardScaler(), SVR(C=100, epsilon=0.1, gamma=0.05)),
    'Random Forest': lambda: RandomForestRegressor(n_estimators=200, max_depth=8, min_samples_leaf=2,
                                                   max_features='sqrt', n_jobs=-1, random_state=SEED),
    'Ridge': lambda: make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
}


def gbm():
    return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=200,
                                         min_samples_leaf=10, random_state=SEED)


# ------------------------------------------------------------ defasagens --
def defasagens(painel, linhas, corte):
    """Para cada linha (município, ano), o que se sabia do município até `corte`."""
    hist = painel[painel.ano <= corte]
    g = {m: s for m, s in hist.groupby('municipio')}
    area = 'area_plantada_ha' if 'area_plantada_ha' in painel else 'soy_area_ha'
    out = []
    for m, ano in zip(linhas.municipio.values, linhas.ano.values):
        s = g.get(m)
        if s is None or s.empty:
            out.append((np.nan, np.nan, np.nan, 0, np.nan))
            continue
        y = s[ALVO].values
        out.append((y[-1], y[-3:].mean(), ano - s.ano.values[-1], len(y), np.log1p(s[area].values[-1])))
    return pd.DataFrame(out, columns=['ultimo', 'media3', 'anos_desde', 'n_hist', 'log_area_ult'],
                        index=linhas.index)


def matriz_defasagens(painel, linhas, h, com_oni):
    """Atributos do modelo de defasagens para linhas cujo corte é ano - h.
    Tudo relativo à referência ajustada até o corte, para o modelo aprender só o
    desvio."""
    partes = []
    for ano, bloco in linhas.groupby('ano'):
        corte = ano - h
        treino = painel[painel.ano <= corte]
        if treino.ano.nunique() < 3:
            continue
        ref = referencia(treino, bloco)
        d = defasagens(painel, bloco, corte)
        f = pd.DataFrame({'ref': ref, 'd_ultimo': d.ultimo - ref, 'd_media3': d.media3 - ref,
                          'anos_desde': d.anos_desde, 'n_hist': d.n_hist,
                          'log_area_ult': d.log_area_ult}, index=bloco.index)
        if com_oni:
            f['oni_son'] = ONI_SON.get(ano - 1, np.nan)
        partes.append(f)
    return pd.concat(partes) if partes else pd.DataFrame()


# --------------------------------------------------------------- pré-safra --
def previsoes_pre_safra(painel, h):
    """Todas as previsões com antecedência h, safra a safra."""
    regs = []
    for T in SAFRAS:
        alvo = painel[painel.ano == T]
        treino = painel[painel.ano <= T - h]
        if alvo.empty or treino.ano.nunique() < 5:
            continue
        p = {'obs': alvo[ALVO].values, 'ano': np.full(len(alvo), T)}
        ref = referencia(treino, alvo)
        p['Referência (média + tendência)'] = ref
        d = defasagens(painel, alvo, T - h)
        geral = treino[ALVO].mean()
        p['Persistência (último valor)'] = d.ultimo.fillna(geral).values
        p['Média do município'] = alvo.municipio.map(treino.groupby('municipio')[ALVO].mean()).fillna(geral).values
        # tendência própria de cada município (com 5+ safras), senão a comum
        b = np.polyfit(treino.ano, treino[ALVO], 1)[0]
        tend = []
        for m in alvo.municipio:
            s = treino[treino.municipio == m]
            if len(s) >= 5:
                tend.append(np.polyval(np.polyfit(s.ano, s[ALVO], 1), T))
            elif len(s):
                tend.append(s[ALVO].mean() + b * (T - s.ano.mean()))
            else:
                tend.append(geral)
        p['Tendência por município'] = np.array(tend)
        # a média das 3 últimas está centrada um ano antes da última safra
        p['Média das 3 últimas + tendência'] = np.where(
            d.media3.notna(), d.media3 + b * (d.anos_desde + 1), ref)
        # previsão "climatológica" do restante: referência + efeito do ONI de SON
        if h == 1:
            res = treino[ALVO].values - referencia(treino, treino)
            o = treino.ano.map(lambda a: ONI_SON.get(a - 1, np.nan)).values
            ok = ~np.isnan(o)
            beta = np.polyfit(o[ok], res[ok], 1) if ok.sum() > 10 else np.array([0, 0])
            p['Referência + ONI (set-nov)'] = ref + np.polyval(beta, ONI_SON.get(T - 1, 0.0))
        # modelos de defasagens: treinam com o passado, cada linha com seu próprio corte
        for nome, com_oni in [('Defasagens (GBM)', False), ('Defasagens + ONI (GBM)', True)]:
            if com_oni and h != 1:
                continue
            Xtr = matriz_defasagens(painel, treino[treino.ano <= T - h], h, com_oni).dropna()
            Xte = matriz_defasagens(painel, alvo, h, com_oni)
            ytr = treino.loc[Xtr.index, ALVO].values - Xtr.ref.values
            if len(Xtr) < 40:
                p[nome] = ref
                continue
            mdl = gbm().fit(Xtr.drop(columns='ref'), ytr)
            p[nome] = Xte.ref.values + mdl.predict(Xte.drop(columns='ref'))
        regs.append(p)
    return regs


# ---------------------------------------------------------- fim do ciclo --
def previsoes_fim_de_ciclo(base):
    """Com o clima e o satélite da safra T, treinando só com safras anteriores."""
    regs = []
    for T in SAFRAS:
        alvo = base[base.ano == T]
        treino = base[base.ano < T]
        if alvo.empty or treino.ano.nunique() < 5:
            continue
        p = {'obs': alvo[ALVO].values, 'ano': np.full(len(alvo), T)}
        ref_te, ref_tr = referencia(treino, alvo), referencia(treino, treino)
        p['Referência (média + tendência)'] = ref_te
        for com_oni in (False, True):
            cols = AMBIENTAIS + (['oni_djf'] if com_oni else [])
            Xtr = treino.assign(oni_djf=treino.ano.map(ONI_DJF))[cols].values
            Xte = alvo.assign(oni_djf=alvo.ano.map(ONI_DJF))[cols].values
            for nome, fab in AMBIENTAL.items():
                rot = f'{nome} ambiental' + (' + ONI (dez-mar)' if com_oni else '')
                p[rot] = ref_te + fab().fit(Xtr, treino[ALVO].values - ref_tr).predict(Xte)
        # só o ONI, sem as demais variáveis
        res = treino[ALVO].values - ref_tr
        beta = np.polyfit(treino.ano.map(ONI_DJF).values, res, 1)
        p['Referência + ONI (dez-mar)'] = ref_te + np.polyval(beta, ONI_DJF[T])
        # ambiente + defasagens
        lag_tr = matriz_defasagens(base, treino, 1, False)
        lag_te = matriz_defasagens(base, alvo, 1, False)
        Xtr = pd.concat([treino.loc[lag_tr.index, AMBIENTAIS], lag_tr.drop(columns='ref')], axis=1)
        Xte = pd.concat([alvo[AMBIENTAIS], lag_te.drop(columns='ref')], axis=1)
        mdl = gbm().fit(Xtr, treino.loc[lag_tr.index, ALVO].values - lag_tr.ref.values)
        p['Ambiental + defasagens (GBM)'] = lag_te.ref.values + mdl.predict(Xte)
        regs.append(p)
    return regs


# -------------------------------------------------------------- avaliação --
def resume(regs, painel):
    obs = np.concatenate([r['obs'] for r in regs])
    anos = np.concatenate([r['ano'] for r in regs])
    nomes = [k for k in regs[0] if k not in ('obs', 'ano')]
    prev = {n: np.concatenate([r[n] for r in regs]) for n in nomes}
    ref = prev['Referência (média + tendência)']
    # registros em que a PAM mudou em relação à safra anterior do município
    ant = painel.set_index(['municipio', 'ano'])[ALVO]
    alvo_idx = pd.concat([painel[painel.ano == a] for a in sorted(set(anos))])
    mudou = np.array([ant.get((m, a - 1), np.nan) != y for m, a, y in
                      zip(alvo_idx.municipio, alvo_idx.ano, alvo_idx[ALVO])])
    saida = {}
    for n in nomes:
        g = ganho_sobre_referencia(obs, prev[n], ref, anos)
        saida[n] = {**metricas(obs, prev[n]), 'ganho_sobre_referencia': g['ganho'], 'IC95': g['IC95'],
                    'so_pares_que_mudaram': {**metricas(obs[mudou], prev[n][mudou]),
                                             'ganho_sobre_referencia':
                                                 ganho_sobre_referencia(obs[mudou], prev[n][mudou],
                                                                        ref[mudou], anos[mudou])['ganho']}}
    return dict(sorted(saida.items(), key=lambda kv: kv[1]['RMSE']))


def main():
    base, pam = carrega_base_para(), carrega_pam_para()
    saida = {'desenho': 'janela crescente; safras-alvo 2010-2024; ganho = 1 - MSE/MSE_referência, '
                        'IC95 por reamostragem de safras',
             'base_dissertacao': {}, 'pam_todos_municipios': {}}
    for h in (1, 2, 3):
        saida['base_dissertacao'][f'antes da safra, h={h}'] = resume(previsoes_pre_safra(base, h), base)
        saida['pam_todos_municipios'][f'antes da safra, h={h}'] = resume(previsoes_pre_safra(pam, h), pam)
        print(f'h={h} feito', flush=True)
    saida['base_dissertacao']['fim do ciclo, com clima e satélite da safra'] = \
        resume(previsoes_fim_de_ciclo(base), base)
    with open(os.path.join(RAIZ, 'previsao_rendimento_para.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    for bloco in ('base_dissertacao', 'pam_todos_municipios'):
        for cen, res in saida[bloco].items():
            print(f'\n== {bloco} | {cen}')
            for n, r in res.items():
                print(f"  {n:45s} RMSE={r['RMSE']:6.1f}  rRMSE={r['rRMSE_%']:5.1f}%  "
                      f"ganho={r['ganho_sobre_referencia']:+.3f} {r['IC95']}  "
                      f"| mudou: ganho={r['so_pares_que_mudaram']['ganho_sobre_referencia']:+.3f}")


if __name__ == '__main__':
    main()
