# -*- coding: utf-8 -*-
"""
Núcleo do painel de estimativa de produtividade da soja no Pará.

Decisões metodológicas (ver dissertação, seção 6):

1. A estimativa combina um MODELO DE REFERÊNCIA (média histórica do município
   somada à tendência tecnológica) com uma correção prevista por Aprendizado de
   Máquina a partir de variáveis climáticas e espectrais.

2. A validação é temporal (leave-one-year-out). Nunca se usa amostragem
   aleatória: como cada município aparece em várias safras, um split aleatório
   coloca o mesmo município no treino e no teste, o modelo memoriza sua média e
   a métrica resultante é otimista e inválida.

3. O painel exibe SEMPRE a margem de erro. Uma estimativa sem incerteza declarada
   não é informação útil para decisão.

4. Sinaliza-se quando a produtividade oficial (PAM/IBGE) repete o valor da safra
   anterior. Cerca de 40% dos pares de safras consecutivas nos municípios
   paraenses apresentam esse padrão, o que limita a confiabilidade do valor
   observado e, por consequência, da estimativa calibrada sobre ele.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "NDVI_mean", "NDVI_max", "EVI_mean", "EVI_max",
    "precip_total", "etp_total", "balanco_hidrico",
    "temp_mean", "temp_max", "srad_mean",
]
ALVO = "rendimento_kg_ha"


# --------------------------------------------------------------------- dados
def carregar(caminho: str) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    df["balanco_hidrico"] = df["precip_total"] - df["etp_total"]
    df = df.dropna(subset=FEATURES + [ALVO]).reset_index(drop=True)
    return df.sort_values(["municipio", "ano"]).reset_index(drop=True)


# ---------------------------------------------------- modelo de referência
def _tendencia(anos: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Inclinação da tendência tecnológica e ano médio, ajustados no treino."""
    lin = LinearRegression().fit(anos.reshape(-1, 1), y)
    return float(lin.coef_[0]), float(anos.mean())


def _baseline(df_treino: pd.DataFrame, municipios: pd.Series, anos: pd.Series) -> np.ndarray:
    """Média histórica do município + tendência. Não usa clima nem NDVI."""
    slope, ano_medio = _tendencia(df_treino["ano"].values, df_treino[ALVO].values)
    medias = df_treino.groupby("municipio")[ALVO].mean()
    geral = df_treino[ALVO].mean()
    return np.array([
        medias.get(m, geral) + slope * (a - ano_medio)
        for m, a in zip(municipios, anos)
    ])


# ------------------------------------------------------------------- modelo
class Estimador:
    """Baseline + correção climática aprendida sobre o resíduo."""

    def __init__(self) -> None:
        self.scaler: StandardScaler | None = None
        self.modelo: MLPRegressor | None = None
        self.df: pd.DataFrame | None = None
        self.rmse: float | None = None
        self.mae: float | None = None
        self.r2: float | None = None
        self.r2_baseline: float | None = None

    def treinar(self, df: pd.DataFrame) -> "Estimador":
        self.df = df
        base = _baseline(df, df["municipio"], df["ano"])
        residuo = df[ALVO].values - base
        self.scaler = StandardScaler().fit(df[FEATURES].values)
        self.modelo = MLPRegressor(
            hidden_layer_sizes=(64, 32), alpha=1e-2,
            max_iter=800, early_stopping=True, random_state=42,
        ).fit(self.scaler.transform(df[FEATURES].values), residuo)
        return self

    def validar(self, df: pd.DataFrame) -> dict:
        """Leave-one-year-out. É a única métrica que o painel reporta."""
        anos = [a for a in sorted(df["ano"].unique()) if (df["ano"] == a).sum() >= 4]
        y_obs, y_est, y_base = [], [], []
        for ano in anos:
            treino, teste = df[df["ano"] != ano], df[df["ano"] == ano]
            b_tr = _baseline(treino, treino["municipio"], treino["ano"])
            b_te = _baseline(treino, teste["municipio"], teste["ano"])
            sc = StandardScaler().fit(treino[FEATURES].values)
            mdl = MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-2,
                               max_iter=800, early_stopping=True, random_state=42)
            mdl.fit(sc.transform(treino[FEATURES].values), treino[ALVO].values - b_tr)
            y_obs += list(teste[ALVO].values)
            y_est += list(b_te + mdl.predict(sc.transform(teste[FEATURES].values)))
            y_base += list(b_te)
        y_obs, y_est, y_base = map(np.array, (y_obs, y_est, y_base))
        self.rmse = float(np.sqrt(mean_squared_error(y_obs, y_est)))
        self.mae = float(mean_absolute_error(y_obs, y_est))
        self.r2 = float(r2_score(y_obs, y_est))
        self.r2_baseline = float(r2_score(y_obs, y_base))
        return {
            "rmse": self.rmse, "mae": self.mae, "r2": self.r2,
            "r2_baseline": self.r2_baseline,
            "rrmse": self.rmse / y_obs.mean() * 100,
            "n": len(y_obs), "anos_testados": len(anos),
        }

    def estimar(self, municipio: str, ano: int, clima: dict | None = None) -> dict:
        """Estimativa pontual, sempre acompanhada da margem de erro."""
        if self.modelo is None or self.df is None:
            raise RuntimeError("chame treinar() antes de estimar()")

        base = float(_baseline(self.df, pd.Series([municipio]), pd.Series([ano]))[0])

        hist = self.df[self.df["municipio"] == municipio]
        if clima is None:
            if hist.empty:
                x = self.df[FEATURES].mean().values
            else:
                x = hist[FEATURES].mean().values
            origem = "médias históricas do município"
        else:
            x = np.array([clima[f] for f in FEATURES], dtype=float)
            origem = "clima informado para a safra"

        correcao = float(self.modelo.predict(self.scaler.transform(x.reshape(1, -1)))[0])
        estimativa = base + correcao
        margem = self.rmse if self.rmse else float("nan")
        return {
            "estimativa_kg_ha": estimativa,
            "baseline_kg_ha": base,
            "correcao_climatica_kg_ha": correcao,
            "margem_kg_ha": margem,
            "intervalo": (estimativa - margem, estimativa + margem),
            "origem_das_variaveis": origem,
        }


# ---------------------------------------------- qualidade do dado oficial
def diagnostico_pam(df: pd.DataFrame, municipio: str) -> dict:
    """Detecta repetição de valores na série oficial de um município."""
    serie = df[df["municipio"] == municipio].sort_values("ano")
    v = serie[ALVO].values
    if len(v) < 2:
        return {"pares": 0, "repetidos": 0, "taxa": 0.0, "maior_sequencia": 0, "anos_repetidos": []}

    iguais = np.diff(v) == 0
    anos_rep = serie["ano"].values[1:][iguais].tolist()

    maior = atual = 1
    for i in range(1, len(v)):
        atual = atual + 1 if v[i] == v[i - 1] else 1
        maior = max(maior, atual)

    return {
        "pares": len(v) - 1,
        "repetidos": int(iguais.sum()),
        "taxa": float(iguais.mean() * 100),
        "maior_sequencia": int(maior),
        "anos_repetidos": anos_rep,
    }


def taxa_repeticao_estadual(df: pd.DataFrame) -> float:
    rep = tot = 0
    for _, d in df.groupby("municipio"):
        v = d.sort_values("ano")[ALVO].values
        if len(v) < 2:
            continue
        rep += int((np.diff(v) == 0).sum())
        tot += len(v) - 1
    return rep / tot * 100 if tot else 0.0
