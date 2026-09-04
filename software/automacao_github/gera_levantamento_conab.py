#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gera_levantamento_conab.py

Consolida as extrações da CONAB de pesquisa/dados/conab/ num único arquivo
legível por máquina — levantamento_atual.json — que é o que o produto lê em
tempo de execução.

Por que existe: até a versão 2.3.2 o preço recebido e o custo de produção eram
literais Python repetidos em financas.py, app.py, MainActivity.kt e três
READMEs, com a data do levantamento escrita por extenso em cada legenda.
Atualizar a CONAB significava editar oito lugares e recompilar o APK — o que,
na prática, quer dizer que não se atualizava. Com este arquivo, trocar o CSV da
série e rodar este script atualiza preço, custo, rótulo da praça, data do
levantamento e a posição do preço na série histórica de uma vez só.

Duas regras de integridade, porque são as que já erraram antes neste produto:

1. Preço e custo saem do MESMO levantamento. Se a CONAB publicar um
   levantamento novo sem divulgar preço (acontece: JAN e MAR de 2024 saem com
   0,00 na planilha), o script fica no último levantamento COM preço em vez de
   misturar o custo novo com o preço velho — ou, pior, tratar o 0,00 como
   cotação. Foi misturar praças assim que fez a versão anterior exibir a
   cotação de Chicago como preço de porteira.

2. Os dois CSVs têm que ser do mesmo levantamento. O custo variável por saca
   aparece na série histórica e na planilha por município; se divergirem, os
   arquivos vieram de extrações diferentes e o script falha em vez de publicar
   um número híbrido.

Uso:
    python software/automacao_github/gera_levantamento_conab.py [--conferir]

--conferir não escreve nada: só verifica se o JSON no disco corresponde aos
CSVs. É o que o CI roda para garantir que ninguém editou um sem o outro.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONAB = RAIZ / "pesquisa" / "dados" / "conab"
SERIE_CSV = CONAB / "serie_pedro_afonso_to.csv"
MUNICIPIOS_CSV = CONAB / "custo_producao_por_municipio.csv"
PRODUTIVIDADE_CSV = CONAB / "custo_variavel_e_produtividade_por_municipio.csv"
SAIDA = CONAB / "levantamento_atual.json"

# Praça de referência. O Pará não integra o MATOPIBA e não tem levantamento de
# custo de soja; adota-se o ponto de coleta da CONAB no cerrado do Tocantins.
PRACA_CSV = "PEDRO AFONSO-TO"
PRACA_ROTULO = "Pedro Afonso (TO)"

FONTE = "https://portaldeinformacoes.conab.gov.br/custos-de-producao.html"
SACA_KG = 60

MESES = {"JAN": "janeiro", "FEV": "fevereiro", "MAR": "março", "ABR": "abril",
         "MAI": "maio", "JUN": "junho", "JUL": "julho", "AGO": "agosto",
         "SET": "setembro", "OUT": "outubro", "NOV": "novembro",
         "DEZ": "dezembro"}
ORDEM_MES = {sigla: i for i, sigla in enumerate(MESES, start=1)}


class LevantamentoInconsistente(RuntimeError):
    """Os CSVs não descrevem um mesmo levantamento."""


def _por_extenso(rotulo: str) -> str:
    """'MAR-2026' -> 'março de 2026'."""
    mes, _, ano = rotulo.partition("-")
    return f"{MESES[mes.upper()]} de {ano}"


def _curto(rotulo: str) -> str:
    """'MAR-2026' -> 'mar/2026'."""
    mes, _, ano = rotulo.partition("-")
    return f"{mes.lower()}/{ano}"


def _chave_ordem(rotulo: str) -> tuple[int, int]:
    mes, _, ano = rotulo.partition("-")
    return (int(ano), ORDEM_MES[mes.upper()])


def _ler_csv(caminho: Path) -> list[dict]:
    with caminho.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def ler_serie() -> list[dict]:
    """Série histórica da praça, em ordem cronológica, já convertida."""
    linhas = []
    for bruta in _ler_csv(SERIE_CSV):
        rotulo = bruta["Ano-Mes.Ano-Mes"].strip().strip('"')
        linhas.append({
            "levantamento": rotulo,
            "preco_recebido_saca": float(bruta["Preco Mercado"]),
            "custo_fixo_saca": float(bruta["Custo Fixo"]),
            "custo_variavel_saca": float(bruta["Custo Variável"]),
            "renda_fatores_saca": float(bruta["Renda de Fatores"]),
            "margem_liquida_saca": float(bruta["Margem Liquida"]),
        })
    return sorted(linhas, key=lambda l: _chave_ordem(l["levantamento"]))


def produtividade_da_praca() -> float:
    """Produtividade de referência do levantamento, em kg/ha.

    É a base da conversão do custo por saca para custo por hectare: a CONAB
    publica o custo por saca comercializada, não por área.
    """
    for linha in _ler_csv(PRODUTIVIDADE_CSV):
        if linha["Municipio.Municipio"].strip().strip('"').upper() == PRACA_CSV:
            return float(linha["Produtividade"])
    raise LevantamentoInconsistente(
        f"{PRACA_CSV} não está em {PRODUTIVIDADE_CSV.name}")


def custo_variavel_publicado() -> float:
    """Custo variável por saca na planilha por município, para conferência."""
    for linha in _ler_csv(PRODUTIVIDADE_CSV):
        if linha["Municipio.Municipio"].strip().strip('"').upper() == PRACA_CSV:
            return float(linha["Custo Variavel Unid Comercializacao(R$)"])
    raise LevantamentoInconsistente(
        f"{PRACA_CSV} não está em {PRODUTIVIDADE_CSV.name}")


def montar() -> dict:
    serie = ler_serie()
    if not serie:
        raise LevantamentoInconsistente(f"{SERIE_CSV.name} está vazio")

    # Regra 1: preço e custo do mesmo levantamento. Levantamentos publicados
    # sem preço saem com 0,00 e não são cotação.
    com_preco = [l for l in serie if l["preco_recebido_saca"] > 0]
    if not com_preco:
        raise LevantamentoInconsistente(
            f"nenhum levantamento de {SERIE_CSV.name} tem preço divulgado")
    atual = com_preco[-1]
    posteriores = [l["levantamento"] for l in serie
                   if _chave_ordem(l["levantamento"]) > _chave_ordem(atual["levantamento"])]

    # Regra 2: os dois CSVs precisam ser do mesmo levantamento.
    publicado = custo_variavel_publicado()
    if round(publicado, 2) != round(atual["custo_variavel_saca"], 2):
        raise LevantamentoInconsistente(
            f"custo variável divergente entre os arquivos: "
            f"{SERIE_CSV.name} diz R$ {atual['custo_variavel_saca']:.2f}/sc no "
            f"levantamento {atual['levantamento']}, e {PRODUTIVIDADE_CSV.name} "
            f"diz R$ {publicado:.2f}/sc. Os dois CSVs têm que vir da mesma "
            f"extração — atualize os dois ou nenhum.")

    prod_kg = produtividade_da_praca()
    prod_sc = prod_kg / SACA_KG

    custo_operacional_sc = atual["custo_fixo_saca"] + atual["custo_variavel_saca"]
    custo_total_sc = custo_operacional_sc + atual["renda_fatores_saca"]

    precos = [l["preco_recebido_saca"] for l in com_preco]
    ordenados = sorted(precos)
    maior = max(com_preco, key=lambda l: l["preco_recebido_saca"])
    menor = min(com_preco, key=lambda l: l["preco_recebido_saca"])
    periodo = (f"{_por_extenso(com_preco[0]['levantamento'])} a "
               f"{_por_extenso(com_preco[-1]['levantamento'])}")
    # Versão compacta, para caber em legenda de celular.
    periodo_curto = (f"{_curto(com_preco[0]['levantamento'])} a "
                     f"{_curto(com_preco[-1]['levantamento'])}")

    dados = {
        "praca": PRACA_ROTULO,
        "praca_csv": PRACA_CSV,
        "levantamento": atual["levantamento"],
        "levantamento_extenso": _por_extenso(atual["levantamento"]),
        "fonte": FONTE,
        "gerado_em": date.today().isoformat(),
        "gerado_por": "software/automacao_github/gera_levantamento_conab.py",

        "preco_recebido_saca": round(atual["preco_recebido_saca"], 2),
        "custo_variavel_saca": round(atual["custo_variavel_saca"], 2),
        "custo_fixo_saca": round(atual["custo_fixo_saca"], 2),
        "custo_operacional_saca": round(custo_operacional_sc, 2),
        "renda_fatores_saca": round(atual["renda_fatores_saca"], 2),
        "custo_total_saca": round(custo_total_sc, 2),
        "margem_liquida_saca": round(atual["margem_liquida_saca"], 2),

        "produtividade_referencia_kg_ha": prod_kg,
        "produtividade_referencia_sc_ha": round(prod_sc, 2),
        "custo_variavel_ha": round(atual["custo_variavel_saca"] * prod_sc, 2),
        "custo_operacional_ha": round(custo_operacional_sc * prod_sc, 2),
        "custo_total_ha": round(custo_total_sc * prod_sc, 2),
        "renda_fatores_ha": round(atual["renda_fatores_saca"] * prod_sc, 2),

        "serie": {
            "levantamentos": len(com_preco),
            "periodo": periodo,
            "periodo_curto": periodo_curto,
            "menor_saca": round(menor["preco_recebido_saca"], 2),
            "menor_levantamento": menor["levantamento"],
            "menor_levantamento_extenso": _por_extenso(menor["levantamento"]),
            "maior_saca": round(maior["preco_recebido_saca"], 2),
            "maior_levantamento": maior["levantamento"],
            "maior_levantamento_extenso": _por_extenso(maior["levantamento"]),
            "mediana_saca": round(statistics.median(precos), 2),
            "media_saca": round(statistics.fmean(precos), 2),
            # 1 = o preço atual é o menor da série.
            "posicao_do_atual": ordenados.index(atual["preco_recebido_saca"]) + 1,
            "levantamentos_negativos": [l["levantamento"] for l in com_preco
                                        if l["margem_liquida_saca"] < 0],
        },
        # Levantamentos mais recentes que o adotado, publicados sem preço. Se a
        # lista não estiver vazia, o custo em uso é o do último com cotação.
        "levantamentos_sem_preco": posteriores,
    }
    dados["textos"] = _textos(dados)
    return dados


# ── SINCRONIZAÇÃO DAS RESERVAS DE EMERGÊNCIA ─────────────────────────────────
# financas.py e app.py carregam o JSON, mas guardam uma cópia literal do
# levantamento para subirem com números corretos se o arquivo não chegar ao
# deploy. As duas cópias são reescritas aqui, entre marcadores, para que
# atualizar a CONAB continue sendo um comando só: sem isso, o PR automático
# traria o JSON novo e deixaria duas reservas defasadas para alguém editar à
# mão — que é exatamente o trabalho manual que este arquivo existe para
# eliminar. test_robustez_painel.py confere o resultado.
INICIO = "# reserva-conab-inicio"
FIM = "# reserva-conab-fim"

RESERVAS = (
    (RAIZ / "software" / "api_backend" / "financas.py",
     "LEVANTAMENTO_RESERVA", None),
    (RAIZ / "software" / "dashboard_web" / "app.py",
     "LEVANTAMENTO_CONAB_RESERVA",
     # O painel não usa o levantamento inteiro; guardar só o que ele lê deixa
     # a reserva legível e evita fingir que app.py conhece campos que ignora.
     ("praca", "levantamento", "levantamento_extenso", "preco_recebido_saca",
      "custo_operacional_saca", "produtividade_referencia_kg_ha",
      "produtividade_referencia_sc_ha", "custo_operacional_ha",
      "custo_total_ha", "renda_fatores_ha", "serie", "textos")),
)


def _literal(dados: dict, nome: str) -> str:
    """Dicionário Python legível, para a reserva ser conferível a olho.

    Usa json.dumps porque o pprint quebra em colunas e produz um bloco difícil
    de ler numa revisão de PR. JSON de dicionários com chaves de texto já é
    literal Python válido; só os três valores abaixo não teriam tradução, e o
    levantamento não os contém.
    """
    if any(isinstance(v, bool) or v is None
           for v in _valores(dados)):
        raise LevantamentoInconsistente(
            "o levantamento tem booleano ou nulo, que não sobrevivem à "
            "conversão para literal Python")
    corpo = json.dumps(dados, ensure_ascii=False, indent=4)
    corpo = "\n".join(l if i == 0 else l for i, l in enumerate(corpo.splitlines()))
    return f"{nome} = {corpo}"


def _valores(no):
    """Todos os valores escalares de uma estrutura aninhada."""
    if isinstance(no, dict):
        for v in no.values():
            yield from _valores(v)
    elif isinstance(no, list):
        for v in no:
            yield from _valores(v)
    else:
        yield no


def sincronizar_reservas(levantamento: dict, conferir: bool = False) -> list[str]:
    """Reescreve (ou confere) as cópias literais. Devolve o que está defasado."""
    # gerado_em muda a cada execução e não é dado da CONAB: fora da reserva,
    # senão todo mês haveria diff só para trocar um carimbo de data.
    base = {k: v for k, v in levantamento.items() if k != "gerado_em"}
    defasados = []
    for caminho, nome, chaves in RESERVAS:
        dados = base if chaves is None else {k: base[k] for k in chaves}
        texto = caminho.read_text(encoding="utf-8")
        ini = texto.index(INICIO)
        ini = texto.index("\n", ini) + 1
        fim = texto.index(FIM)
        novo = texto[:ini] + _literal(dados, nome) + "\n" + texto[fim:]
        if novo == texto:
            continue
        defasados.append(str(caminho.relative_to(RAIZ)))
        if not conferir:
            caminho.write_text(novo, encoding="utf-8")
    return defasados


def _brl(valor: float, casas: int = 2) -> str:
    """R$ no formato brasileiro: 1234.5 -> 'R$ 1.234,50'."""
    return "R$ " + f"{valor:,.{casas}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _textos(d: dict) -> dict:
    """Frases prontas para a interface, geradas junto com os números.

    Ficam aqui, e não escritas nas telas, porque são a única parte da interface
    que envelhece quando a CONAB publica levantamento novo. Geradas com os
    dados, o painel exibe a frase certa na hora e a API a serve ao aplicativo —
    que passa a acompanhar o levantamento sem recompilar o APK.
    """
    s = d["serie"]
    n, pos = s["levantamentos"], s["posicao_do_atual"]
    if n < 2:
        posicao = "o único levantamento disponível"
    elif pos == 1:
        posicao = f"o menor dos {n} levantamentos"
    elif pos == n:
        posicao = f"o maior dos {n} levantamentos"
    else:
        posicao = f"o {pos}º menor dos {n} levantamentos"
    # Metade de baixo da série: a margem calculada é conservadora. Metade de
    # cima: é otimista, e o usuário precisa saber disso do mesmo jeito.
    if n < 2:
        fecho = ""
    elif pos <= (n + 1) // 2:
        fecho = " Cenário conservador, não previsão de preço."
    else:
        fecho = " Cenário otimista: a série já esteve bem abaixo disso."

    nota_preco = (f"{_brl(d['preco_recebido_saca'])}/sc é {posicao} da praça "
                  f"({s['periodo_curto']}, mediana {_brl(s['mediana_saca'])})."
                  f"{fecho}")
    # O .replace fica isolado numa variável de propósito: aplicado à frase
    # inteira ele trocava também o separador decimal de "R$ 109,94".
    prod_kg = f"{d['produtividade_referencia_kg_ha']:,.0f}".replace(",", ".")
    nota_custo = (f"Custo operacional de {_brl(d['custo_operacional_saca'])}/sc, "
                  f"convertido para {_brl(d['custo_operacional_ha'])}/ha pela "
                  f"produtividade de referência do próprio levantamento "
                  f"({prod_kg} kg/ha, "
                  f"{d['produtividade_referencia_sc_ha']:.0f} sc/ha).")
    return {
        "descricao": f"CONAB, {d['praca']}, {d['levantamento_extenso']}",
        "nota_preco": nota_preco,
        "nota_custo": nota_custo,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--conferir", action="store_true",
                    help="não escreve; só verifica se o JSON bate com os CSVs")
    args = ap.parse_args(argv)

    try:
        novo = montar()
    except LevantamentoInconsistente as e:
        print(f"::error::levantamento da CONAB inconsistente: {e}", flush=True)
        return 1

    if args.conferir:
        if not SAIDA.exists():
            print(f"::error::{SAIDA.name} não existe; rode o script sem --conferir")
            return 1
        atual = json.loads(SAIDA.read_text(encoding="utf-8"))
        # gerado_em muda a cada execução e não é dado da CONAB.
        comparavel = {k: v for k, v in novo.items() if k != "gerado_em"}
        no_disco = {k: v for k, v in atual.items() if k != "gerado_em"}
        if comparavel != no_disco:
            print("::error::levantamento_atual.json está defasado em relação "
                  "aos CSVs da CONAB. Rode "
                  "`python software/automacao_github/gera_levantamento_conab.py`.")
            for chave in sorted(set(comparavel) | set(no_disco)):
                if comparavel.get(chave) != no_disco.get(chave):
                    print(f"  {chave}: disco={no_disco.get(chave)!r} "
                          f"csv={comparavel.get(chave)!r}")
            return 1
        defasados = sincronizar_reservas(novo, conferir=True)
        if defasados:
            print("::error::as reservas de emergência estão defasadas em "
                  f"relação ao levantamento: {', '.join(defasados)}. Rode "
                  "`python software/automacao_github/gera_levantamento_conab.py`.")
            return 1
        print(f"{SAIDA.name} e as reservas de emergência conferem com os "
              f"CSVs da CONAB.")
        return 0

    SAIDA.write_text(json.dumps(novo, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    s = novo["serie"]
    print(f"{SAIDA.name}: levantamento {novo['levantamento']} "
          f"({novo['levantamento_extenso']}) em {novo['praca']}")
    print(f"  preço recebido      R$ {novo['preco_recebido_saca']:.2f}/sc "
          f"({s['posicao_do_atual']}º menor de {s['levantamentos']} da série)")
    print(f"  custo operacional   R$ {novo['custo_operacional_saca']:.2f}/sc "
          f"= R$ {novo['custo_operacional_ha']:.2f}/ha")
    for arquivo in sincronizar_reservas(novo):
        print(f"  reserva de emergência atualizada em {arquivo}")
    if novo["levantamentos_sem_preco"]:
        print(f"  aviso: {', '.join(novo['levantamentos_sem_preco'])} "
              f"publicado(s) sem preço; mantido o último com cotação.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
