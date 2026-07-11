# -*- coding: utf-8 -*-
"""
Atualização automática da produtividade oficial (PAM/IBGE) na base do painel.

Executado mensalmente pelo GitHub Actions (.github/workflows/atualiza-dados.yml):

1. Baixa da API do SIDRA o rendimento médio da soja (kg/ha) de todos os
   municípios do Pará, em todos os anos disponíveis — tabela 5457, variável 112,
   produto 40124 (soja em grão), os mesmos parâmetros de 01_coleta_dados/.
2. REVISÕES: onde o IBGE revisou um valor de ano já presente na base, o CSV é
   atualizado em disco (pareamento por código IBGE de 7 dígitos + ano).
3. SAFRA NOVA: se o SIDRA já publica um ano que não existe na base, o script
   apenas sinaliza — as variáveis de satélite e clima (NDVI, CHIRPS, ERA5-Land,
   máscara MapBiomas) precisam ser coletadas no Google Earth Engine com as
   rotinas de 01_coleta_dados/ antes de a safra entrar na base.

Apenas dados/soja_para_mascarado_2001_2024.csv (a base do painel) é atualizado.
A base sem máscara é artefato histórico da comparação feita na dissertação e
permanece congelada.

Saídas para o workflow (arquivo apontado por GITHUB_OUTPUT):
    csv_alterado=true|false   revisoes=N   novo_ano=AAAA (vazio se não houver)
Um resumo em Markdown é gravado no caminho apontado por RESUMO_MD (opcional).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
CSV_PAINEL = RAIZ / "dados" / "soja_para_mascarado_2001_2024.csv"

# n6/in n3 15 = todos os municípios da UF 15 (Pará); p/all = todos os anos.
URL_SIDRA = (
    "https://apisidra.ibge.gov.br/values"
    "/t/5457/n6/in%20n3%2015/v/112/p/all/c782/40124?formato=json"
)
MIN_MUNICIPIOS_ANO_NOVO = 5  # mínimo de municípios com valor para anunciar safra


def baixa_sidra() -> pd.DataFrame:
    """Rendimento médio da soja por município do Pará e ano, via API do SIDRA."""
    resp = requests.get(URL_SIDRA, timeout=120)
    resp.raise_for_status()
    bruto = pd.DataFrame(resp.json())
    bruto = bruto[bruto["V"] != "Valor"]  # descarta a linha de cabeçalho da API
    t = bruto[["D1C", "D1N", "D3C", "V"]].rename(
        columns={"D1C": "cod_ibge7", "D1N": "nome_ibge",
                 "D3C": "ano", "V": "rendimento_kg_ha"}
    )
    t["cod_ibge7"] = pd.to_numeric(t["cod_ibge7"], errors="coerce")
    t["ano"] = pd.to_numeric(t["ano"], errors="coerce")
    t["rendimento_kg_ha"] = pd.to_numeric(t["rendimento_kg_ha"], errors="coerce")
    return t.dropna().astype({"cod_ibge7": int, "ano": int})


def aplica_revisoes(caminho: Path, base: pd.DataFrame, sidra: pd.DataFrame) -> pd.DataFrame:
    """Aplica revisões do IBGE regravando SOMENTE o campo alterado de cada linha.

    O CSV não é reescrito pelo pandas de propósito: a regravação integral muda a
    representação decimal de floats em linhas não relacionadas e polui o diff do
    PR automático. Aqui o texto original é preservado byte a byte, exceto o campo
    rendimento_kg_ha das linhas efetivamente revisadas.
    """
    oficial = sidra.set_index(["cod_ibge7", "ano"])["rendimento_kg_ha"]
    revisoes: dict[tuple[int, int], dict] = {}
    for _, linha in base.iterrows():
        chave = (int(linha["cod_ibge7"]), int(linha["ano"]))
        if chave not in oficial.index:
            continue
        novo = float(oficial.loc[chave])
        atual = float(linha["rendimento_kg_ha"])
        if abs(novo - atual) >= 0.5:  # a base guarda kg/ha inteiros
            revisoes[chave] = {"municipio": linha["municipio"], "ano": chave[1],
                               "antes": int(round(atual)), "depois": int(round(novo))}

    if revisoes:
        linhas_txt = caminho.read_text(encoding="utf-8").splitlines()
        cab = linhas_txt[0].split(",")
        i_ano, i_cod = cab.index("ano"), cab.index("cod_ibge7")
        i_rend = cab.index("rendimento_kg_ha")
        for i, ln in enumerate(linhas_txt[1:], start=1):
            campos = ln.split(",")
            chave = (int(campos[i_cod]), int(campos[i_ano]))
            if chave in revisoes:
                campos[i_rend] = str(revisoes[chave]["depois"])
                linhas_txt[i] = ",".join(campos)
        caminho.write_text("\n".join(linhas_txt) + "\n", encoding="utf-8")

    return pd.DataFrame(revisoes.values())


def detecta_ano_novo(base: pd.DataFrame, sidra: pd.DataFrame) -> int | None:
    """Ano mais recente do SIDRA que ainda não existe na base do painel."""
    ano_max_base = int(base["ano"].max())
    novos = sidra[sidra["ano"] > ano_max_base]
    contagem = novos.groupby("ano").size()
    contagem = contagem[contagem >= MIN_MUNICIPIOS_ANO_NOVO]
    return int(contagem.index.max()) if len(contagem) else None


def grava_saidas(**valores: str) -> None:
    caminho = os.environ.get("GITHUB_OUTPUT")
    if not caminho:
        return
    with open(caminho, "a", encoding="utf-8") as f:
        for nome, valor in valores.items():
            f.write(f"{nome}={valor}\n")


def main() -> int:
    base = pd.read_csv(CSV_PAINEL)
    sidra = baixa_sidra()
    print(f"SIDRA: {len(sidra)} registros município-ano para o Pará")

    revisoes = aplica_revisoes(CSV_PAINEL, base, sidra)
    ano_novo = detecta_ano_novo(base, sidra)

    if len(revisoes):
        print(f"{len(revisoes)} revisões aplicadas em {CSV_PAINEL.name}:")
        print(revisoes.to_string(index=False))
    else:
        print("Nenhuma revisão do IBGE nos anos já presentes na base.")

    if ano_novo:
        print(f"Safra nova disponível no SIDRA: {ano_novo} "
              "(requer coleta GEE das variáveis ambientais)")

    resumo_md = os.environ.get("RESUMO_MD")
    if resumo_md:
        linhas = ["## Atualização automática da base PAM/IBGE", ""]
        if len(revisoes):
            linhas += [
                f"O IBGE revisou o rendimento oficial de {len(revisoes)} "
                "registro(s) município-safra já presentes na base do painel "
                "(`dados/soja_para_mascarado_2001_2024.csv`):", "",
                "| Município | Ano | Antes (kg/ha) | Depois (kg/ha) |",
                "|---|---|---|---|",
            ]
            linhas += [
                f"| {r.municipio} | {r.ano} | {r.antes} | {r.depois} |"
                for r in revisoes.itertuples()
            ]
        if ano_novo:
            linhas += [
                "",
                f"**Safra {ano_novo} já disponível no SIDRA.** Para incorporá-la, "
                "rode a coleta das variáveis ambientais no Google Earth Engine "
                "(`01_coleta_dados/02_coleta_gee_com_mascara_mapbiomas.py`) e "
                "anexe as linhas à base.",
            ]
        Path(resumo_md).write_text("\n".join(linhas) + "\n", encoding="utf-8")

    grava_saidas(
        csv_alterado="true" if len(revisoes) else "false",
        revisoes=str(len(revisoes)),
        novo_ano=str(ano_novo) if ano_novo else "",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
