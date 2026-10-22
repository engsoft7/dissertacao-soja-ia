# Trabalhos futuros: protocolos

Cada item segue o mesmo roteiro: hipótese, dado, desenho do teste e critério de
decisão fixado antes de rodar. O critério comum é o da pasta: ganho de
habilidade sobre o modelo de referência, `1 − MSE(modelo)/MSE(referência)`,
com intervalo de 95% por reamostragem de safras, em janela crescente.

## 1. Conferir a projeção de produção de 2025

- **Hipótese.** A produção do Pará em 2025 cai na faixa de 80% registrada em
  22/10/2026 (3,90 a 4,71 milhões de toneladas).
- **Dado.** PAM 2025, trazida pela rotina `atualiza-dados.yml`.
- **Teste.** Rodar `03_previsao_producao_para.py` com origem em 2024 sem mudar
  nada e comparar com a produção publicada, calculada do mesmo jeito
  (rendimento × área plantada).
- **Critério.** Dentro da faixa: o retroteste descreveu bem o erro. Fora dela:
  registrar o tamanho e o sentido do erro, e qual componente errou (área ou
  produtividade).

## 2. El Niño e La Niña como preditores

- **Hipótese.** O ONI de dezembro a março melhora a previsão da produtividade
  no Pará ao fim do ciclo.
- **Feito em 22/10/2026.** No protocolo da Tabela 6 (`05_oni_na_tabela6.py`) o
  SVR com ONI tem ganho de +0,031 (IC95 −0,024 a +0,090); em janela crescente,
  +0,033 (IC95 −0,026 a +0,094). Os dois apontam no mesmo sentido, nenhum é
  significativo.
- **Teste que falta.** Acrescentar ao ONI o gradiente térmico do Atlântico
  tropical (relevante para a chuva no norte do Brasil), que precisa ser baixado
  da NOAA pela rotina do GitHub Actions, e repetir os dois testes a cada safra
  nova.
- **Critério.** O intervalo do ganho deixa de incluir o zero. Com 24 safras isso
  é improvável; o teste ganha poder a cada safra acrescentada.

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

## 6. Estimativa por drone

- **Dado.** Voos com câmeras RGB, multiespectral e térmica na fase R5–R6, e mapa
  de colheita da colhedora (ou parcelas colhidas) como verdade de campo.
- **Modelo.** Índices por pixel agregados por zona de manejo, com *random
  forest* ou rede neural. A fusão de sensores é o que a literatura aponta como
  ganho.
- **Validação.** Treino e teste separados por talhão e por safra.
- **Uso na pesquisa principal.** Medidas de talhão agregadas por município
  formam uma fonte independente para o item 4.

## 7. Aplicativo assinado automaticamente

O workflow `publica-apk.yml` já compila, assina e anexa o APK ao Release, mas
fica inativo sem os quatro segredos da chave. Ativar só com o aplicativo no
Play App Signing, em que a chave do workflow é a de envio e pode ser trocada.
