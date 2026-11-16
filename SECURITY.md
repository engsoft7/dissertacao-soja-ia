# Segurança

## Como avisar de uma falha

Encontrou uma falha de segurança no aplicativo, na API, no painel ou nos
workflows deste repositório? Avise pela aba **Security → Report a
vulnerability** do GitHub, que abre uma conversa privada com o autor. Não
abra issue pública com os detalhes: até a correção, a falha fica sem
divulgação. Se o botão não aparecer, abra uma issue só pedindo contato, sem
descrever a falha.

Diga o que encontrou, como reproduzir e o que alguém conseguiria fazer com
ela. A resposta vem em até 7 dias, e a correção sai numa versão nova do
aplicativo e da API.

## O que vale

Vale sempre a versão mais recente: a do aplicativo na Google Play e no último
Release, a da API em `agrointeligencia-api.onrender.com` e a do painel no
Streamlit. Versões antigas não recebem correção à parte.

## Como o projeto se protege

- **Segredos fora do código.** A chave de assinatura do aplicativo, a conta
  de serviço da Google Play e o token do Zenodo ficam nos segredos do GitHub
  Actions, e nunca no repositório: o `.gitignore` recusa `*.jks` e
  `keystore.properties`. O aplicativo está no Play App Signing: a chave dos
  workflows é a de envio, que o Google permite trocar.
- **Workflows com o mínimo.** Cada workflow declara as permissões de que
  precisa, a maioria só de leitura. Texto vindo de fora (mensagem de commit,
  entrada de disparo manual) chega aos scripts por variável de ambiente, e
  não escrito no comando.
- **Conexões verificadas.** Toda conexão confere o certificado do servidor.
  Nenhum script desliga essa verificação, nem quando uma fonte apresenta
  certificado inválido: a coleta para e abre uma issue.
- **Aplicativo.** Só conexões HTTPS, sem backup automático para a nuvem, sem
  componentes abertos a outros aplicativos além da tela inicial, e a posição
  sai arredondada a cerca de 1 km. Fotos, marcações e o caderno da safra
  ficam só no celular. Detalhes na
  [política de privacidade](https://engsoft7.github.io/dissertacao-soja-ia/politica-de-privacidade/).
- **API.** Só leitura, sem cadastro, sem cookie e sem dado pessoal guardado.
- **Análise automática.** O CodeQL (`codeql.yml`) analisa o Python e os
  workflows em cada pull request, num push na `main` e toda semana. Os
  alertas ficam em **Security → Code scanning**.
