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
  em execução no Actions.
