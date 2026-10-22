# -*- coding: utf-8 -*-
"""
Custo computacional e escalabilidade dos quatro modelos do estudo nacional.

As seções 4.4 e 4.5 da dissertação treinam com uma subamostra de 7.000
registros por safra (5.000 para o SVR). Este script mede o que essa redução
economiza: ajusta cada modelo, com os hiperparâmetros de 04_avalia_ajustado.py,
em tamanhos crescentes de treino até a base completa, nas cinco safras de teste
(2016-2020), e registra tempo de ajuste, tempo de CPU, tempo de predição, pico
de memória e as previsões.

Cada ajuste roda num processo próprio. O pico de memória vem de ru_maxrss, que
só cresce dentro de um processo: medido em sequência no mesmo interpretador, o
pico de um ajuste esconderia o do seguinte. Por isso a medição tem duas etapas,
mantidas separadas: --preparar lê a base uma vez e grava results/custo/base.npz,
e cada --ajuste carrega só esse arquivo, ajusta e imprime uma linha JSON.

As subamostras são as de 01_treina_modelos.py e 04_avalia_ajustado.py (semente
1000 + safra), de modo que N = 7.000 reproduz a Tabela 3 para RF, XGBoost e MLP.
O SVR com N = 5.000 dá RMSE 460,8 em vez de 460,7 (R² 0,425 nos dois): aqui o
padronizador é ajustado sobre os 5.000 registros, e em 04_ sobre os 7.000 antes
do corte.

Os registros versionados ao lado deste script foram gerados numa máquina virtual
com 2 vCPUs Intel Xeon, 7 GB de RAM, Python 3.13, scikit-learn 1.8.0 e XGBoost
3.4.1. Tempo e memória dependem da máquina; R² e RMSE, não.

  custo_medicoes.jsonl  um ajuste por linha, 2 threads, 9 tamanhos x 4 modelos x 5 safras
  custo_escala.jsonl    base completa com 1 thread, para o ganho com 2 núcleos
  custo_agregado.csv    agregado por modelo e tamanho (saída de --analisar)

Os registros guardam as previsões, mas não a produtividade observada: ela é da
base de von Bloh et al. (2023), que não é redistribuída. --analisar a relê de
data/data_cast.csv, na mesma ordem em que o ajuste a usou.

Uso:  python 10_mede_custo_escalabilidade.py              # mede tudo (cerca de meia hora) e agrega
      python 10_mede_custo_escalabilidade.py --analisar   # agrega os registros versionados
      python 10_mede_custo_escalabilidade.py --analisar results/custo
      python 10_mede_custo_escalabilidade.py --figura     # figura a partir de custo_agregado.csv

Requer data/data_cast.csv (00_baixa_dados.py) para medir e para agregar.
"""
import json
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(RAIZ, 'data', 'data_cast.csv')
TRABALHO = os.path.join(RAIZ, 'results', 'custo')
NPZ = os.path.join(TRABALHO, 'base.npz')
MEDICOES, ESCALA, AGREGADO = 'custo_medicoes.jsonl', 'custo_escala.jsonl', 'custo_agregado.csv'

MODELOS = ['SVR', 'Random Forest', 'XGBoost', 'MLP']
SAFRAS_TESTE = [2016, 2017, 2018, 2019, 2020]
TAMANHOS = [1000, 2000, 4000, 5000, 7000, 10000, 14000, 18000]
BASE_COMPLETA = 99999      # maior que qualquer treino: usa todas as safras restantes
THREADS = 2
SEMENTE_SUB = 1000         # mesma de 01_treina_modelos.py e 04_avalia_ajustado.py
FORA = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']


def preparar():
    """Lê a base uma vez e grava as matrizes que cada ajuste carrega."""
    import numpy as np
    import pandas as pd
    df = pd.read_csv(CSV)
    feat = [c for c in df.columns if c not in FORA and df[c].dtype != 'object']
    X = df[feat].fillna(df[feat].median()).values.astype(np.float64)
    os.makedirs(TRABALHO, exist_ok=True)
    np.savez(NPZ, X=X, T=df.YIELD_TREND.values.astype(float),
             A=df.YIELD_TREND_CORRECTED.values.astype(float), anos=df.HARVESTED.values)
    print(f'base.npz: {X.shape[0]} registros, {len(feat)} preditores')


def ajuste(nome, N, safra, threads):
    """Um ajuste, medido; imprime uma linha JSON. Roda em processo próprio."""
    # o número de threads das bibliotecas numéricas tem de ser fixado antes de
    # importá-las
    for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[var] = str(threads)
    import importlib.util
    import resource
    import warnings
    warnings.filterwarnings('ignore')
    import numpy as np
    from sklearn.base import clone
    from sklearn.preprocessing import StandardScaler

    # os hiperparâmetros são os de 04_avalia_ajustado.py, importados e não
    # recopiados, para que a medição não se descole da Tabela 3
    spec = importlib.util.spec_from_file_location(
        'avalia_ajustado', os.path.join(RAIZ, '04_avalia_ajustado.py'))
    avalia = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(avalia)
    mdl = clone(avalia.AJUSTADOS[nome])
    if 'n_jobs' in mdl.get_params():
        mdl.set_params(n_jobs=threads)

    b = np.load(NPZ)
    X, T, A, anos = b['X'], b['T'], b['A'], b['anos']
    treino = np.where(anos != safra)[0]
    idx = treino if N >= len(treino) else \
        np.random.RandomState(SEMENTE_SUB + safra).choice(treino, N, replace=False)
    te = anos == safra
    Xtr, Xte, atr = X[idx], X[te], A[idx]
    if nome in avalia.PRECISA_ESCALA:
        esc = StandardScaler().fit(Xtr)
        Xtr, Xte = esc.transform(Xtr), esc.transform(Xte)

    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    t0, cpu0 = time.perf_counter(), time.process_time()
    mdl.fit(Xtr, atr)
    fit_s, cpu_s = time.perf_counter() - t0, time.process_time() - cpu0
    rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    t1 = time.perf_counter()
    pred = mdl.predict(Xte) + T[te]
    pred_s = time.perf_counter() - t1

    extra = {}
    if nome == 'SVR':
        extra['n_sv'] = int(len(mdl.support_))
    if nome == 'MLP':
        extra['iter'] = int(mdl.n_iter_)
    print(json.dumps(dict(modelo=nome, N=int(len(idx)), ty=safra, thr=threads,
                          fit_s=fit_s, cpu_s=cpu_s, pred_s=pred_s,
                          rss_base_mb=rss0 / 1024, rss_pico_mb=rss1 / 1024,
                          delta_mb=(rss1 - rss0) / 1024, p=pred.tolist(), **extra)))


def medir():
    """Todos os ajustes, cada um num processo isolado."""
    preparar()

    def roda(nome, N, safra, threads, destino):
        cmd = [sys.executable, '-I', os.path.abspath(__file__), '--ajuste',
               nome, str(N), str(safra), str(threads)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f'FALHA {nome} {N} {safra}:\n{r.stderr}', file=sys.stderr)
            return
        with open(destino, 'a', encoding='utf-8') as f:
            f.write(r.stdout)

    medicoes, escala = os.path.join(TRABALHO, MEDICOES), os.path.join(TRABALHO, ESCALA)
    for arq in (medicoes, escala):
        open(arq, 'w').close()
    for N in TAMANHOS + [BASE_COMPLETA]:
        for nome in MODELOS:
            for safra in SAFRAS_TESTE:
                roda(nome, N, safra, THREADS, medicoes)
            print(f'{time.strftime("%H:%M:%S")} {nome} N={N}', flush=True)
    for nome in MODELOS:
        for safra in SAFRAS_TESTE:
            roda(nome, BASE_COMPLETA, safra, 1, escala)
        print(f'{time.strftime("%H:%M:%S")} escala {nome}', flush=True)
    analisar(TRABALHO)


def observados():
    """Produtividade observada por safra, na ordem em que o ajuste a usou."""
    import pandas as pd
    if not os.path.exists(CSV):
        sys.exit('falta data/data_cast.csv: rode antes python 00_baixa_dados.py')
    df = pd.read_csv(CSV, usecols=['YIELD', 'HARVESTED'])
    return {ty: df.YIELD[df.HARVESTED == ty].values.astype(float) for ty in SAFRAS_TESTE}


def analisar(pasta=RAIZ):
    import numpy as np
    import pandas as pd
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    obs = observados()
    linhas = [json.loads(l) for l in open(os.path.join(pasta, MEDICOES), encoding='utf-8')]
    df = pd.DataFrame(linhas)
    # a base completa tem tamanho diferente em cada safra; entra como um grupo só
    grupo_N = df.N.where(df.N < 20000, -1)
    out = []
    for (m, _), g in df.groupby(['modelo', grupo_N]):
        y = np.concatenate([obs[ty] for ty in g.ty])
        p = np.concatenate([np.array(a) for a in g.p])
        out.append(dict(
            modelo=m, N=int(g.N.mean()), folds=len(g),
            fit_med=g.fit_s.median(), fit_tot=g.fit_s.sum(), cpu_tot=g.cpu_s.sum(),
            pred_tot=g.pred_s.sum(), mem_delta_max=g.delta_mb.max(),
            mem_pico_max=g.rss_pico_mb.max(),
            rmse=np.sqrt(mean_squared_error(y, p)), mae=mean_absolute_error(y, p),
            r2=r2_score(y, p),
            nsv=g['n_sv'].median() if 'n_sv' in g else None,
            it=g['iter'].median() if 'iter' in g else None))
    A = pd.DataFrame(out).sort_values(['modelo', 'N'])
    pd.set_option('display.width', 250)
    pd.set_option('display.max_columns', 30)
    print(A.round(3).to_string(index=False))

    print('\nexpoente empírico do tempo de ajuste (log tempo ~ b log N, N >= 2.000):')
    for m, g in A.groupby('modelo'):
        g = g[g.N >= 2000]
        if len(g) >= 3:
            b = np.polyfit(np.log(g.N), np.log(g.fit_med), 1)[0]
            print(f'  {m}: {b:.2f}')

    completa = A[A.N >= 20000].set_index('modelo')
    print('\ntempo de ajuste somado nas 5 safras, base completa: '
          f'{completa.fit_tot.sum():.0f} s')
    reduzida = A[((A.modelo == 'SVR') & (A.N == 5000)) |
                 ((A.modelo != 'SVR') & (A.N == 7000))]
    print(f'tempo de ajuste somado nas 5 safras, configuração da dissertação: '
          f'{reduzida.fit_tot.sum():.0f} s')

    arq_escala = os.path.join(pasta, ESCALA)
    if os.path.exists(arq_escala):
        E = pd.DataFrame([json.loads(l) for l in open(arq_escala, encoding='utf-8')])
        um = E.groupby('modelo').fit_s.sum()
        print('\nbase completa, tempo de ajuste somado (s) e ganho com 2 núcleos:')
        for m in MODELOS:
            if m in um and m in completa.index:
                print(f'  {m:14s} 1 thread {um[m]:7.1f} | 2 threads '
                      f'{completa.fit_tot[m]:7.1f} | {um[m] / completa.fit_tot[m]:.2f}x')

    destino = os.path.join(pasta, AGREGADO)
    A.to_csv(destino, index=False)
    print(f'\ngravado em {os.path.relpath(destino, RAIZ)}')


def figura():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import pandas as pd
    plt.rcParams.update({'font.family': 'serif', 'font.size': 8.5, 'mathtext.fontset': 'stix',
                         'axes.spines.top': False, 'axes.spines.right': False})
    A = pd.read_csv(os.path.join(RAIZ, AGREGADO))
    estilo = {'SVR': ('k', 'o', '-'), 'Random Forest': ('0.35', 's', '--'),
              'XGBoost': ('0.55', '^', '-.'), 'MLP': ('0.7', 'D', ':')}
    fig, (a, b) = plt.subplots(1, 2, figsize=(6.3, 2.45))
    for m, (c, mk, ls) in estilo.items():
        g = A[A.modelo == m].sort_values('N')
        a.plot(g.N, g.fit_med, ls=ls, marker=mk, ms=3.2, color=c, lw=1.1, label=m)
        b.plot(g.N, g.r2, ls=ls, marker=mk, ms=3.2, color=c, lw=1.1, label=m)
    xt = [1000, 2000, 5000, 10000, 23617]
    for ax in (a, b):
        ax.set_xscale('log')
        ax.set_xticks(xt)
        ax.set_xticklabels(['1 mil', '2 mil', '5 mil', '10 mil', '23,6 mil'])
        ax.minorticks_off()
        ax.set_xlabel('Registros de treino ($N$)')
    a.set_yscale('log')
    a.set_yticks([0.05, 0.1, 1, 10, 30])
    a.set_yticklabels(['0,05', '0,1', '1', '10', '30'])
    a.set_ylabel('Tempo de ajuste por safra (s)')
    a.text(14500, 7.2, 'SVR: $N^{2{,}0}$', fontsize=7.5)
    a.text(2500, 0.25, 'RF: $N^{1{,}0}$', fontsize=7.5)
    a.text(1050, 1.55, 'XGBoost: $N^{0{,}2}$', fontsize=7.5)
    a.set_title('(a) Tempo de ajuste', fontsize=8.5)
    b.set_ylabel('R² (2016–2020)')
    b.set_title('(b) Acurácia', fontsize=8.5)
    marcas = [0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45]
    b.set_yticks(marcas)
    b.set_yticklabels([f'{v:.2f}'.replace('.', ',') for v in marcas])
    b.set_ylim(0.12, 0.45)
    h, l = a.get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=7.5, loc='lower center', ncol=4,
               bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(w_pad=1.5, rect=(0, 0.08, 1, 1))
    os.makedirs(TRABALHO, exist_ok=True)
    destino = os.path.join(TRABALHO, 'fig_custo_escalabilidade.png')
    fig.savefig(destino, dpi=300)
    print(f'gravado em {os.path.relpath(destino, RAIZ)}')


def main():
    args = sys.argv[1:]
    if args[:1] == ['--preparar']:
        preparar()
    elif args[:1] == ['--ajuste']:
        nome, N, safra, threads = args[1], int(args[2]), int(args[3]), int(args[4])
        ajuste(nome, N, safra, threads)
    elif args[:1] == ['--analisar']:
        analisar(os.path.abspath(args[1]) if len(args) > 1 else RAIZ)
    elif args[:1] == ['--figura']:
        figura()
    else:
        medir()


if __name__ == '__main__':
    main()
