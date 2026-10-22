# -*- coding: utf-8 -*-
"""
Anomalias da temperatura do mar no Atlântico tropical norte (TNA) e sul (TSA).

O gradiente TNA − TSA desloca a Zona de Convergência Intertropical e, com ela,
a chuva no norte do Brasil na estação chuvosa, que é o ciclo da soja no Pará.
Fonte: NOAA PSL, séries mensais de Enfield et al. (1999), baseadas no HadISST.

Uso:  python coleta_atlantico.py
Saída: ../dados/atlantico_tna_tsa.csv (ano, mes, tna, tsa)
"""
import io
import os
import time

import pandas as pd
import requests

SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dados')
FONTES = {'tna': ['https://psl.noaa.gov/data/correlation/tna.data',
                  'https://www.psl.noaa.gov/data/correlation/tna.data'],
          'tsa': ['https://psl.noaa.gov/data/correlation/tsa.data',
                  'https://www.psl.noaa.gov/data/correlation/tsa.data']}


def le_psl(texto):
    """Formato PSL: 1ª linha 'ano_ini ano_fim', depois 'ano v1 ... v12'; -99.99 é falta."""
    linhas = texto.strip().splitlines()
    ini, fim = map(int, linhas[0].split()[:2])
    reg = []
    for ln in linhas[1:]:
        p = ln.split()
        if len(p) == 13 and p[0].isdigit() and ini <= int(p[0]) <= fim:
            reg += [(int(p[0]), m + 1, float(v)) for m, v in enumerate(p[1:])]
    s = pd.DataFrame(reg, columns=['ano', 'mes', 'valor'])
    return s[s.valor > -99]


def baixa(urls):
    for url in urls:
        for i in range(3):
            try:
                r = requests.get(url, timeout=60)
                r.raise_for_status()
                return le_psl(r.text), url
            except requests.RequestException as e:
                print(f'  {url}: {type(e).__name__}', flush=True)
                time.sleep(10)
    raise RuntimeError('nenhuma fonte respondeu')


def main():
    os.makedirs(SAIDA, exist_ok=True)
    series = []
    for nome, urls in FONTES.items():
        s, url = baixa(urls)
        print(f'{nome}: {len(s)} meses de {url}, último {s.ano.iloc[-1]}-{s.mes.iloc[-1]:02d}', flush=True)
        series.append(s.rename(columns={'valor': nome}).set_index(['ano', 'mes']))
    pd.concat(series, axis=1).reset_index().to_csv(os.path.join(SAIDA, 'atlantico_tna_tsa.csv'), index=False)


if __name__ == '__main__':
    main()
