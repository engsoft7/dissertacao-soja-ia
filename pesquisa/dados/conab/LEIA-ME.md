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
