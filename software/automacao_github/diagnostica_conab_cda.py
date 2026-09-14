# -*- coding: utf-8 -*-
"""
O portal da CONAB é um Pentaho: descobre o que a API dele oferece.

Por dois meses a issue #87 registrou que a descoberta automática não achava
planilha da CONAB em lugar nenhum. O motivo aparece no DevTools: o botão
"Exportar" do Portal de Informações Agropecuárias não baixa arquivo estático
nem monta CSV no navegador — dispara um POST para o Pentaho CDA, a API de
dados do portal, com os filtros do painel como parâmetros nomeados:

    POST https://pentahoportaldeinformacoes.conab.gov.br/pentaho/plugin/cda/api/doQuery
      path          = /home/SIAGRO/CustoProducao.cda
      dataAccessId  = SQLCustoTotalPrecoUF
      paramano      = [Ano].[2026]
      parammes      = [Mes].[MARÇO]
      paramproduto  = [Produto].[SOJA]
      outputType    = csv

Isso é melhor que uma URL fixa. Parâmetro nomeado se troca; URL fixa congela o
período e faz a automação baixar março de 2026 para sempre, com sucesso, sem
nunca perceber que saiu coisa nova — um silêncio pior que o alarme.

Este script não coleta nada para o repositório. Ele responde três perguntas que
precisam de resposta antes de valer a pena escrever o coletor:

  1. a API responde a quem não é navegador, sem sessão nem token?
  2. quais consultas existem no CustoProducao.cda? São elas que dizem se a
     série de Pedro Afonso e os cortes por município estão ao alcance, ou se
     só o corte por UF está;
  3. o que a API devolve para um mês que o seletor do portal não oferece?
     Silêncio ou erro decide como a automação vai procurar levantamento novo.

Roda no Actions: conab.gov.br é negado pela política de rede do ambiente de
desenvolvimento.

Uso:  python diagnostica_conab_cda.py
"""
import json
import sys

import requests

BASE = 'https://pentahoportaldeinformacoes.conab.gov.br/pentaho/plugin/cda/api'
CDA = '/home/SIAGRO/CustoProducao.cda'
TEMPO = 60
CABECALHO = {
    # O portal responde diferente a quem não parece navegador em alguns
    # endpoints; declarar um agente honesto e identificável é o meio-termo
    # entre mentir e ser recusado.
    'User-Agent': 'dissertacao-soja-ia/1.0 (atualizacao de custos CONAB)',
    'Accept': '*/*',
}

# O payload capturado no DevTools, íntegro. Serve de controle: se este não
# funcionar, nada que eu derive dele vai funcionar.
CAPTURADO = {
    'paramproduto': '[Produto].[SOJA]',
    'paramempreendimento': '[Tipo Empreendimento].[TODOS]',
    'paramsafra': '[Tipo Safra].[TODAS]',
    'paramano': '[Ano].[2026]',
    'parammes': '[Mes].[MARÇO]',
    'paramclassificacao': '[Produto Classificacao].[TODAS]',
    'path': CDA,
    'dataAccessId': 'SQLCustoTotalPrecoUF',
    'outputIndexId': '1',
    'pageSize': '0',
    'pageStart': '0',
    'sortBy': '',
    'paramsearchBox': '',
    'outputType': 'csv',
    'settingattachmentName': 'CustoProducaoPorUF.csv',
    'wrapItUp': 'true',
}


def mostra(titulo):
    print(f'\n{"─" * 74}\n{titulo}\n{"─" * 74}')


def amostra(texto, linhas=6):
    for l in texto.splitlines()[:linhas]:
        print(f'    {l[:150]}')
    resto = len(texto.splitlines()) - linhas
    if resto > 0:
        print(f'    … mais {resto} linhas')


PORTAL = 'https://portaldeinformacoes.conab.gov.br/home/custo-de-producao'


def abre_sessao():
    """Visita o portal antes de consultar, como faria um navegador.

    O painel é declarado público, mas a primeira tentativa fria levou 401. A
    hipótese é a mais simples: o CDA quer a sessão que o Pentaho entrega a
    quem abre a página, e um POST avulso não tem cookie nenhum. Se for isso,
    visitar o portal resolve; se o 401 persistir, a API exige credencial e o
    caminho automático termina aqui.
    """
    s = requests.Session()
    s.headers.update(CABECALHO)
    visitadas = []
    for url in (PORTAL,
                'https://pentahoportaldeinformacoes.conab.gov.br/pentaho/Home',
                f'{BASE}/listQueries'):
        try:
            r = s.get(url, timeout=TEMPO)
            visitadas.append((url, r.status_code, len(s.cookies)))
        except Exception as erro:
            visitadas.append((url, f'erro: {erro}', len(s.cookies)))
    return s, visitadas


def consulta(sessao=None, **extra):
    dados = dict(CAPTURADO, **extra)
    cliente = sessao or requests
    return cliente.post(f'{BASE}/doQuery', data=dados,
                        headers=None if sessao else CABECALHO, timeout=TEMPO)


def main():
    print('Diagnóstico do Pentaho CDA da CONAB')
    print(f'{BASE}\n{CDA}')

    # ── 1. a API atende quem não é navegador? ──
    mostra('1. O payload capturado, reproduzido fora do navegador')
    try:
        r = consulta()
    except Exception as erro:
        print(f'  ✗ falhou: {erro}')
        return 1
    print(f'  HTTP {r.status_code} | {len(r.content):,} bytes | '
          f'{r.headers.get("Content-Type", "?")}')
    sessao = None
    if r.status_code == 200:
        amostra(r.content.decode('utf-8', errors='replace'))
        print('  ✓ responde sem sessão, sem cookie e sem token')
    else:
        print('  ✗ recusou sem sessão')
        amostra(r.text, 3)

        mostra('1b. A mesma consulta, depois de visitar o portal')
        sessao, visitadas = abre_sessao()
        for url, status, n in visitadas:
            print(f'  GET {url[:66]:<66s} {status}  {n} cookies')
        print(f'  cookies: {sorted(c.name for c in sessao.cookies) or "nenhum"}')
        try:
            r = consulta(sessao)
            print(f'\n  HTTP {r.status_code} | {len(r.content):,} bytes | '
                  f'{r.headers.get("Content-Type", "?")}')
            if r.status_code == 200:
                amostra(r.content.decode('utf-8', errors='replace'))
                print('  ✓ a sessão anônima do portal basta')
            else:
                print('  ✗ 401 persiste: a API exige credencial, não só sessão')
                amostra(r.text, 3)
                sessao = None
        except Exception as erro:
            print(f'  ✗ {erro}')
            sessao = None

    # ── 2. que consultas existem no arquivo? ──
    mostra('2. Consultas declaradas em CustoProducao.cda')
    try:
        cliente = sessao or requests
        r = cliente.get(f'{BASE}/listQueries',
                        params={'path': CDA, 'outputType': 'json'},
                        headers=None if sessao else CABECALHO, timeout=TEMPO)
        print(f'  HTTP {r.status_code} | {r.headers.get("Content-Type", "?")}')
        if r.status_code == 200:
            try:
                d = r.json()
                # o CDA devolve {resultset: [[id, nome, tipo], …], metadata: […]}
                linhas = d.get('resultset', d) if isinstance(d, dict) else d
                print(f'  {len(linhas)} consultas:')
                for linha in linhas:
                    print(f'    {linha}')
            except ValueError:
                amostra(r.text, 20)
        else:
            amostra(r.text, 5)
    except Exception as erro:
        print(f'  ✗ {erro}')

    # ── 3. o que responde um mês que o portal não oferece? ──
    mostra('3. Meses de 2026 além de MARÇO')
    print('  O seletor do portal só oferece MARÇO. Se a API devolver vazio')
    print('  para os outros, a automação sabe procurar levantamento novo')
    print('  sozinha, sem precisar de ninguém abrindo o painel.\n')
    for mes in ('MARÇO', 'MAIO', 'JULHO', 'SETEMBRO'):
        try:
            r = consulta(sessao, parammes=f'[Mes].[{mes}]')
            corpo = r.content.decode('utf-8', errors='replace')
            n = max(len(corpo.strip().splitlines()) - 1, 0)
            print(f'  {mes:<10s} HTTP {r.status_code}  {n:>3d} linhas de dado'
                  f'  {len(r.content):>7,} bytes')
        except Exception as erro:
            print(f'  {mes:<10s} ✗ {erro}')

    # ── 4. e anos ── 
    mostra('4. O ano seguinte')
    for ano in ('2026', '2027'):
        try:
            r = consulta(sessao, paramano=f'[Ano].[{ano}]')
            corpo = r.content.decode('utf-8', errors='replace')
            n = max(len(corpo.strip().splitlines()) - 1, 0)
            print(f'  {ano}  HTTP {r.status_code}  {n:>3d} linhas de dado')
        except Exception as erro:
            print(f'  {ano}  ✗ {erro}')

    print('\nNada foi gravado. Este script só pergunta.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
