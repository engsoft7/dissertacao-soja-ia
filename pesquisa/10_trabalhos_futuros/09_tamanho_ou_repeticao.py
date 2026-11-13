# -*- coding: utf-8 -*-
"""
Base pequena ou alvo repetido? Mato Grosso e Maranhão do tamanho do Pará.

06_amazonia_legal.py mostrou ganho sobre a referência em Mato Grosso e no
Maranhão e nenhum no Pará. Os dois estados diferem do Pará em duas coisas ao
mesmo tempo: têm bases maiores (2.290 e 1.043 registros contra 415) e a
produtividade da PAM repete menos (12,1% e 9,5% dos pares de safras sucessivas
contra 40,1%). TRABALHOS_FUTUROS.md, seção 3, deixou a separação para outro
desenho. Este script a faz, cruzando os dois fatores no mesmo estado:

  tamanho      a base inteira do estado, ou uma amostra com a estrutura exata
               do painel do Pará: 38 municípios, cada um com as mesmas safras
               de um município paraense (415 registros);
  repetição    a do próprio estado, ou injetada até os 40,1% do Pará, como em
               04_analise_para/07_injecao_de_repeticao.py (o registro passa a
               repetir o valor da safra anterior; os preditores ficam intactos).

Em cada célula, o protocolo da Tabela 6 (leave-one-year-out, modelos
ajustados ao resíduo sobre a média do município mais a tendência), com a
configuração fixa de cada algoritmo, a mesma do experimento de injeção, e,
nas amostras do tamanho do Pará, também o SVR com a busca aninhada da Tabela
6. O ganho é 1 − MSE(modelo)/MSE(referência), com IC95 por reamostragem de
safras; "detectado" é o IC95 acima de zero. Com repetição injetada, o ganho é
medido contra o alvo que se publicaria (aparente) e contra o valor original.

Pergunta: reduzido ao tamanho do Pará, o estado ainda mostra o ganho? E com a
repetição do Pará?

Uso:   python 09_tamanho_ou_repeticao.py [MT MA] [--replicas 100] [--processos 4]
Saída: tamanho_ou_repeticao.json
"""
import importlib.util
import json
import os
import sys
import time
from multiprocessing import get_context

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
PESQUISA = os.path.abspath(os.path.join(AQUI, '..'))
sys.path.insert(0, os.path.join(PESQUISA, '08_previsao_futura'))
from comum import ganho_sobre_referencia  # noqa: E402

ALVO_REPETICAO = 40.1          # % dos pares de safras sucessivas, a taxa do Pará
REPLICAS, REPLICAS_INTEIRA = 100, 20
MODELOS = ['Random Forest', 'XGBoost', 'SVR', 'MLP']
ANINHADO, ORCAMENTO_ANINHADO = 'SVR', 15
SEED = 42

_m = _al = None


def modulos():
    """O protocolo da Tabela 6 e a leitura dos estados, uma vez por processo."""
    global _m, _al
    if _m is None:
        spec = importlib.util.spec_from_file_location('amazonia_legal', os.path.join(AQUI, '06_amazonia_legal.py'))
        _al = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_al)
        _m = _al.busca()
        for nome in ('Random Forest', 'XGBoost'):      # um núcleo por processo
            _m.FIXOS[nome]['n_jobs'] = 1
    return _m, _al


def taxa_de_repeticao(mun, y):
    r = t = 0
    for u in pd.unique(mun):
        v = y[mun == u]
        r += int((np.diff(v) == 0).sum())
        t += len(v) - 1
    return r / t * 100 if t else float('nan')


def painel_do_para(df, anos_pa, rng):
    """Amostra do estado com a estrutura do painel do Pará: para cada município
    paraense, um município do estado (sem repetir) que tenha todas as safras
    dele, e só essas safras."""
    series = {u: set(g.ano) for u, g in df.groupby('municipio')}
    livres, partes = set(series), []
    for _, ys in sorted(anos_pa.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        cands = sorted(u for u in livres if ys <= series[u])
        escolhido = cands[rng.integers(len(cands))]
        livres.discard(escolhido)
        partes.append(df[(df.municipio == escolhido) & df.ano.isin(ys)])
    return pd.concat(partes).sort_values(['municipio', 'ano']).reset_index(drop=True)


def injeta_ate(df, alvo_pct, rng):
    """Repete o valor da safra anterior em registros sorteados, até a taxa de
    repetição chegar a alvo_pct. Devolve o alvo corrompido, na ordem de df."""
    mun, anos = df.municipio.values, df.ano.values
    y0 = df.rendimento_kg_ha.values.astype(float)
    pos = {(u, a): i for i, (u, a) in enumerate(zip(mun, anos))}
    ordem = rng.permutation([i for i, (u, a) in enumerate(zip(mun, anos)) if (u, a - 1) in pos])

    def aplica(n):
        y = y0.copy()
        for i in sorted(ordem[:n]):          # em sequência: dois seguidos fazem um platô de três
            y[i] = y[pos[(mun[i], anos[i] - 1)]]
        return y

    lo, hi = 0, len(ordem)
    while lo < hi:
        meio = (lo + hi) // 2
        if taxa_de_repeticao(mun, aplica(meio)) >= alvo_pct:
            hi = meio
        else:
            lo = meio + 1
    return aplica(lo)


def previsoes(m, df, y, aninhado):
    """Leave-one-year-out com o alvo y: referência e cada modelo, na mesma ordem."""
    d = df.assign(rendimento_kg_ha=y)
    yy, anos, mun, X, safras = m._matrizes(d)
    te_de = {ty: anos == ty for ty in safras}
    idx = np.concatenate([np.where(te_de[ty])[0] for ty in safras])
    saida = {'_idx': idx, '_anos': anos[idx],
             'referencia': np.concatenate([m.referencia(yy, anos, mun, ~te_de[ty], te_de[ty]) for ty in safras])}
    for nome in MODELOS:
        saida[nome] = np.concatenate([m.preve(nome, m.ATUAL[nome], X, yy, anos, mun, ~te_de[ty], te_de[ty])
                                      for ty in safras])
    if aninhado:
        cands = [m.ATUAL[ANINHADO]] + m.amostra(ANINHADO, ORCAMENTO_ANINHADO, np.random.default_rng(m.SEED))
        partes = []
        for ty in safras:
            tr = ~te_de[ty]
            internas = [a for a in safras if a != ty][-m.N_INTERNAS:]
            erros = [np.mean([np.sqrt(np.mean((yy[anos == vi] - m.preve(ANINHADO, cfg, X, yy, anos, mun,
                                                                       tr & (anos != vi), anos == vi)) ** 2))
                              for vi in internas if (anos == vi).sum() >= m.MIN_MUN]) for cfg in cands]
            partes.append(m.preve(ANINHADO, cands[int(np.argmin(erros))], X, yy, anos, mun, tr, te_de[ty]))
        saida[f'{ANINHADO} (busca aninhada)'] = np.concatenate(partes)
    return saida


def mede(m, df, y_treino, y_original, aninhado):
    """Ganho de cada modelo contra o alvo usado no treino e, se ele foi
    corrompido, também contra o original."""
    p = previsoes(m, df, y_treino, aninhado)
    idx, anos = p['_idx'], p['_anos']
    saida = {}
    for nome in [k for k in p if not k.startswith('_') and k != 'referencia']:
        g = ganho_sobre_referencia(y_treino[idx], p[nome], p['referencia'], anos)
        saida[nome] = {'ganho': g['ganho'], 'IC95': g['IC95']}
        if y_treino is not y_original:
            saida[nome]['ganho_contra_o_original'] = ganho_sobre_referencia(
                y_original[idx], p[nome], p['referencia'], anos, n_boot=1)['ganho']
    return saida


def replica(args):
    uf, celula, semente = args
    m, al = modulos()
    rng = np.random.default_rng(semente)
    df, _ = al.base_do_estado(uf, m)
    reduzida = celula.startswith('tamanho do Pará')
    if reduzida:
        pa = m.carrega()
        df = painel_do_para(df, {u: set(g.ano) for u, g in pa.groupby('municipio')}, rng)
    y0 = df.rendimento_kg_ha.values.astype(float)
    y = injeta_ate(df, ALVO_REPETICAO, rng) if celula.endswith('repetição do Pará') else y0
    return {'registros': int(len(df)), 'municipios': int(df.municipio.nunique()),
            'repeticao': round(taxa_de_repeticao(df.municipio.values, y), 1),
            'modelos': mede(m, df, y, y0, aninhado=reduzida)}


def resume(replicas):
    saida = {'replicas': len(replicas), 'registros': replicas[0]['registros'],
             'municipios': replicas[0]['municipios'],
             'repeticao_media_%': round(float(np.mean([r['repeticao'] for r in replicas])), 1), 'modelos': {}}
    for nome in replicas[0]['modelos']:
        g = np.array([r['modelos'][nome]['ganho'] for r in replicas])
        lo = np.array([r['modelos'][nome]['IC95'][0] for r in replicas])
        s = {'ganho_mediano': round(float(np.median(g)), 3),
             'ganho_quartis': [round(float(q), 3) for q in np.percentile(g, [25, 75])],
             'ganho_min_max': [round(float(g.min()), 3), round(float(g.max()), 3)],
             'replicas_com_ganho_detectado_%': round(float((lo > 0).mean() * 100), 1)}
        if len(replicas) == 1:
            s['IC95'] = replicas[0]['modelos'][nome]['IC95']
        if 'ganho_contra_o_original' in replicas[0]['modelos'][nome]:
            s['ganho_mediano_contra_o_original'] = round(float(np.median(
                [r['modelos'][nome]['ganho_contra_o_original'] for r in replicas])), 3)
        saida['modelos'][nome] = s
    return saida


def main(args):
    opc = {a: args[i + 1] for i, a in enumerate(args) if a.startswith('--')}
    ufs = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or not args[i - 1].startswith('--'))]
    ufs = ufs or ['MT', 'MA']
    n, n_int = int(opc.get('--replicas', REPLICAS)), int(opc.get('--replicas-inteira', REPLICAS_INTEIRA))
    processos = int(opc.get('--processos', 4))
    m, _ = modulos()
    pa = m.carrega()
    y_pa = pa.rendimento_kg_ha.values.astype(float)
    saida = {'nota': ('Ganho = 1 − MSE(modelo)/MSE(referência) no protocolo da Tabela 6, configuração fixa de cada '
                      'algoritmo (a de 07_injecao_de_repeticao.py); "SVR (busca aninhada)" repete a busca da '
                      'Tabela 6 nas amostras do tamanho do Pará. IC95 por reamostragem de safras; ganho detectado '
                      'é IC95 acima de zero. Tamanho do Pará: 38 municípios com as mesmas safras dos municípios '
                      f'paraenses. Repetição do Pará: injetada até {ALVO_REPETICAO}% dos pares.'),
             'Pará': {'registros': int(len(pa)), 'municipios': int(pa.municipio.nunique()),
                      'repeticao_%': round(taxa_de_repeticao(pa.municipio.values, y_pa), 1),
                      'modelos': mede(m, pa, y_pa, y_pa, aninhado=True)}}
    print('Pará', json.dumps(saida['Pará']['modelos'], ensure_ascii=False), flush=True)
    sementes = np.random.SeedSequence(SEED)
    # 'spawn': um processo que herda por fork o OpenMP já iniciado pelo XGBoost trava no primeiro ajuste
    with get_context('spawn').Pool(processos) as pool:
        for uf in ufs:
            saida[uf] = {}
            for celula, r in (('base inteira, repetição do estado', 1),
                              ('base inteira, repetição do Pará', n_int),
                              ('tamanho do Pará, repetição do estado', n),
                              ('tamanho do Pará, repetição do Pará', n)):
                t0 = time.time()
                tarefas = [(uf, celula, s) for s in sementes.spawn(r)]
                saida[uf][celula] = resume(pool.map(replica, tarefas, chunksize=1))
                print(f'{uf} | {celula} ({r} réplicas, {time.time() - t0:.0f} s): '
                      + '; '.join(f"{k} {v['ganho_mediano']:+.3f} ({v['replicas_com_ganho_detectado_%']:.0f}%)"
                                  for k, v in saida[uf][celula]['modelos'].items()), flush=True)
                with open(os.path.join(AQUI, 'tamanho_ou_repeticao.json'), 'w', encoding='utf-8') as f:
                    json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main(sys.argv[1:])
