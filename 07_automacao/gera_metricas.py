# -*- coding: utf-8 -*-
"""
Pré-calcula as métricas da validação leave-one-year-out do painel e as grava em
dados/metricas_validacao.json, junto com o número de registros da base.

Motivação: a validação treina um modelo por ano-safra e leva dezenas de
segundos — tempo que o usuário esperava a cada inicialização a frio do painel.
Com o arquivo presente e compatível com o CSV (mesmo número de registros), o
painel carrega em segundos; ausente ou defasado, ele refaz a validação como
antes.

Executado pelo GitHub Actions sempre que a base muda.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "06_app"))

import model  # noqa: E402  (depende do sys.path acima)

METRICAS_JSON = RAIZ / "dados" / "metricas_validacao.json"


def main() -> int:
    df = model.carregar(str(RAIZ / "dados" / "soja_para_mascarado_2001_2024.csv"))
    met = model.Estimador().validar(df)
    met["registros"] = len(df)
    METRICAS_JSON.write_text(
        json.dumps(met, ensure_ascii=False, indent=2, default=float) + "\n",
        encoding="utf-8",
    )
    print(f"Métricas gravadas em {METRICAS_JSON.name}: "
          f"RMSE {met['rmse']:.1f} kg/ha · {met['registros']} registros")
    return 0


if __name__ == "__main__":
    sys.exit(main())
