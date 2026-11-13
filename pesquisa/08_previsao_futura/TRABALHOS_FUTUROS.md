# Trabalhos futuros: protocolos

Cada item segue o mesmo roteiro: hipótese, dado, desenho do teste e critério de
decisão fixado antes de rodar. O critério comum é o da pasta: ganho de
habilidade sobre o modelo de referência, `1 − MSE(modelo)/MSE(referência)`,
com intervalo de 95% por reamostragem de safras, em janela crescente.

## 1. Conferir a projeção de produção de 2025

- **Hipótese.** A produção do Pará em 2025 cai na faixa de 80% registrada em
  22/10/2026 (3,90 a 4,71 milhões de toneladas).
- **Feito em 22/10/2026** (`06_confere_projecao_2025.py`). A PAM 2025 publicou
  4,37 milhões de toneladas; a projeção era 4,29 (erro de −2,0%, dentro da
  faixa). Área +1,9%, produtividade −3,9%.
- **Próximo teste.** O registro com origem em 2025 projeta 4,81 milhões de
  toneladas para 2026 (faixa de 80%: 4,41 a 5,28). A CONAB estima 5,40. Rodar
  `06` de novo quando a PAM 2026 sair, trocando o ano conferido.

## 2. El Niño e La Niña como preditores

- **Hipótese.** O ONI de dezembro a março melhora a previsão da produtividade
  no Pará ao fim do ciclo.
- **Feito em 22/10/2026.** No protocolo da Tabela 6 (`05_oni_na_tabela6.py`) o
  SVR com ONI tem ganho de +0,031 (IC95 −0,024 a +0,090); em janela crescente,
  +0,033 (IC95 −0,026 a +0,094). Os dois apontam no mesmo sentido, nenhum é
  significativo.
- **Atlântico, feito em 22/10/2026** (`07_variaveis_por_fase.py`). TNA, TSA e
  o gradiente, baixados da NOAA pelo Actions: SVR −0,001 (IC95 −0,042 a
  +0,038) no protocolo da Tabela 6.
- **Repetido em 29/10/2026 com a safra de 2025** (`10_oni_base_produto.py`,
  base do produto, 451 registros): RF +0,046 (IC95 −0,045 a +0,143), XGBoost
  +0,001 (−0,115 a +0,115), SVR −0,006 (−0,066 a +0,044) e MLP −0,004 (−0,011
  a 0,000). Nenhum ganho significativo. O workflow `confere-safra-nova.yml`
  repete o teste sozinho quando a base do produto ganha uma safra.
- **Teste que falta.** Repetir os dois testes a cada safra nova.
- **Critério.** O intervalo do ganho deixa de incluir o zero. Com 24 safras isso
  é improvável; o teste ganha poder a cada safra acrescentada.
- **Feito em 13/11/2026, a janela do nacional ampliada**
  (`03_analise_nacional/14_vinte_safras_e_enso.py`). A subseção 5.4 nota que
  2016, El Niño forte, é a pior safra dos quatro modelos, com um só evento
  intenso na janela de teste. O protocolo da Tabela 3 foi repetido com cada
  uma das vinte safras de 2001 a 2020 deixada de fora: 2016 segue a pior para
  os quatro (R² do SVR de 0,077), mas a intensidade do evento não acompanha o
  desempenho nas vinte (Spearman entre |ONI| e o R² do SVR de −0,09, p = 0,71;
  no ganho sobre a referência, −0,12), e a La Niña forte de 2008 está entre as
  melhores (R² de 0,57). Nas duas safras de |ONI| ≥ 1,5, o R² médio do SVR é
  0,33 contra 0,38 nas outras dezoito. Reunidas as vinte safras, o SVR erra
  436 kg/ha (R² de 0,63) contra 562 da referência (ganho de 0,40, IC95 de 0,25
  a 0,52 por reamostragem de safras), e supera a referência em 17 delas. A
  ressalva fica registrada no JSON: as safras de 2001 a 2015 participaram da
  busca de hiperparâmetros, como treino ou validação, e só as de 2016 a 2020
  são uma leitura limpa.

## 3. Variáveis ambientais novas

Hipótese comum: substituir totais da safra por medidas das fases críticas
melhora o recorte nacional e, no Pará, só se verá ganho onde o alvo não repete.

| Variável | Fonte | Desde | Por que testar |
|---|---|---|---|
| Veranicos, dias com Tmax > 35 °C, déficit de pressão de vapor e graus-dia na floração (R1–R2) e no enchimento (R5–R6) | ERA5-Land, CHIRPS | 2001 | o estresse importa na fase, não no total |
| Umidade do solo em camadas | ERA5-Land; SMAP | 2001; 2015 | apontada na literatura como o principal fator do rendimento |
| Temperatura da superfície | MODIS MOD11 | 2001 | estresse térmico do dossel |
| Fluorescência induzida pelo sol | TROPOMI | 2018 | mede fotossíntese, não só verdor |
| Índices *red-edge* | Sentinel-2 | 2017 | mais sensíveis na fase de enchimento |
| Radar | Sentinel-1 | 2015 | atravessa as nuvens, que cobrem a Amazônia no ciclo |
| Atributos de solo (argila, água disponível) | SoilGrids | estático | limitação reconhecida na dissertação |
| Data de plantio e duração do ciclo | série MODIS de 16 dias | 2001 | fenologia; viabiliza a LSTM |

Desenho: entrar com uma família de cada vez, no protocolo da Tabela 6 e em
janela crescente, e corrigir o nível de significância pelo número de famílias
testadas (Holm).

**Feito em 22/10/2026, no Pará** (`07_variaveis_por_fase.py`): estresse por
fase (veranico, calor acumulado acima de 30 °C, déficit de pressão de vapor e
chuva na floração e no enchimento), umidade do solo em duas camadas, MODIS
MOD11 e fenologia pelo pico de EVI. Nenhuma família superou a referência (p de
Holm = 1,0 em todas).

**Feito em 29/10/2026, LSTM no Pará** (`04_analise_para/09_lstm_series_para.py`,
rodado no Actions): 17 composições de 16 dias de EVI, NDVI e clima por safra,
414 registros, protocolo da Tabela 6 com busca aninhada e 5 sementes. A LSTM
erra 422,5 kg/ha contra 416,1 da referência: ganho de −0,031 (IC95 −0,175 a
+0,093). O SVR da Tabela 6, nos mesmos registros, fica em +0,002 (IC95 −0,041 a
+0,051). A série temporal não tira o Pará do limite da referência.

**Feito em 29/10/2026, SoilGrids** (`10_trabalhos_futuros/05_solo_na_tabela6.py`
e `03_analise_nacional/13_variaveis_extras.py solo`): argila, areia, silte,
carbono orgânico, pH, CTC e densidade de 0 a 30 cm, ponderados pela fração de
soja de cada pixel de 250 m (`coleta/coleta_solo.py`). No Pará nenhum modelo
supera a referência (melhor: SVR, +0,008, IC95 −0,034 a +0,053), como se
esperava: o modelo ajusta o resíduo sobre a média do município, que já absorve
o que é fixo nele. A Tabela 6 refeita sem o solo reproduz os valores publicados
de RF, SVR e MLP; o XGBoost difere (433,2 contra 439,5) pela versão da
biblioteca no Actions. No recorte nacional, onde o modelo não vê a média do
município, os quatro modelos melhoram com o solo, e nenhum intervalo inclui o zero
(diferença de RMSE, com − sem, IC95 por reamostragem de municípios, nos 23.820
registros dos 1.191 municípios pareados ao GAUL): RF −4,0 kg/ha (−5,5 a −2,6),
XGBoost −4,4 (−6,0 a −3,1), SVR −1,8 (−2,9 a −0,8) e MLP −11,1 (−15,1 a −7,0).
O ganho é real e pequeno: no melhor modelo, o SVR, 0,4% do erro (de 449,5 para
447,6 kg/ha). O contraste com o Pará vem do desenho, não do dado: lá o modelo
corrige a média do município, que já carrega o solo; aqui ele não a vê.

**Feito em 29/10/2026, Tabela 3 sem subamostragem**
(`03_analise_nacional/12_sem_subamostragem.py`): os mesmos modelos e
hiperparâmetros, cada safra de teste contra todas as outras (23.617 registros
de treino em vez de 7.000, ou 5.000 no SVR), nas mesmas observações de teste,
com IC95 da diferença de RMSE por reamostragem de municípios. RF não muda
(+0,1 kg/ha, IC95 −2,3 a +2,2); XGBoost (−13,6, IC95 −16,0 a −11,5) e MLP
(−14,3, IC95 −19,6 a −9,1) melhoram; o SVR piora (+5,1, IC95 +3,0 a +7,2). O
SVR com subamostra, 460,7 kg/ha, segue o melhor modelo: a subamostragem não
favoreceu o resultado publicado e não muda a conclusão da Tabela 3.

**Feito em 05/11/2026, variáveis por fase no recorte nacional**
(`03_analise_nacional/13_variaveis_extras.py fases`, rodado no Actions):
umidade do solo em duas camadas, déficit de pressão de vapor e temperatura da
superfície, mês a mês de setembro a março (28 variáveis), em 23.920 registros
de 1.196 municípios, no protocolo da Tabela 3. Diferença de RMSE (com − sem),
IC95 por reamostragem de municípios: RF −9,8 kg/ha (−12,0 a −7,9), XGBoost
−10,3 (−12,3 a −8,4) e SVR −8,6 (−10,2 a −7,0); o MLP piora, +40,8 (+35,9 a
+45,8), sinal de que a rede, com subamostra de 7.000, não absorve 28 variáveis a
mais. O SVR com as fases chega a 449,7 kg/ha, 1,9% abaixo do mesmo modelo sem
elas, ganho maior que o do solo (0,4%), mas medido em outro conjunto de registros. No Pará as mesmas
famílias não superaram a referência (`07_variaveis_por_fase.py`): o limite lá
está no alvo, que repete valores, e não na forma de medir o ambiente.

**Feito em 06/11/2026, sensores lançados depois de 2014 no Pará**
(`10_trabalhos_futuros/02_sensores_recentes.py`, rodado no Actions): cada
família com e sem, nos mesmos registros da base do produto, no protocolo da
Tabela 6. Radar e umidade (Sentinel-1 VV e VH de janeiro a março, SMAP na zona
radicular), 275 registros de 38 municípios, safras 2016 a 2025: com a família,
o melhor modelo é o XGBoost, com ganho de +0,030 sobre a referência (IC95
−0,171 a +0,170), contra −0,056 sem ela. Sentinel-2 (NDVI e NDRE na mediana de
janeiro a março), 212 registros de 37 municípios, 2018 a 2025: a família piora
o Random Forest (ganho de −0,058 sem e −0,123 com, IC95 −0,207 a −0,016) e não
muda o SVR (−0,013 e −0,015). Nenhum braço com a família supera a referência
(p de Holm = 1,0 nos oito). Com oito a dez safras, o teste só acusaria ganho
grande, e os sensores novos não o trazem. O MLP quase repete a referência nos
quatro braços (ganho de 0,000 a +0,004): prevê resíduo perto de zero. O
TROPOMI (fluorescência) não está no catálogo do Earth Engine e ficou fora.

**Feito em 06/11/2026, Amazônia Legal em quatro estados**
(`10_trabalhos_futuros/06_amazonia_legal.py`, rodado no Actions): as onze
variáveis da base do Pará, coletadas da mesma forma em cada estado, com a
produtividade da PAM, no protocolo da Tabela 6 sem mudança, safras 2001 a 2024.
Ganho sobre a referência, IC95 por reamostragem de safras e p de Holm entre os
quatro modelos do estado. A repetição é a fração dos pares de safras
sucessivas de um mesmo município em que a produtividade da PAM se repete, nos
registros da análise (no Pará, os 40,1% da dissertação):

| Estado | Registros (municípios) | Repetição | Referência (kg/ha) | Melhor modelo | Ganho (IC95) | p de Holm |
|---|---|---|---|---|---|---|
| Pará | 415 (38) | 40,1% | 416 | SVR (Tabela 6) | ≈ 0 | — |
| Maranhão | 1.043 (80) | 9,5% | 439,8 | Random Forest | +0,158 (+0,028 a +0,236) | 0,024 |
| | | | | SVR | +0,151 (+0,075 a +0,200) | < 0,001 |
| Mato Grosso | 2.290 (116) | 12,1% | 305,4 | Random Forest | +0,119 (+0,045 a +0,178) | 0,004 |
| Tocantins | 1.639 (108) | 21,0% | 342,1 | XGBoost | +0,113 (−0,013 a +0,216) | 0,14 |
| Rondônia | 485 (41) | 35,3% | 323,5 | SVR | +0,077 (+0,016 a +0,134) | 0,036 |
| Os cinco juntos | 5.872 (383) | 17,9% | 353,3 | XGBoost | +0,100 (+0,030 a +0,163) | < 0,001 |

Em Mato Grosso os quatro modelos superam a referência (ganhos de +0,093 a
+0,119, p de Holm de 0,004 a 0,013); no Maranhão, o Random Forest e o SVR, com
o XGBoost e o MLP (+0,113 e +0,172) perto disso (p de Holm 0,064); em
Rondônia, só o SVR. Em Tocantins, os quatro modelos ganham de 0,09 a 0,11, mas
nenhum passa na correção (o SVR fica em 0,098). É a primeira vez, no protocolo
da Tabela 6, que o clima e a vegetação medidos por satélite explicam a
produtividade municipal além da média do município.

Os dois estados com menos repetição, Maranhão e Mato Grosso, são os de ganho
mais claro, e o Pará, com mais repetição, o de nenhum ganho; é o que a
dissertação atribui ao alvo. A repetição não explica tudo: Rondônia, com
35,3%, ainda tem ganho no SVR, e Tocantins, com 21,0% e quatro vezes os
registros do Pará, não passa na correção. Tamanho da base e variação do alvo
andam juntos nesses estados, e separar os dois pede outro desenho (por
exemplo, subamostrar Mato Grosso ao tamanho do Pará).

Com os cinco estados numa só base (`06_amazonia_legal.py juntos`: o Pará da
dissertação e os quatro estados, 5.872 registros de 383 municípios), os quatro
modelos superam a referência por margem parecida: Random Forest +0,099, XGBoost
e SVR +0,100 e MLP +0,097, com p de Holm de 0,003 ou menos. O protocolo da
Tabela 6, que no Pará não sai da média do município, encontra sinal quando a
base cresce e o alvo repete menos.

**Feito em 07/11/2026, quais preditores pesam em cada estado**
(`10_trabalhos_futuros/08_preditores_estados.py`, nos mesmos registros de
`06_amazonia_legal.py`). Para cada safra deixada de fora, o erro da referência
contra o desvio de cada preditor em relação à média do município, com IC95 por
reamostragem de safras. Em Mato Grosso, só o pico dos índices de vegetação
passa (EVI máximo, r = 0,20; NDVI máximo, 0,13); a temperatura média chega a
−0,23, mas o IC95 (−0,42 a +0,16) inclui o zero, porque o calor de um ano é
parecido no estado inteiro e as safras efetivas são poucas. No Maranhão,
passam sete: temperatura máxima (−0,33), chuva (+0,33), temperatura média
(−0,32), balanço hídrico (+0,31), EVI máximo (+0,31), NDVI máximo (+0,28) e
radiação solar (−0,28). No Pará, só o NDVI máximo, fraco (−0,09) e com o sinal
ao contrário do esperado. Entrou como uma frase, com alteração controlada, na
conclusão da dissertação, depois da Amazônia Legal.

**Feito em 13/11/2026, tamanho da base ou repetição do alvo**
(`10_trabalhos_futuros/09_tamanho_ou_repeticao.py`, rodado no Actions). O
desenho que a seção pedia: Mato Grosso e Maranhão reduzidos, em 100 amostras,
à estrutura exata do painel do Pará (38 municípios, cada um com as safras de
um município paraense, 415 registros), com a repetição do estado e com ela
injetada até os 40,1% do Pará, como em `07_injecao_de_repeticao.py`. Ganho
sobre a referência com a configuração fixa de cada modelo e, nas amostras,
também o SVR com a busca aninhada da Tabela 6; "detectado" é o IC95 acima de
zero.

| Estado | Célula | SVR, ganho mediano (detectado em) | SVR com busca aninhada | Random Forest |
|---|---|---|---|---|
| Mato Grosso | base inteira (2.290), repetição do estado (11,9%) | +0,067 (sim) | — | +0,121 (sim) |
| | base inteira, repetição do Pará (20 réplicas) | +0,041 (70%) | — | +0,073 (100%) |
| | tamanho do Pará, repetição do estado (9,8%) | +0,074 (91%) | +0,161 (76%) | +0,191 (50%) |
| | tamanho do Pará, repetição do Pará (40,3%) | +0,052 (83%) | +0,107 (68%) | +0,128 (62%) |
| Maranhão | base inteira (1.043), repetição do estado (9,6%) | +0,091 (sim) | — | +0,146 (não) |
| | base inteira, repetição do Pará (20 réplicas) | +0,046 (80%) | — | +0,090 (35%) |
| | tamanho do Pará, repetição do estado (8,3%) | +0,069 (99%) | +0,089 (98%) | +0,145 (8%) |
| | tamanho do Pará, repetição do Pará (40,3%) | +0,043 (66%) | +0,062 (66%) | +0,102 (23%) |

No Pará, nas mesmas condições, o SVR dá −0,008 (IC95 −0,032 a +0,014) e a
busca aninhada −0,010. Reduzidos ao tamanho do Pará, os dois estados continuam
mostrando o ganho; com a repetição do Pará injetada, o ganho encolhe e passa a
escapar em parte das amostras, mas não desaparece. O tamanho da base não
explica, sozinho, a ausência de ganho no Pará; a repetição a reduz sem a
produzir; o que resta está nos preditores, que no Pará são os que menos
acompanham o erro da referência (item anterior). Os modelos de árvore são os
mais instáveis entre amostras (detectados em 8% a 62% delas): com 415
registros, só o SVR dá uma resposta estável. Entrou na conclusão da
dissertação, com alteração controlada, em 13/11/2026.

**Feito em 07/11/2026, data de semeadura por satélite**
(`10_trabalhos_futuros/07_data_semeadura.py`, rodado no Actions). Não há
registro público da data de semeadura nem da cultivar por município. A data,
porém, aparece na curva de vegetação: estimou-se o início do verdor de cada
município-safra na série de NDVI de 16 dias do MODIS sobre a máscara de soja
(o primeiro dia acima de 20% da subida até o pico, como no TIMESAT), e a
semeadura como o verdor menos 20 dias. O calendário que sai é o da região: no
sul do Pará (9 municípios, 169 safras), semeadura mediana em 28/10 (quartis
19/10 e 13/11), e no nordeste (13 municípios, 217 safras), em 20/12 (28/11 e
09/01), com 47 e 92 dias do verdor ao pico. Na Tabela 6, com e sem o início do
verdor e os dias até o pico, nos mesmos 407 registros (37 municípios),
nenhum modelo supera a referência: com a fenologia, o MLP fica em −0,011
(IC95 −0,031 a +0,006), o SVR em −0,016, o XGBoost em −0,061 e o Random
Forest em −0,105, contra −0,025, −0,011, −0,064 e −0,065 sem ela (p de Holm
= 1,0 em todos). Do quanto o início do verdor varia, 63% é de uma safra para
outra no mesmo município, mas essa variação, que mistura a semeadura com o
ruído da série de 16 dias sob nuvens, não acompanha a produtividade da PAM.
A cultivar continua sem fonte.

**Milho.** A extensão a outras culturas esbarra na máscara: o MapBiomas
(coleção 10) separa soja, cana, arroz, algodão e café, mas o milho fica em
"outras lavouras temporárias", junto com o que se planta depois da soja. Sem a
máscara, as variáveis de vegetação do milho se misturariam às da soja na
mesma área, e o desenho da base do Pará não se repete.

## 3b. O erro do nacional por estado

- **Por quê.** O objetivo específico d da dissertação pede o comportamento do
  erro por região, e o texto só o tinha por safra.
- **Feito em 13/11/2026** (`03_analise_nacional/15_erro_por_estado.py`). As
  previsões da Tabela 3, repartidas pelos sete estados nas safras de 2016 a
  2020, com o ganho do SVR sobre a referência (média do município + tendência,
  IC95 por reamostragem de municípios) e a repetição da PAM em cada estado:

| Estado | Registros | Repetição | SVR: erro relativo | R² | Ganho sobre a referência (IC95) |
|---|---|---|---|---|---|
| Bahia | 50 | 4.7% | 17.9% | 0.205 | -0.026 (-1.203 a +0.400) |
| Goias | 845 | 23.2% | 12.8% | 0.083 | -0.038 (-0.132 a +0.041) |
| Mato Grosso | 495 | 12.7% | 8.6% | 0.221 | +0.316 (+0.189 a +0.419) |
| Mato Grosso do Sul | 325 | 9.1% | 11.9% | 0.381 | +0.361 (+0.218 a +0.479) |
| Minas Gerais | 675 | 27.6% | 12.8% | 0.124 | +0.216 (+0.105 a +0.319) |
| Parana | 1840 | 4.4% | 13.6% | 0.347 | +0.219 (+0.160 a +0.276) |
| Rio Grande do Sul | 1985 | 12.3% | 18.2% | 0.491 | +0.528 (+0.496 a +0.556) |

  O ganho vai de 0,53 no Rio Grande do Sul a nada em Goiás e na Bahia (50
  registros de teste, intervalo largo). Goiás e Minas Gerais, onde a PAM mais
  repete, estão entre os de menor R², mas com sete estados a associação não se
  estabelece (Spearman de −0,21 no ganho, −0,54 no R², p > 0,2). O erro
  relativo de 14,5% no conjunto é sobre a média das safras de teste (3.171
  kg/ha); os 17,1% da Tabela 3 são sobre a média da base inteira (2.693).
  Entrou na subseção 5.5 da dissertação, com alteração controlada.

## 4. Triangular a variável-alvo

- **Hipótese.** Onde a PAM repete o valor, outra fonte independente varia.
- **Dado.** Estimativas estaduais e por mesorregião da CONAB; registros de
  recebimento de cooperativas e tradings; mapas de colheita de produtores
  parceiros.
- **Teste.** Recalcular as Tabelas 5 e 6 tendo a fonte independente como alvo,
  onde ela existir.
- **Critério.** Se o ganho do ambiente sobre a referência aparecer com o alvo
  independente e não com a PAM, a hipótese subsidiária fica confirmada por uma
  segunda via.
- **Feito em 22/10/2026, por UF** (`08_triangula_conab.py`). A CONAB não
  publica por município nem por mesorregião na série histórica, então o teste
  previsto não é possível com ela. Por UF, no Pará a CONAB varia mais que a
  PAM (desvio da anomalia de 7,1% contra 5,1%) e as duas quase não concordam
  sobre a variação de um ano para o outro (r = 0,12, contra 0,89 a 0,997 nos
  estados de soja antiga). O sinal climático não aparece em nenhuma das duas
  na escala estadual. Falta a fonte municipal ou de talhão.

## 5. Estimativa por foto no aplicativo

Muda a escala, do município para o talhão. A revisão sistemática excluiu de
propósito os estudos em escala de parcela; isto é pesquisa nova, não extensão
do modelo atual.

- **O que a foto mede.** De cima, a câmera vê folhas: as vagens da soja ficam
  escondidas ao longo da haste. Na literatura, fotos de plantas inteiras no
  campo erram cerca de 35% na contagem de vagens; vagens destacadas sobre fundo
  branco erram de 5% a 7,5%.
- **Protocolo.**
  1. O produtor colhe as plantas de 1 m de linha em pontos sorteados do talhão.
  2. Fotografa as vagens destacadas sobre fundo branco.
  3. Um detector do tipo YOLO, rodando no aparelho e sem internet, conta vagens
     e grãos.
  4. O aplicativo estima kg/ha pelos componentes: plantas/m² × vagens/planta ×
     grãos/vagem × peso de mil grãos (da cultivar, ou medido).
- **Dado de treino.** Fotos anotadas de cultivares da região, em várias fases e
  condições de luz.
- **Validação.** Contra a colheita pesada em parcelas. Separar treino e teste
  por fazenda e por safra, nunca por foto, e reportar o erro percentual e o
  RMSE em kg/ha.
- **Critério.** Erro de produtividade menor que o da PAM contra a colheita
  pesada nas mesmas parcelas.
- **Feito em 24 e 25/10/2026.**
  - O aplicativo 2.3.0 traz a tela Estimativa no campo. A contagem de plantas
    e de vagens é feita por toque na foto, e a área é medida pelo GPS. Cada
    foto marcada fica guardada no aparelho (imagem e pontos em JSON) e sai dele
    num `.zip`, só quando o produtor exporta.
  - Levantamento das bases públicas em
    `pesquisa/09_contagem_por_imagem/LEVANTAMENTO_DE_BASES.md`. Para vagens, só
    a YOLO POD tem licença aberta (CC BY 4.0, 1.448 fotos de plantas arrancadas
    sobre pano escuro, 72.709 vagens).
  - Contador por mapa de densidade (Lempitsky e Zisserman, 2010; MobileNetV3,
    `treina_contador_vagens.py`, treinado no Actions). No teste da YOLO POD,
    com fotos separadas do treino mas das mesmas duas localidades (um erro
    medido dentro da base, que tende a ser menor que o de outra região):
    - a melhor versão para contar (v1) erra 5,6% da contagem (R² de 0,969);
    - a melhor para localizar cada vagem (v2) acha 61% delas, com 84% de
      marcas certas.
  - O aplicativo 2.4.0 roda os dois no celular (LiteRT, sem internet), como
    sugestão que o produtor confere: v1 dá o número, v2 as marcas. A
    conversão foi conferida nas mesmas 218 fotos de teste pelo caminho que a
    foto faz no celular (`converte_para_celular.py`): 5,6% de erro na
    contagem e marcas com 85% de acerto que acham 60% das vagens; com a foto
    de cabeça para baixo, o resultado é o mesmo. Fotos com marcas só do
    contador, sem conferência do produtor, não entram no material de treino.
- **Ferramenta pronta em 29/10/2026** (`ciclo_retreino.py`). `junta` monta a
  base do Pará a partir dos `.zip` exportados pelo aplicativo (só fotos de
  vagens com marcação completa, sem repetidas), separando treino, validação e
  teste por fazenda e safra; `mede` roda os modelos do aplicativo nessas fotos
  pelo caminho que a foto faz no celular. Ensaiado em fotos sintéticas; falta
  a primeira remessa real.
- **Feito em 07/11/2026, colheita e modo automático** (aplicativo 2.8.0, na
  branch, sem publicar). Depois de colher, o produtor informa as sacas do
  romaneio do talhão, e a tela compara com a estimativa. O talhão, com os
  pontos (e o número do contador em cada um, quando usado) e a colheita, vai
  no mesmo `.zip` das fotos. `ciclo_retreino.py colheita` mede, contra o que
  foi pesado, a estimativa com as contagens do produtor e a mesma conta com o
  número do contador. O modo automático, em que o número do contador entra sem
  conferência, fica desligado. Ele liga só com um modelo baixado cujo anúncio
  diga `modo_automatico: true`, e `publica` só escreve isso com a medição dos
  mesmos modelos nas fotos de teste do Pará: ao menos 30 fotos e erro médio de
  até 10%. Ligado, ainda pede a conferência do produtor com foto escura ou
  borrada, com vagens por planta fora de 5 a 150, no primeiro ponto do talhão
  e depois em um a cada cinco. Os limites também vêm no anúncio, para serem
  ajustados com as fotos do Pará.
- **Falta.** Medir o erro em fotos do Pará marcadas no aplicativo e, depois,
  contra a colheita pesada (o critério acima).

## 6. Estimativa por drone

- **Dado.** Voos com câmeras RGB, multiespectral e térmica na fase R5–R6, e mapa
  de colheita da colhedora (ou parcelas colhidas) como verdade de campo.
- **Modelo.** Índices por pixel agregados por zona de manejo, com *random
  forest* ou rede neural. A fusão de sensores é o que a literatura aponta como
  ganho.
- **Validação.** Treino e teste separados por talhão e por safra.
- **Uso na pesquisa principal.** Medidas de talhão agregadas por município
  formam uma fonte independente para o item 4.

## 7. Contagem por foto que aprende a cada safra

Hoje o aprendizado é por versões e passa por uma pessoa. O produtor exporta as
fotos marcadas, o modelo é treinado de novo no Actions e chega ao celular numa
versão nova do aplicativo. O plano para torná-lo quase automático:

1. **Envio opcional, com consentimento.** Um botão "Ajudar a melhorar a
   contagem" envia as fotos marcadas para a API. A imagem já é regravada pelo
   aplicativo, sem os metadados de localização da câmera. O envio exige
   armazenamento persistente (o plano gratuito do Render não guarda arquivos)
   e a atualização da política de privacidade na Play Store (LGPD).
2. **Treino periódico no Actions.** Mensalmente, ou a cada N fotos novas,
   treinar com a YOLO POD somada às fotos do Pará. Separar treino e teste por
   fazenda e por safra, nunca por foto.
3. **Portão de qualidade.** Um conjunto fixo de fotos do Pará, marcadas com
   cuidado e que nunca entram no treino, decide a publicação: o modelo novo só
   substitui o atual se errar menos nele. Isso impede que marcações apressadas
   ou fotos ruins piorem o modelo sem que ninguém perceba.
4. **Entrega sem nova versão do aplicativo.** O aplicativo consulta a API e
   baixa o modelo novo, com a versão e o erro medido no portão.

- **Primeiro passo.** Fazer à mão um ciclo completo (exportar, treinar, medir,
  publicar) com as primeiras 50 a 100 fotos do Pará. Automatizar só se o ciclo
  manual reduzir o erro.
- **Feito em 29/10/2026: passos 3 e 4.** `ciclo_retreino.py retreina` parte
  dos pesos publicados, ajusta com as fotos de treino do Pará misturadas às da
  YOLO POD, escolhe a época pela validação do Pará e só aprova o modelo que
  erra menos no teste do Pará sem piorar na YOLO POD além de meio ponto
  percentual; sem a YOLO POD medida, o retreino é só ensaio. `publica` escreve
  o anúncio que a API serve em `/api/contador` (versão, endereço de cada
  `.tflite` preso a um commit da branch `modelo-contagem-vagens`, tamanho e
  SHA-256). O aplicativo 2.6.0 consulta o anúncio uma vez por dia e só adota
  o modelo novo depois de conferir endereço, tamanho, resumo e formato; o
  embutido fica de reserva. Não se usa Release para o modelo, porque cada
  Release publicado gera um depósito no Zenodo. O passo 1, envio pelo
  aplicativo, continua fora: exige servidor com armazenamento e consentimento.
- **Critério.** O erro da contagem no conjunto do portão cai, ou não sobe, a
  cada versão publicada.
- **Fora do escopo.** O aprendizado dentro do próprio aparelho (federado). É
  pesado para o celular e difícil de controlar contra marcações erradas.

## 8. Aplicativo assinado automaticamente

O workflow `publica-apk.yml` já compila, assina e anexa o APK ao Release, mas
fica inativo sem os quatro segredos da chave. Ativar só com o aplicativo no
Play App Signing, em que a chave do workflow é a de envio e pode ser trocada.

- **Feito em 29/10/2026.** Ao lado do APK universal (40,5 MB), o workflow
  passa a anexar um só para arm64-v8a (24,7 MB, 39% menor), a arquitetura de
  quase todo celular vendido desde 2019: tira do universal as bibliotecas
  nativas das outras arquiteturas, realinha e assina de novo com a mesma
  chave, conferido pelo `apksigner verify`.

## 9. Produto: manutenção e conferências

- **API acordada** (`mantem-api-acordada.yml`): consulta `/api/ping` a cada
  10 minutos, para o plano gratuito do Render não adormecer (750 horas por
  mês bastam para um serviço).
- **Monitor das fontes** (`monitor-fontes.yml`): todo dia confere Yahoo,
  Agrolink, Notícias Agrícolas, Open-Meteo, INMET, SIDRA e a própria API, e
  abre uma issue quando alguma falha. Na primeira execução, as sete
  responderam.
- **Safra nova** (`confere-safra-nova.yml`): todo dia 20 confere a projeção
  registrada contra a PAM nova (`09_confere_projecao.py`) e repete o teste do
  ONI na base do produto (`10_oni_base_produto.py`); abre PR com o que mudar.
- **Política de privacidade no GitHub Pages** (`publica-politica.yml`): gera a
  página a partir de `loja/politica_de_privacidade.md` e recusa publicar
  enquanto houver aviso de rascunho ou contato por preencher. Para ativar:
  Settings → Pages → Source: GitHub Actions.
- **Tempo no painel**: a tela Tempo na lavoura do aplicativo também no painel
  web, com as mesmas regras (`api_backend/tempo.py`, porta de
  `TempoCalculo.kt`, com os mesmos casos de teste).
- **Retroteste do preço estimado do Pará**
  (`10_trabalhos_futuros/03_retroteste_preco_para.py`). A média mensal do Pará
  prevista com Chicago do mês e a base do mês anterior, de 12/2024 a 09/2026
  (22 meses): erro médio de R$ 3,44 por saca (2,7%), viés de +R$ 0,30, maior
  erro de R$ 8,54. Chicago sem a base erra R$ 5,78 (viés de +R$ 4,22). Repetir
  o Pará do mês anterior erra R$ 2,92 em média, um pouco menos, mas chega a
  R$ 10,03 no pior mês. A estimativa serve ao que se propõe, acompanhar o dia
  com a bolsa, e não é melhor que a persistência na média do mês.
- **Validação da janela de pulverização** (`10_trabalhos_futuros/04_valida_tempo_inmet.py`):
  a previsão do Open-Meteo (arquivo das rodadas de curto prazo, o caso mais
  favorável) contra 12 estações automáticas do INMET em municípios da base, de
  novembro de 2025 a abril de 2026, 38.079 horas. Erro médio de cerca de 1 °C
  na temperatura, de 5 a 10 pontos na umidade e de 3 a 4,5 km/h no vento, que
  a previsão superestima. Nas estações com a série completa, a previsão acerta
  de 73% a 92% dos dias com chuva de 1 mm ou mais, com 30% a 66% de alarmes
  falsos. A janela concorda pouco com a calculada sobre o medido (acerto de
  42%, kappa de 0,15): das horas previstas como boas, 26% eram boas, cerca de
  63% de atenção e 10,6% a evitar. A maior parte da discordância fica entre
  boa e atenção, coerente com o vento que a previsão põe nas horas calmas; os
  10,6% de horas boas que eram a evitar são o erro que importa ao produtor.
  A janela orienta, não garante: a tela já pede a conferência no local, e o
  texto passa a dizer quanto ela erra.
- **Feito em 13/11/2026, a discordância por critério**
  (`10_trabalhos_futuros/10_janela_por_criterio.py`, rodado no Actions, nas
  mesmas 12 estações e 38.079 horas). Por critério, o que mais pesa é a chuva
  na hora: a previsão a aciona em 47% das horas, o medido em 10%, e 86% dos
  acionamentos previstos são alarme falso (a hora com chance de chuva de 50%
  ou mais conta como chuva). O vento vem em seguida: acima de 10 km/h a 2 m,
  previsto em 6,6% das horas contra 3,7% medidas, com 76% de alarme falso;
  abaixo de 3 km/h, medido em 45% das horas e previsto em 22%. Temperatura e
  umidade acertam cerca de 65% do que o medido aciona. Trocando uma variável
  prevista pela medida: só a temperatura, a concordância vai de 42% para 44%;
  só a umidade, 43%; só o vento, 59%; só a chuva, 58%; vento e chuva juntos,
  92% (kappa de 0,87). Quase toda a discordância está, portanto, no vento e
  na chuva. Corrigir o vento ajuda pouco: a reta ajustada na própria estação
  de novembro a janeiro e aplicada de fevereiro a abril leva a concordância de
  38% para 40%, e o viés por hora do dia, para 42%, mas as horas boas que eram
  a evitar sobem de 10,7% para 12%; a reta da estação mais próxima (79 a 213
  km) piora (40%, e 13,7% de boas a evitar). O limiar da chance de chuva
  também não resolve: de 50% para 90%, ou só com a chuva prevista, a
  concordância vai de 41,9% para 43,7% e as boas que eram a evitar sobem de
  10,6% para 12,1%. O critério do aplicativo fica como está, e a tela segue
  pedindo a conferência no local; o que reduziria o erro é a previsão
  horária de chuva e de vento, não a regra.

## 10. Produto em Mato Grosso, no Maranhão, em Tocantins e em Rondônia

A seção 3 mostrou que, em Mato Grosso e no Maranhão, o clima e a vegetação
medidos por satélite explicam a produtividade além da média do município. O
produto passa a atender os dois estados, na branch, sem publicar antes da
defesa. O Pará continua como está: as rotas da API sem `uf` dão as mesmas
respostas de antes (conferidas uma a uma nas 80 rotas do Pará, antes e
depois da mudança), e o aplicativo do Pará pede e guarda o mesmo de sempre.

- **Base** (`software/automacao_github/monta_base_estados.py`, rodado no
  Actions por `monta-estados.yml` e mantido pela atualização mensal). A
  coleta da seção 3, no formato da base do Pará, com a PAM pelo SIDRA, as
  sedes do mesmo conjunto aberto do Pará e o contorno pela malha do IBGE.
  Ficam em `pesquisa/dados/estados/`. Mato Grosso: 2.452 registros de 118 municípios, safras 2001 a 2025, com a série oficial de 140 municípios; Maranhão: 1.121 registros de 83 municípios, com a série de 94. Dois nomes do GAUL foram corrigidos à mão (Poxoréo, hoje Poxoréu, e Santo Antônio do Leverger); os municípios da coleta que ficaram sem par não aparecem na PAM da soja. O contorno do estado vem da malha do IBGE, que não atendeu na primeira rodada; sem ele, o mapa sai só com os pontos.
- **Modelo.** O mesmo do Pará (referência mais a correção do MLP), treinado
  na base de cada estado. Na validação temporal do produto (deixando uma safra de fora por vez), Mato Grosso erra 303,5 kg/ha (9,6%), com R² de 0,429 contra 0,388 da referência, e o Maranhão erra 411,1 kg/ha (14,3%), com R² de 0,327 contra 0,260. No Pará, o mesmo modelo empata com a referência (R² de 0,253 nos dois): nos dois estados novos, a correção pelo clima e pela vegetação acrescenta o que a seção 3 mediu.
- **Preço e custo.** Os da CONAB no próprio estado, no levantamento em uso
  (março de 2026): em Mato Grosso, Sorriso (R$ 83,66/sc, R$ 5.019,60/ha) ou
  Primavera do Leste (R$ 103,63/sc), a mais perto da sede do município; no
  Maranhão, Balsas (R$ 105,56/sc, R$ 5.489,12/ha). Diferente de Pedro Afonso,
  essas praças não têm o custo aberto por item na extração, e o resultado vai
  pelos dois rateios. O preço do dia é o das praças da Agrolink no estado,
  quando houver: em 07/11/2026, Sorriso (R$ 134,85), Lucas do Rio Verde, Sinop,
  Primavera do Leste e Rondonópolis (R$ 141,40) em Mato Grosso, e Balsas (R$ 143,00)
  no Maranhão. A estimativa pela base mensal fica só no Pará.
- **API** (`software/api_backend/estados.py`). As rotas aceitam `?uf=MT` ou
  `?uf=MA`; `/api/estados` lista os estados e `/api/municipios?com_sedes=true`
  traz as sedes. Mato Grosso e Maranhão treinam depois do Pará, em segundo
  plano, e respondem 503 nos primeiros segundos.
- **Painel.** Seletor de estado na barra lateral. As quatro telas abertas no
  `streamlit.testing` em municípios dos três estados, sem exceção.
- **Simulador de cenário climático, corrigido.** Ele pedia à rede um ano com a
  chuva mudada e todo o resto no normal. Nos dados, um ano mais seco também é
  mais quente, mais ensolarado e menos verde (no Maranhão, a anomalia de chuva
  tem correlação de −0,67 com a de radiação), e a rede respondia a essa
  combinação, que quase não existe, ao contrário da base: 20% menos chuva dava
  +0,9 sc/ha em Balsas. Os controles também iam a ±50% de chuva e +3 °C, muito
  além do que um município varia (de 5% a 95% das safras, cerca de ±20% a 30%
  de chuva e de −0,7 a +1,2 °C). O cenário passa a sair do efeito medido: o
  quanto a produtividade fugiu da referência por 1% de chuva e por 1 °C acima
  do normal do município, as duas juntas, só com o coeficiente de IC95 sem o
  zero (reamostragem de safras), preso à faixa observada no estado. No Pará e
  em Mato Grosso, nenhum dos dois passa (em Mato Grosso, a temperatura dá
  −163 kg/ha por °C, com IC95 de −250 a +114), e o cenário não move a projeção;
  no Maranhão, a chuva passa (+4,5 kg/ha por 1%, IC95 de +0,5 a +8,0), e 20%
  menos chuva tira 1,5 sc/ha. O simulador do Pará continua sem mover a
  projeção, como antes; muda a faixa dos controles e o aviso fora dela.
- **Aplicativo 2.8.0.** Pará, Mato Grosso ou Maranhão na janela de escolha do
  município. Com a API anterior, que ignora `?uf=` e responderia pelo Pará, o
  aplicativo diz que o estado ainda não está no servidor.
- **Feito em 13/11/2026, Tocantins e Rondônia.** Os dois entram como os
  outros (base, API, painel e aplicativo 2.8.0), com o que a seção 3 mediu
  neles: em Tocantins nenhum ganho resiste à correção de Holm e em Rondônia
  só o da SVR, e a tela mostra modelo e referência lado a lado, como no Pará
  (validação temporal do produto: Tocantins 328 kg/ha, R² 0,365 contra 0,310
  da referência; Rondônia 319 kg/ha, 0,303 contra 0,282). Tocantins usa o
  levantamento de Pedro Afonso, do próprio estado, o mesmo do Pará, com o
  custo aberto por item; Rondônia não tem praça de custo na CONAB e usa
  Sorriso (MT), a mais perto, com o nome da praça à vista. Bases pelo SIDRA
  até 2025: Tocantins 1.741 registros de 108 municípios, Rondônia 526 de 41.
- **Feito em 13/11/2026, contorno dos quatro estados.** A API de malhas do
  IBGE não atendeu do Actions em nenhuma tentativa de novembro; a montagem
  ganhou uma segunda fonte, os limites estaduais do IBGE republicados no
  Click That Hood (Code for America), simplificados ao detalhe do contorno do
  Pará (cerca de 300 vértices, 5 KB por estado). O mapa dos quatro estados
  sai com o contorno.
- **Feito em 13/11/2026, safra nova dos outros estados.** A atualização
  mensal, quando a PAM publica uma safra que a coleta de um estado ainda não
  tem, a coleta no Earth Engine (`coleta_amazonia_legal.py`, um estado e uma
  safra por vez) e monta a base de novo; sem a chave, só a série oficial
  avança (`monta_base_estados.py --faltam`).
- **Feito em 13/11/2026, capturas.** `dados_das_capturas.py` grava as
  respostas de um município de cada estado e `CapturasDeTelaTest` desenha
  com elas o resumo, a viabilidade e o cartão do modelo, e a escolha do
  estado com os cinco.
- **Falta.** Publicar (API, painel e aplicativo) depois da defesa; conferir
  com quem planta lá se o custo da praça mais perto representa o município;
  e o teste em emulador com os estados novos (o Teste Premium roda contra a
  API em produção, que ainda não os tem).
