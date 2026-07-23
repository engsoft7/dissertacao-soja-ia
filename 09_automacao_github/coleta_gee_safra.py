# -*- coding: utf-8 -*-
"""
Coleta automática (sem login manual) das variáveis ambientais de UMA safra nova
e acréscimo das linhas à base do painel.

Porta fiel de 01_coleta_dados/02_coleta_gee_com_mascara_mapbiomas.py — mesmas
coleções (MOD13Q1, CHIRPS, ERA5-Land), mesma janela nov(Y-1)–mai(Y), mesma
máscara de soja do MapBiomas (classe 39) — executada de forma headless no
GitHub Actions com uma service account do Google Earth Engine.

Requisitos de ambiente:
    GEE_SERVICE_ACCOUNT_JSON  conteúdo do JSON de chave da service account
                              (secret do repositório; ver README)
    GEE_PROJECT               opcional; padrão: project_id da própria chave

Uso:
    python 07_automacao/coleta_gee_safra.py --ano 2025

Se o MapBiomas ainda não publicou a máscara do ano-alvo, usa-se a máscara mais
recente disponível e o fato é registrado no resumo do PR — as áreas de soja
variam pouco entre anos consecutivos, mas a aproximação fica documentada.

As linhas novas são ACRESCENTADAS ao CSV (o conteúdo existente não é regravado),
no mesmo esquema de colunas do arquivo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

from atualiza_pam import CSV_PAINEL, baixa_sidra, grava_saidas, marca_atualizacao

MES_INI, DIA_INI = 11, 1   # plantio ~novembro do ano anterior
MES_FIM, DIA_FIM = 5, 31   # colheita ~maio do ano da safra
COLL_ID = 10.1             # Coleção MapBiomas
CLASSE_SOJA = 39

BANDAS = ["NDVI_mean", "NDVI_max", "EVI_mean", "EVI_max", "precip_total",
          "temp_mean", "temp_max", "srad_mean", "etp_total"]


def chave(s: str) -> str:
    """Nome normalizado para parear GAUL ("Nome") com IBGE ("Nome - PA")."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\spa$", "", s)


def conecta_gee():
    """Autentica no Earth Engine SEM jamais ecoar a chave no log.

    As exceções da pilha de autenticação do Google podem embutir o conteúdo da
    credencial na mensagem — e o log do Actions é público. Por isso a chave é
    validada antes, e qualquer erro é reduzido a uma mensagem segura.
    """
    import ee

    chave_json = os.environ["GEE_SERVICE_ACCOUNT_JSON"]
    try:
        info = json.loads(chave_json)
    except ValueError:
        sys.exit("GEE_SERVICE_ACCOUNT_JSON não é um JSON válido. Cole o conteúdo "
                 "integral do arquivo de chave baixado do Google Cloud, sem editar.")
    faltando = [c for c in ("client_email", "private_key", "project_id") if c not in info]
    if faltando:
        sys.exit(f"GEE_SERVICE_ACCOUNT_JSON sem os campos {faltando}. Gere uma "
                 "chave JSON da service account e cole o arquivo inteiro.")
    if not str(info["private_key"]).startswith("-----BEGIN PRIVATE KEY-----"):
        sys.exit("O campo private_key do secret está corrompido (não começa com "
                 "'-----BEGIN PRIVATE KEY-----'). Revogue esta chave no Google "
                 "Cloud, gere uma nova e substitua o secret sem editar o texto.")
    try:
        credencial = ee.ServiceAccountCredentials(info["client_email"], key_data=chave_json)
        ee.Initialize(credencial, project=os.environ.get("GEE_PROJECT", info.get("project_id")))
    except Exception as err:
        detalhe = str(err)
        if "PRIVATE KEY" in detalhe or "private_key" in detalhe or len(detalhe) > 400:
            detalhe = f"{type(err).__name__} (detalhe omitido para não expor a credencial)"
        sys.exit(f"Falha ao autenticar no Earth Engine: {detalhe}\n"
                 "Verifique: service account no MESMO projeto registrado no Earth "
                 "Engine, papel 'Gravador de recursos do Earth Engine' e API "
                 "earthengine.googleapis.com ativada.")
    print("Earth Engine conectado como", info["client_email"])
    return ee


def coleta_features(ano: int) -> tuple[pd.DataFrame, int]:
    """Preditores por município do Pará para a safra `ano`.

    Retorna (DataFrame, ano_da_mascara_usada). Espelha coleta_ano() do script
    original do Colab.
    """
    ee = conecta_gee()

    gaul = ee.FeatureCollection("FAO/GAUL/2015/level2")
    brasil = gaul.filter(ee.Filter.eq("ADM0_NAME", "Brazil"))
    nomes = brasil.aggregate_array("ADM1_NAME").distinct().getInfo()
    alvo = [n for n in nomes if n.strip().lower() in ("pará", "para")]
    assert alvo, f"Pará não encontrado no GAUL: {sorted(nomes)}"
    para = brasil.filter(ee.Filter.eq("ADM1_NAME", alvo[0]))

    MODIS = ee.ImageCollection("MODIS/061/MOD13Q1")
    CHIRPS = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
    ERA5 = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
    MB = (ee.ImageCollection("projects/mapbiomas-public/assets/brazil/lulc/v1")
          .filter(ee.Filter.eq("collection_id", COLL_ID)))

    ini = ee.Date.fromYMD(ano - 1, MES_INI, DIA_INI)
    fim = ee.Date.fromYMD(ano, MES_FIM, DIA_FIM)

    col = MB.filter(ee.Filter.eq("year", ano))
    ano_mascara = ano
    if col.size().getInfo() == 0:
        disponiveis = [a for a in MB.aggregate_array("year").distinct().getInfo() if a <= ano]
        assert disponiveis, f"MapBiomas sem nenhuma máscara até {ano}"
        ano_mascara = max(disponiveis)
        col = MB.filter(ee.Filter.eq("year", ano_mascara))
        print(f"MapBiomas ainda sem {ano}; usando a máscara de {ano_mascara}")
    soja = col.mosaic().select("classification").eq(CLASSE_SOJA)

    veg = MODIS.filterDate(ini, fim)
    e = ERA5.filterDate(ini, fim)
    bandas = ee.Image.cat([
        veg.select("NDVI").mean().multiply(0.0001).updateMask(soja).rename("NDVI_mean"),
        veg.select("NDVI").max().multiply(0.0001).updateMask(soja).rename("NDVI_max"),
        veg.select("EVI").mean().multiply(0.0001).updateMask(soja).rename("EVI_mean"),
        veg.select("EVI").max().multiply(0.0001).updateMask(soja).rename("EVI_max"),
        CHIRPS.filterDate(ini, fim).select("precipitation").sum().rename("precip_total"),
        e.select("temperature_2m").mean().subtract(273.15).rename("temp_mean"),
        e.select("temperature_2m_max").mean().subtract(273.15).rename("temp_max"),
        e.select("surface_solar_radiation_downwards_sum").mean().divide(1e6).rename("srad_mean"),
        e.select("potential_evaporation_sum").sum().multiply(-1000).rename("etp_total"),
    ])
    med = bandas.reduceRegions(collection=para, reducer=ee.Reducer.mean(), scale=250)
    area = soja.multiply(ee.Image.pixelArea()).divide(1e4).rename("soy_area_ha")
    ar = area.reduceRegions(collection=para, reducer=ee.Reducer.sum(), scale=30)

    areas = {f["properties"]["ADM2_NAME"]: f["properties"].get("sum", 0)
             for f in ar.getInfo()["features"]}
    linhas = []
    for f in med.getInfo()["features"]:
        p = f["properties"]
        if p.get("NDVI_mean") is None:  # município sem soja mapeada
            continue
        reg = {"municipio": p["ADM2_NAME"], "ano": ano,
               "soy_area_ha": areas.get(p["ADM2_NAME"], 0)}
        for b in BANDAS:
            reg[b] = p.get(b)
        linhas.append(reg)
    print(f"GEE: {len(linhas)} municípios com soja mapeada em {ano} "
          f"(máscara {ano_mascara})")
    return pd.DataFrame(linhas), ano_mascara


def testa_conexao() -> int:
    """Valida a credencial e o acesso aos ativos da coleta, sem tocar na base."""
    ee = conecta_gee()
    n = (ee.FeatureCollection("FAO/GAUL/2015/level2")
         .filter(ee.Filter.eq("ADM0_NAME", "Brazil"))
         .filter(ee.Filter.inList("ADM1_NAME", ["Pará", "Para"]))
         .size().getInfo())
    mb = (ee.ImageCollection("projects/mapbiomas-public/assets/brazil/lulc/v1")
          .filter(ee.Filter.eq("collection_id", COLL_ID)))
    anos = sorted(mb.aggregate_array("year").distinct().getInfo())
    print(f"GAUL: {n} municípios do Pará acessíveis")
    print(f"MapBiomas Coleção {COLL_ID}: máscaras de {anos[0]} a {anos[-1]}")
    print("Teste concluído: credencial e ativos do Earth Engine OK.")
    return 0


def monta_linhas(pred: pd.DataFrame, sidra: pd.DataFrame, ano: int,
                 colunas: list[str], existentes: set[tuple[int, int]]) -> pd.DataFrame:
    """Junta preditores e rendimento oficial; devolve só registros novos e completos."""
    ibge = sidra[sidra["ano"] == ano].copy()
    ibge["chave"] = ibge["nome_ibge"].map(chave)
    pred = pred.copy()
    pred["chave"] = pred["municipio"].map(chave)
    m = pred.merge(ibge[["chave", "cod_ibge7", "rendimento_kg_ha"]], on="chave")
    m = m.drop(columns="chave").dropna(subset=BANDAS + ["rendimento_kg_ha"])
    m = m[[c for c in colunas]]  # ordem exata do CSV
    novos = [
        i for i, r in m.iterrows()
        if (int(r["cod_ibge7"]), ano) not in existentes
    ]
    return m.loc[novos]


def formata_linha(r: pd.Series, colunas: list[str]) -> str:
    campos = []
    for c in colunas:
        v = r[c]
        if c == "municipio":
            campos.append(str(v))
        elif c in ("ano", "cod_ibge7", "rendimento_kg_ha"):
            campos.append(str(int(round(float(v)))))
        else:
            campos.append(repr(float(v)))
    return ",".join(campos)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, help="ano-safra a coletar")
    ap.add_argument("--testar", action="store_true",
                    help="só autentica no Earth Engine e verifica o acesso aos ativos")
    args = ap.parse_args()
    if args.testar:
        return testa_conexao()
    if args.ano is None:
        ap.error("--ano é obrigatório fora do modo --testar")
    ano = args.ano

    texto = CSV_PAINEL.read_text(encoding="utf-8")
    colunas = texto.splitlines()[0].split(",")
    base = pd.read_csv(CSV_PAINEL)
    existentes = {(int(c), int(a)) for c, a in zip(base["cod_ibge7"], base["ano"])}

    sidra = baixa_sidra()
    if not (sidra["ano"] == ano).any():
        sys.exit(f"SIDRA ainda não publica rendimento para {ano}; nada a fazer.")

    pred, ano_mascara = coleta_features(ano)
    novas = monta_linhas(pred, sidra, ano, colunas, existentes)
    if not len(novas):
        sys.exit(f"Nenhum registro novo montado para {ano}: verifique o pareamento.")

    linhas_txt = [formata_linha(r, colunas) for _, r in novas.iterrows()]
    with open(CSV_PAINEL, "a", encoding="utf-8") as f:
        if not texto.endswith("\n"):
            f.write("\n")
        f.write("\n".join(linhas_txt) + "\n")
    marca_atualizacao()
    print(f"{len(novas)} linhas da safra {ano} acrescentadas a {CSV_PAINEL.name}")

    resumo_md = os.environ.get("RESUMO_MD")
    if resumo_md:
        with open(resumo_md, "a", encoding="utf-8") as f:
            f.write(
                f"\n**Safra {ano} incorporada automaticamente:** {len(novas)} "
                f"municípios coletados no Earth Engine (MOD13Q1, CHIRPS, "
                f"ERA5-Land; máscara MapBiomas de {ano_mascara}"
                + (", pois a do ano-alvo ainda não foi publicada" if ano_mascara != ano else "")
                + ") e rendimento oficial do SIDRA.\n"
            )

    grava_saidas(csv_alterado="true", linhas_novas=str(len(novas)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
