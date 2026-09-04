#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
atualiza_conab.py

Traz um levantamento novo de custos de produção da CONAB para dentro da base do
produto, em um comando, e dispara o gerador que propaga o resultado para o
painel, a API e o aplicativo.

Contexto: preço e custo do simulador saem do levantamento da CONAB para Pedro
Afonso (TO). Até aqui, atualizar significava baixar as planilhas do portal,
converter os valores por saca para hectare na mão e editar oito literais
espalhados pelo código — o que na prática significava não atualizar. Este
script cobre a primeira metade; gera_levantamento_conab.py cobre a segunda.

Três modos, do mais garantido ao mais automático:

    # 1. Arquivo baixado do portal (funciona sempre, sem rede)
    python software/automacao_github/atualiza_conab.py --arquivo ~/serie.csv

    # 2. Fonte configurada (variável CONAB_CUSTOS_URL, ou --url)
    python software/automacao_github/atualiza_conab.py

    # 3. Só diagnóstico: diz o que a fonte devolve, sem gravar nada
    python software/automacao_github/atualiza_conab.py --testar

O formato aceito é o CSV que o próprio Portal de Informações Agropecuárias
exporta, que é o dos arquivos já versionados em pesquisa/dados/conab/. O script
identifica qual das três planilhas recebeu pelo cabeçalho, então a ordem dos
arquivos na linha de comando não importa.

Fonte: https://portaldeinformacoes.conab.gov.br/custos-de-producao.html
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONAB = RAIZ / "pesquisa" / "dados" / "conab"
GERADOR = Path(__file__).resolve().parent / "gera_levantamento_conab.py"

# Cadência do levantamento: a CONAB publica custos de produção da soja a cada
# dois meses. Passados quatro meses do levantamento em uso, é quase certo que
# há um mais recente publicado — e o workflow avisa em vez de seguir exibindo
# um preço velho como se fosse o atual.
MESES_ATE_SUSPEITAR = 4

# A URL do arquivo no portal não está fixada no código de propósito: o portal é
# uma aplicação de painéis e o endereço do arquivo muda com ela. Configurar a
# variável de repositório CONAB_CUSTOS_URL (Settings > Variables) liga o modo
# automático sem alterar código; sem ela, vale o modo --arquivo.
ENV_URL = "CONAB_CUSTOS_URL"

# Cada planilha é reconhecida pelo cabeçalho, não pelo nome do arquivo: o
# portal exporta tudo como "dados.csv".
PLANILHAS = {
    "serie_pedro_afonso_to.csv": {
        "chave": "Ano-Mes.Ano-Mes",
        "colunas": ("Renda de Fatores", "Custo Fixo", "Custo Variável",
                    "Preco Mercado", "Preco Mínimo", "Margem Bruta",
                    "Margem Liquida"),
        "modo": "historico",
    },
    "custo_producao_por_municipio.csv": {
        "chave": "municipio",
        "colunas": ("RENDA DE FATORES", "CUSTO FIXO", "CUSTO VARIAVEL",
                    "PRECO RECEBIDO"),
        "modo": "retrato",
    },
    "custo_variavel_e_produtividade_por_municipio.csv": {
        "chave": "Municipio.Municipio",
        "colunas": ("Custo Variavel Unid Comercializacao(R$)", "Produtividade"),
        "modo": "retrato",
    },
    "custo_producao_por_uf.csv": {
        "chave": "uf",
        "colunas": ("RENDA DE FATORES", "CUSTO FIXO", "CUSTO VARIAVEL",
                    "PRECO RECEBIDO"),
        "modo": "retrato",
    },
}


class ConteudoInesperado(RuntimeError):
    """O que chegou não é uma planilha de custos da CONAB."""


def _linhas(texto: str) -> tuple[list[str], list[dict]]:
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    return (leitor.fieldnames or []), list(leitor)


def identificar(texto: str) -> tuple[str, dict]:
    """Descobre a qual planilha o conteúdo corresponde, pelo cabeçalho."""
    cabecalho, _ = _linhas(texto)
    limpo = [c.strip().strip('"') for c in cabecalho]
    for nome, forma in PLANILHAS.items():
        if limpo and limpo[0] == forma["chave"] and \
                all(c in limpo for c in forma["colunas"]):
            return nome, forma
    raise ConteudoInesperado(
        f"cabeçalho não reconhecido: {limpo[:4]}. Esperava a primeira coluna "
        f"em {[f['chave'] for f in PLANILHAS.values()]} — confira se o arquivo "
        f"é a exportação em CSV do Portal de Informações Agropecuárias.")


def _texto_do_csv(cabecalho: list[str], linhas: list[dict]) -> str:
    """Reescreve no formato que o portal exporta: primeira coluna entre aspas,
    as demais sem, separador ';'.

    O csv.DictWriter não reproduz isso — cita tudo ou nada — e um diff em que
    todas as linhas mudam de aspas esconderia a mudança real do levantamento na
    revisão do PR, que é justamente o que se quer ler ali.
    """
    def escrever(campos: list[str]) -> str:
        return ";".join([f'"{campos[0]}"'] + list(campos[1:]))

    saida = [escrever(cabecalho)]
    saida += [escrever([linha[c] for c in cabecalho]) for linha in linhas]
    return "\n".join(saida) + "\n"


def aplicar(texto: str, simular: bool = False) -> tuple[str, list[str]]:
    """Grava a planilha no lugar certo. Devolve (arquivo, o que mudou)."""
    nome, forma = identificar(texto)
    destino = CONAB / nome
    cab_novo, linhas_novas = _linhas(texto)
    if not linhas_novas:
        raise ConteudoInesperado(f"{nome}: a planilha veio sem linhas")

    mudancas: list[str] = []
    if forma["modo"] == "historico":
        # Série histórica: acrescenta levantamentos e nunca reescreve o passado
        # em silêncio. A CONAB revisa valores publicados, e uma revisão que
        # mexe no que a dissertação cita tem que aparecer no diff do PR.
        cab_atual, atuais = _linhas(destino.read_text(encoding="utf-8"))
        chave = forma["chave"]
        por_chave = {l[chave]: l for l in atuais}
        for linha in linhas_novas:
            k = linha[chave]
            if k not in por_chave:
                mudancas.append(f"levantamento novo: {k.strip(chr(34))}")
                atuais.append(linha)
            elif por_chave[k] != linha:
                antes = por_chave[k].get("Preco Mercado")
                mudancas.append(
                    f"revisão em {k.strip(chr(34))}: preço "
                    f"{antes} -> {linha.get('Preco Mercado')}")
                atuais[atuais.index(por_chave[k])] = linha
        conteudo = _texto_do_csv(cab_atual, atuais)
    else:
        # Retrato do levantamento corrente: substitui inteiro.
        antigo = destino.read_text(encoding="utf-8") if destino.exists() else ""
        conteudo = _texto_do_csv(cab_novo, linhas_novas)
        if conteudo != antigo:
            mudancas.append(f"{len(linhas_novas)} linhas substituídas")

    if mudancas and not simular:
        destino.write_text(conteudo, encoding="utf-8")
    return nome, mudancas


def baixar(url: str, tempo: int = 30) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent":
                      "AgroInteligencia-Dissertacao/1.0 (UFPA/EngSoft7)"})
    with urllib.request.urlopen(req, timeout=tempo) as resp:
        bruto = resp.read()
    for codec in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return bruto.decode(codec)
        except UnicodeDecodeError:
            continue
    raise ConteudoInesperado(f"{url}: não decodifica como texto")


def levantamento_em_uso() -> tuple[str, int, int]:
    """(rótulo, ano, mês) do levantamento que o produto está exibindo."""
    sys.path.insert(0, str(GERADOR.parent))
    import gera_levantamento_conab as g

    serie = [l for l in g.ler_serie() if l["preco_recebido_saca"] > 0]
    rotulo = serie[-1]["levantamento"]
    ano, mes = g._chave_ordem(rotulo)
    return rotulo, ano, mes


def meses_de_defasagem() -> tuple[str, int]:
    """Quantos meses separam o levantamento em uso de hoje.

    Não depende de rede: é a única checagem que funciona mesmo sem fonte
    configurada, e é o que permite ao workflow avisar que provavelmente há
    levantamento novo em vez de exibir um preço velho calado.
    """
    rotulo, ano, mes = levantamento_em_uso()
    hoje = date.today()
    return rotulo, (hoje.year - ano) * 12 + (hoje.month - mes)


def _saida(**campos) -> None:
    """Escreve os campos em GITHUB_OUTPUT, se houver. Fora do Actions, imprime."""
    linhas = [f"{k}={v}" for k, v in campos.items()]
    destino = os.environ.get("GITHUB_OUTPUT")
    if destino:
        with open(destino, "a", encoding="utf-8") as fh:
            fh.write("\n".join(linhas) + "\n")
    else:
        for linha in linhas:
            print(f"  [saida] {linha}")


def rodar_gerador() -> int:
    return subprocess.call([sys.executable, str(GERADOR)])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arquivo", action="append", default=[], type=Path,
                    help="planilha CSV exportada do portal (pode repetir)")
    ap.add_argument("--url", default=os.environ.get(ENV_URL, ""),
                    help=f"fonte a baixar (padrão: variável {ENV_URL})")
    ap.add_argument("--testar", action="store_true",
                    help="diz o que a fonte devolve e sai, sem gravar nada")
    ap.add_argument("--simular", action="store_true",
                    help="relata o que mudaria, sem gravar")
    args = ap.parse_args(argv)

    rotulo, defasagem = meses_de_defasagem()
    print(f"levantamento em uso: {rotulo} ({defasagem} meses atrás)")

    conteudos: list[str] = []
    for caminho in args.arquivo:
        conteudos.append(caminho.read_text(encoding="utf-8-sig"))
    if args.url:
        try:
            conteudos.append(baixar(args.url))
        except Exception as e:
            print(f"::warning::não foi possível baixar {args.url}: "
                  f"{type(e).__name__}: {e}")
            if args.testar:
                return 1

    if args.testar:
        if not conteudos:
            print(f"::warning::nenhuma fonte configurada. Defina a variável de "
                  f"repositório {ENV_URL} com o endereço da exportação em CSV "
                  f"do portal, ou use --arquivo.")
            return 1
        for texto in conteudos:
            try:
                nome, forma = identificar(texto)
                _, linhas = _linhas(texto)
                print(f"  reconhecido como {nome} ({forma['modo']}), "
                      f"{len(linhas)} linhas")
            except ConteudoInesperado as e:
                print(f"::error::{e}")
                return 1
        print("fonte válida: o conteúdo é uma planilha de custos da CONAB.")
        return 0

    defasado = "true" if defasagem >= MESES_ATE_SUSPEITAR else "false"
    if not conteudos:
        # Sem fonte configurada, resta a verificação que não precisa de rede.
        if defasado == "true":
            print(f"::warning::o levantamento {rotulo} tem {defasagem} meses. "
                  f"A CONAB publica a cada dois meses, então provavelmente há "
                  f"um mais recente.")
        _saida(csv_alterado="false", revisao="false", defasado=defasado,
               levantamento=rotulo, meses=defasagem)
        return 0

    todas: list[str] = []
    for texto in conteudos:
        try:
            nome, mudancas = aplicar(texto, simular=args.simular)
        except ConteudoInesperado as e:
            print(f"::error::{e}")
            return 1
        if mudancas:
            todas += [f"{nome}: {m}" for m in mudancas]
            print(f"{nome}: {len(mudancas)} mudança(s)")
            for m in mudancas:
                print(f"  - {m}")
        else:
            print(f"{nome}: sem mudanças")

    # Revisão de levantamento já publicado é diferente de levantamento novo: o
    # número revisado pode ser um que a dissertação cita, e por isso o workflow
    # não mergeia sozinho um PR que contenha revisão.
    houve_revisao = any("revisão em" in m for m in todas)
    if not todas:
        print("nada a atualizar.")
        _saida(csv_alterado="false", revisao="false", defasado=defasado,
               levantamento=rotulo, meses=defasagem)
        return 0
    if args.simular:
        print("(simulação: nada foi gravado)")
        _saida(csv_alterado="false", revisao=str(houve_revisao).lower(),
               defasado=defasado, levantamento=rotulo, meses=defasagem)
        return 0

    print("propagando para o painel, a API e o aplicativo...")
    codigo = rodar_gerador()
    if codigo != 0:
        print("::error::o gerador recusou os dados novos; os CSVs foram "
              "gravados mas o levantamento NÃO foi propagado. Confira a "
              "mensagem acima antes de commitar.")
    _saida(csv_alterado="true", revisao=str(houve_revisao).lower(),
           defasado="false", levantamento=rotulo, meses=defasagem)
    resumo = os.environ.get("RESUMO_MD")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as fh:
            fh.write("\nLevantamento de custos da CONAB atualizado:\n\n")
            for m in todas:
                fh.write(f"- {m}\n")
            if houve_revisao:
                fh.write(
                    "\n> **Há revisão de levantamento já publicado.**\n"
                    "> A CONAB reviu um valor que o produto já exibia, e que a\n"
                    "> subseção 4.9 da dissertação pode citar. Este PR **não foi\n"
                    "> mergeado automaticamente**: confira o diff antes.\n")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
