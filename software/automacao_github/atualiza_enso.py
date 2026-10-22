#!/usr/bin/env python3
"""
atualiza_enso.py
Consulta o índice oficial ONI (Oceanic Niño Index) do Climate Prediction Center
(NOAA) e classifica cada SAFRA de soja como El Niño, La Niña ou neutra.
Saída: pesquisa/dados/eventos_enso.json

Regra (a mesma da tabela de episódios da NOAA):
  1. um episódio é uma sequência de pelo menos 5 trimestres móveis seguidos com
     ONI >= +0,5 °C (El Niño) ou <= -0,5 °C (La Niña);
  2. a safra Y, colhida em Y, é classificada pelo trimestre dezembro-fevereiro
     (DJF de Y), o meio do ciclo da soja no Pará (plantio em outubro-janeiro,
     colheita em fevereiro-maio): é El Niño se o DJF pertence a um episódio de
     El Niño, La Niña se pertence a um de La Niña, neutra nos demais casos.

Antes, a classificação era por ano do calendário e partia de uma lista fixa.
Um El Niño que começa em maio marcava como El Niño a safra colhida meses antes,
ainda sob La Niña ou neutra (2023 e 2026), e a lista fixa deixava de fora
episódios oficiais da NOAA (2001, 2005-2007, 2009, 2012, 2018-2020).

Uma sequência que chega ao fim dos dados com menos de 5 trimestres ainda pode
virar episódio; a safra que ela alcança entra na lista e fica marcada como
provisória em historico_detalhado.
"""

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "pesquisa" / "dados" / "eventos_enso.json"
NOAA_ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

TRIMESTRES = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]
LIMIAR = 0.5
MIN_TRIMESTRES = 5
TRIMESTRE_DA_SAFRA = "DJF"
PRIMEIRA_SAFRA = 2000


def buscar_dados_noaa():
    req = urllib.request.Request(
        NOAA_ONI_URL,
        headers={"User-Agent": "AgroInteligencia-Dissertacao/1.0 (UFPA/EngSoft7)"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def ler_oni(conteudo_texto):
    """Série ONI em ordem: lista de (ano, trimestre, anomalia)."""
    lines = [l.strip() for l in conteudo_texto.strip().split("\n") if l.strip()]
    if not lines or len(lines) < 10:
        raise ValueError("Dados NOAA vazios ou incompletos")
    serie = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 4 and parts[0] in TRIMESTRES:
            serie.append((int(parts[1]), parts[0], float(parts[3])))
    serie.sort(key=lambda x: (x[0], TRIMESTRES.index(x[1])))
    return serie


def episodios(anomalias):
    """Fase de cada trimestre: ("El Niño" | "La Niña" | None, provisória?)."""
    fase = [(None, False)] * len(anomalias)
    for sinal, nome in ((1, "El Niño"), (-1, "La Niña")):
        i = 0
        while i < len(anomalias):
            if sinal * anomalias[i] < LIMIAR:
                i += 1
                continue
            j = i
            while j < len(anomalias) and sinal * anomalias[j] >= LIMIAR:
                j += 1
            completo = j - i >= MIN_TRIMESTRES
            if completo or j == len(anomalias):
                for k in range(i, j):
                    fase[k] = (nome, not completo)
            i = j
    return fase


def processar_oni(conteudo_texto):
    serie = ler_oni(conteudo_texto)
    fase = episodios([a for _, _, a in serie])
    por_ano = {}
    for (ano, trim, anom), f in zip(serie, fase):
        por_ano.setdefault(ano, {"trimestres": {}, "fases": {}})
        por_ano[ano]["trimestres"][trim] = anom
        por_ano[ano]["fases"][trim] = f

    el_ninos, la_ninas, detalhes = [], [], {}
    for ano in sorted(por_ano):
        if ano < PRIMEIRA_SAFRA or TRIMESTRE_DA_SAFRA not in por_ano[ano]["trimestres"]:
            continue
        nome, provisoria = por_ano[ano]["fases"][TRIMESTRE_DA_SAFRA]
        if nome == "El Niño":
            el_ninos.append(ano)
        elif nome == "La Niña":
            la_ninas.append(ano)
        detalhes[str(ano)] = {
            "classificacao": nome or "Neutro",
            "provisoria": provisoria,
            "oni_djf": por_ano[ano]["trimestres"][TRIMESTRE_DA_SAFRA],
            "trimestres": por_ano[ano]["trimestres"],
        }

    return {
        "fonte": "NOAA Climate Prediction Center (CPC) - Oceanic Niño Index (ONI)",
        "url_origem": NOAA_ONI_URL,
        "regra": ("safra Y classificada pelo trimestre DJF de Y (dezembro de Y-1 a fevereiro "
                  "de Y): El Niño ou La Niña se esse trimestre pertence a um episódio da NOAA "
                  "(5 ou mais trimestres seguidos com ONI >= +0,5 ou <= -0,5)"),
        "ultima_atualizacao": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "el_ninos": el_ninos,
        "la_ninas": la_ninas,
        "historico_detalhado": detalhes,
    }


def main():
    print("Consultando índice oficial ONI da NOAA...")
    try:
        texto = buscar_dados_noaa()
    except Exception as e:
        # Sem a NOAA, o arquivo existente fica como está: reescrevê-lo com uma
        # lista fixa trocaria dado por suposição.
        print(f"Aviso ao consultar NOAA: {e}. O arquivo existente não foi alterado.")
        return
    dados_enso = processar_oni(texto)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(dados_enso, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Sucesso! Arquivo gerado em {SAIDA}")
    print(f"Safras de El Niño ({len(dados_enso['el_ninos'])}): {dados_enso['el_ninos']}")
    print(f"Safras de La Niña ({len(dados_enso['la_ninas'])}): {dados_enso['la_ninas']}")


if __name__ == "__main__":
    main()
