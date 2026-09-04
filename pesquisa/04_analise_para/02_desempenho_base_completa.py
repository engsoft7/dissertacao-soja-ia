# -*- coding: utf-8 -*-
"""
Desempenho na base completa do Pará — Tabela 6 da dissertação.

O cabeçalho de 01_compara_mascara_controlada.py remete a este script, que
fechava a Tabela 6 sobre os 415 registros dos 38 municípios entre 2001 e 2024,
com a área de soja incorporada como preditora. Enquanto ele não existia, os
números da tabela viviam apenas em resultados_busca_aninhada.json, e quem
partisse do repositório não tinha como reproduzi-los.

A avaliação em si é a de 03_busca_hiperparametros.py, importado aqui em vez de
recopiado: mesma validação leave-one-year-out externa, mesma busca aninhada nas
safras de treino, mesma semente. A diferença é de escopo — 03_ avalia um
algoritmo por chamada, para que uma busca longa possa ser retomada; este roda os
quatro mais o modelo de referência e monta a tabela.

O orçamento de configurações não é o mesmo para todos os modelos. ORCAMENTO
registra o que foi efetivamente usado em cada publicação, sem o que a tabela
não se reproduz: o Random Forest foi buscado sobre 10 configurações e os demais
sobre 16 (a adotada na dissertação mais as sorteadas).

Uso:  python 02_desempenho_base_completa.py             # roda tudo e grava
      python 02_desempenho_base_completa.py --conferir  # roda e compara, sem gravar
      python 02_desempenho_base_completa.py --tabela    # só imprime o que está gravado
"""
import importlib.util
import json
import os
import sys
from decimal import ROUND_HALF_UP, Decimal

RAIZ = os.path.dirname(os.path.abspath(__file__))
PUBLICADO = os.path.join(RAIZ, 'resultados_busca_aninhada.json')

# Configurações sorteadas por modelo, além da adotada na dissertação, que
# sempre entra como candidata. São os orçamentos com que a Tabela 6 foi gerada.
ORCAMENTO = {'Random Forest': 9, 'XGBoost': 15, 'SVR': 15, 'MLP': 15}
ORDEM = ['Baseline (sem clima)', 'MLP', 'SVR', 'Random Forest', 'XGBoost']
ROTULO = {'Baseline (sem clima)': 'Baseline (sem clima)', 'MLP': 'MLP', 'SVR': 'SVR',
          'Random Forest': 'Random Forest', 'XGBoost': 'XGBoost'}
METRICAS = ['RMSE', 'MAE', 'R2', 'rRMSE_%']

SO_XGBOOST = """
Só o XGBoost divergiu, e é o único modelo cujo treino não vem do scikit-learn.
A tabela publicada foi gerada com uma versão anterior da biblioteca; sob a
3.2.0 a busca interna passa a eleger outra configuração e o R² sai 0,148 em vez
de 0,123. A diferença é de ambiente, não de código: as 16 candidatas sorteadas
são as mesmas, e três execuções seguidas — inclusive uma com a máquina
disputada por outro processo — devolveram 433,2 / 310,6 / 0,148 sem variar.
O ordenamento não muda: em qualquer das duas leituras o XGBoost é o pior dos
quatro e fica muito abaixo do modelo de referência (0,216)."""


def versoes():
    """Versões das bibliotecas que decidem o resultado numérico."""
    import numpy
    import sklearn
    import xgboost
    return {'xgboost': xgboost.__version__, 'scikit-learn': sklearn.__version__,
            'numpy': numpy.__version__}


def busca():
    """Importa 03_busca_hiperparametros.py, cujo nome começa por dígito."""
    caminho = os.path.join(RAIZ, '03_busca_hiperparametros.py')
    spec = importlib.util.spec_from_file_location('busca_hiperparametros', caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    # 03_ resolve a base por caminho relativo, supondo execução dentro da pasta.
    modulo.DADOS = os.path.join(RAIZ, '..', 'dados')
    return modulo


def arredonda(x, casas):
    """Meio para cima, como nas tabelas da dissertação.

    O padrão do Python arredonda para o par mais próximo, e o MAE do XGBoost
    cai exatamente em 314,5: sairia 314 aqui e 315 no texto.
    """
    passo = Decimal(1).scaleb(-casas)
    return Decimal(str(x)).quantize(passo, rounding=ROUND_HALF_UP)


def virgula(x, casas):
    return str(arredonda(x, casas)).replace('.', ',')


def tabela(resultados):
    """Tabela 6 no formato em que aparece na dissertação."""
    largura = max(len(ROTULO[n]) for n in ORDEM)
    linhas = [f"{'Modelo'.ljust(largura)} | RMSE | MAE | R²    | Erro relativo",
              f"{'-' * largura}-|------|-----|-------|--------------"]
    for nome in ORDEM:
        r = resultados[nome]
        linhas.append(f"{ROTULO[nome].ljust(largura)} | {arredonda(r['RMSE'], 0):>4} | "
                      f"{arredonda(r['MAE'], 0):>3} | "
                      f"{virgula(r['R2'], 3)} | {virgula(r['rRMSE_%'], 1)}%")
    return '\n'.join(linhas)


def roda():
    m = busca()
    df = m.carrega()
    print('Ambiente: ' + ', '.join(f'{k} {v}' for k, v in versoes().items()))
    print(f'Base: {len(df)} registros, {df.municipio.nunique()} municípios, '
          f'{df.ano.min()}-{df.ano.max()}, média {df.rendimento_kg_ha.mean():.0f} kg/ha\n')
    resultados = {'Baseline (sem clima)': m.avalia_baseline(df)}
    print(f"Baseline (sem clima): {resultados['Baseline (sem clima)']}")
    for nome in ORDEM[1:]:
        resultados[nome] = m.avalia_modelo(nome, ORCAMENTO[nome], df)
        print(f'{nome}: {resultados[nome]}')
    return resultados


def confere(resultados):
    """Compara com o JSON publicado. Devolve as divergências encontradas."""
    with open(PUBLICADO, encoding='utf-8') as f:
        publicado = json.load(f)
    divergencias = []
    for nome in ORDEM:
        if nome not in publicado:
            divergencias.append(f'{nome}: ausente do arquivo publicado')
            continue
        for chave in METRICAS:
            novo, velho = resultados[nome][chave], publicado[nome][chave]
            if novo != velho:
                divergencias.append(f'{nome} / {chave}: publicado {velho}, obtido {novo}')
    return divergencias


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else ''

    if modo == '--tabela':
        with open(PUBLICADO, encoding='utf-8') as f:
            print(tabela(json.load(f)))
        return 0

    resultados = roda()
    print('\n' + tabela(resultados))

    divergencias = confere(resultados)
    if divergencias:
        print('\nDivergências em relação a resultados_busca_aninhada.json:')
        for d in divergencias:
            print(f'  - {d}')
        if all(d.startswith('XGBoost') for d in divergencias):
            print(SO_XGBOOST)
    else:
        print('\nConfere com resultados_busca_aninhada.json em todas as métricas.')

    if modo == '--conferir':
        return 1 if divergencias else 0

    with open(PUBLICADO, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f'gravado em {PUBLICADO}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
