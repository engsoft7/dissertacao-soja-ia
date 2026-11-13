# -*- coding: utf-8 -*-
"""
A síntese da revisão só com os estudos de escala regional.

O terceiro critério de inclusão da revisão pede escala regional (município,
condado, estado ou país). A triagem foi feita sobre título e resumo, e uma
conferência posterior dos resumos, em 13/11/2026, mostrou que 14 dos 53
estudos incluídos operam em escala de talhão, de parcela ou de planta. Este
script não muda a seleção: refaz os percentuais de codificacao_53_estudos.csv
(os das Figuras 2, 4 e 5 da dissertação) só com os 39 estudos de escala
regional, para ver se a síntese depende dos outros 14.

A lista abaixo traz, para cada um dos 14, o que o resumo declara. É uma
leitura de resumo, como a triagem: um estudo regional pode ter ficado de fora
dela, e a lista pode ser discutida linha a linha.

Uso:   python 05_sensibilidade_escala.py
Saída: sensibilidade_escala.json
"""
import json
import os

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))

# DOI -> escala declarada no resumo
FORA_DA_ESCALA_REGIONAL = {
    '10.1371/journal.pone.0252402': 'ensaios de cultivares (Uniform Soybean Tests), genótipo e clima',
    '10.3390/rs13132555': 'parcelas de melhoramento, reflectância hiperespectral',
    '10.3389/fpls.2022.1096619': 'planta: reconhecimento de vagens em imagens',
    '10.1016/j.heliyon.2023.e17432': 'talhão: variabilidade dentro do talhão, colhedora',
    '10.3390/rs14092256': 'talhão: variabilidade dentro do talhão, Sentinel-2 e solo',
    '10.1002/agj2.21473': 'talhão: três talhões em dois anos, monitor de colheita',
    '10.1016/j.atech.2024.100442': 'parcelas de experimento de manejo com plantas de cobertura',
    '10.4025/actasciagron.v40i1.35250': 'parcelas de experimento em Anápolis (GO), características agronômicas',
    '10.1016/j.agrformet.2024.110022': 'talhão: previsão sítio-específica',
    '10.1016/j.eja.2024.127498': 'talhão: 310 talhões no Uruguai, colhedora',
    '10.1590/1413-7054202347002423': 'talhão: sensores orbitais contra a produtividade da parcela',
    '10.1109/igarss47720.2021.9554856': 'talhão: previsão em escala de talhão',
    '10.18011/bioeng.2024.v18.1211': 'planta: parâmetros morfológicos e nutricionais das plantas',
    '10.4025/actasciagron.v46i1.67040': 'planta: imagens da planta e das vagens',
}


def main():
    cod = pd.read_csv(os.path.join(AQUI, 'codificacao_53_estudos.csv'))
    doi = cod.doi.str.lower()
    faltam = sorted(set(FORA_DA_ESCALA_REGIONAL) - set(doi))
    if faltam:
        raise SystemExit(f'DOI que não está entre os 53: {faltam}')
    regional = ~doi.isin(FORA_DA_ESCALA_REGIONAL)
    categorias = [c for c in cod.columns if c not in ('titulo', 'ano', 'doi')]
    saida = {'nota': ('Percentual dos estudos que mencionam cada categoria, no título ou no resumo '
                      '(03_codifica_estudos.py), entre os 53 incluídos e só entre os de escala regional.'),
             'estudos': {'incluídos': int(len(cod)), 'escala regional': int(regional.sum()),
                         'talhão, parcela ou planta': int((~regional).sum())},
             'fora_da_escala_regional': {
                 d: {'titulo': cod.titulo[doi == d].iloc[0], 'ano': int(cod.ano[doi == d].iloc[0]), 'escala': e}
                 for d, e in FORA_DA_ESCALA_REGIONAL.items()},
             'percentuais': {}}
    print(f"{'':30s} {'53':>9s} {str(int(regional.sum())) + ' regionais':>14s}")
    for c in categorias:
        todos, reg = cod[c].mean() * 100, cod.loc[regional, c].mean() * 100
        saida['percentuais'][c] = {'53 incluídos': {'estudos': int(cod[c].sum()), '%': round(todos)},
                                   'escala regional': {'estudos': int(cod.loc[regional, c].sum()), '%': round(reg)}}
        print(f'{c:30s} {cod[c].sum():3d} ({todos:3.0f}%) {cod.loc[regional, c].sum():6d} ({reg:3.0f}%)')
    with open(os.path.join(AQUI, 'sensibilidade_escala.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
