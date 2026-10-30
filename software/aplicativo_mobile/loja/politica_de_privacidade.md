# Política de privacidade do aplicativo AgroInteligência

Última atualização: 30 de outubro de 2026.

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
  aparelho, sem Internet. Nada disso sai do celular, a não ser que o produtor
  toque em exportar e escolha para onde enviar o arquivo .zip.
- **Posição do GPS para medir a área do talhão.** Usada só com a tela aberta,
  para calcular a área; não é enviada.

## O que sai do celular, para quê e para onde

| Dado | Para quê | Para onde |
|---|---|---|
| Nome do município escolhido | estimativa de produtividade, histórico, mapa, finanças | API do produto (servidor no Render) |
| Posição aproximada, arredondada a cerca de 1 km: a sede do município ou, se o produtor escolher "Minha localização", a posição do GPS | previsão do tempo e janela de pulverização | Open-Meteo (open-meteo.com) |
| A mesma posição aproximada e, quando é a sede, o código IBGE do município | avisos meteorológicos do INMET para o lugar | API do produto, que consulta o INMET |
| Nada além da própria consulta, uma vez por dia | saber se há versão nova do modelo de contagem de vagens e, se houver, baixá-la | API do produto e GitHub (raw.githubusercontent.com) |

Como em qualquer acesso à Internet, os servidores que recebem essas
requisições registram o endereço IP do aparelho. A API do produto usa a
posição só para escolher os avisos do lugar e não a grava em banco de dados;
os registros de acesso do servidor (Render) guardam por algum tempo o
endereço de cada requisição, que inclui a posição aproximada. O tratamento
pelo Open-Meteo segue os termos dele (https://open-meteo.com/en/terms).

A posição do GPS para a previsão do tempo só é lida quando o produtor toca em
"Minha localização" e autoriza o acesso à localização no Android. A
autorização pode ser retirada a qualquer momento nas configurações do
celular; a previsão volta então à sede do município.

## Permissões

- **Localização:** medir a área do talhão e, se o produtor pedir, a previsão
  do tempo no lugar dele. Só com o aplicativo aberto.
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
