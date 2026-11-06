# -*- coding: utf-8 -*-
"""Produtividade oficial do IBGE fora da base do modelo.

A base do modelo (soja_para_painel.csv) só guarda as safras em que a máscara de
soja do MapBiomas acha soja no município, porque o modelo precisa das variáveis
de satélite. O IBGE publica a produtividade também nos outros anos. Sem eles, a
API dava a Pau D'Arco a última safra em 2017 e a "safra esperada" de 2020.

pam_soja_para.csv, gravado por atualiza_pam.py a cada execução mensal, tem
todas as safras publicadas nos municípios da base. Este módulo só depende do
pandas, para os testes rodarem no CI sem FastAPI nem scikit-learn.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PAM_PATH = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "pam_soja_para.csv"


def carrega_pam(caminho: Path = PAM_PATH) -> dict[int, dict[int, float]]:
    """Rendimento oficial (kg/ha) por código IBGE e safra; vazio sem o arquivo."""
    if not caminho.exists():
        return {}
    pam: dict[int, dict[int, float]] = {}
    tabela = pd.read_csv(caminho)[["cod_ibge7", "ano", "rendimento_kg_ha"]]
    for cod, ano, valor in tabela.itertuples(index=False):
        if valor > 0:
            pam.setdefault(int(cod), {})[int(ano)] = float(valor)
    return pam


def ultima_safra_publicada(ultima_da_base: int, pam: dict[int, dict[int, float]]) -> int:
    """A safra de onde partem as projeções, a mesma para todos os municípios.

    É a última da base ou, se o IBGE já publicou uma mais nova que a coleta de
    satélite ainda não trouxe, essa.
    """
    return max([int(ultima_da_base)] + [a for safras in pam.values() for a in safras])


def safras_fora_da_base(oficiais: dict[int, float], anos_base: set[int], ate: int) -> list[tuple[int, float]]:
    """Safras publicadas pelo IBGE que a base do município não tem, em ordem."""
    return [(ano, real) for ano, real in sorted(oficiais.items()) if ano not in anos_base and ano <= ate]
