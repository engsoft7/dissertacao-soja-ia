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
  aprendida sobre o resíduo. *(Em versões posteriores ao commit registrado, a
  partir da `v2.4.1`, a correção climática voltou a ser aprendida por um
  Perceptron Multicamadas (`MLPRegressor`), o modelo que a Tabela 6 da
  dissertação documenta para a base completa do Pará. O Random Forest entrara
  no commit `e5e3d8e`, de 26/07/2026, mas as métricas exibidas continuaram
  sendo as do MLP; a seção 9.1 registra o defeito e a correção.)*
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
  *(A partir da `v2.4.4`, a rotina atualiza só a base do produto,
  `soja_para_painel.csv`; a base da dissertação fica congelada. A mesma rotina
  ganha a coleta de dados para a previsão de safras, disparada manualmente.)*

---

## 6. Funcionalidades Principais

1. **Previsão de Produtividade (Machine Learning):** Treinamento e inferência automática de algoritmos de I.A. (Random Forest) para simular o rendimento (kg/ha e scs/ha) baseado em tendências históricas. *(A partir da `v2.4.1`, o algoritmo é o Perceptron Multicamadas, conforme a nota da seção 5.1.)*
2. **Dashboard Web B2B (Módulo SaaS - Single Page Application):** Sistema executivo moderno projetado sob arquitetura modular, comportando mapas de calor regionais Folium (Inteligência Territorial), laboratórios Climáticos "What-if" e módulos matemáticos interativos gerados por Plotly Analytics para renderização de marcos históricos paramétricos (El Niño/La Niña). *(A partir da `v2.4.4`, cada safra é classificada pelo trimestre dezembro-fevereiro, segundo a regra de episódios da NOAA; antes, pelo ano do calendário.)*
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
     │  (MLP)             │
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
| Tag `v2.3.8` (05/09/2026) — geradores do artigo submetido | 60 | 11.680 | `506baabfca171e40cc5d968d0ca47a7aff1877938d92f532376d67d7c1429a83` |
| Tag `v2.3.9` (14/09/2026) — análises da revisão | 64 | 12.792 | `b9a4a09bca08161efdef3e8f746ff84c1d314c79a19e10335cc5a005a3e5305d` |
| Tag `v2.4.0` (14/09/2026) — conferência de referências e primeiro teste do aplicativo | 74 | 14.683 | `f5e8d0673c108b8795467b04d7532a0be59dfb6632b6242e70852ce315ae28a6` |
| Tag `v2.4.1` (18/09/2026) — correções do painel web | 77 | 15.288 | `d9f118ead8a19e172f87118c40b76b7378bb7979b9eab9aec400254ef74644a5` |
| Tag `v2.4.2` (18/09/2026) — projeção no painel web | 77 | 15.384 | `7f04fddedf5d63285a1310cca9549e41fea47d646a3a22720e43e7d42f8168bb` |
| Tag `v2.4.3` (22/10/2026) — medição de custo e revisão para os artigos SBC | 79 | 15.815 | `859bcf907bb73422be18952970a0d0ee9d4fdfa1b75c6a5ebcf7da5b91d69a84` |
| Tag `v2.4.4` (22/10/2026) — previsão de safras futuras, safra 2025 no produto e ENSO por safra | 95 | 17.923 | `5ebaa5df49a04f1bf619f9ec6b8aeea04fe418af614b9fbb031c61b05b9d5696` |
| Tag `v2.4.5` (22/10/2026) — métricas de validação do aplicativo servidas pela API | 97 | 18.036 | `f98568169031c82a2dcda524286b0f541f515f5d901fc49deebf94f1c25294da` |
| Tag `v2.4.6` (22/10/2026) — tela Mercado no aplicativo | 99 | 18.438 | `c96b5a6c643a2d15dd8187f7835418ea04bd9672c9856c0f8338e848bfd28444` |
| Tag `v2.4.7` (22/10/2026) — gráficos legíveis, ajustes de interface e capturas de tela do aplicativo; registro automático do DOI | 102 | 18.977 | `270db6e46daf2cef7649057fa45dec3454574eea102087515b54bc4c77839820` |
| Tag `v2.4.8` (22/10/2026) — publicação e registro automáticos da versão | 102 | 19.139 | `0bd893a160fe63bb3a94239551deee7fa5c331c8ea0dfd70df04cb313e680cc7` |
| Tag `v2.4.9` (23/10/2026) — ícone adaptativo do aplicativo (2.2.2) e capturas de tela com dados reais | 104 | 19.317 | `fbbe44202edc5fbb0ca0b92e79c48ff936289f1adc5bec3fd0b7e138da529b2a` |

A `v2.3.8` (DOI 10.5281/zenodo.22348036) acrescenta os três geradores do
manuscrito submetido à CEA em `pesquisa/05_artigo/` — são os primeiros
arquivos-fonte a entrar depois da versão da defesa, e por isso a primeira
mudança de hash desde ela. As correções de identidade do autor que a
acompanham tocam apenas `.cff` e `.md`, que ficam fora do conjunto resumido e
não alteram o valor.

A `v2.3.9` (DOI 10.5281/zenodo.22739059) acrescenta os quatro scripts escritos para responder às objeções da
revisão da Computers and Electronics in Agriculture: o nulo que preserva a
dependência temporal das séries, a verificação de coerência interna entre
rendimento e área plantada, o confronto da repetição com o sinal orbital e o
experimento de injeção controlada. É o depósito que o artigo ressubmetido cita.

A `v2.4.0` acrescenta dez arquivos-fonte à `v2.3.9` e altera outros dez. Entram os
geradores e conferidores que acompanharam a submissão do artigo — a resolução
dos DOIs impressos contra a Crossref, a busca por preprint, a declaração de
conflito de interesses e o resumo gráfico —, o diagnóstico da coleta da CONAB,
que estabeleceu ser a rota automática fechada por autenticação e não por falta
de endereço, a codificação dos 53 estudos da revisão, a conferência dos anos de
publicação desses estudos e das obras clássicas que faltavam citar, e o primeiro
teste de unidade do aplicativo, sobre a função que calcula a margem por hectare.
Entre os arquivos alterados estão `MainActivity.kt`, que passou a guardar o
preço informado pelo produtor em precisão dupla, e `build.gradle.kts`, sem o
qual o aplicativo não compilava a partir de um clone limpo.

O DOI de versão desta etiqueta é 10.5281/zenodo.22755108, atribuído pelo Zenodo
no depósito disparado pela publicação do Release em 14/09/2026. O DOI de
conceito, 10.5281/zenodo.21285918, passa a resolver para ela.

O resumo criptográfico não muda entre o commit `2351dcfd` e a etiqueta: os
arquivos alterados na preparação da `v2.4.0` são `.md` e `.cff`, que ficam fora
do conjunto resumido — o mesmo que já ocorrera na `v2.3.8`.

A `v2.4.1` corrige o painel web e existe por uma razão que vale registrar: a
`v2.4.0` carrega um defeito. Nela, `software/dashboard_web/model.py` prevê com
uma `RandomForestRegressor`, mas `pesquisa/dados/metricas_validacao.json`
guarda as métricas do `MLPRegressor` anterior — o commit `e5e3d8e`, de
26/07/2026, trocou o algoritmo e o arquivo nunca foi regerado. Quem baixar a
`v2.4.0` e executar o painel recebe, nos quatro indicadores do topo, a precisão
de um modelo que não é o que está prevendo. Como o DOI de conceito resolve
sempre para a versão mais recente, corrigir exigia uma etiqueta nova.

O painel volta ao `MLPRegressor`, que é o modelo documentado na Tabela 6 da
dissertação para a base completa do Pará, e as métricas passam a gravar a
identidade de quem as produziu — classe do regressor e hiperparâmetros —, com
um teste que reprova quando as duas deixam de corresponder. Os valores
gravados não mudaram: a validação com o MLP restaurado reproduz o arquivo
dígito a dígito. Entram ainda a correção da barra de ferramentas do Plotly, que
cobria a legenda dos dois gráficos, e um roteiro que abre o painel num
navegador e confere que o mapa desenha, executado no GitHub Actions porque o
Leaflet vem de CDN.

São três arquivos-fonte novos e sete alterados em relação à `v2.4.0`. Dois dos
alterados não são do painel e vêm de antes destas correções: a pizza por
família de técnica da revisão sistemática, em
`pesquisa/02_revisao_sistematica/03_codifica_estudos.py`, e a mesma figura na
medida do slide, em `pesquisa/06_figuras_defesa/gera_figuras_defesa.py`.

O DOI de versão desta etiqueta é 10.5281/zenodo.22833602, atribuído pelo Zenodo
no depósito disparado pela publicação do Release em 18/09/2026. O DOI de
conceito, 10.5281/zenodo.21285918, passa a resolver para ela — e é o que corrige,
para quem cita o conceito, o retrato defeituoso que a `v2.4.0` deixava.

O resumo criptográfico não muda entre o commit `555af62` e a etiqueta: o único
arquivo alterado na preparação da `v2.4.1` é este `REGISTRO_INPI.md`, que fica
fora do conjunto resumido — o mesmo que já ocorrera na `v2.3.8` e na `v2.4.0`.
Conferido depois de etiquetar, sobre uma cópia limpa da `v2.4.1`: o valor
confere.

A `v2.4.2`, etiquetada em 18/09/2026 sobre o commit `b03cee5`, traz duas
melhorias do painel: ele passa a desenhar a projeção das safras seguintes, como
o aplicativo já fazia, e o cartão de projeção declara quanto o modelo acrescenta
à referência, 0,65 kg/ha em média. Os dois arquivos-fonte alterados são
`software/dashboard_web/app.py` e `software/dashboard_web/ui/charts.py`; nenhum
entra. A versão foi publicada sem o commit de preparação que as anteriores
tiveram, e por isso só entra neste registro agora, com o resumo recalculado em
22/10/2026 sobre uma cópia limpa da etiqueta. O DOI de versão desta etiqueta é
10.5281/zenodo.22837962, atribuído pelo Zenodo no depósito disparado pela
publicação do Release em 18/09/2026.

A `v2.4.3` reúne a revisão feita para os dois artigos no modelo da SBC (ERAD e
ERAMIA). São dois arquivos-fonte novos e quatro alterados em relação à
`v2.4.2`.

Os novos são a medição de custo e escalabilidade do estudo nacional,
`pesquisa/03_analise_nacional/10_mede_custo_escalabilidade.py`, que ajusta os
quatro modelos da Tabela 3 em tamanhos crescentes de treino até a base
completa, cada ajuste num processo isolado para medir o pico de memória, e o
teste de acaso com dependência temporal no Pará,
`pesquisa/04_analise_para/08_nulo_com_dependencia_para.py`, que reaproveita as
funções do nulo nacional e acrescenta o IAAFT e o AR(1) à permutação simples.

Entre os alterados, três corrigem a contagem da repetição.
`pesquisa/06_figuras_defesa/gera_figuras_defesa.py` passa a calcular a
repetição por quartil de área com os pares de safras como denominador —
56,8 / 50,0 / 33,0 / 20,2%, em vez de 43,3 / 45,2 / 35,0 / 22,1%, que contavam
como "não repetiu" o primeiro ano de cada município. `05_natureza_da_repeticao.py`
e `06_repeticao_e_sinal_espectral.py`, em `pesquisa/04_analise_para/`, marcam
os dez pares cuja safra anterior presente na base não é a do ano anterior e
informam 147 de 367 ao lado dos 151 de 377. O quarto,
`pesquisa/04_analise_para/02_desempenho_base_completa.py`, muda só a mensagem
impressa quando o XGBoost diverge, que passa a indicar a versão 3.3.0 da
biblioteca como a primeira que reproduz a Tabela 6.

Nenhum código-fonte do aplicativo Android muda nesta versão. Os números da
dissertação nas Tabelas 3, 5 e 6 tampouco: foram reproduzidos sobre ela com
scikit-learn 1.8.0 e XGBoost 3.4.1. O DOI de versão desta etiqueta é
10.5281/zenodo.23560491, atribuído pelo Zenodo no depósito disparado pela
publicação do Release em 22/10/2026. O DOI de conceito, 10.5281/zenodo.21285918,
passa a resolver para ela.

O resumo criptográfico da `v2.4.3` foi calculado sobre o commit `9cf625c` e
conferido sobre o commit de merge `ac47b88`, onde dá o mesmo valor. A preparação
da versão altera apenas este `REGISTRO_INPI.md` e o `CITATION.cff`, que ficam
fora do conjunto resumido, de modo que o valor se mantém na etiqueta. Conferido
depois de etiquetar, sobre uma cópia limpa da `v2.4.3` (commit `e267526`): o
valor confere.

A `v2.4.4` reúne a previsão de safras futuras, a safra 2025 no produto e a
classificação do El Niño e da La Niña por safra. São dezesseis arquivos-fonte
novos e nove alterados em relação à `v2.4.3`.

Quinze dos novos estão em `pesquisa/08_previsao_futura/`. Oito são análises
que avaliam a previsão em janela crescente, treinando só com safras anteriores
à prevista, e confrontam os modelos com o modelo de referência da dissertação;
uma delas confere contra a PAM 2025 a projeção de produção registrada antes de
o IBGE publicá-la. Três são módulos comuns (`comum.py`, `fases.py` e
`conab.py`), e quatro são os coletores de `coleta/`, que o GitHub Actions
executa para baixar a PAM, as séries do Atlântico tropical da NOAA, a série
histórica de safras da CONAB e as séries diárias e de 8 e 16 dias do Earth
Engine. O décimo sexto é o teste da nova classificação climática,
`software/automacao_github/test_atualiza_enso.py`.

Os nove alterados se dividem em três mudanças. A primeira separa a base do
produto da base da dissertação: o painel, a API e a rotina de atualização
(`app.py`, `api.py`, `atualiza_pam.py`, `gera_metricas.py`, `gera_municipios.py`
e `test_atualiza_pam_paths.py`) passam a ler e escrever
`pesquisa/dados/soja_para_painel.csv`, e `soja_para_mascarado_2001_2024.csv`,
que produz as Tabelas 5 e 6, fica congelada. Foi na base do produto que a
rotina incluiu a safra 2025, e as métricas que o painel exibe passaram de
R² 0,216, RMSE 415,6 kg/ha e 415 registros para 0,253, 412,8 kg/ha e 451
registros. A segunda muda a classificação climática (`atualiza_enso.py`,
`app.py`, `charts.py` e `api.py`): cada safra passa a ser classificada pelo
trimestre dezembro-fevereiro, segundo a regra de episódios da NOAA, e não pelo
ano do calendário a partir de uma lista fixa, que marcava como El Niño as safras
2023 e 2026, colhidas antes de os eventos começarem, e omitia episódios oficiais.
O texto do painel que atribuía ao El Niño as maiores quebras do Pará foi
corrigido: quatro das cinco piores safras foram de La Niña. A terceira reúne
correções do painel (`app.py` e `model.py`): a largura dos gráficos na API atual
do Streamlit, o texto da repetição, o rótulo do custo e a documentação do
modelo.

Nenhum código-fonte do aplicativo Android muda nesta versão; o quadro de
validação do aplicativo continua a exibir os números da Tabela 6, escritos no
código, enquanto o painel exibe os da base do produto. Os números da
dissertação nas Tabelas 3, 5 e 6 tampouco mudam, porque as análises novas leem
a base congelada. O DOI de versão desta etiqueta é 10.5281/zenodo.23573276,
atribuído pelo Zenodo no depósito disparado pela publicação do Release em
22/10/2026. O DOI de conceito, 10.5281/zenodo.21285918, passa a resolver para
ela.

O resumo criptográfico da `v2.4.4` foi calculado sobre o commit de merge
`5d63b49`, com o mesmo comando, que reproduz na mesma data o valor registrado
para a `v2.4.3`. A preparação da versão altera apenas este `REGISTRO_INPI.md` e
o `CITATION.cff`, que ficam fora do conjunto resumido, de modo que o valor se
mantém na etiqueta. Conferido depois de etiquetar, sobre uma cópia limpa da
`v2.4.4` (commit `3f3a4ef`): o valor confere.

O APK da `v2.4.4` não foi anexado na publicação: o workflow que assina estava
inativo, sem a chave nos segredos do repositório. A chave anterior foi
substituída por uma nova, gerada em 22/10/2026 e guardada só nos segredos e com
o autor, e o workflow passou a aceitar disparo manual para anexar a um Release
já publicado, sem republicá-lo (o que geraria outro depósito no Zenodo). O APK
e o AAB da `v2.4.4` foram assinados e anexados assim; o certificado da chave
nova tem SHA-256
`EA4236D3B44D59F7D1E970B1D5DE85CABA598DDB38A137EE793533796DD99AC3`. Aparelhos
com o aplicativo assinado pela chave anterior precisam desinstalá-lo antes de
instalar um pacote assinado pela nova.

A `v2.4.5` tira do código do aplicativo as métricas de validação. A tela
"Origem dos Dados & IA" exibia R² 0,216, ± 416 kg/ha e 415 registros escritos
em `MainActivity.kt`, que ficaram para trás quando a safra 2025 entrou na base
do produto. São dois arquivos-fonte novos e quatro alterados em relação à
`v2.4.4`. Os novos são `software/api_backend/validacao.py`, que monta as
métricas a partir de `pesquisa/dados/metricas_validacao.json` (o arquivo que o
painel web exibe e que a rotina de atualização regrava), e o teste dele,
`test_validacao.py`. Os alterados são `api.py`, que passa a enviá-las junto com
a previsão; `ApiService.kt` e `MainActivity.kt`, que passam a exibi-las e, sem
conexão, dizem que estão indisponíveis em vez de mostrar números de outra base;
e `build.gradle.kts`, que leva o aplicativo a `versionCode` 14, `versionName`
2.1.7. O DOI de versão desta etiqueta é 10.5281/zenodo.23574981, atribuído pelo
Zenodo no depósito disparado pela publicação do Release em 22/10/2026; o APK e
o AAB foram assinados e anexados pelo workflow na própria publicação.

O resumo criptográfico da `v2.4.5` foi calculado sobre o commit de merge
`6d4899c`. A preparação da versão altera apenas este `REGISTRO_INPI.md` e o
`CITATION.cff`, que ficam fora do conjunto resumido, de modo que o valor se
mantém na etiqueta. Conferido depois de etiquetar, sobre uma cópia limpa da
`v2.4.5` (commit `cca0215`): o valor confere.

A `v2.4.6` acrescenta ao aplicativo a tela Mercado, com a cotação da soja em
Chicago convertida para reais por saca. São dois arquivos-fonte novos e quatro
alterados em relação à `v2.4.5`. Os novos são
`software/api_backend/mercado.py`, que busca no Yahoo Finance a soja na CBOT
(`ZS=F`) e o dólar (`BRL=X`) e converte cada vela pelo câmbio do seu instante,
com cache de dois minutos, e o teste dele, `test_mercado.py`. Os alterados são
`api.py`, que expõe a cotação em `/api/mercado` junto com o físico do dia e o
preço de porteira da CONAB; `ApiService.kt` e `MainActivity.kt`, que trazem a
aba Mercado, com gráfico de velas de 1 dia a 6 meses; e `build.gradle.kts`, que
leva o aplicativo a `versionCode` 15, `versionName` 2.2.0. O DOI de versão
desta etiqueta é 10.5281/zenodo.23575177, atribuído pelo Zenodo no depósito
disparado pela publicação do Release em 22/10/2026; o APK e o AAB foram
assinados e anexados pelo workflow na própria publicação. A cotação gratuita
chega com atraso de 10 a 15 minutos, e a tela declara isso e que preço de bolsa
não é preço de porteira; cotação em tempo real exigiria licença paga da CME ou
da B3.

O resumo criptográfico da `v2.4.6` foi calculado sobre o commit de merge
`81cbb77`. A preparação da versão altera apenas este `REGISTRO_INPI.md` e o
`CITATION.cff`, de modo que o valor se mantém na etiqueta. Conferido depois de
etiquetar, sobre uma cópia limpa da `v2.4.6` (commit `d8b501c`): o valor
confere.

A `v2.4.7` revisa a interface do aplicativo, que vai a `versionCode` 16,
`versionName` 2.2.1, e automatiza o registro do DOI. São três arquivos-fonte
novos e dois alterados em relação à `v2.4.6`. O primeiro novo é o teste
`software/aplicativo_mobile/app/src/test/java/com/agrointeligencia/app/CapturasDeTelaTest.kt`,
que desenha as telas com dados de exemplo nos temas claro e escuro (Robolectric
e Roborazzi, sem emulador); o workflow `capturas.yml` publica as imagens na
branch `capturas-de-tela` a cada mudança no aplicativo. Os alterados são
`MainActivity.kt` e `build.gradle.kts`. Nos gráficos, o texto passa de pixels
fixos (cerca de 8 sp num celular comum) a sp, as faixas de El Niño e La Niña
perdem o rótulo em cada safra e ganham legenda, o eixo do histórico deixa de
começar em zero, o toque mostra o valor de um ano ou de uma vela, e os
gráficos ganham descrição para leitor de tela. Na interface, o seletor de
município fica só nas telas em que tem efeito, a aba Mercado deixa de depender
da previsão do município, o texto secundário passa a uma cor com contraste
acima de 7:1 e a no mínimo 12 sp, os termos ficam em português e os números
no formato brasileiro em qualquer aparelho.

Os outros dois novos são `software/automacao_github/registra_doi.py` e o teste
dele, `test_registra_doi.py`. Na publicação de cada Release, o workflow
`registra-doi.yml` espera o Zenodo atribuir o DOI de versão, recalcula o resumo
criptográfico sobre uma cópia limpa da etiqueta com o mesmo critério do comando
acima e, se conferir com a linha da tabela, abre um PR que troca o "a
preencher" pelo DOI e registra a conferência; se não conferir, abre uma issue.
O cálculo em Python reproduz os valores registrados das etiquetas `v2.4.5` e
`v2.4.6`.

O resumo criptográfico da `v2.4.7` foi calculado sobre o commit `348fccb`, que
acrescenta o registro automático do DOI à revisão de interface. A preparação da
versão altera apenas este `REGISTRO_INPI.md` e o `CITATION.cff`, de modo que o
valor se mantém na etiqueta. Conferido depois de etiquetar, sobre uma cópia
limpa da `v2.4.7` (commit `e05a140`), pelo workflow `registra-doi.yml`: o valor
confere. O DOI de versão desta etiqueta é 10.5281/zenodo.23576847, atribuído
pelo Zenodo no depósito disparado pela publicação do Release em 22/10/2026.

A `v2.4.8` foi registrada pelo workflow `registra-doi.yml` na publicação do
Release, em 22/10/2026, com o título “v2.4.8 — Publicação e registro automáticos
da versão”. Em relação à `v2.4.7`, mudam 2 arquivos-fonte
(`software/automacao_github/registra_doi.py` e
`software/automacao_github/test_registra_doi.py`).

O resumo criptográfico da `v2.4.8` foi calculado pelo mesmo workflow sobre uma
cópia limpa da etiqueta (commit `e86b106`), com o critério do comando acima: 102
arquivos e 19.139 linhas. O DOI de versão desta etiqueta é
10.5281/zenodo.23577538, atribuído pelo Zenodo no depósito disparado pela
publicação do Release em 22/10/2026.

A `v2.4.9` foi registrada pelo workflow `registra-doi.yml` na publicação do
Release, em 23/10/2026, com o título “v2.4.9 — Ícone adaptativo do aplicativo
(2.2.2) e capturas de tela com dados reais”. Em relação à `v2.4.8`, entram 2
arquivos-fonte (`software/automacao_github/dados_das_capturas.py` e
`software/dashboard_web/capturas_do_painel.py`); mudam 2
(`software/aplicativo_mobile/app/build.gradle.kts` e
`software/aplicativo_mobile/app/src/test/java/com/agrointeligencia/app/CapturasDeTelaTest.kt`).

O resumo criptográfico da `v2.4.9` foi calculado pelo mesmo workflow sobre uma
cópia limpa da etiqueta (commit `64b32fb`), com o critério do comando acima: 104
arquivos e 19.317 linhas. O DOI de versão desta etiqueta é
10.5281/zenodo.23583614, atribuído pelo Zenodo no depósito disparado pela
publicação do Release em 23/10/2026.

Os treze valores registrados antes da `v2.4.2` foram recalculados em 22/10/2026
a partir de cópias limpas dos respectivos commits, e conferem; o da `v2.4.2` foi
calculado pela primeira vez na mesma data. A tag da defesa é a `v2.3.7`, e é do
Release dela que sai o APK distribuído (`versionCode` 13, `versionName` 2.1.6,
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

2. **Executar o comando de hash** — o mesmo da seção 9.1, com `LC_ALL=C` nas
   duas etapas, sem o qual a ordenação varia com o idioma do sistema e o
   resultado não confere:
   ```bash
   LC_ALL=C find . \( -name '*.py' -o -name '*.kt' -o -name '*.kts' \) \
     -not -path './.git/*' -not -path '*/build/*' \
     -not -path '*__pycache__*' -not -path '*/.gradle/*' \
     | LC_ALL=C sort | xargs sha256sum | sha256sum
   ```

3. **Resultado esperado:**
   ```
   5a93dfca9511fcab534c76da4618e670e5c6ed6d33d48ac2a557963a5ef9f11d  -
   ```

   > Esta seção trazia aqui, até esta revisão, o valor `7eca3e90…`, que a
   > seção 9.1 declara irreproduzível. Um examinador que seguisse estes passos
   > obteria divergência e concluiria, sem razão, que a prova de integridade não
   > se sustenta. O valor acima é o que o comando devolve no commit-âncora, e
   > confere em execuções repetidas.

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
- **DOI da versão da defesa (`v2.3.7`), citada como referência de dados do
  artigo submetido:** 10.5281/zenodo.22343315
- **DOI da `v2.3.8`:** 10.5281/zenodo.22348036
- **DOI da `v2.3.9`, citada como referência de dados do artigo ressubmetido:**
  10.5281/zenodo.22739059
- **DOI da `v2.4.0`:** 10.5281/zenodo.22755108
- **DOI da `v2.4.1`:** 10.5281/zenodo.22833602
- **DOI da `v2.4.2`:** 10.5281/zenodo.22837962
- **DOI da `v2.4.3`:** 10.5281/zenodo.23560491
- **DOI da `v2.4.4`:** 10.5281/zenodo.23573276
- **DOI da `v2.4.5`:** 10.5281/zenodo.23574981
- **DOI da `v2.4.6`:** 10.5281/zenodo.23575177
- **DOI da `v2.4.7`:** 10.5281/zenodo.23576847
- **DOI da `v2.4.8`:** 10.5281/zenodo.23577538
- **DOI da versão mais recente (`v2.4.9`):** 10.5281/zenodo.23583614
- **Painel Web:** https://soja-para.streamlit.app
- **API Render:** https://agrointeligencia-api.onrender.com
