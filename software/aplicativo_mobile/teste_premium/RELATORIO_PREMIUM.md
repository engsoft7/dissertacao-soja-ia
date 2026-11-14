# Relatório Premium do aplicativo AgroInteligência

Testes de 06/11/2026 sobre o app publicado (2.7.3, versionCode 27) e a versão
2.7.4 desta branch, com a API em produção. Tudo roda de novo pelo Actions:
`auditoria-app.yml` (números) e `teste-premium.yml` (API e aparelhos). As
tabelas completas estão nas pastas ao lado, e as capturas de tela na branch
`teste-premium-capturas`. A seção 8 traz a rodada de 13 e 14/11/2026, com o
2.8.0 publicado na v2.5.0 (cinco estados) e o 2.8.1, publicado na v2.5.1.

## Resumo

| Área | Resultado no 2.7.3 publicado | Na 2.7.4 |
|---|---|---|
| Números (API × fontes, telas × telas) | 3 defeitos de produtividade (IBGE) | corrigidos na API, já em produção, conferidos nos 38 municípios |
| Páginas de 16 KB (Android 15) | conforme | conforme |
| Privacidade e segurança | backup copiava fotos e valores para o Google Drive; permissão sem uso; links do mapa presos no app | corrigidos; política de privacidade atualizada |
| API: robustez | nenhuma entrada estranha virou erro 500; nada refletido em HTML; HTTP vai para HTTPS | idem, e CORS sem credenciais |
| API: desempenho | 30 aberturas simultâneas: p95 de 29,6 s | p95 de 0,97 s, já em produção |
| App: tamanho e memória | R8 desligado: 12 MB de código sem enxugar | R8 ligado: APK 28% menor, 35 a 40% menos memória |
| App: percurso, sem internet, monkey | tudo passa; com sinal fraco, o aviso de sem conexão levava até 1 min | tudo passa; aviso na hora |
| App: fonte do sistema em 200% | rótulos das abas quebrados, textos encavalados no Resumo e no Mercado | corrigidos |
| App: coerência | simulador na safra 2026 com o Resumo em 2027 | mesma safra |

Na rodada de 14/11 (seção 8), o 2.8.0 publicado e o 2.8.1 passaram em todas as
verificações nos três emuladores, e o percurso passou no Pará e em Mato Grosso.

## 1. Números

`auditoria/RELATORIO.md`. A primeira rodada achou Pau D'Arco com "Safra 2017,
IBGE" e a safra esperada de 2020, São João do Araguaia na safra 2026 e 70
safras publicadas pelo IBGE fora do histórico do app. A API passou a projetar
a partir da última safra publicada e a completar o histórico com a PAM
(`pesquisa/dados/pam_soja_para.csv`, regravado todo mês). A terceira rodada, em
produção, deu as 521 safras iguais ao SIDRA e nenhuma divergência entre telas.
Preços das praças, Chicago, CONAB e avisos do INMET já estavam iguais às fontes.

## 2. Páginas de 16 KB

As 8 bibliotecas nativas do AAB, nas 4 arquiteturas, têm os segmentos LOAD
alinhados a 16 KB, e no APK estão guardadas sem compressão e alinhadas: é o que
a Play exige para aparelhos com Android 15 ou mais novo. O app não foi aberto
num emulador com páginas de 16 KB.

## 3. Privacidade e segurança

Manifesto do APK publicado: permissões de Internet, estado da rede, estado do
Wi-Fi e localização; só a atividade principal exportada; tráfego sem
criptografia proibido.

| Achado | Gravidade | Correção na 2.7.4 |
|---|---|---|
| `allowBackup="true"` sem regras: o backup automático do Android copiava para o Google Drive do usuário as fotos da Estimativa no campo, as marcações e os valores digitados, e a política diz que ficam só no celular | média | backup desligado |
| Permissão `ACCESS_WIFI_STATE` sem uso no código | baixa | removida |
| A WebView do mapa abria links de fora (crédito do OpenStreetMap) dentro do quadro, sem volta, e não negava o acesso a arquivos (padrão até o Android 10) | baixa | links de fora no navegador; sem acesso a arquivos e conteúdo |
| CORS com `*` e credenciais: o Starlette ecoava a origem de qualquer site (confirmado em produção) | baixa (a API não tem login) | sem credenciais |
| A política não citava a posição da previsão do tempo guardada no celular nem os quatro servidores de bibliotecas que o mapa carrega | baixa | política de 06/11/2026 |

## 4. API em produção

`api/api.md`. Rotas que o app chama, nos 38 municípios, depois de aquecer:

| Rota | p50 | p95 | Tamanho |
|---|---|---|---|
| /api/previsao | 1.101 ms | 1.912 ms | 2,1 KB |
| /api/financas | 101 ms | 201 ms | 1,3 KB |
| /api/mercado (1 dia) | 104 ms | 192 ms | 7,5 KB |
| /api/mapa/render | 404 ms | 518 ms | 88 KB |
| demais (municípios, contador, avisos) | ~105 ms | ~210 ms | < 1,3 KB |

Todas vêm comprimidas pelo Cloudflare do Render.

- **Entradas estranhas**: nenhum erro 500. Município inexistente, nome de 5.000
  letras, `../`, emoji e rota inexistente dão 404; corpo inválido dá 422;
  cara de injeção de SQL é barrada pelo firewall do Render (403); a página do
  mapa não devolve o HTML que vem na URL.
- **Simultâneas**: 30 aberturas de /api/previsao ao mesmo tempo, sem erro, mas
  com p50 de 25,4 s e p95 de 29,6 s. Cada chamada refazia dezenas de
  estimativas e o servidor atende uma por vez. O histórico passou a ficar
  guardado por município, preparado na partida do servidor, com as mesmas
  respostas nos 38 municípios. Em produção, depois do merge do PR #181: as 30
  aberturas simultâneas sem erro e com p95 de 970 ms.
- Pontos menores, que ficam como estão: /api/financas de município inexistente
  responde 200 (o custo é o mesmo levantamento para todos), e /api/avisos com
  latitude 999 responde 200 sem avisos.

## 5. App em emuladores

`teste-premium.yml`, três emuladores com a tela de um Pixel 6 (411 × 914 dp) e
a API em produção: Android 8 (API 26, o mínimo do app) e Android 14 (API 34)
com a 2.7.4, e Android 14 com a 2.7.3 publicada (o AAB do Release, convertido
em APK universal). Capturas na branch `teste-premium-capturas`.

**Percurso** (`teste_aparelho.py`, app de release por adb): escolher Pau
D'Arco na busca, Resumo na safra 2027 com a safra 2025 do IBGE, as cinco abas,
Estimativa no campo e Tempo. Passa nas três versões, e também com fonte em
200%, modo escuro, tela pequena (360 × 640 dp) e tablet (800 × 1.280 dp).

**Sem internet** (modo avião conferido com ping): o app abre com os dados
guardados, avisa "Sem conexão: mostrando os dados guardados em…", o Mapa
explica que precisa de conexão, e a Estimativa no campo funciona, nas três
versões. Um caso que o emulador não reproduz: rede que existe e não navega
(sinal fraco, Wi-Fi com login). Nele a 2.7.3 só avisa quando a chamada à API
cai no tempo limite de 60 s, que existe para o servidor do Render acordar; a
2.7.4 pergunta ao Android se a rede foi validada e avisa na hora, sem deixar de
tentar.

**Monkey**: 3.000 toques, arrastos e teclas aleatórios em cada emulador, sem
nenhuma falha nem ANR.

**Desempenho**, Android 14, a mesma tela e a mesma API:

| Medida | 2.7.3 | 2.7.4 |
|---|---|---|
| APK universal | 38,6 MB | 27,6 MB |
| Memória (PSS) no Resumo | 61,9 MB | 36,8 MB |
| Memória depois das cinco abas | 108,6 MB | 87,0 MB |
| Dados de Pau D'Arco na tela, depois da escolha | 5,2 s | 5,7 s |

A memória e o tamanho repetiram nas duas rodadas (na primeira, 57,5 contra
39,9 MB no Resumo). A partida a frio e a fluidez da rolagem não: os emuladores
do Actions desenham sem GPU, e as duas rodadas deram resultados opostos para a
partida (0,7 contra 1,3 s numa, 1,6 contra 0,8 s na outra). Esses números
valem no Android vitals do Play Console, depois da publicação.

## 6. Acessibilidade

Duas fontes: as verificações do Accessibility Test Framework do Google em cada
tela do `PercursoNoAparelhoTest` (as mesmas do Scanner de Acessibilidade:
contraste, tamanho de alvo, rótulos, texto cortado) e a árvore de
acessibilidade de cada captura do `teste_aparelho.py` (alvos menores que
48 dp e botões sem rótulo).

As verificações do Accessibility Test Framework (contraste, tamanho de alvo,
rótulos e texto cortado) não acusaram nada nas telas que o percurso cobriu em
Android 8 e 14: boas-vindas, lista de municípios e Resumo, rolado do alto ao
meio. O percurso parou ao rolar adiante, por um defeito do próprio teste: ele
achava a lista pelo cabeçalho, que deixa de existir quando sai da tela, e o
passo seguinte não a encontrava. O teste já está corrigido para a próxima
rodada; as demais telas ainda não passaram pelo ATF. A árvore do uiautomator,
em todas as telas, apontou só dois alvos abaixo de 48 dp no Sobre (links do
texto, com 42 a 46 dp de altura) e o WebView do mapa sem rótulo próprio, que
o cartão em volta já descreve.

Pelas capturas com a fonte do sistema em 200%, três defeitos, todos já na
2.7.3 e corrigidos na 2.7.4:

| Tela | Defeito | Correção |
|---|---|---|
| Barra de abas | "Resu/mo", "Histór/ico", "Merca/do": o rótulo quebrava no meio da palavra | uma linha, fonte crescendo até 1,15 vez; o ícone segue ao lado |
| Resumo | "Safra 2025, IBGE" encostava em "Em relação a 2025" ("IBGEEm") | cada coluna com metade da largura |
| Mercado | o nome da praça ficava com uma letra de largura ("B-a-r-c-a-r-e-n-a") | com fonte grande, a data desce para baixo do preço; resta "Paragominas", longo demais para a coluna, quebrar em "Parago/minas" |

E um de coerência: o simulador climático do Resumo dizia "Projeção com o
cenário, safra 2026" e outro número, logo abaixo de "Resumo Agronômico (safra
2027)". O app manda a safra em curso, e a API simula nela.

Nos emuladores Android 14 do Actions, o Pixel Launcher travou em duas rodadas
(113 avisos de "isn't responding" numa delas) e cobriu a tela: as verificações
dessas rodadas valem como falha do ambiente, não do app, e o script passou a
fechar o aviso sozinho. As rodadas sem o travamento passaram em tudo.

## 7. Painel web (Streamlit)

- **Mesmos números do aplicativo.** A estimativa da safra 2027 do painel e a
  da API, que o aplicativo mostra, são iguais nos 38 municípios: diferença de
  0,0 kg/ha, porque os dois treinam o mesmo modelo na mesma base. Desde o PR
  #183, o painel também abre na safra em curso, usa o preço do dia da praça
  mais perto e mostra as safras do IBGE fora da base, como o aplicativo.
- **Todas as telas em todos os municípios.** As quatro telas (Inteligência
  Territorial, Análise Histórica, Viabilidade Financeira e Tempo na lavoura)
  abertas nos 38 municípios com o `streamlit.testing` (152 aberturas): nenhuma
  exceção, nenhuma mensagem de erro, todas na safra 2027. A rodada foi feita sem
  acesso às cotações, ao Yahoo e à previsão do tempo, e o painel seguiu com as
  reservas (preço da CONAB, avisos de fonte indisponível).
- **No ar.** `confere-painel.yml` abre o painel num navegador e confere o mapa;
  `mantem-painel-acordado.yml` o visita a cada 4 horas, abaixo das 12 horas sem
  visita que fazem o Streamlit Community Cloud pôr o app para dormir.
- **Falta**: o painel em largura de celular e as verificações automáticas de
  acessibilidade no navegador.

## 8. Rodada de 13 e 14/11/2026: 2.8.0 publicado e 2.8.1

Depois do Release v2.5.0, com o app 2.8.0 e a extensão a Mato Grosso,
Maranhão, Tocantins e Rondônia, o `teste-premium.yml` rodou cinco vezes nesta
branch, da run 43460955234 à 43585073563. O percurso no emulador ganhou Mato
Grosso e passou a usar a API da própria branch, que o workflow sobe no runner
com os estados preparados como no Render. O app de release segue apontado à
API em produção, e suas 19 verificações vão da abertura ao monkey: percurso
pelas abas, fonte em 200%, telas pequena, tablet e deitada, sem internet e a
volta da rede.

Na última rodada, de 14/11, tudo passou:

| | Android 8, 2.8.1 | Android 14, 2.8.1 | Android 14, 2.8.0 publicado |
|---|---|---|---|
| App de release, 19 verificações | 19 ok | 19 ok | 19 ok |
| Percurso do Pará | completo, sem a parte sem internet¹ | completo | — |
| Percurso de Mato Grosso, em Sorriso | completo | completo | — |
| Telas sem achado de acessibilidade | 27 de 27 | 30 de 30 | — |
| Dados de Pau D'Arco na tela | 3,7 s | 5,3 s | 5,6 s |
| Memória (PSS) no Resumo | 33,8 MB | 40,4 MB | 41,0 MB |
| Memória depois das cinco abas | 80,3 MB | 83,3 MB | 94,0 MB |

¹ No Android 8, o `svc` não derruba a rede do emulador, e o modo avião pede
root, que o percurso não tem. A parte sem internet fica com o teste do app de
release, que usa root no mesmo emulador e passou.

**Achados no app e na API**, corrigidos nesta branch:

| Onde | Achado | Correção |
|---|---|---|
| Sobre | As fontes com link de uma linha, INMET e MapBiomas, tinham 44 e 46 dp de alvo de toque (Accessibility Test Framework). | Mínimo de 48 dp, no 2.8.1. |
| Cartão do tempo, no Resumo | Dois avisos do mesmo evento apareciam como "2 avisos do INMET: tempestade, tempestade". | O nome entra uma vez, no 2.8.1, com teste de unidade. |
| API no Render | A cada deploy ou reinício, a API treinava os quatro estados novos depois do Pará: uns 90 s de CPU numa máquina comum, na ordem de 15 minutos no décimo de CPU do plano gratuito. Nesse tempo os quatro respondem 503 e dividem a CPU com o Pará. Na leitura de 13/11 às 16h34 UTC, logo depois do deploy, nenhum estava pronto. | Os estados saem prontos da build (`prepara_estados.py`). Na API do runner, os cinco vieram do cache. Em produção desde a v2.5.1: na leitura de 14/11, os cinco vieram do cache da build. |

**Do próprio teste.** Quatro coisas paravam o percurso sem defeito do app, e
o teste foi corrigido:

- A lista de municípios só desenha os nomes que cabem na janela, e Sorriso só
  aparece pela busca.
- O Histórico começa pela projeção mais distante, 2028, e não pela safra em
  curso.
- A aba Mercado tem dois itens, e o teste rolava até o terceiro.
- O percurso de Mato Grosso começava logo depois do modo avião do percurso do
  Pará, antes de a rede do emulador voltar. Agora cada percurso espera a API
  responder.

**Do ambiente do Actions.**

- O aviso "Pixel Launcher isn't responding" cobriu a tela do Android 14 em
  três emuladores das duas primeiras rodadas, com 112 ou 113 avisos em cada
  um, e neles o app de release não chegou aos dados de Pau D'Arco. O teste
  tocava em "Wait", que só adia o aviso. Agora toca em "Close app", e o emulador não mostra o aviso de apps em
  segundo plano. Nas três rodadas seguintes apareceu um aviso só, fechado pelo
  teste.
- A previsão do tempo vem direto do Open-Meteo, do celular, e não pela API. No
  emulador ela não chegou em duas das cinco rodadas, e chegou nas demais. O
  percurso confere que a tela mostra a previsão ou diz que não a baixou.
- A conferência de que a rede voltou falhava em todas as rodadas desde 06/11,
  só com ping. Agora usa a rede padrão do Android, com o ping de reserva e mais
  tempo de espera, e passou nos três emuladores.

## 9. O que este relatório não cobre

- **Aparelhos físicos.** Os testes rodam em emuladores x86_64. O relatório de
  pré-lançamento do Play Console roda o app em aparelhos reais quando um AAB
  entra numa faixa de teste: vale olhar o de cada versão enviada.
- **TalkBack de verdade.** As verificações automáticas não substituem ouvir
  as telas com o leitor de tela ligado.
- **Câmera, GPS e redes lentas reais.** A câmera é a do próprio Android (por
  intent), e o GPS não foi simulado em movimento; a rede lenta do campo foi
  testada só nos extremos (com e sem internet).
- **Segurança dos dados na Play.** O formulário é preenchido no Play Console;
  a 2.7.4 não muda o que o app coleta ou compartilha.
