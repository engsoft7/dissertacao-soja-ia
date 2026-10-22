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
| `05_oni_na_tabela6.py` | O ONI, como variável, melhora os modelos no protocolo da Tabela 6? | `oni_na_tabela6.json` |
| `06_confere_projecao_2025.py` | A projeção registrada para 2025 acertou? E os modelos municipais, fora da amostra? | `confere_projecao_2025.json` |
| `07_variaveis_por_fase.py` | Medir o ambiente na floração e no enchimento, e o Atlântico, melhora os modelos? | `variaveis_por_fase.json` |
| `08_triangula_conab.py` | A CONAB concorda com a PAM? O clima aparece mais nela? | `triangula_conab.json` |

Os dados que só o GitHub Actions alcança (SIDRA, NOAA, CONAB, Earth Engine)
são baixados por `coleta/`, disparada na aba Actions com a opção
`coleta_previsao` do workflow `atualiza-dados.yml` (`tudo` ou uma fonte), e
gravados em `dados/`. O workflow recusa gravar na branch principal.

```bash
cd pesquisa/08_previsao_futura
python 01_enso_para.py
python 02_previsao_rendimento_para.py      # ~1 min
python 03_previsao_producao_para.py
python 04_referencia_nacional.py           # requer 03_analise_nacional/data/data_cast.csv (00_baixa_dados.py)
python 05_oni_na_tabela6.py                # ~5 min, busca aninhada
python 06_confere_projecao_2025.py         # requer dados/pam_para_municipios.csv
python 07_variaveis_por_fase.py            # ~1 h, busca aninhada por família
python 08_triangula_conab.py
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
2025 entrar na base, e conferida no mesmo dia, quando a coleta a trouxe (seção
6). Ressalvas: a área depende de preço, crédito e abertura de áreas, que não
estão no modelo; a escolha do melhor modelo usa o próprio retroteste, e o erro
dele é otimista.

**Correção.** A ressalva original dizia que a produção aqui era rendimento ×
área *plantada*, e não a colhida, que a PAM usa. Está errada: a coluna
`area_plantada_ha` de `03_analise_nacional/pam_soja_municipios.csv` guarda a
variável 216 do SIDRA, que o IBGE chama de "Área colhida". A coleta de 2025
leu o nome na própria resposta da API e conferiu: os totais de 2001-2024
batem com a área colhida sem diferença, e com a plantada diferem em até 2,2%.
A produção calculada aqui é, portanto, a da PAM (4.372.392 t em 2025, contra
4.372.363 t publicadas; a diferença é de arredondamento). Os números da
projeção não mudam; o script `03` e o JSON ficam como foram registrados.

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

### 5. ONI no protocolo da Tabela 6 (`05`)

Mesma avaliação da Tabela 6 (leave-one-year-out com busca aninhada, mesmos
orçamentos e semente), com o ONI de dezembro a março somado às onze variáveis:

| Modelo | Tabela 6 (RMSE / R²) | Com ONI (RMSE / R²) | Ganho sobre a referência (IC95) |
|---|---|---|---|
| SVR | 417,6 / 0,208 | 409,0 / 0,241 | +0,031 (−0,024 a +0,090) |
| Random Forest | 431,9 / 0,153 | 414,7 / 0,220 | +0,005 (−0,076 a +0,089) |
| XGBoost | 439,5 / 0,123 | 428,6 / 0,166 | −0,063 (−0,151 a +0,014) |
| MLP | 415,6 / 0,216 | 425,3 / 0,179 | −0,047 (−0,126 a −0,002) |
| Referência | 415,6 / 0,216 | — | — |

O ONI melhora três dos quatro modelos, e o SVR com ONI é o primeiro a ficar
numericamente acima da referência neste protocolo. O ganho, +0,031, é o mesmo
medido em janela crescente (+0,033), mas o intervalo inclui o zero: com 24
safras, a melhora não se distingue do acaso. O MLP piora. A Tabela 6 da
dissertação não muda.

### 6. A projeção de 2025, conferida (`06`)

A PAM 2025 saiu antes de esta pasta ser fechada, e a coleta pelo Actions a
trouxe. O script lê a projeção registrada, confere que ela se reproduz com a
série até 2024 e só então compara:

| | Projetado (origem 2024) | Publicado (PAM 2025) | Erro da projeção |
|---|---|---|---|
| Produção | 4,29 milhões t (faixa de 80%: 3,90 a 4,71) | 4,37 milhões t | −2,0% |
| Área colhida | 1,35 milhão ha | 1,32 milhão ha | +1,9% |
| Produtividade | 3.175 kg/ha | 3.303 kg/ha | −3,9% |

A produção caiu dentro da faixa de 80%, e o erro de 2,0% é menor que 86% dos
erros do retroteste a 1 safra. Área e produtividade erraram em sentidos
opostos e se compensaram em parte. A revisão do IBGE não mudou nenhum valor de
2001 a 2024. Um acerto só não valida o método; ele mostra que a faixa do
retroteste descreveu bem o erro desta vez.

**Novo registro, com origem em 2025** (mesmo modelo, série nova):

| Safra | Produção projetada | Faixa de 80% |
|---|---|---|
| 2026 | 4,81 milhões t | 4,41 a 5,28 milhões t |
| 2027 | 5,35 milhões t | 4,45 a 6,71 milhões t |
| 2028 | 5,83 milhões t | 4,47 a 9,59 milhões t |

A CONAB estima 5,40 milhões de toneladas para 2026 (levantamento de outubro de
2026), acima da faixa. A PAM 2026, prevista para o segundo semestre de 2027,
decide quem errou.

**Os modelos municipais, fora da amostra.** A rotina de atualização coletou as
onze variáveis de 2025 para 36 municípios. Com os modelos treinados só em
2001-2024 (configurações do Quadro 8):

| Modelo | RMSE em 2025 | Ganho sobre a referência (IC95, por municípios) |
|---|---|---|
| Referência (média + tendência) | 463 kg/ha (13,7%) | — |
| MLP (o do painel) | 464 kg/ha | −0,002 (−0,003 a 0,000) |
| SVR | 503 kg/ha | −0,181 (−0,304 a −0,056) |

O MLP repete a referência, como na Tabela 6. O SVR, o melhor modelo ambiental
em *leave-one-year-out*, fica pior que ela na primeira safra realmente nova.
É uma safra só, e o intervalo reamostra municípios, não safras: o resultado
não decide nada sozinho, mas aponta no mesmo sentido do resto da pasta.

### 7. Ambiente por fase e Atlântico tropical (`07`)

Resultados em andamento (a busca aninhada por família leva cerca de uma hora).

### 8. PAM contra CONAB (`08`)

A CONAB publica por UF, então o teste municipal previsto (refazer as Tabelas 5
e 6 com outro alvo) não é possível com ela. Por UF, 2001-2025, nas 15 UFs com
mais de 100 mil hectares:

| UF | Diferença média de produtividade (CONAB − PAM) | r da variação anual | Desvio da anomalia PAM / CONAB |
|---|---|---|---|
| PR, RS, PI, BA, MS | −0,7% a +3,2% | 0,98 a 0,997 | iguais (±1,6 p.p.) |
| MT, MG, SC, SP, GO, MA, TO | −0,1% a +2,1% | 0,89 a 0,96 | iguais (±3 p.p.) |
| RO | −0,4% | 0,42 | 4,1% / 4,7% |
| RR | +4,0% | 0,21 | 11,2% / 7,0% |
| **PA** | **+0,2%** | **0,12** | **5,1% / 7,1%** |

Onde a soja é antiga, as duas fontes contam a mesma história ano a ano. No
Pará, elas concordam na média, mas quase não concordam sobre quais safras
foram boas ou ruins (r = 0,12 para a variação anual); Rondônia (0,42) e
Roraima (0,21), também na fronteira norte, concordam pouco. A CONAB varia mais
que a PAM no Pará (7,1% contra 5,1% de desvio da anomalia), o que é compatível
com a PAM achatada pela repetição municipal.

O teste de que a CONAB carregaria o sinal climático que falta à PAM não se
confirma: no Pará, chuva, EVI máximo, ONI e gradiente do Atlântico têm
correlação baixa com a anomalia das duas fontes (|ρ| ≤ 0,30, nenhuma
significativa), e as diferenças entre elas têm intervalos que cruzam o zero.
O que fica é negativo e útil: no Pará, nem o alvo oficial nem a fonte
independente medem a mesma variação de ano para ano, e nenhum dos dois a liga
ao clima na escala estadual. A triangulação que resolveria a questão precisa
de dado municipal ou de talhão (itens 5 e 6 de `TRABALHOS_FUTUROS.md`).

**Previsões da safra 2025 no Pará:** a CONAB estimou 3,90 milhões de toneladas
em fevereiro de 2025 e fechou em 4,50; a PAM publicou 4,37. A projeção desta
pasta (4,29) partiu da PAM até 2024, que só saiu em setembro de 2025; não é
uma previsão feita na mesma data que a da CONAB e não deve ser comparada como
tal.

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
