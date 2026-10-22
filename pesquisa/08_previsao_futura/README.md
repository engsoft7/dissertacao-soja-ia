# Previsão de safras futuras

A dissertação avalia os modelos em *leave-one-year-out*: para prever 2016, o
treino inclui 2001–2015 e também 2017–2024. Isso mede o quanto as variáveis
explicam uma safra deixada de fora, mas não é previsão, porque usa safras
posteriores à prevista. Esta pasta testa a previsão de verdade, em **janela
crescente**: para prever a safra T com antecedência de h safras, entra só o
que se sabia ao fim da safra T−h.

Todos os experimentos comparam com o **modelo de referência** da dissertação
(média do município + tendência comum, ajustadas só no treino). A função em
`comum.py` reproduz a linha de referência da Tabela 6 (RMSE 416 kg/ha, MAE
296, R² 0,216, 13,9%) quando rodada em *leave-one-year-out*.

| Script | Pergunta | Saída |
|---|---|---|
| `01_enso_para.py` | El Niño e La Niña se associam à chuva e à produtividade no Pará? | `enso_para.json` |
| `02_previsao_rendimento_para.py` | Que modelo prevê melhor a produtividade municipal 1, 2 e 3 safras à frente, e ao fim do ciclo? | `previsao_rendimento_para.json` |
| `03_previsao_producao_para.py` | Quanto o Pará vai produzir nas próximas safras? | `previsao_producao_para.json`, `fig_previsao_producao_para.png` |
| `04_referencia_nacional.py` | No recorte nacional, o SVR supera o modelo de referência? | `referencia_nacional.json` |

```bash
cd pesquisa/08_previsao_futura
python 01_enso_para.py
python 02_previsao_rendimento_para.py      # ~1 min
python 03_previsao_producao_para.py
python 04_referencia_nacional.py           # requer 03_analise_nacional/data/data_cast.csv (00_baixa_dados.py)
```

O **ganho** é a habilidade sobre a referência, `1 − MSE(modelo)/MSE(referência)`:
zero é empatar com ela, positivo é superá-la. O intervalo de 95% vem de
reamostragem de safras inteiras no Pará (um ano ruim é ruim para todos os
municípios) e de municípios no recorte nacional (5 safras de teste são poucas
para reamostrar). Hipótese nula em todos os casos: ganho zero.

## Resultados (rodados em 22/10/2026)

### 1. El Niño e La Niña no Pará (`01`, exploratório)

Por safra (n = 24), ONI de dezembro a março do ano de colheita:

| Relação | Spearman | p |
|---|---|---|
| ONI × chuva anômala | −0,61 | 0,002 |
| ONI × produtividade anômala | +0,45 | 0,026 |
| idem, sem os registros repetidos | +0,46 | 0,022 |
| ONI × EVI máximo anômalo | −0,22 | 0,29 |

Anomalia média de produtividade por fase: El Niño +65 kg/ha (IC95 −13 a +116),
La Niña −93 kg/ha (IC95 −160 a −20), neutro +29 kg/ha. O El Niño seca o Pará
(−113 mm), e mesmo assim a produtividade sobe; a La Niña molha (+88 mm) e ela
cai. Hipótese que daí sai: no Pará o limite não é a falta de chuva, e sim o
excesso (colheita, doenças, menos radiação). Exploratório: 24 safras, sem
correção para testes múltiplos, efeito pequeno diante do erro de 416 kg/ha.

### 2. Produtividade municipal (`02`)

**Antes da safra, na base da dissertação (38 municípios), safras-alvo 2010–2024:**

| Antecedência | Referência (RMSE) | Melhor alternativo | Ganho do melhor (IC95) |
|---|---|---|---|
| 1 safra | 452 kg/ha (14,9%) | Referência + ONI de set-nov | −0,005 (−0,049 a +0,027) |
| 2 safras | 489 kg/ha (16,1%) | Média das 3 últimas + tendência | −0,038 (−0,125 a +0,059) |
| 3 safras | 511 kg/ha (16,9%) | Média das 3 últimas + tendência | +0,005 (−0,045 a +0,073) |

Persistência do último valor, média do município, tendência própria de cada
município e um *gradient boosting* com defasagens (com e sem ONI) ficam todos
abaixo da referência ou empatam com ela. Em todos os municípios da PAM (53), a
média das 3 últimas safras + tendência e o *boosting* chegam a +0,066 e +0,065
de ganho a 1 safra, com intervalos que cruzam o zero.

**Ao fim do ciclo, com clima e satélite da própria safra (treino só com o passado):**

| Modelo | RMSE | Ganho (IC95) |
|---|---|---|
| SVR ambiental + ONI de dez-mar | 445 kg/ha (14,7%) | +0,033 (−0,026 a +0,094) |
| Ridge ambiental + ONI | 448 | +0,020 (−0,044 a +0,062) |
| SVR, Ridge, MLP ambientais sem ONI | 451–452 | ≈ 0 |
| Referência | 452 | — |
| Random Forest ambiental | 463 | −0,050 |

Nenhum modelo supera a referência com significância, e o resultado se repete
nos pares de safras em que a PAM mudou de valor. O ONI é o único acréscimo que
melhora todos os modelos ambientais ao mesmo tempo, mas o ganho é pequeno e o
intervalo inclui o zero. A previsão honesta é de **15% de erro a 1 safra e 17%
a 3 safras**, um pouco acima dos 13,9% medidos em *leave-one-year-out*.

### 3. Produção do Pará (`03`)

Área, produtividade e produção estaduais, origens de 2010 a 2023:

| Erro percentual médio | 1 safra | 2 safras | 3 safras |
|---|---|---|---|
| Produtividade estadual (média + tendência) | 3,3% | 3,8% | 4,3% |
| Área (crescimento amortecido) | 7,7% | 17,7% | 26,7% |
| Produção (área amortecida × produtividade com tendência) | 6,7% | 16,4% | 27,1% |
| Produção, combinação fixada de antemão (área exponencial 5 anos × produtividade com tendência) | 11,9% | 24,3% | 39,9% |

No agregado do estado a produtividade é previsível; quem move a produção, e o
erro, é a área plantada, que passou de 500 mil ha em 2017 para 1,19 milhão em
2024. Projeção a partir de 2024, com faixa de 80% dos erros do retroteste:

| Safra | Produção projetada | Faixa de 80% |
|---|---|---|
| 2025 | 4,29 milhões t | 3,90 a 4,71 milhões t |
| 2026 | 4,77 milhões t | 3,93 a 6,01 milhões t |
| 2027 | 5,20 milhões t | 3,98 a 8,73 milhões t |

**Registro antecipado.** A projeção foi feita em 22/10/2026, antes de a PAM de
2025 entrar na base. Quando a rotina de atualização trouxer 2025, rodar de novo
`03` com origem em 2024 e comparar com a produção publicada é um teste fora da
amostra, que nenhum retroteste substitui. Ressalvas: a produção aqui é
rendimento × área plantada (a PAM usa a área colhida); a área depende de preço,
crédito e abertura de áreas, que não estão no modelo; a escolha do melhor
modelo usa o próprio retroteste, e o erro dele é otimista.

### 4. Referência no recorte nacional (`04`)

Safras de teste 2016–2020, 6.215 registros, mesma subamostragem da Tabela 3:

| Modelo | RMSE | R² | Ganho sobre a referência (IC95) |
|---|---|---|---|
| E1 SVR da Tabela 3 (tendência da base) | 460,7 | 0,425 | +0,385 (0,357 a 0,410) |
| E2 tendência da base sozinha | 633,7 | −0,087 | — |
| E2 referência: média + tendência (LOYO) | 587,3 | 0,066 | — |
| E2 referência: média + tendência (só passado) | 601,4 | 0,021 | — |
| E3 SVR sobre o resíduo da referência (LOYO) | 458,7 | 0,430 | +0,390 (0,369 a 0,410) |
| E4 SVR sobre o resíduo, só passado | 477,5 | 0,383 | +0,370 (0,350 a 0,389) |

O E1 reproduz a Tabela 3 exatamente. No recorte nacional, o ambiente acrescenta
muito ao histórico: o SVR reduz o erro quadrático em cerca de 38% em relação à
referência, sem depender da tendência fornecida pela base (E3) e também
treinando só com o passado (E4). No Pará, o mesmo contraste dá ganho nulo. A
diferença entre os recortes deixa de ser de método e passa a ser de dado, o que
é a hipótese subsidiária da dissertação: onde o alvo repete valores, a
capacidade de discriminar modelos desaparece.

## O que isso responde

- **Dá para prever a safra futura?** Sim, com cerca de 15% de erro a 1 safra e
  17% a 3 safras na escala municipal, e com cerca de 7% (1 safra) a 27% (3
  safras) na produção estadual. Quem faz a previsão é o histórico com tendência;
  no Pará, nenhum dos modelos testados acrescenta a ele um ganho significativo.
- **As variáveis ambientais não servem?** Servem onde o alvo é bom: no recorte
  nacional, o ganho é de 0,37 a 0,39, com intervalo longe do zero. No Pará, o
  ganho fica dentro do ruído do alvo.
- **O El Niño importa?** Associa-se à chuva e, mais fracamente, à produtividade
  no Pará, e é o único acréscimo que melhora todos os modelos ambientais ao fim
  do ciclo; o ganho não é significativo com 24 safras.

Os protocolos para o que ainda falta testar estão em
[`TRABALHOS_FUTUROS.md`](TRABALHOS_FUTUROS.md).
