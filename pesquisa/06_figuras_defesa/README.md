# Figuras da defesa

Redesenha as figuras usadas no baralho de slides da defesa, já na medida em que
elas aparecem projetadas (1 pt no gráfico é 1 pt no slide). As figuras da
dissertação foram compostas para a página A4, com corpo de 9 a 11 pt; reduzidas
para o slide, ficavam com rótulos de 8 a 10 pt ao lado de um texto de 25 pt.

    python3 gera_figuras_defesa.py

Saídas (não versionadas):

| arquivo | onde entra | medida |
|---|---|---|
| `fig_fluxograma.png` | slide 6 — Figura 1 | 9,10 × 5,35 pol |
| `fig_modelos.png` | slide 7 — Figura 2 | 9,10 × 3,55 pol |
| `fig_repeticao.png` | slide 8 — Figura 3 | 9,10 × 3,55 pol |
| `fig_fluxograma_pagina.png` | Figura 1 da dissertação, coluna única | 6,10 × 8,00 pol |

Os números vêm de `pesquisa/03_analise_nacional/resultados_ajustados.json` e de
`pesquisa/dados/soja_para_mascarado_2001_2024.csv`; nada é redigitado.

## Correções de conteúdo em relação à Figura 1 da dissertação

A versão anterior do fluxograma divergia do texto da dissertação em três pontos:

1. **Bases da revisão.** Trazia Scopus, IEEE Xplore, Web of Science, ACM e
   ScienceDirect. A revisão foi conduzida sobre **OpenAlex e Crossref**; a seção
   de método justifica expressamente a opção por bases abertas em vez da Scopus
   e da Web of Science.
2. **Algoritmos.** Trazia cinco, incluindo LSTM. Foram implementados e comparados
   **quatro** — Random Forest, XGBoost, SVR e MLP. A LSTM é discutida na revisão
   de literatura, não na modelagem.
3. **Fontes de dados.** Trazia NASA POWER e Sentinel-2 sem distinguir os recortes.
   O recorte nacional usa a base de von Bloh et al. (2023); o do Pará usa IBGE,
   MODIS, CHIRPS, ERA5-Land e a máscara de soja do MapBiomas.
