# Política de privacidade do aplicativo AgroInteligência

Última atualização: 14 de novembro de 2026 (versão 2.9.0 do aplicativo).

O AgroInteligência é um aplicativo gratuito, sem anúncios e sem cadastro,
desenvolvido como produto técnico de dissertação do Programa de Pós-Graduação
em Computação Aplicada (PPCA) da Universidade Federal do Pará. Ele não pede
nome, e-mail, telefone ou documento, e não usa ferramentas de análise de uso
nem de publicidade.

## O que fica só no celular

- **Valores que o produtor informa** (preço da saca, custo por hectare,
  produtividade) e as respostas guardadas para uso sem Internet (estimativas,
  cotações, previsão do tempo). Ficam na memória do aplicativo e saem quando
  ele é desinstalado ou quando os dados dele são apagados nas configurações
  do Android.
- **Fotos e marcações da Estimativa no campo.** As fotos são tiradas com a
  câmera do próprio celular e guardadas na pasta do aplicativo, regravadas sem
  os metadados de localização da câmera, com as marcas das plantas e vagens. A contagem automática de vagens roda no próprio
  aparelho, sem Internet. Junto delas ficam os talhões contados: os pontos, a
  área e, se o produtor informar, as sacas colhidas, sem a posição do talhão.
  Nada disso sai do celular, a não ser que o produtor toque em exportar e
  escolha para onde enviar o arquivo .zip.
- **Posição do GPS para medir a área do talhão.** Usada só com a tela aberta,
  para calcular a área; não é enviada.
- **Município escolhido**, para o aplicativo abrir nele da próxima vez.
- **Grupo de cultivar e classe de solo** escolhidos na janela de plantio, para
  a tela abrir com a mesma escolha.
- **Caderno da safra:** os lançamentos de plantio, insumos, operações,
  colheita e vendas. Ficam num arquivo na pasta do aplicativo e só saem do
  celular se o produtor exportar a planilha (.csv) e escolher para onde
  enviá-la.
- **Leitura em voz alta e resumo para compartilhar.** O texto lido é entregue
  ao mecanismo de voz do próprio Android, e o aplicativo não o envia a nenhum
  servidor. O resumo em imagem ou PDF é gerado no celular e só sai dele pelo
  compartilhamento, para onde o produtor escolher.
- **Escolhas dos alertas** (o que avisar, a praça e o preço-alvo), o lugar da
  previsão e o estado, para a conferência em segundo plano, e os avisos já
  mostrados, para não repetir. Com todos os alertas desligados, nada é
  conferido em segundo plano.
- **Posição para a previsão do tempo**, se o produtor escolher "Minha
  localização": guardada já arredondada a cerca de 1 km, para a previsão abrir
  no mesmo lugar da próxima vez. Sai quando ele volta à sede do município ou
  desinstala o aplicativo.
- **Posição do GPS para achar o município mais próximo.** Lida só quando o
  produtor toca em "Usar minha localização" na escolha do município. A sede
  mais próxima é calculada no próprio celular; a posição não é guardada nem
  enviada, e só o nome do município escolhido segue para a API, como na
  escolha pela lista.

O aplicativo desliga o backup automático do Android: nada disso é copiado
para o Google Drive nem passa para um celular novo na transferência de dados.

## O que sai do celular, para quê e para onde

| Dado | Para quê | Para onde |
|---|---|---|
| Nome do município escolhido e o estado | estimativa de produtividade, histórico, mapa, finanças, cotações das praças, janela de plantio | API do produto (servidor no Render) |
| O idioma em que o aplicativo está (português ou inglês) | receber no mesmo idioma as frases que a API monta (preço, custo, janela de plantio, legenda do mapa) | API do produto |
| Posição aproximada, arredondada a cerca de 1 km: a sede do município ou, se o produtor escolher "Minha localização", a posição do GPS | previsão do tempo e janela de pulverização | Open-Meteo (open-meteo.com) |
| A mesma posição aproximada e, quando é a sede, o código IBGE do município | avisos meteorológicos do INMET para o lugar | API do produto, que consulta o INMET |
| Nada além da própria consulta, ao abrir a aba Mapa | as bibliotecas que desenham o mapa (Leaflet, jQuery, Bootstrap) | servidores públicos de bibliotecas: cdn.jsdelivr.net, cdnjs.cloudflare.com, code.jquery.com e netdna.bootstrapcdn.com |
| Nada além da própria consulta, uma vez por dia | saber se há versão nova do modelo de contagem de vagens e, se houver, baixá-la | API do produto e GitHub (raw.githubusercontent.com) |
| Só com algum alerta ligado, a cada 3 horas, mesmo com o aplicativo fechado: a mesma posição aproximada (avisos e previsão) e o estado (cotação das praças) | conferir os alertas ligados (avisos do INMET, janela de pulverização, preço da saca) | API do produto e Open-Meteo, como acima |

Como em qualquer acesso à Internet, os servidores que recebem essas
requisições registram o endereço IP do aparelho. A API do produto usa a
posição só para escolher os avisos do lugar e não a grava em banco de dados;
os registros de acesso do servidor (Render) guardam o endereço de cada
requisição, que inclui a posição aproximada, e são apagados automaticamente
pelo Render em até 30 dias. O tratamento
pelo Open-Meteo segue os termos dele (https://open-meteo.com/en/terms).

A posição do GPS para a previsão do tempo só é lida quando o produtor toca em
"Minha localização" e autoriza o acesso à localização no Android. A
autorização pode ser retirada a qualquer momento nas configurações do
celular; a previsão volta então à sede do município.

## Permissões

- **Localização:** medir a área do talhão, achar o município mais próximo e,
  se o produtor pedir, a previsão do tempo no lugar dele. Só com o aplicativo
  aberto, e só depois de o produtor tocar no botão correspondente.
- **Notificações:** mostrar os alertas que o produtor ligar. No Android 13 ou
  mais novo, o aplicativo pede a autorização ao ligar o primeiro alerta.
- **Iniciar com o celular:** voltar a agendar a conferência dos alertas depois
  que o celular reinicia. Sem alerta ligado, nada é agendado.
- **Internet:** buscar estimativas, cotações, previsão do tempo, avisos e
  versões novas do modelo de contagem de vagens. O modelo baixado só é usado
  depois de conferido (tamanho e resumo SHA-256 anunciados); as fotos
  continuam no celular.

O aplicativo não pede permissão de câmera (usa o aplicativo de câmera do
próprio Android), de contatos, de microfone nem de arquivos fora da pasta dele.

## Crianças

O aplicativo é voltado a produtores rurais e técnicos, e não se dirige a
crianças.

## Direitos do titular (LGPD)

O aplicativo não mantém cadastro nem base de dados pessoais no servidor. Os
dados guardados ficam no próprio celular, sob controle do usuário. Dúvidas e
pedidos sobre esta política: **maycon.engineer@gmail.com**.

## Código aberto

O código do aplicativo e da API é aberto e pode ser conferido em
https://github.com/engsoft7/dissertacao-soja-ia.
