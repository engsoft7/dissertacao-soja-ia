# -*- coding: utf-8 -*-
"""
Série histórica de safras da CONAB (soja por UF): procura e baixa.

É a fonte independente da PAM para triangular a variável-alvo (item 4 de
TRABALHOS_FUTUROS.md). A CONAB já mudou o endereço desses arquivos mais de uma
vez (conab.gov.br, gov.br/conab, portal de informações), então o script não
presume um endereço: parte de páginas conhecidas, segue os links que parecem
arquivos de série histórica e guarda o que conseguir baixar, com um relatório
de cada tentativa. A leitura da planilha fica para a análise, depois que se
souber o formato que a CONAB publica hoje.

A verificação de certificado nunca é desligada. Se o HTTPS de um endereço
falhar, tenta-se o mesmo endereço em HTTP, e o relatório registra isso.

Uso:  python coleta_conab_safras.py
Saída: ../dados/conab/<arquivo> e ../dados/conab/coleta_conab.json
"""
import json
import os
import re
import urllib.parse
from datetime import date

import requests

SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dados', 'conab')
UA = {'User-Agent': 'AgroInteligencia-Dissertacao/1.0 (UFPA/EngSoft7; pesquisa academica)'}
INICIAIS = [
    'https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/series-historicas/graos/soja',
    'https://portaldeinformacoes.conab.gov.br/downloads/arquivos/SerieHistoricaGraos.txt',
    'https://portaldeinformacoes.conab.gov.br/download-arquivos.html',
    'https://portaldeinformacoes.conab.gov.br/safra-serie-historica-graos.html',
    'https://www.conab.gov.br/info-agro/safras/serie-historica-das-safras',
    'https://www.conab.gov.br/info-agro/safras/serie-historica-das-safras/itemlist/category/911-soja',
    'https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/series-historicas',
    'https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/series-historicas/graos',
    'https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/series-historicas/graos/soja',
    'https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/safra-de-graos',
]
DADOS = ('.xls', '.xlsx', '.csv', '.txt', '.zip', '.ods')
# no gov.br (Plone) o arquivo vem como .../nome.xls/@@download/file ou .../nome.xls/view
EH_DADO = re.compile(r'\.(xlsx?|csv|txt|zip|ods)(/(@@download|view|at_download)\b.*)?$', re.I)
INTERESSE = re.compile(r'soja|serie.?hist|seriehist|graos|safra', re.I)
FORA = re.compile(r'facebook|twitter|whatsapp|linkedin|@@images|/noticias/|\.(png|jpe?g|gif|svg)$', re.I)
MAX_PAGINAS, MAX_ARQUIVOS, MAX_BYTES = 25, 20, 60_000_000


def pega(url):
    """GET com certificado verificado; se o HTTPS falhar por SSL, tenta HTTP."""
    try:
        return requests.get(url, headers=UA, timeout=60, allow_redirects=True), None
    except requests.exceptions.SSLError as e:
        aviso = f'SSL recusado em HTTPS ({str(e)[:160]})'
        if url.startswith('https://'):
            try:
                return requests.get('http://' + url[8:], headers=UA, timeout=60), aviso + '; tentado HTTP'
            except requests.RequestException as e2:
                return None, aviso + f'; HTTP também falhou ({type(e2).__name__})'
        return None, aviso


def links(html, base):
    achados = set()
    for bruto in re.findall(r'(?:href|src|data-url)\s*=\s*["\']([^"\']+)["\']', html, re.I):
        url = urllib.parse.urljoin(base, bruto.strip()).split('#')[0]
        if url.startswith('http') and INTERESSE.search(urllib.parse.unquote(url)) and not FORA.search(url):
            achados.add(url)
    return sorted(achados)


def nome_arquivo(url, resp):
    cd = resp.headers.get('content-disposition', '')
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
    nome = urllib.parse.unquote(m.group(1) if m else urllib.parse.urlparse(url).path.rstrip('/').split('/')[-1])
    return re.sub(r'[^A-Za-z0-9._-]', '_', nome) or 'arquivo'


def main():
    os.makedirs(SAIDA, exist_ok=True)
    fila, vistos, relato, salvos = list(INICIAIS), set(), [], []
    paginas = 0
    while fila and paginas < MAX_PAGINAS and len(salvos) < MAX_ARQUIVOS:
        url = fila.pop(0)
        if url in vistos:
            continue
        vistos.add(url)
        try:
            r, aviso = pega(url)
        except requests.RequestException as e:
            relato.append({'url': url, 'erro': f'{type(e).__name__}: {str(e)[:200]}'})
            print(f'x {url}: {type(e).__name__}', flush=True)
            continue
        item = {'url': url}
        if aviso:
            item['aviso'] = aviso
        if r is None:
            relato.append(item)
            print(f'x {url}: {aviso}', flush=True)
            continue
        tipo = r.headers.get('content-type', '').lower()
        item.update({'status': r.status_code, 'tipo': tipo, 'bytes': len(r.content), 'final': r.url})
        print(f'{r.status_code} {url} [{tipo[:40]}] {len(r.content)} B' + (f' ({aviso})' if aviso else ''), flush=True)
        if r.status_code != 200:
            relato.append(item)
            continue
        caminho = urllib.parse.urlparse(r.url).path
        if 'html' in tipo and not EH_DADO.search(caminho):
            paginas += 1
            todos = links(r.text, r.url)
            novos = [u for u in todos if u not in vistos]
            # arquivos de dados antes das páginas; páginas só do mesmo órgão e, de
            # preferência, as de série histórica
            dados = [u for u in novos if EH_DADO.search(urllib.parse.urlparse(u).path)]
            pags = [u for u in novos if u not in dados and 'conab' in u.lower()]
            pags.sort(key=lambda u: ('serie' not in u.lower(), 'soja' not in u.lower()))
            item['links_dados'] = dados[:40]
            if 'series-historicas' in r.url or 'serie-historica' in r.url:
                item['links_todos'] = todos[:80]
            fila = dados + fila + pags[:15]
        elif tipo.startswith('image/'):
            item['ignorado'] = 'imagem'
        elif len(r.content) <= MAX_BYTES:
            nome = nome_arquivo(r.url, r)
            with open(os.path.join(SAIDA, nome), 'wb') as f:
                f.write(r.content)
            item['salvo_como'] = nome
            salvos.append(nome)
            amostra = r.content[:400].decode('latin-1', 'replace').replace('\r', '')
            print('   amostra:', amostra[:300].replace('\n', ' | '), flush=True)
        relato.append(item)
    with open(os.path.join(SAIDA, 'coleta_conab.json'), 'w', encoding='utf-8') as f:
        json.dump({'coletado_em': date.today().isoformat(), 'salvos': salvos, 'tentativas': relato},
                  f, indent=2, ensure_ascii=False)
    print(f'{len(salvos)} arquivos salvos: {salvos}')


if __name__ == '__main__':
    main()
