# -*- coding: utf-8 -*-
"""
Retroteste do preço estimado da soja no Pará (software/api_backend/precos_para.py).

O produto estima o preço paraense a cada momento como a cotação de Chicago em
reais somada à base do Pará no mês: média mensal do Pará (Agrolink) menos a
média de Chicago no mesmo mês. A estimativa nunca foi comparada com o preço
que se observou depois. Aqui, mês a mês, a média do Pará é prevista só com o
que se sabia no fim do mês anterior:

    estimativa(m) = média de Chicago em m + base(m − 1)

e comparada com a média do Pará publicada para m, ao lado de duas referências
ingênuas: Chicago sem base, e o Pará do mês anterior (persistência).

É a média do mês, e não o preço de cada instante: a Agrolink não publica o
diário em texto, e só a média mensal pode ser conferida.

Roda no Actions (a Agrolink e o Yahoo não respondem a todo ambiente).

Uso:   python 03_retroteste_preco_para.py
Saída: retroteste_preco_para.json
"""
import json
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'software', 'api_backend'))
import precos_para  # noqa: E402


def erros(obs, prev):
    e = np.asarray(prev) - np.asarray(obs)
    return {'MAE_R$_sc': round(float(np.mean(np.abs(e))), 2), 'vies_R$_sc': round(float(np.mean(e)), 2),
            'MAPE_%': round(float(np.mean(np.abs(e) / np.asarray(obs)) * 100), 2),
            'maior_erro_R$_sc': round(float(np.max(np.abs(e))), 2), 'n': int(len(e))}


def main():
    hist = precos_para._baixa_agrolink()
    chicago = precos_para._baixa_chicago_diario()
    serie = precos_para.combina(hist, chicago)          # meses com as duas médias
    meses = []
    for ant, atual in zip(serie[:-1], serie[1:]):
        meses.append({'mes': atual['mes'], 'para': atual['para'], 'chicago': atual['chicago'],
                      'base_mes_anterior': ant['base'],
                      'estimativa': round(atual['chicago'] + ant['base'], 2),
                      'persistencia': ant['para']})
    # O mês corrente entra com média parcial nas duas fontes: fica fora do teste.
    completos = meses[:-1]
    obs = [m['para'] for m in completos]
    saida = {
        'nota': ('Média mensal do Pará (Agrolink) prevista com a média de Chicago do mês e a base do mês anterior; '
                 'o mês corrente, com média parcial, fica de fora.'),
        'fonte': precos_para.FONTE,
        'periodo': [completos[0]['mes'], completos[-1]['mes']] if completos else None,
        'estimativa_do_produto': erros(obs, [m['estimativa'] for m in completos]),
        'chicago_sem_base': erros(obs, [m['chicago'] for m in completos]),
        'persistencia_mes_anterior': erros(obs, [m['persistencia'] for m in completos]),
        'meses': meses,
    }
    with open(os.path.join(AQUI, 'retroteste_preco_para.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: saida[k] for k in ('periodo', 'estimativa_do_produto', 'chicago_sem_base',
                                            'persistencia_mes_anterior')}, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
