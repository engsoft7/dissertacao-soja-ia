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

## Compilação e Lançamento
1. Clone o repositório ou abra o projeto (diretório raiz do gradle).
2. Utilize o Android Studio para abrir o projeto.
3. Para compilar Release na Play Store, garanta as configurações de *Keystore* em seu `build.gradle` (Build > Generate Signed Bundle / APK).

AgroInteligência © 2026. Todos os direitos reservados.
