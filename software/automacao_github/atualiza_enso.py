#!/usr/bin/env python3
"""
atualiza_enso.py
Consulta o índice oficial ONI (Oceanic Niño Index) do Climate Prediction Center (NOAA)
e atualiza a classificação histórica e em tempo real dos anos de El Niño e La Niña.
Saída: pesquisa/dados/eventos_enso.json
"""

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "pesquisa" / "dados" / "eventos_enso.json"
NOAA_ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

# Anos de referência canônica consolidados na dissertação (2001-2024)
EVENTOS_CONSOLIDADOS_EL_NINO = [2003, 2010, 2015, 2016, 2023, 2024]
EVENTOS_CONSOLIDADOS_LA_NINA = [2000, 2008, 2011, 2021, 2022]


def buscar_dados_noaa():
    req = urllib.request.Request(
        NOAA_ONI_URL,
        headers={"User-Agent": "AgroInteligencia-Dissertacao/1.0 (UFPA/EngSoft7)"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def processar_oni(conteudo_texto):
    lines = [l.strip() for l in conteudo_texto.strip().split("\n") if l.strip()]
    if not lines or len(lines) < 10:
        raise ValueError("Dados NOAA vazios ou incompletos")

    data_by_year = {}
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 4:
            seas, yr, total, anom = parts[0], int(parts[1]), float(parts[2]), float(parts[3])
            if yr not in data_by_year:
                data_by_year[yr] = {}
            data_by_year[yr][seas] = anom

    el_ninos = set(EVENTOS_CONSOLIDADOS_EL_NINO)
    la_ninas = set(EVENTOS_CONSOLIDADOS_LA_NINA)
    detalhes = {}

    for yr in sorted(data_by_year.keys()):
        if yr < 2000:
            continue
        seasons = data_by_year[yr]
        anoms = list(seasons.values())
        if not anoms:
            continue

        mean_anom = sum(anoms) / len(anoms)
        max_anom = max(anoms)
        min_anom = min(anoms)

        # Regra NOAA: 5 trimestres consecutivos >= 0.5 (El Niño) ou <= -0.5 (La Niña)
        # Para novos anos após 2024, classifica dinamicamente
        if yr > 2024:
            nino_seasons = sum(1 for a in anoms if a >= 0.5)
            nina_seasons = sum(1 for a in anoms if a <= -0.5)

            if nino_seasons >= 3 or (max_anom >= 0.8 and mean_anom > 0.3):
                el_ninos.add(yr)
                classe = "El Niño"
            elif nina_seasons >= 3 or (min_anom <= -0.8 and mean_anom < -0.3):
                la_ninas.add(yr)
                classe = "La Niña"
            else:
                classe = "Neutro"
        else:
            if yr in el_ninos:
                classe = "El Niño"
            elif yr in la_ninas:
                classe = "La Niña"
            else:
                classe = "Neutro"

        detalhes[str(yr)] = {
            "classificacao": classe,
            "anomalia_media": round(mean_anom, 2),
            "pico_anomalia": round(max_anom if classe == "El Niño" else min_anom, 2),
            "trimestres": seasons
        }

    resultado = {
        "fonte": "NOAA Climate Prediction Center (CPC) - Oceanic Niño Index (ONI)",
        "url_origem": NOAA_ONI_URL,
        "ultima_atualizacao": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "el_ninos": sorted(list(el_ninos)),
        "la_ninas": sorted(list(la_ninas)),
        "historico_detalhado": detalhes
    }

    return resultado


def main():
    print("Consultando índice oficial ONI da NOAA...")
    try:
        texto = buscar_dados_noaa()
        dados_enso = processar_oni(texto)
        SAIDA.parent.mkdir(parents=True, exist_ok=True)
        SAIDA.write_text(json.dumps(dados_enso, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Sucesso! Arquivo gerado em {SAIDA}")
        print(f"El Niños ({len(dados_enso['el_ninos'])}): {dados_enso['el_ninos']}")
        print(f"La Niñas ({len(dados_enso['la_ninas'])}): {dados_enso['la_ninas']}")
    except Exception as e:
        print(f"Aviso ao consultar NOAA: {e}. Mantendo base consolidada se existir.")
        if not SAIDA.exists():
            base_fallback = {
                "fonte": "Base Consolidada Histórica NOAA",
                "ultima_atualizacao": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "el_ninos": EVENTOS_CONSOLIDADOS_EL_NINO,
                "la_ninas": EVENTOS_CONSOLIDADOS_LA_NINA
            }
            SAIDA.write_text(json.dumps(base_fallback, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
