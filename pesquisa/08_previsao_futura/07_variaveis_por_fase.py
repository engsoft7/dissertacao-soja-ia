# -*- coding: utf-8 -*-
"""
Variáveis por fase e Atlântico tropical no protocolo da Tabela 6 e em janela crescente.

Itens 2 e 3 de TRABALHOS_FUTUROS.md. Cada família de fases.py entra sozinha,
somada às onze variáveis da Tabela 6, em dois desenhos:

  A  protocolo da Tabela 6: leave-one-year-out com busca aninhada, mesmos
     orçamentos e semente (rotinas de 04_analise_para/03_busca_hiperparametros.py,
     importadas, como em 05_oni_na_tabela6.py);
  B  janela crescente: para a safra T (2010-2024), treino só com safras < T,
     SVR e Ridge nas configurações de 02_previsao_rendimento_para.py.

Cada família é avaliada nos registros em que ela existe (a temperatura da
superfície falta onde as nuvens cobrem o ciclo; a fase de enchimento, quando o
pico de verdor cai tarde demais para caber na série), e a referência e o modelo
de onze variáveis são refeitos nesses mesmos registros, para que nenhuma
comparação misture amostras.

Critério fixado antes de rodar: ganho do SVR sobre o modelo de referência no
desenho A, p unilateral por reamostragem de safras, corrigido por Holm sobre
as cinco famílias. Os demais modelos e o desenho B são secundários.

Uso:  python 07_variaveis_por_fase.py        (~45 min)
Saída: variaveis_por_fase.json
"""
import importlib.util
import json
import os

import numpy as np

from comum import RAIZ, ganho_sobre_referencia
from fases import FAMILIAS, acrescenta

PARA = os.path.join(RAIZ, '..', '04_analise_para')
ORCAMENTO = {'Random Forest': 9, 'XGBoost': 15, 'SVR': 15, 'MLP': 15}
PRIMARIO = 'SVR'


def modulo(caminho, nome):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def holm(ps):
    ordem = sorted(ps, key=ps.get)
    aj, maximo = {}, 0.0
    for i, k in enumerate(ordem):
        maximo = max(maximo, min(1.0, (len(ps) - i) * ps[k]))
        aj[k] = round(maximo, 4)
    return aj


def desenho_a(m, df, cols):
    """Busca aninhada da Tabela 6 com as variáveis `cols`; devolve previsões externas por modelo."""
    m.FEATURES = cols
    y, anos, mun, _, safras = m._matrizes(df)
    original = m.preve
    externas, saida = {}, {}

    def guarda(nome, cfg, X, y_, anos_, mun_, tr, te):
        p = original(nome, cfg, X, y_, anos_, mun_, tr, te)
        if np.array_equal(tr, ~te):
            externas[int(anos_[te][0])] = p
        return p

    m.preve = guarda
    try:
        for nome, n in ORCAMENTO.items():
            externas.clear()
            r = m.avalia_modelo(nome, n, df)
            saida[nome] = {'metricas': {k: r[k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%')},
                           'prev': np.concatenate([externas[t] for t in safras])}
            print(f'   {nome}: {saida[nome]["metricas"]}', flush=True)
    finally:
        m.preve = original
    return saida


def desenho_b(p02, df, cols):
    """Janela crescente, como em 02: modelo sobre o resíduo da referência ajustada no passado."""
    prev, obs, anos, ref = {k: [] for k in ('SVR', 'Ridge')}, [], [], []
    for T in p02.SAFRAS:
        alvo, treino = df[df.ano == T], df[df.ano < T]
        if alvo.empty or treino.ano.nunique() < 5:
            continue
        r_te, r_tr = p02.referencia(treino, alvo), p02.referencia(treino, treino)
        for k in prev:
            mdl = p02.AMBIENTAL[k]().fit(treino[cols].values, treino.rendimento_kg_ha.values - r_tr)
            prev[k].append(r_te + mdl.predict(alvo[cols].values))
        obs.append(alvo.rendimento_kg_ha.values)
        anos.append(alvo.ano.values)
        ref.append(r_te)
    obs, anos, ref = map(np.concatenate, (obs, anos, ref))
    return {k: ganho_sobre_referencia(obs, np.concatenate(v), ref, anos) for k, v in prev.items()}, (obs, anos, ref)


def main():
    m = modulo(os.path.join(PARA, '03_busca_hiperparametros.py'), 'busca')
    m.DADOS = os.path.join(PARA, '..', 'dados')
    p02 = modulo(os.path.join(RAIZ, '02_previsao_rendimento_para.py'), 'p02')
    base_cols = list(m.FEATURES)
    df0 = acrescenta(m.carrega())
    saida = {'registros_base': int(len(df0)), 'familias': FAMILIAS,
             'primario': f'{PRIMARIO}, desenho A, Holm sobre {len(FAMILIAS)} famílias', 'A': {}, 'B': {}}
    cache, ps = {}, {}
    for fam, cols in FAMILIAS.items():
        df = df0.dropna(subset=cols).sort_values(['municipio', 'ano']).reset_index(drop=True)
        chave = tuple(zip(df.municipio, df.ano))
        print(f'{fam}: {len(df)} registros, {df.ano.nunique()} safras', flush=True)
        m.FEATURES = base_cols
        y, anos, mun, _, safras = m._matrizes(df)
        obs = np.concatenate([y[anos == t] for t in safras])
        aa = np.concatenate([anos[anos == t] for t in safras])
        ref = np.concatenate([m.referencia(y, anos, mun, anos != t, anos == t) for t in safras])
        if chave not in cache:
            print('  11 variáveis da Tabela 6 nestes registros', flush=True)
            cache[chave] = desenho_a(m, df, base_cols), desenho_b(p02, df, base_cols)[0]
        base_a, base_b = cache[chave]
        print('  com a família', flush=True)
        res = desenho_a(m, df, base_cols + cols)
        a = {'registros': int(len(df)), 'referencia': m.metricas(obs, ref, y.mean()),
             'tabela_6_mesmos_registros': {k: {**v['metricas'], **ganho_sobre_referencia(obs, v['prev'], ref, aa)}
                                           for k, v in base_a.items()}, 'com_familia': {}}
        for k, v in res.items():
            a['com_familia'][k] = {**v['metricas'], **ganho_sobre_referencia(obs, v['prev'], ref, aa),
                                   'ganho_sobre_11_variaveis': ganho_sobre_referencia(obs, v['prev'], base_a[k]['prev'], aa)}
        saida['A'][fam] = a
        ps[fam] = a['com_familia'][PRIMARIO]['p_unilateral']
        saida['B'][fam] = {'tabela_6_mesmos_registros': base_b, 'com_familia': desenho_b(p02, df, base_cols + cols)[0]}
        print('  A:', {k: (v['RMSE'], v['ganho'], v['IC95']) for k, v in a['com_familia'].items()}, flush=True)
        print('  B:', saida['B'][fam], flush=True)
    for fam, p in holm(ps).items():
        saida['A'][fam]['com_familia'][PRIMARIO]['p_holm'] = p
    with open(os.path.join(RAIZ, 'variaveis_por_fase.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    print(json.dumps({f: saida['A'][f]['com_familia'][PRIMARIO] for f in FAMILIAS}, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
