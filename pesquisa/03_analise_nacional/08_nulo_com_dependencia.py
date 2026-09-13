# -*- coding: utf-8 -*-
"""
Teste de permutação que preserva a dependência temporal das séries.

O nulo de 07_repeticao_27_estados.py embaralha os valores dentro de cada
município. Isso preserva a distribuição marginal — e portanto o arredondamento
e as duplicatas que ele já produz —, mas destrói a ordem. Uma série real de
produtividade tem tendência e autocorrelação: safras vizinhas se parecem mais
do que safras sorteadas. Contra um nulo que ignora isso, parte do excesso
observado poderia ser mero efeito da suavidade temporal, e não de falha de
medida. A objeção é legítima e este script a responde.

O substituto usado é o IAAFT (iterative amplitude adjusted Fourier transform),
padrão em análise de séries não lineares. Ele itera entre duas projeções:

  1. impõe o espectro de potência da série original, o que fixa a função de
     autocorrelação — toda a dependência temporal linear;
  2. impõe a distribuição marginal original por ordenação, o que devolve os
     valores exatos da série, com o mesmo arredondamento e as mesmas
     duplicatas.

O resultado é uma série com a mesma autocorrelação e exatamente os mesmos
valores da observada, mas com as fases embaralhadas. Se a taxa de repetição
observada continuar muito acima desse nulo, nem a suavidade temporal nem o
arredondamento a explicam — e sobra a hipótese de que os valores não foram
medidos safra a safra.

O script também conta platôs: sequências de safras consecutivas no mesmo valor.
Autocorrelação alta produz valores próximos, não idênticos, e por isso a cauda
da distribuição de comprimento é o discriminante mais forte que existe aqui.

Uso:  python 08_nulo_com_dependencia.py
      python 08_nulo_com_dependencia.py --replicas 500
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(RAIZ, 'pam_soja_municipios.csv')
SAIDA = os.path.join(RAIZ, 'nulo_com_dependencia.json')

REPLICAS = 200
ITERACOES = 100
SEED = 42
RHOS = (0.3, 0.5, 0.7, 0.9)
MIN_SAFRAS = 6      # abaixo disso o espectro de uma série é curto demais
                    # para o IAAFT dizer alguma coisa sobre autocorrelação


def series_por_municipio(df):
    """Séries ordenadas por ano, só as longas o bastante para o substituto."""
    saida = []
    for _, d in df.groupby('cod_ibge7'):
        v = d.sort_values('ano').rendimento_kg_ha.values.astype(float)
        if len(v) >= MIN_SAFRAS:
            saida.append(v)
    return saida


def repeticoes(M):
    """Pares consecutivos idênticos e total de pares, numa matriz de séries."""
    d = np.diff(M, axis=1)
    return int((d == 0).sum()), int(d.size)


def platos(M, minimo=2):
    """Quantas sequências de `minimo` ou mais safras no mesmo valor.

    Um platô de k safras contém k-1 pares repetidos, mas conta como um platô
    só: é a extensão da sequência que distingue série carregada de série
    autocorrelacionada, não a contagem de pares.
    """
    total = 0
    for v in M:
        corrida = 1
        for a, b in zip(v[:-1], v[1:]):
            if a == b:
                corrida += 1
            else:
                if corrida >= minimo:
                    total += 1
                corrida = 1
        if corrida >= minimo:
            total += 1
    return total


def autocorrelacao_lag1(M):
    """Autocorrelação média de defasagem 1, para conferir o que o nulo preserva."""
    saida = []
    for v in M:
        x, y = v[:-1], v[1:]
        if x.std() > 0 and y.std() > 0:
            saida.append(float(np.corrcoef(x, y)[0, 1]))
    return float(np.mean(saida)) if saida else float('nan')


def iaaft(M, rng, iteracoes=ITERACOES):
    """Substitutos IAAFT para uma matriz de séries de mesmo comprimento.

    Vetorizado sobre as linhas: cada iteração é uma FFT da matriz inteira, o
    que torna viável gerar centenas de réplicas para milhares de municípios.
    """
    n = M.shape[1]
    ordenada = np.sort(M, axis=1)
    amplitude = np.abs(np.fft.rfft(M, axis=1))
    # ponto de partida: uma permutação aleatória de cada série
    idx = np.argsort(rng.random(M.shape), axis=1)
    S = np.take_along_axis(M, idx, axis=1)
    for _ in range(iteracoes):
        fase = np.angle(np.fft.rfft(S, axis=1))
        S = np.fft.irfft(amplitude * np.exp(1j * fase), n=n, axis=1)
        postos = np.argsort(np.argsort(S, axis=1), axis=1)
        S = np.take_along_axis(ordenada, postos, axis=1)
    return S


def permutacao_simples(M, rng):
    """O nulo antigo, para a comparação lado a lado."""
    idx = np.argsort(rng.random(M.shape), axis=1)
    return np.take_along_axis(M, idx, axis=1)


def ar1_com_marginal(M, rho, rng):
    """Séries AR(1) de autocorrelação imposta, mapeadas à marginal observada.

    O IAAFT herda parte da autocorrelação, não toda: a etapa que devolve os
    valores originais por ordenação estraga um pouco o espectro, e com dados
    tão discretizados quanto estes a perda é visível. Em vez de argumentar que
    a perda é pequena, este nulo faz o contrário — impõe uma autocorrelação
    escolhida, inclusive bem acima da observada, e pergunta quanta repetição
    uma série tão suave assim produziria.

    O mapeamento por posto devolve exatamente os valores da série original, com
    o mesmo arredondamento e as mesmas duplicatas. A repetição que sobra vem da
    única fonte que resta: postos vizinhos caindo no mesmo grupo de empates.
    """
    n = M.shape[1]
    ruido = rng.standard_normal(M.shape)
    z = np.empty_like(ruido)
    z[:, 0] = ruido[:, 0]
    escala = np.sqrt(1 - rho ** 2)
    for k in range(1, n):
        z[:, k] = rho * z[:, k - 1] + escala * ruido[:, k]
    postos = np.argsort(np.argsort(z, axis=1), axis=1)
    return np.take_along_axis(np.sort(M, axis=1), postos, axis=1)


def por_comprimento(series):
    """Agrupa as séries por comprimento, para operar em matriz."""
    grupos = {}
    for v in series:
        grupos.setdefault(len(v), []).append(v)
    return {k: np.array(v) for k, v in sorted(grupos.items())}


def analisa(df, replicas):
    series = series_por_municipio(df)
    grupos = por_comprimento(series)
    rng = np.random.default_rng(SEED)

    rep_obs = tot_obs = 0
    for M in grupos.values():
        r, t = repeticoes(M)
        rep_obs += r
        tot_obs += t
    taxa_obs = rep_obs / tot_obs * 100

    print(f'{len(series):,} municípios com ao menos {MIN_SAFRAS} safras')
    print(f'{tot_obs:,} pares, {rep_obs:,} repetidos, taxa observada {taxa_obs:.1f}%')
    print(f'autocorrelação de defasagem 1, observada: '
          f'{np.mean([autocorrelacao_lag1(M) for M in grupos.values()]):.3f}')
    print(f'\nGerando {replicas} réplicas sob cada nulo…')

    resultados = {}
    for nome, gera in (('permutacao', permutacao_simples), ('iaaft', iaaft)):
        t0 = time.time()
        taxas = np.empty(replicas)
        p2 = np.empty(replicas)
        p3 = np.empty(replicas)
        p4 = np.empty(replicas)
        acf = []
        for i in range(replicas):
            rep = tot = 0
            n2 = n3 = n4 = 0
            for M in grupos.values():
                S = gera(M, rng)
                r, t = repeticoes(S)
                rep += r
                tot += t
                n2 += platos(S, 2)
                n3 += platos(S, 3)
                n4 += platos(S, 4)
                if i == 0:
                    acf.append(autocorrelacao_lag1(S))
            taxas[i] = rep / tot * 100
            p2[i], p3[i], p4[i] = n2, n3, n4
        resultados[nome] = {
            'taxa_media': round(float(taxas.mean()), 2),
            'taxa_dp': round(float(taxas.std()), 3),
            'taxa_max': round(float(taxas.max()), 2),
            'z': round(float((taxa_obs - taxas.mean()) / taxas.std()), 1),
            'replicas_acima_do_observado': int((taxas >= taxa_obs).sum()),
            'autocorrelacao_lag1': round(float(np.mean(acf)), 3),
            'platos_2_ou_mais': round(float(p2.mean()), 1),
            'platos_3_ou_mais': round(float(p3.mean()), 1),
            'platos_4_ou_mais': round(float(p4.mean()), 1),
            'segundos': round(time.time() - t0),
        }
        r = resultados[nome]
        print(f'  {nome:11s} taxa {r["taxa_media"]:.2f}% ± {r["taxa_dp"]:.3f} '
              f'| z = {r["z"]} | acf1 = {r["autocorrelacao_lag1"]:+.3f} '
              f'| {r["segundos"]}s')

    print('\nAR(1) com autocorrelação imposta, acima da observada:')
    for rho in RHOS:
        taxas = np.empty(replicas)
        acf = []
        for i in range(replicas):
            rep = tot = 0
            for M in grupos.values():
                S = ar1_com_marginal(M, rho, rng)
                r_, t_ = repeticoes(S)
                rep += r_
                tot += t_
                if i == 0:
                    acf.append(autocorrelacao_lag1(S))
            taxas[i] = rep / tot * 100
        resultados[f'ar1_rho_{rho:.1f}'] = {
            'rho_alvo': rho,
            'taxa_media': round(float(taxas.mean()), 2),
            'taxa_dp': round(float(taxas.std()), 3),
            'taxa_max': round(float(taxas.max()), 2),
            'z': round(float((taxa_obs - taxas.mean()) / taxas.std()), 1),
            'replicas_acima_do_observado': int((taxas >= taxa_obs).sum()),
            'autocorrelacao_lag1': round(float(np.mean(acf)), 3),
        }
        r = resultados[f'ar1_rho_{rho:.1f}']
        print(f'  rho = {rho:.1f}   taxa {r["taxa_media"]:5.2f}% ± {r["taxa_dp"]:.3f} '
              f'| z = {r["z"]:6.1f} | acf1 obtida = {r["autocorrelacao_lag1"]:+.3f}')

    obs = {'taxa': round(taxa_obs, 2), 'pares': tot_obs, 'repetidos': rep_obs,
           'municipios': len(series),
           'autocorrelacao_lag1': round(
               float(np.mean([autocorrelacao_lag1(M) for M in grupos.values()])), 3),
           'platos_2_ou_mais': platos_total(grupos, 2),
           'platos_3_ou_mais': platos_total(grupos, 3),
           'platos_4_ou_mais': platos_total(grupos, 4),
           'plato_mais_longo': max(maior_plato(M) for M in grupos.values())}
    return {'observado': obs, 'nulos': resultados,
            'replicas': replicas, 'iteracoes_iaaft': ITERACOES,
            'semente': SEED, 'min_safras': MIN_SAFRAS}


def platos_total(grupos, minimo):
    return sum(platos(M, minimo) for M in grupos.values())


def maior_plato(M):
    maior = 1
    for v in M:
        corrida = 1
        for a, b in zip(v[:-1], v[1:]):
            corrida = corrida + 1 if a == b else 1
            maior = max(maior, corrida)
    return maior


def imprime(r):
    o, n = r['observado'], r['nulos']
    print('\n' + '─' * 68)
    print('Platôs — sequências de safras consecutivas no mesmo valor')
    print(f'{"":22s}{"observado":>12s}{"permutação":>14s}{"IAAFT":>12s}')
    for k, rot in (('platos_2_ou_mais', '2 safras ou mais'),
                   ('platos_3_ou_mais', '3 safras ou mais'),
                   ('platos_4_ou_mais', '4 safras ou mais')):
        print(f'  {rot:20s}{o[k]:>12,}{n["permutacao"][k]:>14,.1f}{n["iaaft"][k]:>12,.1f}')
    print(f'  {"platô mais longo":20s}{o["plato_mais_longo"]:>12,}')
    print('─' * 68)


def main():
    replicas = REPLICAS
    if '--replicas' in sys.argv:
        replicas = int(sys.argv[sys.argv.index('--replicas') + 1])
    df = pd.read_csv(CSV)
    r = analisa(df, replicas)
    imprime(r)
    with open(SAIDA, 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    print(f'\ngravado em {os.path.basename(SAIDA)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
