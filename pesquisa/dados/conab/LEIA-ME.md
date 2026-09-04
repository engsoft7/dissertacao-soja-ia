# Custos de produção da soja — CONAB

Extrações do Portal de Informações Agropecuárias da CONAB, série **Custos de
Produção**, cultura da soja. Levantamento de **março de 2026**.

Fonte: <https://portaldeinformacoes.conab.gov.br/custos-de-producao.html>

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `custo_producao_por_municipio.csv` | Renda de fatores, custo fixo, custo variável e preço recebido, por município levantado |
| `custo_variavel_e_produtividade_por_municipio.csv` | Custo variável por saca e produtividade de referência |
| `custo_producao_por_uf.csv` | Os mesmos componentes agregados por unidade da federação |
| `serie_pedro_afonso_to.csv` | Série histórica de Pedro Afonso (TO), de março de 2023 a março de 2026 |

## Como o número do painel é obtido

O Pará não integra o MATOPIBA e não tem levantamento de custo de soja. Adota-se
**Pedro Afonso (TO)**, ponto de coleta da CONAB no cerrado do Tocantins.

A CONAB publica o custo **por saca comercializada**. A conversão para hectare
usa a produtividade de referência do próprio levantamento, 2.880 kg/ha, ou
48 sc/ha:

```
custo variável (custeio)       R$  85,03/sc  ×  48  =  R$ 4.081,44/ha
custo fixo                     R$  24,91/sc  ×  48  =  R$ 1.195,68/ha
custo operacional (var + fixo) R$ 109,94/sc  ×  48  =  R$ 5.277,12/ha   ← usado
renda de fatores               R$   9,12/sc  ×  48  =  R$   437,76/ha
custo total                    R$ 119,06/sc  ×  48  =  R$ 5.714,88/ha
```

O painel usa o **custo operacional**, que é o que a CONAB define como variável
mais fixo e o que o campo "Custo Operacional" representa. Os valores estão em
`software/api_backend/financas.py`.

## Onde o preço de março de 2026 está na série

O preço recebido pelo produtor nesse levantamento, **R$ 105,09 por saca**, é o
**menor dos 13 levantamentos** de Pedro Afonso entre março de 2023 e março de
2026 (`serie_pedro_afonso_to.csv`; JAN e MAR de 2024 saem com preço 0,00 na
planilha da CONAB e não são cotação):

| estatística | R$/saca |
|---|---|
| menor (MAR-2026, o adotado) | 105,09 |
| mediana | 116,91 |
| média | 118,89 |
| maior (MAR-2023) | 146,35 |

É também um dos dois únicos levantamentos da série em que a própria CONAB apura
**margem líquida negativa** na praça (−R$ 4,85/sc; o outro é MAI-2023). Entre os
13 municípios levantados em março de 2026, Pedro Afonso é o **terceiro menor
preço** — só Primavera do Leste (MT) e Sorriso (MT), a R$ 103,90, ficam abaixo.

O número é oficial e está correto. A consequência é que a margem do simulador
nasce do momento mais pessimista do triênio: numa lavoura de 55 sc/ha e custo
operacional de R$ 5.277,12/ha, o resultado vai de **+R$ 534/ha** aos R$ 105,09
para **+R$ 1.188/ha** à mediana da série e **+R$ 2.816/ha** ao maior preço. Por
isso o painel e o aplicativo informam a posição do preço na série, em vez de
apresentá-lo como "o preço da soja".

Preço e custo têm de vir do **mesmo levantamento**: trocar o preço pela mediana
da série mantendo o custo de março de 2026 misturaria dois momentos e inflaria a
margem — foi esse tipo de mistura que fez a versão anterior exibir a cotação de
Chicago como preço de porteira. Quem quiser simular outro preço deve usar o
campo editável, que existe exatamente para isso.
