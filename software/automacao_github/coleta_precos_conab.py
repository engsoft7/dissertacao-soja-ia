# -*- coding: utf-8 -*-
"""Preço da soja em grão recebido pelo produtor, da CONAB: por semana e município, e por mês e estado.

A CONAB levanta toda semana os preços agropecuários e publica o resultado no
Portal de Informações Agropecuárias, em arquivos de texto abertos:

    PrecosSemanalMunicipio.txt   semana a semana, por município levantado
    PrecosMensalUF.txt           média do mês, por unidade da federação

Os dois trazem todos os produtos e níveis de comercialização (varejo, atacado,
preço pago e preço recebido pelo produtor), em R$/kg. Daqui sai só a soja em
grão no preço recebido pelo produtor, nos cinco estados do produto
(software/api_backend/estados.py), também em R$/saca de 60 kg. É a reserva
oficial da Agrolink, que não tem contrato com o produto e já mudou de formato
sem aviso.

O portal ficou com o certificado emitido para outro nome de 23/10 a 15/11/2026
(visto pelo monitor das fontes), e a coleta esperou: baixar sem conferir o
certificado não garante que o arquivo é da CONAB. A verificação fica sempre
ligada.

O formato, conferido em 16/11/2026: separador ";", campos com espaços à
direita, decimal com vírgula, valor vazio quando não houve cotação, e linhas em
UTF-8 misturadas com linhas em Latin-1 no mesmo arquivo. No arquivo semanal o
nível de comercialização vem cortado em 20 caracteres ("PREÇO RECEBIDO P/ PR");
no mensal, inteiro. Um cabeçalho diferente do esperado interrompe a coleta com
erro, e o workflow abre uma issue em vez de gravar dado lido errado.

Os CSVs gravados guardam o histórico: a cada coleta, as linhas novas entram e
as que a CONAB revisou são trocadas, mas uma semana que saia do arquivo dela
continua aqui.

Uso:
    python coleta_precos_conab.py --diagnostico
        baixa e resume, sem gravar nada
    python coleta_precos_conab.py --saida pesquisa/dados/conab [--resumo resumo.md]
        grava precos_soja_semanal_municipio.csv e precos_soja_mensal_uf.csv
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator

import requests

PASTA = "https://portaldeinformacoes.conab.gov.br/downloads/arquivos/"
URL_SEMANAL = PASTA + "PrecosSemanalMunicipio.txt"
URL_MENSAL = PASTA + "PrecosMensalUF.txt"
PAGINA = "https://portaldeinformacoes.conab.gov.br/download-arquivos.html"
UA = {"User-Agent": "AgroInteligencia-Dissertacao/1.0 (UFPA; pesquisa academica)"}
ESTADOS = ("PA", "MT", "MA", "TO", "RO")
SACA_KG = 60
# Faixa de plausibilidade em R$/saca, a mesma de precos_para.py: fora dela é
# erro de digitação ou de unidade, e a linha fica de fora (e aparece no resumo).
PRECO_MIN, PRECO_MAX = 40.0, 400.0

COLUNAS_SEMANAL = ("produto", "classificao_produto", "id_produto", "nom_municipio", "cod_ibge", "uf",
                   "regiao", "ano", "mes", "data_inicial_final_semana", "semana",
                   "dsc_nivel_comercializacao", "valor_produto_kg")
COLUNAS_MENSAL = ("produto", "classificao_produto", "id_produto", "uf", "regiao", "ano", "mes",
                  "dsc_nivel_comercializacao", "valor_produto_kg")

ARQ_SEMANAL = "precos_soja_semanal_municipio.csv"
ARQ_MENSAL = "precos_soja_mensal_uf.csv"
CAMPOS_SEMANAL = ("uf", "cod_ibge", "municipio", "inicio", "fim", "preco_kg", "preco_saca")
CAMPOS_MENSAL = ("uf", "ano", "mes", "preco_kg", "preco_saca")

_MINUSCULAS = {"DA", "DAS", "DE", "DO", "DOS", "E"}


class FormatoNovo(RuntimeError):
    """O arquivo da CONAB não tem o formato esperado: a coleta para em vez de gravar dado lido errado."""


def texto(bruto: bytes) -> str:
    """Uma linha do arquivo: UTF-8 quando for, senão Latin-1, porque o arquivo mistura os dois."""
    try:
        return bruto.decode("utf-8")
    except UnicodeDecodeError:
        return bruto.decode("cp1252", "replace")


def normaliza(s: str) -> str:
    """Sem acento, em maiúsculas e com um espaço só entre as palavras."""
    s = unicodedata.normalize("NFKD", s)
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).upper().split())


def numero(s: str) -> float | None:
    """'2,08' → 2.08; vazio ou ilegível → None."""
    s = s.strip()
    if not s:
        return None
    try:
        return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)
    except ValueError:
        return None


def semana(s: str) -> tuple[date, date]:
    """'17-11-2025 - 21-11-2025' → (17/11/2025, 21/11/2025)."""
    datas = re.findall(r"(\d{2})-(\d{2})-(\d{4})", s)
    if len(datas) != 2:
        raise ValueError(f"semana ilegível: {s!r}")
    ini, fim = (date(int(a), int(m), int(d)) for d, m, a in datas)
    if fim < ini:
        raise ValueError(f"semana invertida: {s!r}")
    return ini, fim


def nome_municipio(bruto: str, uf: str) -> str:
    """'PRIMAVERA DO LESTE-MT' → 'Primavera do Leste'; "ALTA FLORESTA D'OESTE-RO" → "Alta Floresta D'Oeste"."""
    n = bruto.strip()
    if n.upper().endswith("-" + uf.upper()):
        n = n[: -len(uf) - 1].strip()
    palavras = []
    for i, p in enumerate(n.split()):
        if i and p.upper() in _MINUSCULAS:
            palavras.append(p.lower())
        else:
            palavras.append("'".join(q[:1].upper() + q[1:].lower() for q in p.split("'")))
    return " ".join(palavras)


def registros(linhas: Iterable[bytes], colunas: tuple[str, ...],
              descartes: collections.Counter | None = None) -> Iterator[dict[str, str]]:
    """As linhas do arquivo como dicionários, depois de conferir o cabeçalho."""
    it = iter(linhas)
    for bruto in it:
        cabecalho = texto(bruto).lstrip("﻿").strip()
        if cabecalho:
            break
    else:
        raise FormatoNovo("arquivo vazio")
    nomes = tuple(c.strip().lower() for c in cabecalho.split(";"))
    if nomes != colunas:
        raise FormatoNovo(f"cabeçalho {nomes}; esperado {colunas}")
    for bruto in it:
        linha = texto(bruto).rstrip("\r\n")
        if not linha.strip():
            continue
        campos = [c.strip() for c in linha.split(";")]
        if len(campos) != len(colunas):
            if descartes is not None:
                descartes["linha com outro número de campos"] += 1
            continue
        yield dict(zip(colunas, campos))


def soja_recebido(r: dict[str, str]) -> bool:
    """Soja em grão, preço recebido pelo produtor.

    O teste é folgado de propósito: "EM GRÃOS" e "PREÇO RECEBIDO" chegam com
    acento, sem acento ou cortados, conforme a linha e o arquivo. Os outros
    níveis (varejo, atacado, preço pago pelo produtor) não têm "RECEBIDO".
    """
    return (normaliza(r["produto"]) == "SOJA" and normaliza(r["classificao_produto"]).startswith("EM GR")
            and "RECEBIDO" in normaliza(r["dsc_nivel_comercializacao"]))


def _preco(valor: str, descartes: collections.Counter) -> tuple[float, float] | None:
    kg = numero(valor)
    if kg is None:
        descartes["sem valor"] += 1
        return None
    saca = round(kg * SACA_KG, 2)
    if not PRECO_MIN <= saca <= PRECO_MAX:
        descartes["fora da faixa de R$ 40 a R$ 400 por saca"] += 1
        return None
    return kg, saca


def semanal_por_municipio(linhas: Iterable[bytes]) -> tuple[list[dict], collections.Counter]:
    """Soja em grão, preço recebido pelo produtor, por município e semana, nos estados do produto."""
    saida: dict[tuple, dict] = {}
    descartes: collections.Counter = collections.Counter()
    for r in registros(linhas, COLUNAS_SEMANAL, descartes):
        uf = r["uf"].upper()
        if uf not in ESTADOS or not soja_recebido(r):
            continue
        preco = _preco(r["valor_produto_kg"], descartes)
        if preco is None:
            continue
        try:
            ini, fim = semana(r["data_inicial_final_semana"])
        except ValueError:
            descartes["semana ilegível"] += 1
            continue
        chave = (uf, r["cod_ibge"], ini.isoformat())
        if chave in saida and saida[chave]["preco_kg"] != preco[0]:
            descartes["semana repetida com outro valor (vale a última)"] += 1
        saida[chave] = {"uf": uf, "cod_ibge": r["cod_ibge"], "municipio": nome_municipio(r["nom_municipio"], uf),
                        "inicio": ini.isoformat(), "fim": fim.isoformat(),
                        "preco_kg": preco[0], "preco_saca": preco[1]}
    return _ordena_semanal(saida.values()), descartes


def mensal_por_uf(linhas: Iterable[bytes]) -> tuple[list[dict], collections.Counter]:
    """Soja em grão, preço recebido pelo produtor, média do mês em cada estado do produto."""
    saida: dict[tuple, dict] = {}
    descartes: collections.Counter = collections.Counter()
    for r in registros(linhas, COLUNAS_MENSAL, descartes):
        uf = r["uf"].upper()
        if uf not in ESTADOS or not soja_recebido(r):
            continue
        preco = _preco(r["valor_produto_kg"], descartes)
        if preco is None:
            continue
        try:
            ano, mes = int(r["ano"]), int(r["mes"])
            if not 1 <= mes <= 12:
                raise ValueError
        except ValueError:
            descartes["mês ilegível"] += 1
            continue
        saida[(uf, ano, mes)] = {"uf": uf, "ano": ano, "mes": mes, "preco_kg": preco[0], "preco_saca": preco[1]}
    return _ordena_mensal(saida.values()), descartes


def _ordena_semanal(linhas: Iterable[dict]) -> list[dict]:
    return sorted(linhas, key=lambda x: (x["uf"], x["municipio"], x["cod_ibge"], x["inicio"]))


def _ordena_mensal(linhas: Iterable[dict]) -> list[dict]:
    return sorted(linhas, key=lambda x: (x["uf"], int(x["ano"]), int(x["mes"])))


def _formata(v) -> str:
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return str(v)


def le_csv(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def junta(antigas: list[dict], novas: list[dict], chave: tuple[str, ...]) -> list[dict]:
    """O histórico gravado mais a coleta de agora; na mesma chave, vale a coleta de agora."""
    por_chave = {tuple(str(l[c]) for c in chave): {k: _formata(v) for k, v in l.items()} for l in antigas}
    for l in novas:
        por_chave[tuple(str(l[c]) for c in chave)] = {k: _formata(v) for k, v in l.items()}
    return list(por_chave.values())


def grava(linhas: list[dict], campos: tuple[str, ...], caminho: Path) -> bool:
    """Grava o CSV; devolve se o conteúdo mudou."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=campos, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for l in linhas:
        w.writerow({k: _formata(l[k]) for k in campos})
    novo = buf.getvalue()
    if caminho.exists() and caminho.read_text(encoding="utf-8") == novo:
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(novo, encoding="utf-8")
    return True


def _reais(v) -> str:
    return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _br(iso: str) -> str:
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


def resumo(semanal: list[dict], mensal: list[dict], descartes: collections.Counter) -> str:
    """O que há em cada estado, para o log e para o corpo do PR."""
    out = ["## Preço da soja em grão recebido pelo produtor (CONAB)", "",
           f"Fonte: [Portal de Informações Agropecuárias da CONAB]({PAGINA}), "
           "arquivos PrecosSemanalMunicipio.txt e PrecosMensalUF.txt. Valores em R$/saca de 60 kg.", ""]
    if semanal:
        out += ["### Por semana e município", "", "| UF | Município | Semanas | Desde | Última semana | Preço |",
                "|---|---|---:|---|---|---:|"]
        grupos = collections.defaultdict(list)
        for l in semanal:
            grupos[(l["uf"], l["municipio"])].append(l)
        for (uf, mun), ls in sorted(grupos.items()):
            ls = sorted(ls, key=lambda x: x["inicio"])
            out.append(f"| {uf} | {mun} | {len(ls)} | {_br(ls[0]['inicio'])} | "
                       f"{_br(ls[-1]['inicio'])} a {_br(ls[-1]['fim'])} | {_reais(ls[-1]['preco_saca'])} |")
        out.append("")
    if mensal:
        out += ["### Média do mês por estado", "", "| UF | Meses | Desde | Último mês | Preço |", "|---|---:|---|---|---:|"]
        grupos = collections.defaultdict(list)
        for l in mensal:
            grupos[l["uf"]].append(l)
        for uf, ls in sorted(grupos.items()):
            ls = sorted(ls, key=lambda x: (int(x["ano"]), int(x["mes"])))
            out.append(f"| {uf} | {len(ls)} | {int(ls[0]['mes']):02d}/{ls[0]['ano']} | "
                       f"{int(ls[-1]['mes']):02d}/{ls[-1]['ano']} | {_reais(ls[-1]['preco_saca'])} |")
        out.append("")
    sem_dado = [uf for uf in ESTADOS if uf not in {l["uf"] for l in semanal} | {l["uf"] for l in mensal}]
    if sem_dado:
        out += [f"Sem preço de soja em grão nos arquivos: {', '.join(sem_dado)}.", ""]
    if descartes:
        out += ["Linhas deixadas de fora: " + "; ".join(f"{n} {motivo}" for motivo, n in sorted(descartes.items())) + ".", ""]
    return "\n".join(out)


def baixa(url: str) -> Iterator[bytes]:
    """As linhas do arquivo, com a verificação de certificado ligada (o padrão do requests)."""
    with requests.get(url, headers=UA, timeout=120, stream=True) as r:
        r.raise_for_status()
        yield from r.iter_lines()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--diagnostico", action="store_true", help="baixa e resume, sem gravar nada")
    ap.add_argument("--saida", type=Path, help="pasta onde gravar os CSVs (pesquisa/dados/conab)")
    ap.add_argument("--resumo", type=Path, help="grava também o resumo em Markdown neste arquivo")
    args = ap.parse_args(argv)
    if not args.diagnostico and args.saida is None:
        ap.error("use --diagnostico ou --saida")

    semanal, d1 = semanal_por_municipio(baixa(URL_SEMANAL))
    mensal, d2 = mensal_por_uf(baixa(URL_MENSAL))
    if not semanal and not mensal:
        raise FormatoNovo("nenhuma linha de soja em grão (preço recebido pelo produtor) nos estados do produto")

    if args.saida is not None and not args.diagnostico:
        semanal = _ordena_semanal(junta(le_csv(args.saida / ARQ_SEMANAL), semanal, ("uf", "cod_ibge", "inicio")))
        mensal = _ordena_mensal(junta(le_csv(args.saida / ARQ_MENSAL), mensal, ("uf", "ano", "mes")))
        mudou = [nome for nome, linhas, campos in ((ARQ_SEMANAL, semanal, CAMPOS_SEMANAL),
                                                   (ARQ_MENSAL, mensal, CAMPOS_MENSAL))
                 if grava(linhas, campos, args.saida / nome)]
        print("Arquivos alterados:", ", ".join(mudou) if mudou else "nenhum")

    texto_resumo = resumo(semanal, mensal, d1 + d2)
    print(texto_resumo)
    if args.resumo is not None:
        args.resumo.write_text(texto_resumo, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
