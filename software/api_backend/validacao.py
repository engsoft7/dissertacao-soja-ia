# -*- coding: utf-8 -*-
"""Métricas de validação que a API entrega aos clientes.

O aplicativo exibia R², erro e número de registros escritos no próprio código,
e eles ficavam para trás a cada safra nova que a rotina de atualização trazia,
enquanto o painel web já lia o arquivo. Agora os dois clientes leem a mesma
fonte: pesquisa/dados/metricas_validacao.json, gravado por gera_metricas.py.

O arquivo só vale se descreve a base carregada (mesmo número de registros);
caso contrário, valem as métricas que a API calcula ao iniciar. É o mesmo
critério do painel web.
"""
import json
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "metricas_validacao.json"


def metricas_validacao(n_registros: int, n_municipios: int, calculadas: dict | None,
                       arquivo: Path = ARQUIVO) -> dict | None:
    """R² do modelo e da referência, erro e tamanho da base, prontos para exibir."""
    m, fonte = calculadas, "calculadas na inicialização da API"
    try:
        salvas = json.loads(Path(arquivo).read_text(encoding="utf-8"))
        if salvas.get("registros") == n_registros:
            m, fonte = salvas, "metricas_validacao.json"
    except (OSError, ValueError):
        pass
    if not m:
        return None
    return {
        "r2": round(float(m["r2"]), 3),
        "r2_referencia": round(float(m["r2_baseline"]), 3),
        "rmse_kg_ha": round(float(m["rmse"]), 1),
        "rrmse_pct": round(float(m["rrmse"]), 1),
        "registros": int(n_registros),
        "municipios": int(n_municipios),
        "fonte": fonte,
    }
