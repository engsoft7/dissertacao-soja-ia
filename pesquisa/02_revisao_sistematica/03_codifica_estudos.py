# -*- coding: utf-8 -*-
"""
Codifica os 53 estudos incluídos por algoritmo, preditor, fonte e métrica.

Por que existe: os percentuais que a dissertação reporta na síntese da revisão
— LSTM em 42% dos estudos, Random Forest em 32%, variáveis climáticas em 43% e
assim por diante — não tinham fonte versionada. Existiam apenas no texto, o que
os torna impossíveis de conferir por quem lê. Num trabalho cuja contribuição
central é sobre a rastreabilidade de um dado, isso é um problema.

O QUE ESTE SCRIPT É, E O QUE NÃO É
──────────────────────────────────
Ele NÃO recupera a codificação original. Aquela foi feita pelo autor sobre os
textos completos e não foi preservada. Este é um segundo levantamento,
independente, e com método declaradamente mais fraco: lê apenas TÍTULO e
RESUMO, que é o que o repositório guarda dos 53 estudos.

A diferença de método tem consequência previsível e é preciso dizê-la: um
estudo pode empregar LSTM sem mencioná-lo no resumo, e o resumo pode citar um
método apenas para dizer que não o usou. O resultado daqui é, portanto, um
piso — mede o que os resumos declaram, não o que os trabalhos fizeram.

O valor está em ser reprodutível. Qualquer pessoa roda e obtém o mesmo número,
e as regras estão à vista abaixo, uma linha por termo, podendo ser discutidas
uma a uma. Um percentual que ninguém consegue recalcular não se discute: ou se
acredita nele, ou não.

Uso:  python 03_codifica_estudos.py            # tabela e comparação
      python 03_codifica_estudos.py --graficos # gera também as figuras
"""
import os
import re
import sys

import pandas as pd

RAIZ = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(RAIZ, 'estudos_triados.csv')
SAIDA = os.path.join(RAIZ, 'codificacao_53_estudos.csv')

# Cada categoria é uma lista de padrões. A busca é por expressão regular com
# fronteira de palavra, sobre título e resumo reunidos e sem acento, para que
# "regressão" e "regressao" contem igual. Siglas curtas — CNN, RF, MLP — exigem
# fronteira estrita, senão casam dentro de outras palavras.
ALGORITMOS = {
    # A dissertação reporta 42% para "redes recorrentes do tipo Long Short-Term
    # Memory". Contando apenas quem escreve LSTM no resumo chega-se a 32%;
    # contando a família recorrente — LSTM, RNN e GRU — chega-se a 42%, que é o
    # número do texto. A categoria abaixo é a família, como o texto diz, e a
    # contagem estrita fica ao lado para a diferença ficar à vista em vez de
    # depender de quem lê o rótulo.
    'Recorrentes (LSTM/RNN/GRU)': [r'\blstm\b', r'long[ -]short[ -]term memory',
                                   r'\brnn\b', r'recurrent neural',
                                   r'recurrent network', r'\bgru\b',
                                   r'gated recurrent'],
    'LSTM (menção estrita)': [r'\blstm\b', r'long[ -]short[ -]term memory'],
    'CNN': [r'\bcnn\b', r'convolutional neural', r'convolution neural'],
    'Random Forest': [r'random forest', r'\brf\b'],
    'XGBoost': [r'xgboost', r'\bxgb\b', r'extreme gradient boosting'],
    'SVR/SVM': [r'support vector', r'\bsvr\b', r'\bsvm\b'],
    'Rede neural rasa/MLP': [r'multilayer perceptron', r'multi-layer perceptron',
                             r'\bmlp\b', r'\bann\b', r'artificial neural network',
                             r'backpropagation'],
    'Transformer': [r'\btransformer\b', r'attention mechanism', r'self-attention'],
    'Regressão linear': [r'linear regression', r'\bols\b', r'ridge regression',
                         r'\blasso\b'],
}

PREDITORES = {
    'Climáticas': [r'precipitation', r'rainfall', r'temperature', r'solar radiation',
                   r'\bclimat', r'\bweather\b', r'evapotranspiration'],
    'Solo': [r'\bsoil\b', r'soil propert', r'soil moisture'],
    'Índices espectrais': [r'\bndvi\b', r'\bevi\b', r'vegetation index',
                           r'vegetation indices', r'\blai\b', r'\bsif\b'],
    'Manejo': [r'\bmanagement\b', r'fertiliz', r'sowing date', r'planting date',
               r'irrigation'],
}

FONTES = {
    'MODIS': [r'\bmodis\b'],
    'Sentinel': [r'sentinel'],
    'Landsat': [r'landsat'],
    'Google Earth Engine': [r'google earth engine', r'\bgee\b', r'earth engine'],
}

METRICAS = {
    'RMSE': [r'\brmse\b', r'root mean squared? error'],
    'R²': [r'\br2\b', r'r\^2', r'coefficient of determination', r'r-squared',
           r'\br²\b'],
    'MAE': [r'\bmae\b', r'mean absolute error'],
    'MAPE': [r'\bmape\b', r'mean absolute percentage error'],
}

BLOCOS = [('algoritmo', ALGORITMOS), ('preditor', PREDITORES),
          ('fonte', FONTES), ('metrica', METRICAS)]

# O que a dissertação afirma, para a comparação. Transcrito do texto; é
# justamente o que não tinha fonte.
DISSERTACAO = {
    'Recorrentes (LSTM/RNN/GRU)': 42, 'CNN': 38, 'Random Forest': 32, 'XGBoost': 17,
    'Rede neural rasa/MLP': 17, 'SVR/SVM': 17,
    'Climáticas': 43, 'Solo': 23,
    'MODIS': 21, 'Sentinel': 21, 'Google Earth Engine': 9,
    'RMSE': 34, 'R²': 25, 'MAE': 17,
}


def sem_acento(t):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', str(t))
                   if unicodedata.category(c) != 'Mn').lower()


def main():
    d = pd.read_csv(ENTRADA)
    inc = d[d.DECISAO == 'S'].copy().reset_index(drop=True)
    n = len(inc)
    texto = (inc.titulo.fillna('') + ' ' + inc.abstract.fillna('')).map(sem_acento)

    saida = inc[['titulo', 'ano', 'doi']].copy()
    for _, categorias in BLOCOS:
        for rotulo, padroes in categorias.items():
            saida[rotulo] = texto.map(
                lambda t, p=padroes: int(any(re.search(x, t) for x in p)))

    saida.to_csv(SAIDA, index=False, encoding='utf-8')
    print(f'{n} estudos incluídos codificados por título e resumo')
    print(f'gravado em {os.path.basename(SAIDA)}\n')

    print(f'{"":<24}{"este script":>13}{"dissertação":>14}{"diferença":>12}')
    for nome, categorias in BLOCOS:
        print(f'\n── {nome} ──')
        for rotulo in categorias:
            k = int(saida[rotulo].sum())
            pct = round(k / n * 100)
            afirmado = DISSERTACAO.get(rotulo)
            if afirmado is None:
                print(f'  {rotulo:<22}{k:>4} ({pct:>3}%){"—":>13}')
            else:
                dif = pct - afirmado
                marca = 'ok' if abs(dif) <= 5 else '<<<'
                print(f'  {rotulo:<22}{k:>4} ({pct:>3}%){afirmado:>12}%{dif:>+9} pp  {marca}')

    print('\nanos dos 53 incluídos, do próprio CSV:')
    print(' ', inc.ano.value_counts().sort_index().to_dict())

    if '--graficos' in sys.argv:
        gera_graficos(saida, n)
        gera_grafico_anos(ENTRADA, n)
    return 0


def gera_graficos(saida, n):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for nome, categorias in BLOCOS:
        rotulos = [r for r in categorias if saida[r].sum() > 0]
        valores = [int(saida[r].sum()) for r in rotulos]
        fig, ax = plt.subplots(figsize=(6.2, 4.2))
        # Barra, e não pizza: as categorias não são exclusivas — um estudo usa
        # LSTM e CNN ao mesmo tempo —, e pizza de partes que somam mais que o
        # todo engana quem olha.
        ordem = sorted(range(len(valores)), key=lambda i: valores[i])
        ax.barh([rotulos[i] for i in ordem], [valores[i] for i in ordem],
                color='#2E75B6')
        for y, i in enumerate(ordem):
            ax.text(valores[i] + 0.4, y, f'{valores[i]}  ({valores[i]/n*100:.0f}%)',
                    va='center', fontsize=9)
        ax.set_xlim(0, max(valores) * 1.25)
        ax.set_xlabel(f'estudos que mencionam, entre os {n} incluídos')
        ax.set_title(nome.capitalize())
        fig.tight_layout()
        caminho = os.path.join(RAIZ, f'fig_revisao_{nome}.png')
        fig.savefig(caminho, dpi=200)
        plt.close(fig)
        print(f'  {os.path.basename(caminho)}')


def gera_grafico_anos(entrada, n):
    """A distribuição por ano, em colunas.

    Aqui, ao contrário dos demais blocos, as categorias são exclusivas: cada
    estudo tem um ano e um só, e os oito somam os 53. Ainda assim não é pizza,
    e sim coluna sobre o eixo do tempo — o que o dado mostra é o adensamento
    recente da área, e pizza embaralha a ordem cronológica, que é justamente a
    informação que interessa.
    """
    import collections

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import pandas as pd

    df = pd.read_csv(entrada)
    inc = df[df['DECISAO'].astype(str).str.strip().str.upper() == 'S']
    contagem = collections.Counter(inc['ano'].astype(int))
    anos = sorted(contagem)
    valores = [contagem[a] for a in anos]
    assert sum(valores) == n, f'{sum(valores)} != {n}'

    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.bar([str(a) for a in anos], valores, color='#2E75B6')
    for x, v in enumerate(valores):
        ax.text(x, v + 0.25, str(v), ha='center', fontsize=9)
    ax.set_ylim(0, max(valores) * 1.2)
    ax.set_ylabel(f'estudos incluídos (n = {n})')
    ax.set_xlabel('ano de publicação')
    ax.set_title('Distribuição por ano')
    fig.tight_layout()
    caminho = os.path.join(RAIZ, 'fig_revisao_ano.png')
    fig.savefig(caminho, dpi=200)
    plt.close(fig)
    print(f'  {os.path.basename(caminho)}')


if __name__ == '__main__':
    sys.exit(main())
