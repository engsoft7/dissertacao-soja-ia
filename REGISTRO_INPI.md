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
| **CPF** | *-* |
| **Endereço** | *-* |
| **E-mail** | *-* |

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
(MapBiomas) e registros oficiais do IBGE (PAM). O sistema possui quatro módulos
principais:

### 5.1 Módulo de Aprendizado de Máquina (Backend)
- Núcleo preditivo baseado em modelo Random Forest (sklearn), com baseline
  de referência (média histórica + tendência tecnológica) e correção climática
  aprendida sobre o resíduo.
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
- Versão: 2.1.1 (versionCode 8), compatível com Android 8.0+ (API 26).
- Pronto para publicação na Google Play Store.

### 5.4 Automação (GitHub Actions)
- Atualização mensal automática da base de dados via API SIDRA/IBGE.
- Coleta automatizada de variáveis ambientais no Google Earth Engine.
- Pipeline CI/CD com pull requests automáticos para revisões e safras novas.

---

## 6. Funcionalidades Principais

1. **Previsão de Produtividade (Machine Learning):** Treinamento e inferência automática de algoritmos de I.A. (Random Forest) para simular o rendimento (kg/ha e scs/ha) baseado em tendências históricas.
2. **Dashboard Web B2B (Módulo SaaS - Single Page Application):** Sistema executivo moderno projetado sob arquitetura modular, comportando mapas de calor regionais Folium (Inteligência Territorial), laboratórios Climáticos "What-if" e módulos matemáticos interativos gerados por Plotly Analytics para renderização de marcos históricos paramétricos (El Niño/La Niña).
3. **Módulo de Síntese em Linguagem Natural (IA Heurística):** Agente preditivo (Agente de Síntese BIA) embutido nativamente no Painel Financeiro que reescreve a lógica matemática e projeções logarítmicas de fluxo hídrico num linguajar executivo humano e avaliativo (ex: sentenças de alerta "Alta Viabilidade", "Alerta" ou "Risco Crítico").
4. **Captura de cotação e referências econômicas:** Consulta ao contrato futuro de soja em Chicago (CBOT `ZS=F`) e ao câmbio (`BRL=X`) pelo Yahoo Finance, convertidos para reais por saca de 60 kg, com valor de reserva fixo quando a consulta falha. O custo operacional e o Valor da Terra Nua não são coletados: são uma tabela de referência estática de sete municípios, embutida em `software/api_backend/financas.py` e editável na interface. *(Em versões posteriores ao commit registrado, a cotação passou a priorizar o preço físico em Paranaguá com o CBOT como reserva; o custo passou a vir do levantamento da CONAB para Pedro Afonso (TO) e o Valor da Terra Nua da tabela da Receita Federal de 2026.)*
5. **Plataforma SDK Integrada:** Aplicação nativa programada em Kotlin/Android (UI baseada em Jetpack Compose) espelhando conectividade remota através de uma API Serverless arquitetada em FastAPI (Render).
6. **Automação Contínua e Integração:** Rotinas macro estruturadas em nuvem (via `.github/workflows/atualiza-dados.yml` e Streamlit Cloud Instances) garantindo paralelismo autônomo e manutenção perpétua da aplicação de ponta a ponta.

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

## 9. Código-Fonte — Resumo Criptográfico (Hash) e Prova de Integridade

### 9.1 Hash Global do Código-Fonte

Os resumos criptográficos SHA-256 abaixo abrangem **todos os arquivos-fonte**
(Python `.py`, Kotlin `.kt` e Gradle `.kts`) do repositório — 45 arquivos e
5.505 linhas no commit registrado no INPI. O hash é gerado de forma
determinística: a lista de arquivos é ordenada alfabeticamente, cada arquivo
recebe seu SHA-256 individual e, em seguida, o conjunto de hashes é resumido
em um único hash final (hash-of-hashes).

```bash
# Comando para reproduzir o hash — executar na raiz do repositório.
# LC_ALL=C fixa a ordenação, que de outro modo varia com o idioma do sistema.
LC_ALL=C find . \( -name '*.py' -o -name '*.kt' -o -name '*.kts' \) \
  -not -path './.git/*' -not -path '*/build/*' \
  -not -path '*__pycache__*' -not -path '*/.gradle/*' \
  | LC_ALL=C sort | xargs sha256sum | sha256sum
```

Para conferir o estado exato de um commit ou versão, sem alterar a cópia de
trabalho:

```bash
git worktree add --detach /tmp/conferencia 7b8375df   # ou: v2.3.3
cd /tmp/conferencia && <comando acima>
```

**Hashes globais verificados:**

| Estado | Arquivos | Linhas | SHA-256 do conjunto |
|---|---|---|---|
| Commit-âncora `7b8375df` (19/08/2026) — código depositado no INPI | 45 | 5.505 | `5a93dfca9511fcab534c76da4618e670e5c6ed6d33d48ac2a557963a5ef9f11d` |
| Tag `v2.3.0` (30/08/2026) | 47 | 6.822 | `47f50a1e28486d618d8ab92e0507d984a26c0138bc863ce2c0c31cd62884c775` |
| Tag `v2.3.1` (31/08/2026) | 47 | 6.927 | `dd2219ca6885ae934dc31fc3bc44834a2916a372f63651af1214bea7258d5ae2` |
| Tag `v2.3.2` (03/09/2026) | 49 | 7.357 | `796a300e962b1803056e3229c2db21514bc08a8d46da4d122d4133269fd77d43` |
| Tag `v2.3.3` (04/09/2026) | 52 | 8.956 | `dd1b118301cf246b3a7a6a3d53e19f9fc0b992607edd58ece2901aa14873db77` |
| Tag `v2.3.4` (04/09/2026) | 53 | 9.234 | `890a97644fefdeddc0321c7fd8e927c9deb2572e37a2fbecc215c66f1026d448` |
| Tag `v2.3.5` (04/09/2026) | 54 | 10.072 | `acf5c75d0d9c53cfc86c486e40eeea356af4eabf2096b1b7644b5249de600450` |
| Tag `v2.3.6` (04/09/2026) | 55 | 10.252 | `d6c87068c6e4fb9bbca849f63541d2f6abb648ea8cbb75db66bfaf15677de7a5` |
| Tag `v2.3.7` (05/09/2026) — versão da defesa | 57 | 10.711 | `0a2aaf79c45e875bfb6d89714a74a034e4d8ef5739bf6fd7e1ff7fa31073cd7a` |
| Commit `b0f3628` (05/09/2026) — geradores do artigo submetido | 60 | 11.680 | `506baabfca171e40cc5d968d0ca47a7aff1877938d92f532376d67d7c1429a83` |

A última linha não é uma tag: registra o estado do `main` depois que os três
geradores do manuscrito submetido à CEA entraram em `pesquisa/05_artigo/`. Ela
continua valendo para o commit que a acrescenta, porque o conjunto resumido
cobre apenas `.py`, `.kt` e `.kts` — alterar este `.md` não muda o hash. É esse
o valor que a próxima tag levará, se nenhum arquivo-fonte for tocado até lá.

Os nove foram recalculados a partir de cópias limpas dos respectivos commits e
conferem em execuções repetidas. A tag da defesa é a `v2.3.7`, e é do Release
dela que sai o APK distribuído (`versionCode` 13, `versionName` 2.1.6,
SHA-256 `5ee2ea9697b092c9b27fe76f3c1533eaf7aabb79e68c7b1d4700ced34bd18a21`).
Esse binário não difere em comportamento do publicado na `v2.3.5`: nem a
`v2.3.6` nem a `v2.3.7` alteram código do aplicativo — as duas mexem apenas na
pesquisa, na documentação e nos metadados de citação. As anteriores ficam
registradas pelo que as separa:

- a `v2.3.0` é anterior às correções do simulador financeiro e do ranking de
  municípios;
- a `v2.3.1` ainda traz, na tela "Sobre" do aplicativo, um coeficiente de
  determinação de 0,963 e uma variação de 12,4% escritos diretamente no código,
  que não correspondem à validação — os valores da Tabela 6 são R² de 0,216 e
  erro relativo de 13,9%, e é o que a `v2.3.2` já exibe;
- a `v2.3.2` corrige a tela "Sobre", mas a **API ainda serve a cotação de
  Chicago no campo do preço recebido pelo produtor**: o painel usava o preço de
  porteira da CONAB e o aplicativo, a cotação de bolsa convertida, de modo que
  as duas telas do mesmo produto exibiam margens diferentes para o mesmo
  município. A `v2.3.3` corrige isso na origem, prende o simulador climático à
  faixa em que o modelo foi ajustado, remove a camada de mapa de terceiro, e
  passa a ler preço e custo do levantamento da CONAB versionado em
  `pesquisa/dados/conab/levantamento_atual.json`, com a praça, a data e a
  posição do preço na série declaradas em tela. O painel e o aplicativo também
  calculam, a cada leitura, a idade do levantamento em uso, e avisam quando ele
  passa da cadência de publicação da CONAB — de modo que o produto deixa de
  poder exibir um preço antigo como se fosse o corrente;
- a `v2.3.3` avisa que o preço envelheceu, mas ainda abre com o padrão da CONAB
  como se um levantamento bimestral pudesse acompanhar um preço diário. A
  `v2.3.4` inverte isso: o aplicativo guarda o preço informado pelo produtor,
  com a data, e passa a abrir com ele; o padrão vira ponto de partida; e a API
  serve o preço físico de Paranaguá, relido de hora em hora, como a única
  referência diária do produto.
- a `v2.3.5` prometia, no cabeçalho de `01_compara_mascara_controlada.py`, um
  `02_desempenho_base_completa.py` que não existia: os números da Tabela 6
  viviam só em `resultados_busca_aninhada.json`, sem script que os regerasse. A
  `v2.3.6` acrescenta esse script e registra o que dele se reproduz — modelo de
  referência, MLP, SVR e Random Forest saem idênticos; o XGBoost, único cujo
  treino não vem do scikit-learn, dá R² 0,148 sob `xgboost` 3.2.0 contra os
  0,123 publicados, por diferença de versão da biblioteca. Não altera código do
  aplicativo, e por isso o APK distribuído continua sendo o da `v2.3.5`.

- a `v2.3.6` foi etiquetada antes de a base nacional entrar no repositório, de
  modo que não contém `pam_soja_municipios.csv`, `repeticao_27_estados.json` nem
  os scripts que os produzem e conferem. A `v2.3.7` é a primeira que arquiva a
  medida de repetição nas 27 unidades da federação e a conferência das
  referências na Crossref, e é dela que sai o depósito citado como referência de
  dados do artigo submetido.

A subseção 4.9 da dissertação, que afirma serem os mesmos os números do produto
e os da Tabela 6, vale da `v2.3.2` em diante.

> **Sobre o agregado publicado em 19/08/2026.** A versão anterior desta seção
> trazia `7eca3e90aadcd5d0eaa765b92a8ad7e55083f90846a78fdc1854525fffa94e6b`
> como hash global. Esse valor **não se regenera** pelo comando acima no
> commit-âncora, nem por variações do procedimento (ordenação por outros
> locales, resumo só dos dígitos, dígitos concatenados, conteúdo concatenado,
> caminhos sem o prefixo `./`). A contagem de arquivos e de linhas declarada
> na época — 45 arquivos e 5.505 linhas — confere exatamente, o que indica
> divergência na etapa de agregação, e não no conjunto de arquivos. A tabela
> da seção 9.3 foi reconferida arquivo a arquivo contra o commit-âncora:
> **os 45 hashes individuais conferem, nenhum difere**. A prova de integridade
> do código depositado permanece, portanto, sustentada pelos hashes
> individuais e pelo SHA-1 do commit; o agregado acima substitui o anterior
> por ser reproduzível.

> **Hashes anteriores:**
> - 23/07/2026: `2fca0acd8026bef2810b72f825943ebcca4cc9e89e2659a79964f3e02226deec`
> - 19/08/2026 (pré-auditoria): `1b5773b994ccd6f147e40271aa3a17557f50849b1da190a4f7ded66d0b7e1095`
> - 19/08/2026 (publicado, não reproduzível): `7eca3e90aadcd5d0eaa765b92a8ad7e55083f90846a78fdc1854525fffa94e6b`

---

### 9.2 Âncora no Controle de Versão (Git)

O primeiro hash da tabela acima, `5a93dfca…`, corresponde ao estado exato
do repositório no commit:

| Campo | Valor |
|---|---|
| **Commit SHA-1 (Git)** | `7b8375df14ca031355c4b9c87fd42942bffec6ae` |
| **Data do commit** | 19/08/2026 — 15:41:31 (UTC-3) |
| **Mensagem** | docs: corrige menções a XGBoost para Random Forest (modelo real de produção) |
| **Repositório** | https://github.com/engsoft7/dissertacao-soja-ia |
| **Branch** | `main` |
| **DOI (Zenodo)** | [10.5281/zenodo.21286115](https://doi.org/10.5281/zenodo.21286115) |

> **Por que isso constitui prova?** O Git é um sistema de controle de versão
> baseado em hashes criptográficos (SHA-1). Cada commit é imutável: qualquer
> alteração retroativa mudaria o hash do commit e de todos os subsequentes. O
> commit acima está publicado no GitHub (servidor de terceiros) e arquivado no
> Zenodo (CERN), que atribuiu um DOI permanente. Essas três camadas — hash
> local, GitHub e Zenodo — garantem que o código-fonte existia nesta forma
> exata na data indicada.

---

### 9.3 Hash Individual por Arquivo (45 arquivos)

<details>
<summary>Clique para expandir a tabela completa de hashes SHA-256</summary>

| # | Arquivo | SHA-256 |
|---|---|---|
| 1 | `patch_esq.py` | `27e78e93813b68704d60a5a6c42642eeaed37a66619543962433d092facf4ad4` |
| 2 | `patch_sidebar.py` | `ad751c1bca554a5af36171216752864d1fea29f96e63074760b764f7e5d88a5e` |
| 3 | `patch_tabs.py` | `6a2bed084de21d6326d304f5dae11e3a77daf5b7914b3198ae4ead28f1d181cc` |
| 4 | `pesquisa/01_coleta_dados/01_coleta_gee_sem_mascara.py` | `723a8c6454ea69f3a88f21451b0e73fc3b6899f422b4a3af5585bfc42fdf79b2` |
| 5 | `pesquisa/01_coleta_dados/02_coleta_gee_com_mascara_mapbiomas.py` | `ad893ae1422f30cd3a2370fc2926c0de5304a7f529dd9fe7f6bbbd11089a7c1a` |
| 6 | `pesquisa/02_revisao_sistematica/01_busca_bases_abertas.py` | `7451324b2ffa73b9079173416a28867eb9489b00eea490633a89a53129eb04ef` |
| 7 | `pesquisa/02_revisao_sistematica/02_recupera_autoria_crossref.py` | `d165caa42d42e94e765394a38c9c7c788e5aeccb442be1d418387ea5c20d5209` |
| 8 | `pesquisa/03_analise_nacional/00_baixa_dados.py` | `5358b6944154fde93b9c14b1eb1bfdccb08770ea847d713a21c45ea87cbd8690` |
| 9 | `pesquisa/03_analise_nacional/01_treina_modelos.py` | `875ed72a7986a63912055575c8c78718e8b07202c26a7f052a2aceff85e23910` |
| 10 | `pesquisa/03_analise_nacional/02_gera_figuras.py` | `b9698b6ada314e0063c2da5d741218db53e5b22f2eed39eaf989e6f59c79d328` |
| 11 | `pesquisa/04_analise_para/01_compara_mascara_e_baseline.py` | `98f77030c53cd76b7702c0e37c46aa616b75f60c602044c13cdc62a1ac5e0cd6` |
| 12 | `pesquisa/04_analise_para/02_gera_figuras.py` | `06e9e81d3a194afafb477d754066a90b7671708c9c6cedf08243d22853bdb7de` |
| 13 | `pesquisa/05_artigo/gera_figuras_artigo.py` | `9a3a7e62ebd7f238d27220b3820880f64756bef43009ad6e52ded945c1351893` |
| 14 | `software/api_backend/api.py` | `4ae9033d6bb2debffb3938d6a6fdc87a5a91dafc49ee1dbf9cff2119d48ac52e` |
| 15 | `software/api_backend/financas.py` | `b5169387c513b55845d01ed5b3da6ee1c972b6ed3599963d682d8ca2b8c4dfde` |
| 16 | `software/api_backend/test_logic.py` | `a4a94290f45df9095ccf3597c9ac5be3cd080349c1defac76eaf78da1ca5712b` |
| 17 | `software/api_backend/test_mun.py` | `7c4fc257ef92c2aed0f688a5435a1cafa512c8796bdf82b4807a647919e32ed7` |
| 18 | `software/aplicativo_mobile/app/build.gradle.kts` | `501be524fc6f30860b48343d7ca9e2065d60d5a6d6073cb6d132cb9226a5e06b` |
| 19 | `software/aplicativo_mobile/app/…/ApiService.kt` | `3aae69fd4fe90d3c5a9be25153bc8c140254dac77e2a5835a6af6656a4e58ee2` |
| 20 | `software/aplicativo_mobile/app/…/MainActivity.kt` | `c951ad5af2c8e785b966550e203a4fa2a127a08252483322728d356376b76ba7` |
| 21 | `software/aplicativo_mobile/build.gradle.kts` | `e5531f277ccc9d892e70e9a6ff7c49b951d8e0d0789b0d47e01412d61df6575e` |
| 22 | `software/aplicativo_mobile/patch_offline_flag.py` | `c0d4bd0251535b3d6470fb7945c09df039acd41511090c25b84ea8d70bbc7418` |
| 23 | `software/aplicativo_mobile/patch_system_bars.py` | `918dc7453fc6181b73a49c95cd32e5eb506b08e6823e9d1a21b2b719e27c5424` |
| 24 | `software/aplicativo_mobile/patch_theme.py` | `b2ecf342561c70057d82052d9c09aff9b763c3caf0d102a399ea81a62c55bef1` |
| 25 | `software/aplicativo_mobile/settings.gradle.kts` | `001ef8debc5d6891edf415bb0a929eaf8403791aa835166159afbbd05fd6aac5` |
| 26 | `software/automacao_github/atualiza_enso.py` | `ffbeb0347826170d19c4f961801d74f6e4d2ae09cdcfa45a99415f5a7dd62292` |
| 27 | `software/automacao_github/atualiza_pam.py` | `ac456c00b2a69787b084805949f5322a35728117a8e9ee97a878dd4141e759f9` |
| 28 | `software/automacao_github/bot_agente_vtn.py` | `3022b14b70538c200eac2724f7264b4a65bdff5ad2ce70248abbd93aa5d15d91` |
| 29 | `software/automacao_github/coleta_gee_safra.py` | `4b97575764e524ded29ae243588795e5d0b7f694b43c0f64a1b29ccfd4f6d4d5` |
| 30 | `software/automacao_github/gera_geo_para.py` | `2312453c562c678562b011f25eec477c71528fc08b488cfa7be16a7f90cd9e78` |
| 31 | `software/automacao_github/gera_metricas.py` | `248bf2e63b914d5c929b146cd047f7ac226fdff27de1c0a1756904d57826475f` |
| 32 | `software/automacao_github/gera_municipios.py` | `fd32f02773c3233d27495b5d9cfdff73dfbdd0e6bb37a57a0d53467c6f89e23d` |
| 33 | `software/automacao_github/gera_rios_para.py` | `841ee7066f723e177809a7117857b0f02e6b6912dabaa863c4909d2189ad9330` |
| 34 | `software/automacao_github/test_atualiza_pam_paths.py` | `4e6d1ef84e95529ff8ae8f7e9333f77d38654c310b3c1d095b2f64f417babb7d` |
| 35 | `software/dashboard_web/app.py` | `6df428294dce11cd64920315bf1298cad2f6ee4ae1efc03a87e9b9994fa9859d` |
| 36 | `software/dashboard_web/components/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 37 | `software/dashboard_web/data/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 38 | `software/dashboard_web/data/loaders.py` | `ca709168e26548b5098207e93f9ca3461578010a5133baca5d7a9b62a5d5a3bc` |
| 39 | `software/dashboard_web/model.py` | `47cbfafbf9e7cdd70881d00643ce3212ac8bffbbccf33877f6e509323e1843ec` |
| 40 | `software/dashboard_web/services/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 41 | `software/dashboard_web/test_meta.py` | `cae35a32a2e5b574a6edf88d9d4f13c7c1f1b9f774de687c3b85de1bbb9b69d7` |
| 42 | `software/dashboard_web/ui/charts.py` | `6848fb48f2116ae24479189015aa130ca5dcfb5bb052684ad3348a84a02315c2` |
| 43 | `software/dashboard_web/ui/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 44 | `software/dashboard_web/ui/themes.py` | `ceb3b36228bf56f4d93ce82cdff57b0f8fdf06f94611ee3055ec0bce644a165f` |
| 45 | `software/dashboard_web/ui/utils.py` | `e63f31ec71e57bdfdf11c0a5908466554e894fc2d9c4a6b0342af26e28a1685e` |

</details>

---

### 9.4 Como Verificar (Prova Independente)

Qualquer perito ou examinador pode reproduzir e confirmar o hash seguindo
estes passos:

1. **Clonar o repositório no commit exato:**
   ```bash
   git clone https://github.com/engsoft7/dissertacao-soja-ia.git
   cd dissertacao-soja-ia
   git checkout 7b8375df14ca031355c4b9c87fd42942bffec6ae
   ```

2. **Executar o comando de hash:**
   ```bash
   find . \( -name '*.py' -o -name '*.kt' -o -name '*.kts' \) \
     -not -path './.git/*' -not -path '*/build/*' \
     -not -path '*__pycache__*' -not -path '*/.gradle/*' \
     | sort | xargs sha256sum | sha256sum
   ```

3. **Resultado esperado:**
   ```
   7eca3e90aadcd5d0eaa765b92a8ad7e55083f90846a78fdc1854525fffa94e6b  -
   ```

4. **Verificação cruzada:** O mesmo código está arquivado permanentemente no
   Zenodo (CERN) sob DOI [10.5281/zenodo.21286115](https://doi.org/10.5281/zenodo.21286115),
   servindo como carimbo de tempo de terceiro confiável.

> **Nota:** O algoritmo SHA-256 é padronizado pelo NIST (FIPS 180-4) e aceito
> pelo INPI como resumo criptográfico para registro de programa de computador.

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
  previsão da produtividade da soja*. 2026. Dissertação (Em andamento) (PPCA/UFPA), Tucuruí.
- **Repositório:** https://github.com/engsoft7/dissertacao-soja-ia
- **DOI (conceito, resolve para a versão mais recente):** 10.5281/zenodo.21285918
- **DOI da versão da defesa (`v2.3.7`):** 10.5281/zenodo.22343315
- **Painel Web:** https://soja-para.streamlit.app
- **API Render:** https://agrointeligencia-api.onrender.com
