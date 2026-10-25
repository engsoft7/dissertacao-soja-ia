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
Holm = 1,0 em todas). **Falta:** o mesmo teste no recorte nacional, que decide
se o limite é o alvo ou a forma de medir o ambiente; e as fontes de 2015 em
diante (SMAP, TROPOMI, Sentinel-1 e 2), que exigem um desenho só com as safras
recentes, e o SoilGrids.

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
  - Contador por mapa de densidade (MobileNetV3, `treina_contador_vagens.py`,
    treinado no Actions). No teste da YOLO POD:
    - a melhor versão para contar (v1) erra 5,6% da contagem (R² de 0,969);
    - a melhor para localizar cada vagem (v2) acha 61% delas, com 84% de
      marcas certas.
- **Falta.** Medir o erro em fotos do Pará marcadas no aplicativo e, depois,
  contra a colheita pesada (o critério acima). Ligar o modelo ao aplicativo
  como sugestão que o produtor confere (LiteRT).

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
- **Critério.** O erro da contagem no conjunto do portão cai, ou não sobe, a
  cada versão publicada.
- **Fora do escopo.** O aprendizado dentro do próprio aparelho (federado). É
  pesado para o celular e difícil de controlar contra marcações erradas.

## 8. Aplicativo assinado automaticamente

O workflow `publica-apk.yml` já compila, assina e anexa o APK ao Release, mas
fica inativo sem os quatro segredos da chave. Ativar só com o aplicativo no
Play App Signing, em que a chave do workflow é a de envio e pode ser trocada.
