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
        gera_pizza_familias(saida, n)
        gera_pizza_anos(ENTRADA, n)
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


# Superfície e tinta da figura, e a ordem fixa das cores categóricas. Ordem
# fixa, e não ciclada: a cor acompanha a categoria, não a posição no ranking.
SUPERFICIE = '#fcfcfb'
TINTA = '#0b0b0b'
# tinta secundária: etiqueta acompanha o valor sem competir com ele
TINTA2 = '#52514e'
CATEGORICAS = ('#2a78d6', '#eb6834', '#1baf7a', '#eda100')
# Rampa sequencial de um só tom, clara para escura. Ano é dado ordenado: cor
# que escurece com o tempo preserva a ordem que a pizza, por si, embaralha.
RAMPA_AZUL = ('#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef',
              '#6da7ec', '#5598e7', '#3987e5', '#256abf')


def _pizza(ax, valores, rotulos, cores, n):
    """Desenha a pizza com rótulo direto em cada fatia.

    Rótulo direto porque o validador de paleta avisa que duas das cores ficam
    abaixo de 3:1 contra a superfície — e porque fatias de tamanho próximo não
    se comparam a olho. Com o número escrito, o leitor não depende da área.
    """
    cunhas, _ = ax.pie(
        valores, colors=cores, startangle=90, counterclock=False,
        # 2 px da cor da superfície entre as fatias: separa sem desenhar borda
        wedgeprops=dict(edgecolor=SUPERFICIE, linewidth=2))
    import numpy as np
    for cunha, rot, v in zip(cunhas, rotulos, valores):
        meio = np.deg2rad((cunha.theta1 + cunha.theta2) / 2)
        raio = 0.68 if v / n >= 0.08 else 1.16
        ax.text(raio * np.cos(meio), raio * np.sin(meio),
                f'{rot}\n{v} ({v / n * 100:.0f}%)',
                ha='center', va='center', fontsize=8.5, color=TINTA,
                linespacing=1.25)
    ax.set_aspect('equal')


def gera_pizza_familias(saida, n):
    """A partição dos 53 por família de técnica — exclusiva, logo somável.

    As barras por algoritmo não podem virar pizza: as categorias se sobrepõem e
    somam 163%. Esta parte de outra pergunta — qual família cada estudo
    emprega — e essa tem resposta única por estudo, de modo que as quatro
    fatias fecham os 53.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    profundo = ['Recorrentes (LSTM/RNN/GRU)', 'CNN', 'Transformer']
    classico = ['Random Forest', 'XGBoost', 'SVR/SVM', 'Rede neural rasa/MLP',
                'Regressão linear']
    tem_p = saida[profundo].sum(axis=1) > 0
    tem_c = saida[classico].sum(axis=1) > 0

    grupos = [
        ('Apenas métodos clássicos', int((tem_c & ~tem_p).sum())),
        ('Ambas as famílias (híbrido ou comparação)', int((tem_c & tem_p).sum())),
        ('Apenas aprendizado profundo', int((tem_p & ~tem_c).sum())),
        ('Sem técnica declarada no resumo', int((~tem_p & ~tem_c).sum())),
    ]
    assert sum(v for _, v in grupos) == n, grupos

    import numpy as np

    # Rosca, e não pizza cheia: o miolo carrega o total e os nomes saem de
    # dentro das fatias, onde encavalavam. A legenda fica à direita, em coluna,
    # porque quatro nomes longos não cabem em volta de um círculo sem colidir.
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    centro, raio, espessura = (-0.98, 0.0), 0.88, 0.35
    valores = [v for _, v in grupos]
    cunhas, _ = ax.pie(
        valores, colors=CATEGORICAS, startangle=90, counterclock=False,
        center=centro, radius=raio,
        # 2 px da cor da superfície entre as fatias: separa sem desenhar borda
        wedgeprops=dict(width=espessura, edgecolor=SUPERFICIE, linewidth=2))

    # Rótulo direto na fatia — só a contagem, que é curta e cabe fora do anel,
    # sobre a superfície. É o canal que não depende da cor: o leitor liga a
    # fatia à linha da legenda pelo número, não pelo tom.
    for cunha, v in zip(cunhas, valores):
        meio = np.deg2rad((cunha.theta1 + cunha.theta2) / 2)
        cos, sen = np.cos(meio), np.sin(meio)
        ax.text(centro[0] + (raio + 0.12) * cos, centro[1] + (raio + 0.12) * sen,
                str(v), fontsize=10.5, color=TINTA, va='center',
                ha='left' if cos > 0.2 else ('right' if cos < -0.2 else 'center'))

    ax.text(*centro, f'{n}\n', fontsize=23, color=TINTA, ha='center',
            va='center', linespacing=0.9)
    ax.text(centro[0], centro[1] - 0.19, 'estudos', fontsize=9.5,
            color=TINTA2, ha='center', va='center')

    # Legenda em coluna: pastilha, valor e nome. O valor vem acima do nome, e
    # maior, porque é o dado; o nome é a etiqueta.
    for i, ((rotulo, v), cor) in enumerate(zip(grupos, CATEGORICAS)):
        y = 0.92 - i * 0.60
        ax.add_patch(FancyBboxPatch(
            (0.16, y - 0.038), 0.078, 0.078, boxstyle='round,pad=0,rounding_size=0.02',
            facecolor=cor, edgecolor='none'))
        ax.text(0.32, y, f'{v} ({v / n * 100:.0f}%)', fontsize=13,
                color=TINTA, va='center')
        ax.text(0.32, y - 0.185, rotulo, fontsize=9.2, color=TINTA2, va='center')

    ax.set_aspect('equal')
    ax.set_xlim(-2.08, 2.08)
    ax.set_ylim(-1.35, 1.35)
    ax.set_axis_off()
    # sem título: a legenda ABNT da Figura 3 já o diz, acima da imagem
    fig.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.005)
    caminho = os.path.join(RAIZ, 'fig_revisao_familia_pizza.png')
    fig.savefig(caminho, dpi=200, facecolor=SUPERFICIE)
    plt.close(fig)
    print(f'  {os.path.basename(caminho)}')


def gera_pizza_anos(entrada, n):
    """A distribuição por ano em pizza, como o orientador sugeriu.

    Categoria exclusiva e somável, portanto legítima. Registre-se, ainda assim,
    que a coluna comunica melhor o que este dado tem de relevante — o
    adensamento recente —, porque pizza não tem eixo do tempo. Daí a rampa
    sequencial e o sentido horário a partir do topo: é o que resta da ordem
    cronológica dentro de um círculo.
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
    assert sum(valores) == n

    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    _pizza(ax, valores, [str(a) for a in anos], RAMPA_AZUL[:len(anos)], n)
    ax.set_title(f'Distribuição por ano de publicação (n = {n})', color=TINTA)
    fig.patch.set_facecolor(SUPERFICIE)
    fig.tight_layout()
    caminho = os.path.join(RAIZ, 'fig_revisao_ano_pizza.png')
    fig.savefig(caminho, dpi=200, facecolor=SUPERFICIE)
    plt.close(fig)
    print(f'  {os.path.basename(caminho)}')


if __name__ == '__main__':
    sys.exit(main())
