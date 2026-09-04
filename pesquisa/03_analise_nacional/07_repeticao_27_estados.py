# -*- coding: utf-8 -*-
"""
Taxa de repetição da PAM para a soja nas 27 unidades da federação.

O artigo sobre a repetição mede a taxa no Pará e a compara com os sete estados
consolidados da base de von Bloh et al. (2023). A comparação sustenta o achado,
mas deixa o escopo estreito: sete estados de um recorte de terceiro, com janela
temporal distinta da paraense. Este script refaz a medida sobre a fonte
primária — a tabela 5457 do SIDRA —, para todos os municípios do país e todas as
safras disponíveis, de modo que Pará e demais estados sejam medidos pelo mesmo
instrumento e no mesmo período.

Baixa duas variáveis: o rendimento médio (112), que é o alvo da medida, e a área
plantada (216), que permite repetir o gradiente por porte observado no Pará.

O denominador da taxa é o par de safras consecutivas, nunca o registro. A
distinção importa: um município com n safras oferece n-1 pares, e dividir pelos
n registros dilui a taxa em cada estado de forma desigual, conforme o quanto
cada um tem de séries curtas.

Uso:  python 07_repeticao_27_estados.py            # baixa, analisa e grava
      python 07_repeticao_27_estados.py --conferir # refaz a análise do CSV local
"""
import json
import os
import sys
import time
from datetime import date

import numpy as np
import pandas as pd
import requests

RAIZ = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(RAIZ, 'pam_soja_municipios.csv')
SAIDA = os.path.join(RAIZ, 'repeticao_27_estados.json')

API = 'https://apisidra.ibge.gov.br/values/t/5457/n6/all/v/{var}/p/{ano}/c782/40124'
ANO_INI, ANO_FIM = 2001, 2024
VARIAVEIS = {'112': 'rendimento_kg_ha', '216': 'area_plantada_ha'}
PERMUTACOES = 2000
SEED = 42
MIN_PARES = 30          # abaixo disso a taxa estadual é ruído; entra na tabela sem ranque

UF = {
    11: ('RO', 'Rondônia'), 12: ('AC', 'Acre'), 13: ('AM', 'Amazonas'),
    14: ('RR', 'Roraima'), 15: ('PA', 'Pará'), 16: ('AP', 'Amapá'),
    17: ('TO', 'Tocantins'), 21: ('MA', 'Maranhão'), 22: ('PI', 'Piauí'),
    23: ('CE', 'Ceará'), 24: ('RN', 'Rio Grande do Norte'), 25: ('PB', 'Paraíba'),
    26: ('PE', 'Pernambuco'), 27: ('AL', 'Alagoas'), 28: ('SE', 'Sergipe'),
    29: ('BA', 'Bahia'), 31: ('MG', 'Minas Gerais'), 32: ('ES', 'Espírito Santo'),
    33: ('RJ', 'Rio de Janeiro'), 35: ('SP', 'São Paulo'), 41: ('PR', 'Paraná'),
    42: ('SC', 'Santa Catarina'), 43: ('RS', 'Rio Grande do Sul'),
    50: ('MS', 'Mato Grosso do Sul'), 51: ('MT', 'Mato Grosso'),
    52: ('GO', 'Goiás'), 53: ('DF', 'Distrito Federal'),
}


# ───────────────────────────────── coleta ─────────────────────────────────
def baixa_ano_variavel(ano, var, tentativas=3):
    """Uma requisição ao SIDRA. Devolve DataFrame com código, nome e valor."""
    url = API.format(var=var, ano=ano)
    for n in range(tentativas):
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            dados = r.json()
        except Exception as erro:
            if n == tentativas - 1:
                print(f'  {ano}/{var}: falhou ({erro})')
                return None
            time.sleep(2 ** n)
            continue
        if len(dados) < 2:                       # só o cabeçalho: ano sem dado
            return None
        d = pd.DataFrame(dados[1:])[['D1C', 'D1N', 'V']]
        d.columns = ['cod_ibge7', 'nome', VARIAVEIS[var]]
        d[VARIAVEIS[var]] = pd.to_numeric(d[VARIAVEIS[var]], errors='coerce')
        d['ano'] = ano
        return d.dropna(subset=[VARIAVEIS[var]])
    return None


def coleta():
    """Percorre anos e variáveis. O SIDRA limita 50.000 valores por requisição."""
    print(f'Baixando a tabela 5457 do SIDRA, {ANO_INI}-{ANO_FIM}...')
    por_variavel = {}
    for var, nome in VARIAVEIS.items():
        partes = []
        for ano in range(ANO_INI, ANO_FIM + 1):
            d = baixa_ano_variavel(ano, var)
            if d is not None:
                partes.append(d)
                print(f'  {nome} {ano}: {len(d)} municípios')
            time.sleep(1)
        if not partes:
            raise SystemExit(f'nenhum dado obtido para {nome}')
        por_variavel[nome] = pd.concat(partes, ignore_index=True)

    df = por_variavel['rendimento_kg_ha'].merge(
        por_variavel['area_plantada_ha'].drop(columns=['nome']),
        on=['cod_ibge7', 'ano'], how='left')
    df['cod_ibge7'] = df.cod_ibge7.astype(str)
    df['uf_cod'] = df.cod_ibge7.str[:2].astype(int)
    df['uf'] = df.uf_cod.map(lambda c: UF.get(c, ('??', '?'))[0])
    df = df[df.rendimento_kg_ha > 0]
    return df.sort_values(['cod_ibge7', 'ano']).reset_index(drop=True)


# ──────────────────────────────── medida ────────────────────────────────
def pares_e_repetidos(df):
    """Conta pares de safras consecutivas e quantos repetem, por município."""
    total = repetidos = 0
    for _, d in df.groupby('cod_ibge7'):
        v = d.sort_values('ano').rendimento_kg_ha.values
        if len(v) < 2:
            continue
        total += len(v) - 1
        repetidos += int((np.diff(v) == 0).sum())
    return total, repetidos


def taxa(df):
    t, r = pares_e_repetidos(df)
    return (r / t * 100) if t else float('nan')


def teste_de_permutacao(df, rng):
    """Embaralha cada série municipal preservando suas duplicatas.

    O desenho é conservador de propósito: preservar a distribuição marginal
    mantém as repetições que o arredondamento já produz, de modo que o excesso
    observado não possa ser atribuído a valores redondos.
    """
    series = [d.sort_values('ano').rendimento_kg_ha.values
              for _, d in df.groupby('cod_ibge7')]
    series = [v for v in series if len(v) >= 2]
    total = sum(len(v) - 1 for v in series)
    nulos = np.empty(PERMUTACOES)
    for i in range(PERMUTACOES):
        rep = 0
        for v in series:
            w = v.copy()
            rng.shuffle(w)
            rep += int((np.diff(w) == 0).sum())
        nulos[i] = rep / total * 100
    return nulos


def tabela_de_pares(df):
    """Um registro por par de safras consecutivas, na mesma definição da taxa.

    Consecutivo aqui é adjacente na série do município, não no calendário: é o
    que a medida de pares_e_repetidos conta, e as duas precisam coincidir. Uma
    série com lacuna produz um par que salta o ano ausente; quantos são disso
    fica registrado em pares_com_lacuna, para que a escolha possa ser conferida.
    """
    d = df.sort_values(['cod_ibge7', 'ano']).copy()
    d['anterior'] = d.groupby('cod_ibge7').rendimento_kg_ha.shift()
    d['ano_anterior'] = d.groupby('cod_ibge7').ano.shift()
    pares = d[d.anterior.notna()].copy()
    pares['repetiu'] = pares.rendimento_kg_ha == pares.anterior
    pares['com_lacuna'] = pares.ano_anterior != pares.ano - 1
    return pares


def quartis_por_area(pares):
    """Gradiente por porte, com o par — e não o registro — no denominador.

    Dividir pelos registros dilui a taxa, porque a primeira safra de cada
    município entra no denominador sem ter par: no Pará isso levava 40,1% a
    36,4% e desfazia a monotonicidade do gradiente.
    """
    p = pares[pares.area_plantada_ha.notna()]
    if len(p) < 4:
        return {}
    q = p.groupby(pd.qcut(p.area_plantada_ha, 4,
                          labels=['Q1', 'Q2', 'Q3', 'Q4']), observed=True)
    return {str(k): {'taxa': round(float(g.repetiu.mean() * 100), 1), 'pares': int(len(g))}
            for k, g in q}


def analisa(df):
    rng = np.random.default_rng(SEED)
    fora = {}

    total, repetidos = pares_e_repetidos(df)
    nulos = teste_de_permutacao(df, rng)
    obs = repetidos / total * 100
    fora['brasil'] = {
        'municipios': int(df.cod_ibge7.nunique()), 'registros': int(len(df)),
        'pares': total, 'repetidos': repetidos, 'taxa': round(obs, 1),
        'h0_media': round(float(nulos.mean()), 1), 'h0_dp': round(float(nulos.std()), 1),
        'h0_max': round(float(nulos.max()), 1),
        'z': round(float((obs - nulos.mean()) / nulos.std()), 1),
        'permutacoes': PERMUTACOES,
        'nulos_acima_do_observado': int((nulos >= obs).sum()),
        'multiplos_de_100': round(float((df.rendimento_kg_ha % 100 == 0).mean() * 100), 1),
    }

    estados = {}
    for uf, d in df.groupby('uf'):
        t, r = pares_e_repetidos(d)
        cod = int(d.uf_cod.iloc[0])
        estados[uf] = {
            'nome': UF.get(cod, ('??', '?'))[1],
            'municipios': int(d.cod_ibge7.nunique()), 'registros': int(len(d)),
            'pares': t, 'repetidos': r,
            'taxa': round(r / t * 100, 1) if t else None,
            'multiplos_de_100': round(float((d.rendimento_kg_ha % 100 == 0).mean() * 100), 1),
            'amostra_suficiente': t >= MIN_PARES,
        }
    fora['estados'] = dict(sorted(estados.items(),
                                  key=lambda kv: -(kv[1]['taxa'] or -1)))

    pares = tabela_de_pares(df)
    assert len(pares) == total, 'as duas contagens de pares divergiram'
    fora['brasil']['pares_com_lacuna'] = int(pares.com_lacuna.sum())
    fora['quartis_area'] = quartis_por_area(pares)
    fora['periodo'] = [int(df.ano.min()), int(df.ano.max())]
    fora['gerado_em'] = date.today().isoformat()
    fora['fonte'] = 'IBGE/SIDRA, tabela 5457, variáveis 112 e 216, soja em grão'
    return fora


# ───────────────────────────────── saída ─────────────────────────────────
def imprime(r):
    b = r['brasil']
    print(f"\nBrasil: {b['municipios']} municípios, {b['registros']} registros, "
          f"{r['periodo'][0]}-{r['periodo'][1]}")
    print(f"  pares {b['pares']} | repetidos {b['repetidos']} | taxa {b['taxa']}%")
    print(f"  H0 {b['h0_media']}% ± {b['h0_dp']} (máx {b['h0_max']}%) | "
          f"z = {b['z']} | {b['nulos_acima_do_observado']} de {b['permutacoes']} ≥ observado")
    print(f"  múltiplos de 100 kg/ha: {b['multiplos_de_100']}%\n")
    print(f"{'UF':4s} {'taxa':>7s} {'pares':>7s} {'mun':>5s} {'mult100':>8s}")
    for uf, e in r['estados'].items():
        marca = '' if e['amostra_suficiente'] else '  (amostra pequena)'
        taxa_ = f"{e['taxa']}%" if e['taxa'] is not None else '—'
        print(f"{uf:4s} {taxa_:>7s} {e['pares']:>7d} {e['municipios']:>5d} "
              f"{e['multiplos_de_100']:>7.1f}%{marca}")
    if r['quartis_area']:
        print('\nquartis de área plantada:')
        for k, v in r['quartis_area'].items():
            print(f"  {k}: {v['taxa']}%  ({v['pares']} pares)")


def main():
    conferir = '--conferir' in sys.argv

    if conferir:
        if not os.path.exists(CSV):
            raise SystemExit(f'{CSV} não existe — rode sem --conferir para baixar.')
        df = pd.read_csv(CSV, dtype={'cod_ibge7': str})
        print(f'Lendo {CSV}: {len(df)} registros')
    else:
        df = coleta()
        df.to_csv(CSV, index=False)
        print(f'\ngravado em {CSV}: {len(df)} registros')

    r = analisa(df)
    imprime(r)

    if not conferir:
        with open(SAIDA, 'w', encoding='utf-8') as f:
            json.dump(r, f, indent=2, ensure_ascii=False)
        print(f'\ngravado em {SAIDA}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
