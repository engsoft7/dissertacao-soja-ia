# Relatório Premium do aplicativo AgroInteligência

Testes de 06/11/2026 sobre o app publicado (2.7.3, versionCode 27) e a versão
2.7.4 desta branch, com a API em produção. Tudo roda de novo pelo Actions:
`auditoria-app.yml` (números) e `teste-premium.yml` (API e aparelhos). As
tabelas completas estão nas pastas ao lado, e as capturas de tela na branch
`teste-premium-capturas`.

## Resumo

| Área | Resultado no 2.7.3 publicado | Na 2.7.4 |
|---|---|---|
| Números (API × fontes, telas × telas) | 3 defeitos de produtividade (IBGE) | corrigidos na API, já em produção, conferidos nos 38 municípios |
| Páginas de 16 KB (Android 15) | conforme | conforme |
| Privacidade e segurança | backup copiava fotos e valores para o Google Drive; permissão sem uso; links do mapa presos no app | corrigidos; política de privacidade atualizada |
| API: robustez | nenhuma entrada estranha virou erro 500; nada refletido em HTML; HTTP vai para HTTPS | idem, e CORS sem credenciais |
| API: desempenho | 30 aberturas simultâneas: p95 de 29,6 s | histórico guardado por município (12 ms por resposta) |
| App: tamanho e partida | R8 desligado: 12 MB de código sem enxugar | R8 ligado: APK 28% menor, partida 3,5 vezes mais rápida |
| App: percurso, sem internet, monkey | ver abaixo | ver abaixo |
| Acessibilidade | ver abaixo | ver abaixo |

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
  estimativas e o servidor atende uma por vez. Na 2.7.4 o histórico fica
  guardado por município e é preparado na partida do servidor; as respostas
  são as mesmas nos 38 municípios, e a chamada repetida leva 12 ms.
- Pontos menores, que ficam como estão: /api/financas de município inexistente
  responde 200 (o custo é o mesmo levantamento para todos), e /api/avisos com
  latitude 999 responde 200 sem avisos.

## 5. App em emuladores

PENDENTE

## 6. Acessibilidade

PENDENTE

## 7. O que este relatório não cobre

- **Aparelhos físicos.** Os testes rodam em emuladores x86_64. O relatório de
  pré-lançamento do Play Console roda o app em aparelhos reais quando um AAB
  entra numa faixa de teste: vale olhar o da 2.7.4.
- **TalkBack de verdade.** As verificações automáticas não substituem ouvir
  as telas com o leitor de tela ligado.
- **Câmera, GPS e redes lentas reais.** A câmera é a do próprio Android (por
  intent), e o GPS não foi simulado em movimento; a rede lenta do campo foi
  testada só nos extremos (com e sem internet).
- **Segurança dos dados na Play.** O formulário é preenchido no Play Console;
  a 2.7.4 não muda o que o app coleta ou compartilha.
