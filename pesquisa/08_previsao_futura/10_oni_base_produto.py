# -*- coding: utf-8 -*-
"""
O teste do ONI (05_oni_na_tabela6.py) repetido na base do produto, a cada safra nova.

Item 2 de TRABALHOS_FUTUROS.md: com 24 safras, o ganho do ONI não é
significativo, e o teste só ganha poder com safras novas. A base da
dissertação é congelada (2001-2024); a do produto (soja_para_painel.csv)
recebe cada safra nova pela rotina de atualização. Este script roda o mesmo
05 sobre ela, trocando só a base, e registra o resultado com o ano da última
safra, para o workflow confere-safra-nova.yml saber quando repetir.

Uso:  python 10_oni_base_produto.py
Saída: oni_base_produto.json
"""
import importlib.util
import json
import os

import numpy as np
import pandas as pd

from comum import RAIZ

PARA = os.path.join(RAIZ, '..', '04_analise_para')
PAINEL = os.path.join(RAIZ, '..', 'dados', 'soja_para_painel.csv')


def main():
    spec = importlib.util.spec_from_file_location('p05', os.path.join(RAIZ, '05_oni_na_tabela6.py'))
    p05 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p05)
    original = p05.busca

    def busca_produto():
        m = original()
        def carrega():
            df = pd.read_csv(PAINEL)
            df['balanco_hidrico'] = df.precip_total - df.etp_total
            df['log_area'] = np.log1p(df.soy_area_ha)
            return (df.dropna(subset=m.FEATURES + ['rendimento_kg_ha'])
                      .sort_values(['municipio', 'ano']).reset_index(drop=True))
        m.carrega = carrega
        return m

    p05.busca = busca_produto
    destino = os.path.join(RAIZ, 'oni_na_tabela6.json')
    guardado = open(destino, encoding='utf-8').read()     # 05 grava neste arquivo: preserva o da dissertação
    try:
        p05.main()
        resultado = json.load(open(destino, encoding='utf-8'))
    finally:
        open(destino, 'w', encoding='utf-8').write(guardado)
    base = pd.read_csv(PAINEL)
    resultado['base'] = {'arquivo': 'pesquisa/dados/soja_para_painel.csv', 'registros': int(len(base)),
                         'ultima_safra': int(base.ano.max())}
    resultado['nota'] = ('05_oni_na_tabela6.py sobre a base do produto; "tabela_6" continua sendo o valor publicado '
                         'na dissertação, sobre a base congelada, só para referência.')
    with open(os.path.join(RAIZ, 'oni_base_produto.json'), 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: v.get('ganho_com_oni_sobre_referencia') for k, v in resultado['modelos'].items()}))


if __name__ == '__main__':
    main()
