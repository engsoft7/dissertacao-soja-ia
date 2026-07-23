# Documentação para Registro de Programa de Computador — INPI

> Este documento contém as informações necessárias para o preenchimento do
> formulário de registro de programa de computador no Instituto Nacional da
> Propriedade Industrial (INPI), conforme a Instrução Normativa nº 199/2024.

---

## 1. Dados do Programa

| Campo | Valor |
|---|---|
| **Título** | AgroInteligência — Sistema Inteligente de Predição de Rendimento de Soja |
| **Data de criação** | 09/07/2026 |
| **Data de publicação** | 09/07/2026 |
| **País de origem** | Brasil |
| **Tipo de programa** | Aplicativo / Sistema de Informação |

---

## 2. Dados do(s) Autor(es) / Titular(es)

| Campo | Valor |
|---|---|
| **Nome completo** | Maycon Lima dos Santos |
| **Nacionalidade** | Brasileiro |
| **CPF** | *(preencher)* |
| **Endereço** | *(preencher)* |
| **E-mail** | *(preencher)* |

> **Nota:** Se o programa foi desenvolvido no âmbito da UFPA, verificar se há
> cláusula de cessão de direitos na política de propriedade intelectual da
> universidade. Nesse caso, a UFPA pode figurar como cotitular.

---

## 3. Linguagens de Programação

- Python 3.10+
- Kotlin (Android / Jetpack Compose)
- SQL (consultas via API SIDRA/IBGE)
- HTML/CSS (interface Streamlit)
- JavaScript (integração Google Earth Engine)

---

## 4. Campo de Aplicação (Tabela INPI)

| Código | Descrição |
|---|---|
| AG-01 | Agricultura |
| ED-04 | Inteligência Artificial / Aprendizado de Máquina |
| IN-06 | Processamento de dados / Banco de dados |

---

## 5. Descrição Resumida do Programa (Memorial Descritivo)

O sistema **AgroInteligência** é uma plataforma inteligente para estimativa de
rendimento da soja em municípios do estado do Pará, integrando dados de
sensoriamento remoto (MODIS, CHIRPS, ERA5-Land), máscara de uso do solo
(MapBiomas) e registros oficiais do IBGE (PAM). O sistema possui três módulos
principais:

### 5.1 Módulo de Aprendizado de Máquina (Backend)
- Núcleo preditivo baseado em modelos MLP (Multi-Layer Perceptron) e XGBoost.
- Treinamento com validação *leave-one-year-out* para evitar vazamento temporal.
- Decomposição produtividade = tendência tecnológica + anomalia climática.
- API REST (FastAPI) hospedada na nuvem (Render) para consumo por clientes.
- Endpoints: previsão por município, simulação climática What-If, KPIs econômicos.

### 5.2 Painel Web Interativo (Streamlit)
- Dashboard publicado em https://soja-para.streamlit.app.
- Visualizações interativas: mapa georreferenciado com círculos proporcionais,
  gráficos de série temporal, tabelas de comparação de modelos.
- Simulador climático: permite ajustar precipitação e temperatura para projetar
  impactos no rendimento.
- Análise financeira: cálculo de receita, lucro líquido e ROI por hectare.

### 5.3 Aplicativo Android Nativo (Kotlin / Jetpack Compose)
- Interface mobile com design premium (dark mode, Material 3).
- Consumo da API via Retrofit2.
- Funcionalidades: resumo agronômico, simulador climático, viabilidade financeira,
  histórico completo e seção de metodologia.
- Versão: 1.0.2 (versionCode 3), compatível com Android 8.0+ (API 26).
- Pronto para publicação na Google Play Store.

### 5.4 Automação (GitHub Actions)
- Atualização mensal automática da base de dados via API SIDRA/IBGE.
- Coleta automatizada de variáveis ambientais no Google Earth Engine.
- Pipeline CI/CD com pull requests automáticos para revisões e safras novas.

---

## 6. Funcionalidades Principais

1. Previsão de rendimento de soja (kg/ha e sc/ha) por município.
2. Projeção para até 3 safras futuras.
3. Simulação climática interativa (What-If: precipitação e temperatura).
4. Análise de viabilidade financeira (receita, custo, lucro, ROI, ponto de equilíbrio).
5. Mapa georreferenciado com rendimento e área plantada.
6. Atualização automática de dados via integração IBGE + Earth Engine.
7. Acesso multiplataforma: web (Streamlit), mobile (Android) e API REST.

---

## 7. Fontes de Dados Utilizadas

| Fonte | Uso | Licença |
|---|---|---|
| IBGE / PAM (SIDRA, tabela 5457) | Produtividade municipal | Dados públicos |
| MODIS MOD13Q1 | NDVI, EVI | Aberto (NASA/GEE) |
| CHIRPS | Precipitação | Aberto (GEE) |
| ERA5-Land | Temperatura, radiação, ETP | Aberto (ECMWF/GEE) |
| MapBiomas Coleção 10.1 | Máscara de soja e área | Aberto (GEE) |

---

## 8. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────┐
│                   FONTES DE DADOS                   │
│  IBGE/SIDRA  │  MODIS  │  CHIRPS  │  ERA5  │  MB   │
└──────────┬──────────────────────────────────────────┘
           │
     ┌─────▼─────┐
     │  COLETA    │  (Google Earth Engine + SIDRA API)
     │  AUTOMAÇÃO │  (GitHub Actions)
     └─────┬─────┘
           │
     ┌─────▼──────────────┐
     │  MODELO ML         │
     │  (MLP / XGBoost)   │
     │  model.py          │
     └─────┬──────────────┘
           │
     ┌─────▼──────────────┐
     │  API REST           │
     │  (FastAPI / Render) │
     │  api.py             │
     └──┬──────────────┬───┘
        │              │
  ┌─────▼─────┐  ┌─────▼──────────┐
  │  WEB       │  │  ANDROID        │
  │  Streamlit │  │  Kotlin/Compose │
  │  app.py    │  │  MainActivity   │
  └────────────┘  └─────────────────┘
```

---

## 9. Código-Fonte (Resumo Hash)

Para o registro no INPI é necessário o **hash do código-fonte** (resumo
criptográfico). Execute o comando abaixo na raiz do repositório para gerar:

```bash
# Gerar hash SHA-256 de todos os arquivos fonte
find . \( -name '*.py' -o -name '*.kt' -o -name '*.kts' \) \
  -not -path './.git/*' -not -path '*/build/*' \
  -not -path '*__pycache__*' -not -path '*/.gradle/*' \
  | sort | xargs sha256sum | sha256sum
```

**Hash gerado em 23/07/2026:**
```
2fca0acd8026bef2810b72f825943ebcca4cc9e89e2659a79964f3e02226deec
```

---

## 10. Licença de Uso

O software está atualmente publicado sob **Licença MIT** (permissiva).

> **Atenção:** Se pretende comercializar o software no futuro, considere alterar
> a licença antes do registro. A licença MIT permite que terceiros usem, modifiquem
> e redistribuam o código livremente. Para proteção comercial, avalie licenças
> como Apache 2.0, BSL ou proprietária.

---

## 11. Checklist para Registro no INPI (e-Software)

- [ ] Criar conta no portal [e-Software do INPI](https://gru.inpi.gov.br/pePI/servlet/ProgramaServletController)
- [ ] Pagar a GRU (taxa de registro — ~R$185,00 para pessoa física)
- [ ] Preencher formulário com os dados acima
- [ ] Gerar o hash SHA-256 do código-fonte (comando da seção 9)
- [ ] Anexar listagem parcial do código-fonte (primeiras 10 e últimas 10 páginas ou trechos representativos)
- [ ] Anexar o memorial descritivo (seção 5 deste documento)
- [ ] Enviar e aguardar o certificado de registro (~10 dias úteis)

---

## 12. Referências

- **Dissertação:** SANTOS, M. L. dos. *Aplicação da Inteligência Artificial na
  previsão da produtividade da soja*. 2026. Dissertação (PPCA/UFPA), Tucuruí.
- **Repositório:** https://github.com/engsoft7/dissertacao-soja-ia
- **DOI:** 10.5281/zenodo.21286115
- **Painel Web:** https://soja-para.streamlit.app
- **API Render:** https://agrointeligencia-api.onrender.com
