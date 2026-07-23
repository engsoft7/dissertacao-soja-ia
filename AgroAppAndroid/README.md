# AgroInteligência

Aplicativo Android focado em Inteligência Artificial para estimar o rendimento da soja através de dados satelitais e climáticos. Integrado com backend local e Cloud (Render) para simulação e resultados otimizados.

## Funcionalidades
- **Resumo Agronômico:** Visualize as expectativas de rendimento por hectare e estimativas de performance (em sacas) para o município selecionado.
- **Simulador Climático:** Altere fatores de temperatura e precipitação para projetar impactos diretos no seu rendimento da safra.
- **Viabilidade Financeira:** Projeções financeiras como margem de lucro por hectare e ROI com base em cotações e custos de produção.
- **Integração Real-Time:** Conexão direta com modelo preditivo em FastAPI hospedado no Render, com dados atualizados pelas fontes MapBiomas, CHIRPS e ERA5-Land.

## Requisitos
- Android 8.0 (API 26) ou superior.
- Conexão de Internet.

## Publicação na Play Store
1. No Android Studio, vá em **Build > Generate Signed Bundle / APK**.
2. Crie ou selecione um **Keystore** com senha segura.
3. Gere um **Android App Bundle (AAB)** para upload.
4. Acesse o **Google Play Console**, crie uma nova aplicação ou selecione a existente.
5. Faça upload do AAB, preencha as informações de listagem (descrição, screenshots, classificação indicativa, política de privacidade, etc.).
6. Defina a versão (versãoCode e versionName já atualizadas) e envie para revisão.
7. Após aprovação, o app estará disponível na Play Store.

## Compilação e Lançamento
1. Clone o repositório ou abra o projeto (diretório raiz do gradle).
2. Utilize o Android Studio para abrir o projeto.
3. Para compilar Release na Play Store, garanta as configurações de *Keystore* em seu `build.gradle` (Build > Generate Signed Bundle / APK).

AgroInteligência © 2026. Todos os direitos reservados.
