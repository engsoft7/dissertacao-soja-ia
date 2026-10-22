# -*- coding: utf-8 -*-
"""
O ONI como variável no protocolo da Tabela 6.

Item 2 de TRABALHOS_FUTUROS.md. Repete a avaliação da Tabela 6 (base completa
do Pará, leave-one-year-out com busca aninhada, mesmos orçamentos e semente)
acrescentando às onze variáveis ambientais o ONI de dezembro a março do ano de
colheita. As rotinas são as de 04_analise_para/03_busca_hiperparametros.py,
importadas e não recopiadas; só a lista de variáveis muda.

Hipótese: o ONI reduz o erro dos modelos em relação aos valores publicados na
Tabela 6. Critério: comparar RMSE e R² com e sem o ONI, modelo a modelo; o
modelo de referência não usa variáveis e não muda.

Uso:  python 05_oni_na_tabela6.py
Saída: oni_na_tabela6.json
"""
import importlib.util
import json
import os

from comum import RAIZ, oni

PARA = os.path.join(RAIZ, '..', '04_analise_para')
ORCAMENTO = {'Random Forest': 9, 'XGBoost': 15, 'SVR': 15, 'MLP': 15}


def busca():
    spec = importlib.util.spec_from_file_location('busca', os.path.join(PARA, '03_busca_hiperparametros.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.DADOS = os.path.join(PARA, '..', 'dados')
    return m


def main():
    m = busca()
    djf, _ = oni()
    # carrega com a lista original (o ONI não está no CSV) e só depois acrescenta
    df = m.carrega()
    df['oni_djf'] = df.ano.map(djf)
    m.FEATURES = m.FEATURES + ['oni_djf']
    with open(os.path.join(PARA, 'resultados_busca_aninhada.json'), encoding='utf-8') as f:
        publicado = json.load(f)
    saida = {'variaveis': m.FEATURES, 'modelos': {}}
    for nome, n in ORCAMENTO.items():
        r = m.avalia_modelo(nome, n, df)
        pub = publicado[nome]
        saida['modelos'][nome] = {'com_oni': {k: r[k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%')},
                                  'tabela_6': {k: pub[k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%')}}
        print(nome, saida['modelos'][nome], flush=True)
    saida['referencia_tabela_6'] = {k: publicado['Baseline (sem clima)'][k] for k in ('RMSE', 'MAE', 'R2', 'rRMSE_%')}
    with open(os.path.join(RAIZ, 'oni_na_tabela6.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
