# Auditoria dos números: API × fontes (06/11/2026 15:25, horário de Belém)

API conferida: https://agrointeligencia-api.onrender.com

| Grupo | Item | Situação | App | Fonte | Nota |
|---|---|---|---|---|---|
| Municípios | lista da API × sedes do app | ok | 38 | 38 |  |
| API | respostas dos 38 municípios | ok |  |  |  |
| Produtividade (IBGE) | 521 safras município a município | ok |  |  |  |
| Praças do Pará (Agrolink) | Barcarena | ok | R$ 149.50 em 2026-11-06 | R$ 149.50 em 2026-11-06 |  |
| Praças do Pará (Agrolink) | Paragominas | ok | R$ 133.12 em 2026-10-05 | R$ 133.12 em 2026-10-05 |  |
| Praças do Pará (Agrolink) | Redenção | ok | R$ 149.50 em 2026-11-06 | R$ 149.50 em 2026-11-06 |  |
| Chicago (CBOT) | R$/saca | ok | R$ 143.69 | R$ 143.77 | diferença -0.05% (as duas leituras têm minutos de distância) |
| Chicago (CBOT) | conversão da própria API | ok | R$ 143.69 | R$ 143.69 | US$/bushel × 2,2046 bushels/saca × câmbio |
| Média do Pará estimada | Chicago + base | ok | R$ 143.83 | R$ 143.83 | base de 2026-11: R$ +0.14 |
| Custo e preço (CONAB) | custo_ha | ok | 5277.12 | 5277.12 | levantamento MAR-2026 de Pedro Afonso (TO) |
| Custo e preço (CONAB) | soja_preco_saca | ok | 105.09 | 105.09 | levantamento MAR-2026 de Pedro Afonso (TO) |
| Custo e preço (CONAB) | custo_area_ha | ok | 5042.88 | 5042.88 | levantamento MAR-2026 de Pedro Afonso (TO) |
| Custo e preço (CONAB) | custo_transporte_saca | ok | 3.3 | 3.3 | levantamento MAR-2026 de Pedro Afonso (TO) |
| Custo e preço (CONAB) | taxa_cessr | ok | 0.015 | 0.015 | levantamento MAR-2026 de Pedro Afonso (TO) |
| Custo e preço (CONAB) | levantamento × série do portal | ok | R$ 105.09/sc; R$ 5277.12/ha | R$ 105.09/sc; (24.91 + 85.03) × 48 sc |  |
| Custo e preço (CONAB) | componentes somam o custo da CONAB (48 sc/ha) | ok | R$ 5276.94 | R$ 5277.12 |  |
| Custo e preço (CONAB) | mesmo levantamento nos 38 municípios | ok |  |  | 1 combinação(ões) de custo e preço |
| Custo e preço (CONAB) | idade do levantamento | ok | 8 | MAR-2026 | meses desde o levantamento; o app avisa o produtor |
| Avisos (INMET) | Paragominas | ok | 0 | 0 |  |
| Avisos (INMET) | Redenção | ok | 1 | 1 |  |
| Avisos (INMET) | Santarém | ok | 0 | 0 |  |
| Avisos (INMET) | Dom Eliseu | ok | 0 | 0 |  |
| Avisos (INMET) | Novo Progresso | ok | 1 | 1 |  |
| Avisos (INMET) | Altamira | ok | 1 | 1 |  |
