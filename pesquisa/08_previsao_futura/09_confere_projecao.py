# -*- coding: utf-8 -*-
"""
Confere a projeção da produção do Pará para uma safra, quando a PAM dela sair.

Generaliza 06_confere_projecao_2025.py para as safras seguintes. O registro a
conferir é o feito antes de a safra ser publicada: para 2026, o de origem em
2025 gravado em confere_projecao_2025.json em 22/10/2026 (4,81 milhões de
toneladas, faixa de 80% de 4,41 a 5,28). A produção observada é a soma, por
município, de rendimento x área, da mesma variável de área que o registro
usou, como no 06.

Roda sozinho todo mês no workflow confere-safra-nova.yml: enquanto a PAM da
safra não sair, só informa isso e termina sem erro.

Uso:  python 09_confere_projecao.py 2026
Saída: confere_projecao_<ano>.json (só quando a PAM do ano já saiu)
"""
import importlib.util
import json
import os
import sys

import pandas as pd

from comum import RAIZ

PAM = os.path.join(RAIZ, 'dados', 'pam_para_municipios.csv')
COLETA = os.path.join(RAIZ, 'dados', 'pam_coleta.json')


def main(ano):
    with open(os.path.join(RAIZ, f'confere_projecao_{ano - 1}.json'), encoding='utf-8') as f:
        anterior = json.load(f)
    registro = anterior.get(f'novo_registro_origem_{ano - 1}')
    if not registro or str(ano) not in registro['projecao']:
        raise SystemExit(f'sem projeção registrada para {ano} em confere_projecao_{ano - 1}.json')
    proj = registro['projecao'][str(ano)]
    spec = importlib.util.spec_from_file_location('p06', os.path.join(RAIZ, '06_confere_projecao_2025.py'))
    p06 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p06)
    pam = pd.read_csv(PAM)
    if ano not in set(pam.ano):
        print(f'A PAM coletada vai até {pam.ano.max()}; {ano} ainda não saiu. Nada a conferir.')
        return 0
    col = anterior['area_usada']['coluna']
    o = p06.serie(pam, col).loc[ano]
    lo, hi = proj['faixa80_t']
    erro = proj['central_t'] / o.producao - 1
    saida = {
        'registro': {'modelo': registro['modelo'], 'feito_em': registro['feito_em'], **proj},
        'area_usada': col,
        f'observado_{ano}': {'producao_t': round(o.producao), 'producao_ibge_t': round(o.producao_ibge),
                             'area_ha': round(o.area), 'rendimento_kg_ha': round(o.rendimento),
                             'municipios': int(o.municipios)},
        'resultado': {'dentro_da_faixa_80': bool(lo <= o.producao <= hi), 'erro_producao_%': round(erro * 100, 1)},
    }
    with open(os.path.join(RAIZ, f'confere_projecao_{ano}.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    print(json.dumps(saida, indent=1, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 2026))
