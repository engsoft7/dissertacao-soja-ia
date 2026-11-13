# -*- coding: utf-8 -*-
"""Monta a base do produto nos outros estados da Amazônia Legal, no formato da do Pará.

A dissertação deixa como trabalho futuro estender o produto a outros estados
da Amazônia Legal. O protocolo da Tabela 6 já rodou neles
(pesquisa/10_trabalhos_futuros/06_amazonia_legal.py): em Mato Grosso os quatro
modelos superam a referência; no Maranhão, a Random Forest e a SVR; em Rondônia,
só a SVR; em Tocantins, nenhum ganho resiste à correção para comparações
múltiplas. Nos dois últimos o produto entra como no Pará: a estimativa quase
coincide com a referência, e a tela mostra as duas lado a lado. Este script
leva os mesmos registros ao formato que a API e o painel leem, um arquivo por
estado em pesquisa/dados/estados/:

  soja_<UF>_painel.csv   variáveis de satélite e clima por município e safra
                         (coleta/coleta_amazonia_legal.py, a mesma conta da base
                         do Pará) com a produtividade da PAM; entra o registro
                         com soja na máscara do MapBiomas e as variáveis completas
  pam_soja_<UF>.csv      a série oficial inteira (cod_ibge7, ano, kg/ha), também
                         dos municípios e safras fora da máscara, para o
                         histórico do aplicativo não parar anos atrás
  municipios_<UF>.csv    nome oficial e sede (latitude, longitude)
  <UF>_geo.json          contorno do estado, para o mapa

Fontes:
  - PAM/IBGE pelo SIDRA, tabela 5457 (a do Pará, em atualiza_pam.py); sem
    acesso, a extração de 03_analise_nacional/pam_soja_municipios.csv, até 2024.
  - Sedes: kelvins/municipios-brasileiros, o mesmo conjunto aberto de
    gera_municipios.py.
  - Contorno: malha do IBGE (API de malhas, qualidade mínima). Essa API não
    atendeu do Actions em nenhuma tentativa de novembro de 2026; sem ela, o
    contorno sai dos limites estaduais do IBGE republicados no projeto Click
    That Hood, da Code for America (brazil-states.geojson), simplificados
    aqui para o detalhe do contorno do Pará.

Os nomes da coleta vêm do GAUL, sem acento e às vezes de antes de um
desmembramento; o pareamento com o IBGE é pelo nome normalizado dentro do
estado, como em 06_amazonia_legal.py, e o que não pareia é listado. Com dois
nomes corrigidos à mão (ALIASES), Mato Grosso fica com 118 municípios, dois a
mais que na análise da pesquisa.

Quando a PAM publica uma safra que a coleta ainda não tem, a base do modelo
para na safra anterior, e só a série oficial avança. `--faltam` lista essas
safras ("UF ano", uma por linha), a partir do que já está em
pesquisa/dados/estados/; a atualização mensal as coleta no Earth Engine
(coleta/coleta_amazonia_legal.py) e monta a base de novo.

Uso:   python software/automacao_github/monta_base_estados.py [MT MA TO RO]
       python software/automacao_github/monta_base_estados.py --faltam
       SEM_IBGE=1 python ...   sem tentar o SIDRA e a malha (onde o IBGE não é alcançável)
"""
from __future__ import annotations

import csv
import glob
import io
import json
import math
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
COLETA = RAIZ / "pesquisa" / "10_trabalhos_futuros" / "dados"
PAM_NACIONAL = RAIZ / "pesquisa" / "03_analise_nacional" / "pam_soja_municipios.csv"
SAIDA = RAIZ / "pesquisa" / "dados" / "estados"

ESTADOS = {"MT": 51, "MA": 21, "TO": 17, "RO": 11}
COLUNAS = ["municipio", "ano", "soy_area_ha", "NDVI_mean", "NDVI_max", "EVI_mean", "EVI_max",
           "precip_total", "temp_mean", "temp_max", "srad_mean", "etp_total", "cod_ibge7",
           "rendimento_kg_ha"]
VARIAVEIS = COLUNAS[3:12]

URL_SIDRA = ("https://apisidra.ibge.gov.br/values"
             "/t/5457/n6/in%20n3%20{uf}/v/112/p/all/c782/40124?formato=json")
URL_MALHA = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
             "?formato=application/vnd.geo+json&qualidade=minima")
URL_SEDES = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
URL_MALHA_RESERVA = ("https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/"
                     "brazil-states.geojson")
TOLERANCIA_GRAUS = 0.02      # cerca de 2 km: o detalhe do contorno do Pará no mapa


def chave(s) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return re.sub(r"[^a-z]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def baixa(url: str, tentativas: int = 3, espera_s: int = 20) -> requests.Response | None:
    if os.environ.get("SEM_IBGE") and "ibge.gov.br" in url:
        return None
    for i in range(1, tentativas + 1):
        try:
            # 20 s para conectar: o servidor de malhas do IBGE às vezes não
            # atende, e esperar dois minutos a cada tentativa não ajuda.
            r = requests.get(url, timeout=(20, 120))
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            print(f"  {url[:70]}…: {type(e).__name__} (tentativa {i}/{tentativas})", flush=True)
            if i < tentativas:
                time.sleep(espera_s)
    return None


def pam_do_estado(uf: str) -> tuple[pd.DataFrame, str]:
    """cod_ibge7, nome, ano, rendimento_kg_ha de todos os municípios do estado com soja."""
    r = baixa(URL_SIDRA.format(uf=ESTADOS[uf]))
    if r is not None:
        bruto = pd.DataFrame(r.json())
        bruto = bruto[bruto["V"] != "Valor"]
        t = bruto[["D1C", "D1N", "D3C", "V"]].rename(
            columns={"D1C": "cod_ibge7", "D1N": "nome", "D3C": "ano", "V": "rendimento_kg_ha"})
        fonte = "SIDRA, tabela 5457"
    else:
        p = pd.read_csv(PAM_NACIONAL)
        t = p[(p.uf == uf) & (p.area_plantada_ha > 0)][["cod_ibge7", "nome", "ano", "rendimento_kg_ha"]]
        fonte = f"{PAM_NACIONAL.relative_to(RAIZ)} (SIDRA fora do ar)"
    for c in ("cod_ibge7", "ano", "rendimento_kg_ha"):
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t = t.dropna()
    t = t[t.rendimento_kg_ha > 0].astype({"cod_ibge7": int, "ano": int})
    t["nome"] = t.nome.str.replace(r"\s+-\s+[A-Z]{2}$", "", regex=True).str.strip()
    return t.sort_values(["cod_ibge7", "ano"]).reset_index(drop=True), fonte


def coleta_do_estado(uf: str) -> pd.DataFrame:
    """Variáveis da coleta do GEE, num arquivo ou em partes (MT foi coletado por faixas de anos)."""
    partes = sorted(glob.glob(str(COLETA / f"amazonia_legal_{uf}.csv")) +
                    glob.glob(str(COLETA / f"amazonia_legal_{uf}_*.csv")))
    if not partes:
        raise SystemExit(f"nenhuma coleta de {uf} em {COLETA}")
    return (pd.concat([pd.read_csv(f) for f in partes], ignore_index=True)
            .drop_duplicates(["municipio_gaul", "ano"], keep="last"))


# Nomes do GAUL que não batem com o do IBGE nem normalizados: o município
# mudou de nome (Poxoréo virou Poxoréu em 2017) ou o GAUL troca a preposição.
ALIASES = {"poxoreo": "poxoreu", "santoantoniodoleverger": "santoantoniodeleverger"}


def monta_base(coleta: pd.DataFrame, pam: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Registros com soja na máscara, variáveis completas e produtividade oficial."""
    nomes = pam.drop_duplicates("cod_ibge7").assign(k=lambda d: d.nome.map(chave))
    # Dois municípios com o mesmo nome normalizado no estado não pareiam: melhor de fora que trocado.
    nomes = nomes[~nomes.k.duplicated(keep=False)]
    cod_por_chave = nomes.set_index("k").cod_ibge7
    nome_por_cod = nomes.set_index("cod_ibge7").nome
    g = coleta.assign(k=coleta.municipio_gaul.map(chave).replace(ALIASES))
    g["cod_ibge7"] = g.k.map(cod_por_chave)
    sem_par = sorted(g[g.cod_ibge7.isna()].municipio_gaul.unique())
    g = g.dropna(subset=["cod_ibge7"]).astype({"cod_ibge7": int})
    df = g.merge(pam[["cod_ibge7", "ano", "rendimento_kg_ha"]], on=["cod_ibge7", "ano"], how="inner")
    df = df[df.soy_area_ha > 0].dropna(subset=VARIAVEIS + ["rendimento_kg_ha"])
    df["municipio"] = df.cod_ibge7.map(nome_por_cod)
    df["rendimento_kg_ha"] = df.rendimento_kg_ha.round().astype(int)
    return df[COLUNAS].sort_values(["municipio", "ano"]).reset_index(drop=True), sem_par


def sedes(codigos, nomes: dict[int, str]) -> pd.DataFrame:
    r = baixa(URL_SEDES)
    if r is None:
        raise SystemExit("sem as coordenadas das sedes")
    r.encoding = "utf-8"
    coords = {int(l["codigo_ibge"]): (float(l["latitude"]), float(l["longitude"]))
              for l in csv.DictReader(io.StringIO(r.text))}
    linhas = [{"cod_ibge7": c, "municipio": nomes[c], "latitude": coords[c][0], "longitude": coords[c][1]}
              for c in sorted(codigos) if c in coords]
    faltam = sorted(set(codigos) - set(coords))
    if faltam:
        print(f"  sem coordenada: {faltam}")
    return pd.DataFrame(linhas).sort_values("municipio")


def simplifica(anel: list, tolerancia: float) -> list:
    """Douglas-Peucker: tira os vértices que se afastam menos que a tolerância da linha entre os vizinhos mantidos."""
    if len(anel) < 5:
        return anel
    # Anel fechado: parte em dois no vértice mais distante do primeiro, para a corda não ter comprimento zero.
    longe = max(range(len(anel)), key=lambda k: math.hypot(anel[k][0] - anel[0][0], anel[k][1] - anel[0][1]))
    manter = [False] * len(anel)
    manter[0] = manter[longe] = manter[-1] = True
    pilha = [(0, longe), (longe, len(anel) - 1)]
    while pilha:
        i, j = pilha.pop()
        (x1, y1), (x2, y2) = anel[i], anel[j]
        dx, dy = x2 - x1, y2 - y1
        n = math.hypot(dx, dy)
        maior, k = 0.0, None
        for q in range(i + 1, j):
            x, y = anel[q]
            d = abs(dy * (x - x1) - dx * (y - y1)) / n if n else math.hypot(x - x1, y - y1)
            if d > maior:
                maior, k = d, q
        if k is not None and maior > tolerancia:
            manter[k] = True
            pilha += [(i, k), (k, j)]
    return [p for p, m in zip(anel, manter) if m]


_reserva: dict | None = None


def contorno_reserva(uf: str) -> dict | None:
    """O contorno do estado nos limites do IBGE republicados no Click That Hood, simplificado."""
    global _reserva
    if _reserva is None:
        r = baixa(URL_MALHA_RESERVA)
        _reserva = r.json() if r is not None else {}
    f = next((f for f in _reserva.get("features", []) if f.get("properties", {}).get("sigla") == uf), None)
    if f is None:
        return None
    g = f["geometry"]
    poligonos = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]

    def caixa(pol):
        xs, ys = [p[0] for p in pol[0]], [p[1] for p in pol[0]]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))

    maior = max(caixa(p) for p in poligonos)
    saida = []
    for pol in poligonos:
        if caixa(pol) < 0.01 * maior:          # ilhas pequenas não aparecem no fundo do mapa
            continue
        aneis = [simplifica([[float(x), float(y)] for x, y in anel], TOLERANCIA_GRAUS) for anel in pol]
        aneis = [a for a in aneis if len(a) >= 4]
        if aneis:
            saida.append(aneis)
    if not saida:
        return None
    geometria = ({"type": "Polygon", "coordinates": saida[0]} if len(saida) == 1
                 else {"type": "MultiPolygon", "coordinates": saida})
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": geometria}]}


def contorno(uf: str, destino: Path) -> str | None:
    """Grava o contorno do estado e devolve de onde ele veio; None se nenhuma fonte atendeu."""
    # Como gera_geo_para.py: a API de malhas oscila, e vale tentar mais vezes.
    r = baixa(URL_MALHA.format(uf=ESTADOS[uf]), tentativas=3, espera_s=20)
    geo, fonte = (r.json() if r is not None else None), "malha do IBGE"
    if geo is not None and (geo.get("type") != "FeatureCollection" or not geo.get("features")):
        print(f"  malha de {uf} em formato inesperado: {str(geo)[:200]}")
        geo = None
    if geo is None:
        geo, fonte = contorno_reserva(uf), "limites do IBGE no Click That Hood (Code for America), simplificados"
    if geo is None:
        return None
    # Como o do Pará: sem propriedades e com 3 casas decimais (~100 m), que bastam ao fundo do mapa.
    def arredonda(x):
        return [arredonda(v) for v in x] if isinstance(x, list) else round(x, 3) if isinstance(x, float) else x
    for f in geo["features"]:
        f.pop("properties", None)
        if "coordinates" in f.get("geometry", {}):
            f["geometry"]["coordinates"] = arredonda(f["geometry"]["coordinates"])
    destino.write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return fonte


def safras_novas(anos_pam, anos_coletados) -> list[int]:
    """Safras publicadas na PAM depois da última que a coleta tem."""
    ultima = max(anos_coletados, default=0)
    return sorted(int(a) for a in set(anos_pam) if a > ultima)


def faltam(ufs: list[str]) -> list[tuple[str, int]]:
    saida = []
    for uf in ufs:
        pam = SAIDA / f"pam_soja_{uf}.csv"
        if not pam.exists():
            continue
        saida += [(uf, a) for a in safras_novas(pd.read_csv(pam).ano, coleta_do_estado(uf).ano)]
    return saida


def main(ufs: list[str]) -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    leia = SAIDA / "LEIA-ME.json"
    resumo_anterior = json.loads(leia.read_text(encoding="utf-8")).get("estados", {}) if leia.exists() else {}
    # Rodando para parte dos estados, os outros ficam como estavam no LEIA-ME.
    resumo = {uf: e for uf, e in resumo_anterior.items() if uf not in ufs}
    for uf in ufs:
        print(f"{uf}:", flush=True)
        pam, fonte = pam_do_estado(uf)
        base, sem_par = monta_base(coleta_do_estado(uf), pam)
        base.to_csv(SAIDA / f"soja_{uf}_painel.csv", index=False)
        (pam[["cod_ibge7", "ano", "rendimento_kg_ha"]].assign(rendimento_kg_ha=lambda d: d.rendimento_kg_ha.round()
                                                             .astype(int))
         .to_csv(SAIDA / f"pam_soja_{uf}.csv", index=False))
        nomes = pam.drop_duplicates("cod_ibge7").set_index("cod_ibge7").nome.to_dict()
        sedes(base.cod_ibge7.unique(), nomes).to_csv(SAIDA / f"municipios_{uf}.csv", index=False)
        arq_geo = SAIDA / f"{uf.lower()}_geo.json"
        anterior = resumo_anterior.get(uf, {})
        # Com o contorno do IBGE já gravado, não se troca pelo da reserva nem se pede de novo.
        if arq_geo.exists() and anterior.get("contorno_fonte") == "malha do IBGE":
            fonte_contorno = "malha do IBGE"
        else:
            fonte_contorno = contorno(uf, arq_geo) or (anterior.get("contorno_fonte") if arq_geo.exists() else None)
        tem_contorno = arq_geo.exists()
        resumo[uf] = {"fonte_pam": fonte, "registros": int(len(base)), "municipios": int(base.cod_ibge7.nunique()),
                      "safras": [int(base.ano.min()), int(base.ano.max())],
                      "ultima_safra_pam": int(pam.ano.max()), "municipios_na_pam": int(pam.cod_ibge7.nunique()),
                      "coleta_sem_par_no_ibge": sem_par, "contorno": tem_contorno,
                      "contorno_fonte": fonte_contorno}
        print(json.dumps(resumo[uf], ensure_ascii=False, indent=1), flush=True)
    (SAIDA / "LEIA-ME.json").write_text(json.dumps(
        {"gerado_por": "software/automacao_github/monta_base_estados.py", "estados": resumo},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    if "--faltam" in sys.argv[1:]:
        for uf, ano in faltam([a.upper() for a in sys.argv[1:] if a != "--faltam"] or list(ESTADOS)):
            print(uf, ano)
        sys.exit(0)
    sys.exit(main([a.upper() for a in sys.argv[1:]] or list(ESTADOS)))
