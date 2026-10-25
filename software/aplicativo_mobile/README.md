# AgroInteligência

Aplicativo Android focado em Inteligência Artificial para estimar o rendimento da soja através de dados satelitais e climáticos. Integrado com backend local e Cloud (Render) para simulação e resultados otimizados.

## Funcionalidades
- **Resumo Agronômico:** Visualize as expectativas de rendimento por hectare e estimativas de performance (em sacas) para o município selecionado.
- **Simulador Climático:** Altere fatores de temperatura e precipitação para projetar impactos diretos no seu rendimento da safra.
- **Viabilidade Financeira:** Projeções financeiras como margem de lucro por hectare e ROI com base em cotações e custos de produção.
- **Estimativa no campo:** O produtor fotografa uma linha da lavoura e algumas plantas arrancadas, toca em cada planta e vagem para contar, e o app calcula a produtividade do talhão por componentes de rendimento (plantas/m² × vagens/planta × grãos/vagem × peso de mil grãos), em sacas e em reais. A área pode ser digitada ou medida marcando os cantos do talhão com o GPS. Na foto das vagens, o botão **Contar sozinho (teste)** roda no próprio celular, sem Internet, um contador treinado com a base YOLO POD (Xiang et al., 2023, *Plant Methods* 19:8, CC BY 4.0): um modelo dá o número de vagens e outro sugere as marcas, que o produtor confere tocando na foto. O contador foi treinado com fotos da China e ainda não foi conferido em lavouras do Pará, e a tela diz isso. Cada foto marcada fica guardada no celular com as marcações (pontos em pixels, num JSON ao lado da imagem, com a origem das marcas), e o produtor pode exportar tudo num .zip pelo compartilhamento do Android; nada sai do aparelho sem que ele exporte. Foto com marcas só do contador, sem conferência, não é guardada. Os modelos ficam em `app/src/main/assets` e saem de `pesquisa/09_contagem_por_imagem/converte_para_celular.py`.
- **Tempo na lavoura:** No alto do Resumo, a temperatura de agora e se a hora é boa para pulverizar; o toque abre a tela completa, para a sede do município ou para a posição do GPS (arredondada a cerca de 1 km). Mostra o tempo agora (temperatura, sensação, umidade, vento e rajadas, índice UV pela escala da OMS, nascer e pôr do sol), os avisos meteorológicos do INMET que atingem o lugar, a janela de pulverização hora a hora nas próximas 24 h com a próxima janela boa, a previsão de 7 dias e a chuva dos últimos 7 dias contra a evapotranspiração de referência. A janela segue os critérios da Embrapa Soja (Adegas e Gazziero, 2020, *Tecnologias de produção de soja*, cap. 12): até 30 °C, umidade acima de 60%, vento de 3 a 8 km/h (até 10 km/h só com ponta antideriva) e sem chuva nas 2 horas seguintes, com o vento de 10 m reduzido a 2 m pelo perfil da FAO-56. A previsão vem direto do Open-Meteo (CC BY 4.0), sem depender da API acordar; os avisos passam pela API (`/api/avisos`), que reduz a lista do INMET do país inteiro aos do lugar. Sem rede, a tela mostra a última previsão baixada, com a hora. A previsão do tempo não entra na estimativa de produtividade, que usa o clima observado das safras. As contas estão em `TempoCalculo.kt`.
- **Integração Real-Time:** Conexão direta com modelo preditivo em FastAPI hospedado no Render, com dados atualizados pelas fontes MapBiomas, CHIRPS e ERA5-Land.

## Requisitos
- Android 8.0 (API 26) ou superior.
- Conexão de Internet (a Estimativa no campo funciona sem ela).
- Localização só para medir a área com o GPS e, se o produtor pedir, para a previsão do tempo no lugar dele, com a tela aberta; a câmera é a do próprio celular, sem permissão de câmera. Para a previsão, a posição sai do celular arredondada a cerca de 1 km, para o Open-Meteo e para a API do produto (avisos do INMET); o rascunho da política de privacidade está em [`loja/politica_de_privacidade.md`](loja/politica_de_privacidade.md), para o autor revisar e hospedar.

## Publicação na Play Store
1. No Android Studio, vá em **Build > Generate Signed Bundle / APK**.
2. Crie ou selecione um **Keystore** com senha segura.
3. Gere um **Android App Bundle (AAB)** para upload.
4. Acesse o **Google Play Console**, crie uma nova aplicação ou selecione a existente.
5. Faça upload do AAB, preencha as informações de listagem (descrição, screenshots, classificação indicativa, política de privacidade, etc.). O ícone de 512 × 512 px que a loja pede está em `loja/icone_512.png`, desenhado com as mesmas camadas do ícone adaptativo (`res/drawable/ic_launcher_*.xml`); as capturas de tela atuais ficam na branch `capturas-de-tela`, geradas pelo workflow `capturas.yml`.
6. Defina a versão (versãoCode e versionName já atualizadas) e envie para revisão.
7. Após aprovação, o app estará disponível na Play Store.

## Compilação e Lançamento
1. Clone o repositório ou abra o projeto (diretório raiz do gradle).
2. Utilize o Android Studio para abrir o projeto.
3. Para compilar Release na Play Store, garanta as configurações de *Keystore* em seu `build.gradle` (Build > Generate Signed Bundle / APK).

AgroInteligência © 2026. Todos os direitos reservados.

## Arquivos de manutenção

Os scripts `patch_offline_flag.py`, `patch_system_bars.py` e `patch_theme.py`,
nesta pasta, e os de `ferramentas/` são edições pontuais em `MainActivity.kt` que
já foram aplicadas; não fazem parte da compilação e não devem ser rodados de
novo. Os três `patch_*.py` ficam aqui, e não em `ferramentas/`, porque constam
da tabela de hashes do depósito no INPI. O que cada um fez está em
[`ferramentas/README.md`](ferramentas/README.md).
