# -*- coding: utf-8 -*-
"""Redesenha as três figuras do baralho no tamanho em que elas aparecem
projetadas. As originais foram feitas para a página A4 da dissertação (corpo 9
a 11 pt) e, reduzidas para o slide, ficavam com rótulos de 8 a 10 pt ao lado de
um texto de 25 pt. Aqui cada figura é gerada já na medida do slide, de modo que
1 pt no gráfico é 1 pt projetado.

Dados: os mesmos arquivos do repositório. Nada é redigitado.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.ticker import FuncFormatter

REPO = Path(__file__).resolve().parents[2]
SAI = Path(__file__).parent

# paleta do próprio modelo de slides
ESCURO, PRIM, MUDO = "#071D69", "#0F5995", "#B8C1D9"
TINTA, TINTA2, GRADE = "#33335B", "#5A6488", "#DDE2EC"
CLARO = "#EAF0F8"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 15,
    "text.color": TINTA, "axes.labelcolor": TINTA,
    "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.edgecolor": GRADE, "axes.linewidth": 1.0,
    "xtick.major.size": 0, "ytick.major.size": 0,
    "figure.facecolor": "white", "axes.facecolor": "white",
})
VIRG = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))


def limpa(ax, grade_y=True):
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(GRADE)
    if grade_y:
        ax.set_axisbelow(True)
        ax.yaxis.grid(True, color=GRADE, lw=1.0)
    ax.tick_params(length=0)


# ---------------------------------------------------------------- Figura 2 ---
def figura_modelos():
    r = json.loads((REPO / "pesquisa/03_analise_nacional/resultados_ajustados.json").read_text())
    ordem = ["SVR", "Random Forest", "XGBoost", "MLP"]
    r2 = [r[m]["R2_pool"] for m in ordem]
    rmse = [r[m]["RMSE_pool"] for m in ordem]
    destaque = [PRIM if m == "SVR" else MUDO for m in ordem]

    fig, eixos = plt.subplots(1, 2, figsize=(9.10, 3.55))
    for ax, val, titulo, fmt, folga in (
            (eixos[0], r2, "Coeficiente de determinação R²", "{:.3f}", 0.06),
            (eixos[1], rmse, "Erro quadrático médio (kg/ha)", "{:.0f}", 60)):
        b = ax.bar(range(4), val, color=destaque, width=0.62)
        for x, v in zip(range(4), val):
            ax.text(x, v + folga * 0.18, fmt.format(v).replace(".", ","),
                    ha="center", va="bottom", fontsize=15, color=TINTA,
                    fontweight="bold" if x == 0 else "normal")
        ax.set_xticks(range(4))
        ax.set_xticklabels(["SVR\najustado", "Random\nForest", "XGBoost", "MLP"], fontsize=14)
        ax.set_ylim(0, max(val) + folga)
        ax.set_title(titulo, fontsize=16, color=TINTA, pad=12, loc="left")
        ax.yaxis.set_major_formatter(VIRG)
        limpa(ax)
        b[0].set_edgecolor("white"); b[0].set_linewidth(2)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.86, bottom=0.19, wspace=0.26)
    fig.savefig(SAI / "fig_modelos.png", dpi=220, facecolor="white")
    plt.close(fig)
    print("fig_modelos.png  R²:", r2, " RMSE:", rmse)


# ---------------------------------------------------------------- Figura 3 ---
def figura_repeticao():
    pa = (pd.read_csv(REPO / "pesquisa/dados/soja_para_mascarado_2001_2024.csv")
            .sort_values(["municipio", "ano"]))
    rep = tot = 0
    por_ano = {}
    for _, d in pa.groupby("municipio"):
        v, a = d.rendimento_kg_ha.values, d.ano.values
        for i in range(1, len(v)):
            por_ano.setdefault(a[i], [0, 0])
            por_ano[a[i]][1] += 1
            tot += 1
            if v[i] == v[i - 1]:
                por_ano[a[i]][0] += 1
                rep += 1
    taxa = rep / tot * 100
    anos = sorted(por_ano)
    pct = [por_ano[a][0] / por_ano[a][1] * 100 for a in anos]

    pa["rep"] = pa.groupby("municipio").rendimento_kg_ha.transform(lambda s: s.diff().eq(0))
    quart = pa.groupby(pd.qcut(pa.soy_area_ha, 4,
                               labels=["Q1", "Q2", "Q3", "Q4"]),
                       observed=True).rep.mean() * 100

    fig, eixos = plt.subplots(1, 2, figsize=(9.10, 3.55),
                              gridspec_kw={"width_ratios": [1, 1.35], "wspace": 0.30})

    # (a) a repetição cresce onde a área plantada é menor
    ax = eixos[0]
    ax.bar(range(4), quart.values, color=PRIM, width=0.80)
    for i, v in enumerate(quart.values):
        ax.text(i, v - 1.8, f"{v:.1f}".replace(".", ","), ha="center", va="top",
                fontsize=15, color="white", fontweight="bold")
    ax.set_xticks(range(4))
    ax.set_xticklabels(list(quart.index), fontsize=14)
    ax.set_xlabel("menor \u2192 maior área plantada", fontsize=13, labelpad=6)
    ax.set_ylim(0, max(quart.values) * 1.12)
    ax.set_ylabel("repetição (%)", fontsize=14)
    ax.yaxis.set_major_formatter(VIRG)
    ax.set_title("Por quartil de área plantada", fontsize=15, color=TINTA, pad=10, loc="left")
    limpa(ax)

    # (b) proporção por safra
    ax = eixos[1]
    ax.bar(anos, pct, color=PRIM, width=0.68)
    ax.axhline(taxa, color=ESCURO, lw=1.6)
    ax.text(anos[0] - 0.4, max(pct) * 1.10, f"média {taxa:.1f}%".replace(".", ","),
            va="top", ha="left", fontsize=14, color=ESCURO)
    ax.set_ylabel("% de municípios", fontsize=14)
    ax.set_xticks([2005, 2010, 2015, 2020])
    ax.set_xlim(anos[0] - 1, anos[-1] + 1)
    ax.set_ylim(0, max(pct) * 1.16)
    ax.yaxis.set_major_formatter(VIRG)
    ax.set_title(f"Por safra ({rep} de {tot} pares)", fontsize=15, color=TINTA, pad=10, loc="left")
    limpa(ax)

    fig.subplots_adjust(left=0.085, right=0.985, top=0.86, bottom=0.20, wspace=0.30)
    fig.savefig(SAI / "fig_repeticao.png", dpi=220, facecolor="white")
    plt.close(fig)
    print(f"fig_repeticao.png  taxa={taxa:.1f}%  {rep}/{tot}  quartis="
          + ", ".join(f"{v:.1f}" for v in quart.values))


# ---------------------------------------------------------------- Figura 1 ---
FASES = [
    ("Fase 1 — Revisão sistemática",
     "Protocolo PRISMA 2020; bases OpenAlex\ne Crossref; 1.182 triados, 53 incluídos"),
    ("Fase 2 — Coleta e integração",
     "Nacional: base de von Bloh et al. (2023).\nPará: IBGE, MODIS, CHIRPS, ERA5-Land\ne máscara de soja do MapBiomas"),
    ("Fase 3 — Pré-processamento",
     "Limpeza, imputação, alinhamento\nespaço-temporal e atributos derivados"),
    ("Fase 4 — Modelagem",
     "Random Forest, XGBoost, SVR e MLP;\nbusca de hiperparâmetros"),
    ("Fase 5 — Validação",
     "Validação temporal leave-one-year-out;\nRMSE, MAE e R² contra referência"),
    ("Fase 6 — Produto técnico",
     "Base aberta, painel web e aplicativo;\ncódigo sob licença MIT e registro"),
]


def figura_fluxograma():
    fig, ax = plt.subplots(figsize=(9.10, 5.35))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    larg, alt = 43.0, 26.0
    cols, linhas = (2.0, 55.0), (70.0, 37.0, 4.0)
    for i, (titulo, corpo) in enumerate(FASES):
        x, y = cols[i // 3], linhas[i % 3]
        ax.add_patch(FancyBboxPatch((x, y), larg, alt, boxstyle="round,pad=0,rounding_size=2.2",
                                    facecolor=CLARO, edgecolor=PRIM, linewidth=1.6))
        ax.text(x + larg / 2, y + alt - 6.5, titulo, ha="center", va="center",
                fontsize=15, fontweight="bold", color=ESCURO)
        ax.text(x + larg / 2, y + alt / 2 - 6.4, corpo, ha="center", va="center",
                fontsize=12.5, color=TINTA, linespacing=1.45)

    seta = dict(arrowstyle="-|>", color=ESCURO, lw=1.8, mutation_scale=22,
                shrinkA=0, shrinkB=0, joinstyle="miter")
    for c in (0, 1):                                   # descidas dentro de cada coluna
        for y in linhas[:2]:
            meio = cols[c] + larg / 2
            ax.add_patch(FancyArrowPatch((meio, y - 0.6), (meio, y - 6.4), **seta))
    # da coluna 1 para a coluna 2, pela calha entre elas
    calha = (cols[0] + larg + cols[1]) / 2
    meio_esq, meio_dir = linhas[2] + alt / 2, linhas[0] + alt / 2
    ax.plot([cols[0] + larg, calha, calha], [meio_esq, meio_esq, meio_dir],
            color=ESCURO, lw=1.8, solid_joinstyle="miter", clip_on=False)
    ax.add_patch(FancyArrowPatch((calha, meio_dir), (cols[1] - 0.4, meio_dir), **seta))

    fig.tight_layout(pad=0.2)
    fig.savefig(SAI / "fig_fluxograma.png", dpi=220, facecolor="white")
    plt.close(fig)
    print("fig_fluxograma.png")


figura_modelos()
figura_repeticao()
figura_fluxograma()


def figura_fluxograma_pagina():
    """Mesma Figura 1, no formato da página da dissertação (coluna única)."""
    fig, ax = plt.subplots(figsize=(6.10, 8.00))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    larg, alt = 92.0, 13.4
    topo = [84.0, 67.4, 50.8, 34.2, 17.6, 1.0]
    for (titulo, corpo), y in zip(FASES, topo):
        ax.add_patch(FancyBboxPatch((4.0, y), larg, alt, boxstyle="round,pad=0,rounding_size=1.2",
                                    facecolor=CLARO, edgecolor=PRIM, linewidth=1.1))
        ax.text(50.0, y + alt - 3.4, titulo, ha="center", va="center",
                fontsize=10.5, fontweight="bold", color=ESCURO)
        ax.text(50.0, y + alt / 2 - 3.3, corpo, ha="center", va="center",
                fontsize=8.8, color=TINTA, linespacing=1.45)
    seta = dict(arrowstyle="-|>", color=ESCURO, lw=1.2, mutation_scale=14,
                shrinkA=0, shrinkB=0)
    for y in topo[:-1]:
        ax.add_patch(FancyArrowPatch((50.0, y - 0.4), (50.0, y - 3.0), **seta))
    fig.tight_layout(pad=0.2)
    fig.savefig(SAI / "fig_fluxograma_pagina.png", dpi=300, facecolor="white")
    plt.close(fig)
    print("fig_fluxograma_pagina.png")


figura_fluxograma_pagina()


# --------------------------------------------- Figura 3 (nova) — repetição ---
def figura_variavel_alvo():
    """Por que os valores se repetem: a distribuição e um município exemplar."""
    pa = (pd.read_csv(REPO / "pesquisa/dados/soja_para_mascarado_2001_2024.csv")
            .sort_values(["municipio", "ano"]))
    sc = pa.rendimento_kg_ha / 60.0

    fig, eixos = plt.subplots(1, 2, figsize=(9.10, 3.55),
                              gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.26})

    # (a) a distribuição encosta nos múltiplos de cinco sacas
    ax = eixos[0]
    bordas = np.arange(11.5, 78.5, 1.0)
    n, _ = np.histogram(sc, bins=bordas)
    centros = (bordas[:-1] + bordas[1:]) / 2
    cheio = np.isclose(np.round(centros) % 5, 0)
    ax.bar(centros[~cheio], n[~cheio], width=0.92, color=MUDO)
    ax.bar(centros[cheio], n[cheio], width=0.92, color=ESCURO)
    pico = int(n[np.isclose(centros, 50.0)][0])
    exatos = int((pa.rendimento_kg_ha == 3000).sum())
    ax.annotate("50 sc/ha\n3.000 kg/ha", xy=(50, pico), xytext=(58, pico * 0.86),
                fontsize=13, color=ESCURO, ha="left",
                arrowprops=dict(arrowstyle="-", color=ESCURO, lw=1.2))
    ax.set_xlabel("rendimento (sacas por hectare)", fontsize=14)
    ax.set_ylabel("registros", fontsize=14)
    ax.set_xticks([20, 30, 40, 50, 60, 70])
    ax.set_xlim(11, 78)
    ax.set_title("Distribuição do rendimento", fontsize=15, color=TINTA, pad=10, loc="left")
    limpa(ax)

    # (b) um município: doze anos travados em 50 sacas
    d = (pa[pa.municipio == "Floresta Do Araguaia"]
         .set_index("ano").reindex(range(2001, 2025)))       # safras ausentes viram lacuna
    ax = eixos[1]
    serie = d.rendimento_kg_ha / 60.0
    ax.plot(serie.index, serie.values, "-o", color=PRIM, lw=2.2, ms=5)
    ax.axhline(50, color=ESCURO, lw=1.2, zorder=0)
    ax.annotate("50 sc/ha, de 2005 a 2016", xy=(2005, 50), xytext=(2003.5, 60),
                fontsize=13, color=ESCURO)
    ax.set_ylabel("sacas por hectare", fontsize=14)
    ax.set_xticks([2005, 2010, 2015, 2020])
    ax.set_ylim(0, 70)
    ax.set_title("Floresta do Araguaia", fontsize=15, color=TINTA, pad=10, loc="left")
    limpa(ax)

    fig.subplots_adjust(left=0.085, right=0.985, top=0.86, bottom=0.17)
    fig.savefig(SAI / "fig_variavel_alvo.png", dpi=220, facecolor="white")
    plt.close(fig)
    print(f"fig_variavel_alvo.png  barra dos 50 sc/ha: {pico}; valor exato 3.000 kg/ha: {exatos} de {len(sc)}")


figura_variavel_alvo()
