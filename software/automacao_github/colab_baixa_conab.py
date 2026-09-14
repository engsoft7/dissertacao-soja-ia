# -*- coding: utf-8 -*-
"""
Baixa e confere as planilhas de custos da CONAB, para rodar no Google Colab.

Por que existe: o ambiente de desenvolvimento não alcança conab.gov.br nem
dados.gov.br, e a descoberta automática de atualiza_conab.py já falhou uma vez
(issue #87) porque o Portal de Informações Agropecuárias é uma aplicação de
painéis cujo endereço de exportação muda com ela. O Colab tem rede aberta e um
navegador do lado, o que torna o caminho manual rápido — desde que alguém
confira o arquivo antes de ele ir para o repositório.

Conferir é o ponto. O atualiza_conab.py rejeita cabeçalho que não reconhece, e
descobrir isso depois de abrir o PR custa uma viagem inteira. Aqui a
verificação acontece com o portal ainda aberto na outra aba: se o arquivo veio
errado, você baixa o certo em trinta segundos.

Como usar, numa célula do Colab:

    !wget -q https://raw.githubusercontent.com/engsoft7/dissertacao-soja-ia/main/software/automacao_github/colab_baixa_conab.py
    %run colab_baixa_conab.py

Ele tenta baixar sozinho; se não conseguir, abre o seletor de arquivos para
você subir as planilhas que baixou do portal. No fim, empacota o que foi
validado num .zip para você trazer para a máquina e rodar:

    python software/automacao_github/atualiza_conab.py \\
      --arquivo serie_pedro_afonso_to.csv \\
      --arquivo custo_producao_por_municipio.csv \\
      --arquivo custo_variavel_e_produtividade_por_municipio.csv

Fonte: https://portaldeinformacoes.conab.gov.br/custos-de-producao.html
"""
import csv
import io
import os
import sys
import zipfile

# Mesma especificação de atualiza_conab.py. Repetida de propósito: este arquivo
# roda sozinho no Colab, sem o repositório clonado, e importar de lá exigiria
# baixar o pacote inteiro para conferir um cabeçalho.
PLANILHAS = {
    'serie_pedro_afonso_to.csv': {
        'chave': 'Ano-Mes.Ano-Mes',
        'colunas': ('Renda de Fatores', 'Custo Fixo', 'Custo Variável',
                    'Preco Mercado', 'Preco Mínimo', 'Margem Bruta',
                    'Margem Liquida'),
        'descricao': 'série histórica de Pedro Afonso (TO)',
    },
    'custo_producao_por_municipio.csv': {
        'chave': 'municipio',
        'colunas': ('RENDA DE FATORES', 'CUSTO FIXO', 'CUSTO VARIAVEL',
                    'PRECO RECEBIDO'),
        'descricao': 'custo de produção por município',
    },
    'custo_variavel_e_produtividade_por_municipio.csv': {
        'chave': 'Municipio.Municipio',
        'colunas': ('Custo Variavel Unid Comercializacao(R$)', 'Produtividade'),
        'descricao': 'custo variável e produtividade por município',
    },
    'custo_producao_por_uf.csv': {
        'chave': 'uf',
        'colunas': ('RENDA DE FATORES', 'CUSTO FIXO', 'CUSTO VARIAVEL',
                    'PRECO RECEBIDO'),
        'descricao': 'custo de produção por unidade da federação',
    },
}

PORTAL = 'https://portaldeinformacoes.conab.gov.br/custos-de-producao.html'
SAIDA = 'conab_validado'


def identifica(texto):
    """Diz a qual planilha o conteúdo corresponde, ou None.

    O critério é o mesmo de atualiza_conab.py: a primeira coluna do cabeçalho
    identifica o arquivo e as demais precisam estar presentes. Pelo cabeçalho, e
    não pelo nome do arquivo, porque o portal exporta tudo como
    "export (1).csv" e o nome não diz nada.
    """
    leitor = csv.DictReader(io.StringIO(texto), delimiter=';')
    cabecalho = [c.strip().strip('"') for c in (leitor.fieldnames or [])]
    if not cabecalho:
        return None, cabecalho, 0
    linhas = sum(1 for _ in leitor)
    for nome, forma in PLANILHAS.items():
        if cabecalho[0] == forma['chave'] and \
                all(c in cabecalho for c in forma['colunas']):
            return nome, cabecalho, linhas
    return None, cabecalho, linhas


def decodifica(dados):
    """O portal alterna entre UTF-8 e Latin-1 conforme o painel exportado."""
    for cod in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return dados.decode(cod)
        except UnicodeDecodeError:
            continue
    return dados.decode('utf-8', errors='replace')


def tenta_baixar(url):
    """Uma tentativa automática, sem insistência.

    A issue #87 registra que a descoberta automática não achou candidata
    válida. Esta função existe para o caso de você já ter a URL da exportação —
    passe em CONAB_CUSTOS_URL. Sem ela, o caminho é o envio manual, que é o que
    funciona.
    """
    import urllib.request
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (colab; atualizacao de custos CONAB)'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return decodifica(r.read())


def relata(origem, texto):
    nome, cabecalho, linhas = identifica(texto)
    if nome:
        print(f'  ✓ {origem}')
        print(f'      {PLANILHAS[nome]["descricao"]} — {linhas} linhas')
        print(f'      grava como {nome}')
        return nome, texto
    print(f'  ✗ {origem}')
    print(f'      cabeçalho não reconhecido: {cabecalho[:4]}')
    print('      não é uma exportação em CSV do Portal de Informações '
          'Agropecuárias')
    return None, None


def do_upload():
    """Seletor de arquivos do Colab. Fora do Colab, devolve vazio."""
    try:
        from google.colab import files
    except ImportError:
        print('Fora do Colab: passe os arquivos como argumentos.\n'
              '  python colab_baixa_conab.py serie.csv municipios.csv ...')
        return {}
    print(f'\nBaixe as três planilhas em CSV do portal e selecione-as aqui.')
    print(f'  {PORTAL}\n')
    return files.upload()


def main():
    print('Planilhas de custos da CONAB — coleta e conferência\n')
    validas = {}

    url = os.environ.get('CONAB_CUSTOS_URL', '')
    if url:
        print(f'Tentando {url}')
        try:
            nome, texto = relata(url, tenta_baixar(url))
            if nome:
                validas[nome] = texto
        except Exception as erro:
            print(f'  ✗ falhou: {erro}')

    brutos = {}
    if len(sys.argv) > 1:
        for caminho in sys.argv[1:]:
            with open(caminho, 'rb') as f:
                brutos[os.path.basename(caminho)] = f.read()
    elif len(validas) < 3:
        brutos = do_upload()

    if brutos:
        print('\nConferindo o que chegou:')
        for origem, dados in brutos.items():
            nome, texto = relata(origem, decodifica(dados))
            if nome:
                validas[nome] = texto

    if not validas:
        print('\nNenhuma planilha válida. Confira se baixou a exportação em CSV '
              'e não a imagem do painel.')
        return 1

    os.makedirs(SAIDA, exist_ok=True)
    for nome, texto in validas.items():
        with open(os.path.join(SAIDA, nome), 'w', encoding='utf-8') as f:
            f.write(texto)

    pacote = 'conab.zip'
    with zipfile.ZipFile(pacote, 'w', zipfile.ZIP_DEFLATED) as z:
        for nome in validas:
            z.write(os.path.join(SAIDA, nome), nome)

    print(f'\n{len(validas)} de 3 planilhas validadas e gravadas em {SAIDA}/')
    faltando = [n for n in ('serie_pedro_afonso_to.csv',
                            'custo_producao_por_municipio.csv',
                            'custo_variavel_e_produtividade_por_municipio.csv')
                if n not in validas]
    if faltando:
        print('Faltam, e o painel precisa das três:')
        for n in faltando:
            print(f'  - {PLANILHAS[n]["descricao"]}')

    print('\nNa sua máquina, depois de baixar o zip:\n')
    print('  python software/automacao_github/atualiza_conab.py \\')
    print('    ' + ' \\\n    '.join(f'--arquivo {n}' for n in sorted(validas)))

    try:
        from google.colab import files
        files.download(pacote)
    except ImportError:
        print(f'\npacote em {pacote}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
