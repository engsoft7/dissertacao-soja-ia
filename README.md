# Aplicação da Inteligência Artificial na Previsão da Produtividade da Soja

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21286115-1682D4?logo=doi&logoColor=white)](https://doi.org/10.5281/zenodo.21286115)
[![Painel online](https://img.shields.io/badge/painel_online-soja--para.streamlit.app-FF4B4B?logo=streamlit&logoColor=white)](https://soja-para.streamlit.app)
[![Download App (Android)](https://img.shields.io/badge/Download_APK-Android_Nativo-3DDC84?logo=android&logoColor=white)](https://github.com/engsoft7/dissertacao-soja-ia/releases/latest)

<!--Códigos e dados da dissertação de Mestrado Profissional em Computação Aplicada
(PPCA/UFPA — Campus de Tucuruí).-->

> ### 🚀 Produtos Técnicos (Acesso Direto)
> 
> 📱 **Aplicativo Mobile Oficial (v2.1.1):** [Baixar APK Android](https://github.com/engsoft7/dissertacao-soja-ia/releases/latest)  
> *Versão nativa construída em Kotlin+Jetpack Compose com simulação climática, feedback tátil (haptics) e alta performance offline.*
> 
> 🌐 **Painel Original na Web:** [Acessar Dashboard](https://soja-para.streamlit.app)  
> *Plataforma via navegador projetada usando Streamlit.*

<!--**Autor:** Maycon Lima dos Santos
**Orientador:** Prof. Dr. Caio Carvalho Moreira
**Ano:** 2026-->

---

## Sobre

O trabalho compara modelos de Aprendizado de Máquina para prever a produtividade
municipal da soja, em dois recortes:

1. **Estudo nacional** — 24.860 registros município-safra (2001–2020, 7 estados),
   a partir da base pública de von Bloh *et al.* (2023).
2. **Estudo de caso do Pará** — base construída nesta pesquisa: 415 registros
   município-safra, 38 municípios, 2001–2024, integrando IBGE, MODIS, CHIRPS,
   ERA5-Land e a máscara anual de soja do MapBiomas.

### Principais resultados

| Recorte | Melhor modelo | RMSE | R² | Erro relativo |
|---|---|---|---|---|
| Nacional | **SVR** (ajustado) | **461 kg/ha** | 0,425 | **17,1%** |
| Pará (com máscara) | MLP | 416 kg/ha | 0,216 | 13,9% |

No recorte nacional os números acima são os da **busca de hiperparâmetros**
(`03_busca_hiperparametros.py` → `04_avalia_ajustado.py`). Depois do ajuste o
SVR passa a ser o melhor modelo, à frente do XGBoost, que liderava na versão
sem ajuste. O script `01_treina_modelos.py` foi preservado como registro dessa
versão anterior e **não reproduz a Tabela 3** — quem quiser os números da
dissertação deve rodar `04_avalia_ajustado.py`.

*Nota de Engenharia:* Embora o **MLP** tenha empatado como o melhor modelo matemático puro, o **Random Forest** foi a arquitetura escolhida para integração no Produto Técnico (Dashboard e App Mobile) devido à sua alta explicabilidade (Feature Importance) e menor custo computacional em implantações de nuvem.

No Pará, **as variáveis climáticas e espectrais não superaram um modelo de
referência** baseado apenas no histórico municipal e na tendência tecnológica.
Esse resultado se sustenta sob dois controles adicionais:

- **A máscara de soja foi avaliada em amostra controlada.** As duas bases do
  Pará têm tamanhos diferentes (493 registros sem máscara, 415 com máscara), e
  compará-las diretamente confunde o efeito da máscara com o efeito de estar
  olhando conjuntos distintos de municípios e safras. O script
  `01_compara_mascara_controlada.py` roda os dois cenários sobre os **379
  registros comuns** às duas bases e traz uma verificação embutida: como o
  baseline não usa variável ambiental alguma, ele tem de dar exatamente o mesmo
  resultado nos dois cenários, e o script aborta se não der. Sob esse controle os
  baselines coincidem (405,8 kg/ha nos dois) e o efeito real da máscara aparece:
  −3,7 kg/ha no Random Forest, −7,4 no XGBoost, +0,7 no SVR e +0,1 no MLP. O
  desenho anterior, que comparava as duas bases inteiras, sugeria uma diferença
  bem maior — mas ela vinha da amostra, não da máscara.
- **Nenhum modelo supera o baseline mesmo após busca aninhada.** Uma objeção
  natural é que os modelos poderiam vencer se fossem melhor ajustados.
  `03_busca_hiperparametros.py` responde com validação cruzada aninhada: os
  hiperparâmetros são escolhidos dentro de cada dobra, sem jamais ver a safra
  avaliada. Nenhum modelo supera o baseline (415,6 kg/ha): o MLP e o SVR **empatam**
  com ele (415,4 e 416,0 kg/ha — diferenças dentro do ruído), e os métodos de
  árvore ficam atrás (Random Forest 425,4 e XGBoost 428,6). Um modelo que empata
  com o baseline aprendeu a prever resíduo aproximadamente nulo: as variáveis
  ambientais não o moveram. A configuração vencedora só se repete em 8% a 25% das
  dobras — a validação interna não encontra um ótimo consistente, o que se espera
  quando não há sinal a encontrar.

A investigação da variável-alvo revelou que **40,1% dos pares de safras
consecutivas da PAM/IBGE nos municípios paraenses apresentam produtividade
rigorosamente idêntica**, o que indica imputação nos levantamentos oficiais e
impõe um teto estrutural à acurácia de qualquer modelo calibrado sobre essa base.

---

## Estrutura

```
pesquisa/01_coleta_dados/
  01_coleta_gee_sem_mascara.py            coleta inicial (média do município)
  02_coleta_gee_com_mascara_mapbiomas.py  versão usada nos resultados
pesquisa/02_revisao_sistematica/
  01_busca_bases_abertas.py               busca em OpenAlex e Crossref (PRISMA)
  02_recupera_autoria_crossref.py         autoria real via DOI, formato ABNT
  estudos_triados.csv                     70 elegíveis, com decisão e motivo
  referencias_53_estudos_abnt.txt         os 53 incluídos, em ABNT
pesquisa/03_analise_nacional/
  00_baixa_dados.py                       baixa a base de von Bloh et al. (2023)
  01_treina_modelos.py                    RF, XGBoost, SVR, MLP — SEM ajuste (registro)
  02_gera_figuras.py                      figuras da versão sem ajuste
  03_busca_hiperparametros.py             busca aleatória na janela 2001–2015
  06_confirma_busca.py                    reavalia o topo do ranking com 7.000 registros
  04_avalia_ajustado.py                   avaliação em 2016–2020 → Tabela 3
  05_gera_figuras_ajustado.py             Figuras 2, 3 e 4 (importância por permutação)
  resultados_busca.json                   ranking completo da busca
  confirmacao_7000.json                   confirmação do topo do ranking
  resultados_ajustados.json               métricas da Tabela 3
pesquisa/04_analise_para/
  01_compara_mascara_controlada.py        com/sem máscara na amostra comum → Tabela 5, Figura 5
  02_gera_figuras.py
  03_busca_hiperparametros.py             busca aninhada → Tabela 6
  04_gera_fig6_aninhada.py                Figura 6
  comparacao_controlada.json              métricas da Tabela 5
  resultados_busca_aninhada.json          métricas da Tabela 6
  01_compara_mascara_e_baseline_DEPRECADO.py
                                          desenho anterior, confundido; mantido
                                          como registro histórico (não usar)
pesquisa/05_artigo/
  gera_figuras_artigo.py                  figuras do artigo sobre a PAM
pesquisa/dados/
  soja_para_mascarado_2001_2024.csv       base principal (atualizada por automação)
  soja_para_sem_mascara_2001_2023.csv     base sem máscara (comparação)
  municipios_para.csv                     nome oficial acentuado e centroide (mapa)
  para_geo.json                           contorno do estado (fundo do mapa)
  rios_para.json                          principais rios (contexto do mapa)
  eventos_enso.json                       períodos históricos de El Niño/La Niña
  metricas_validacao.json                 métricas pré-calculadas para o painel
software/api_backend/
  api.py                                  API REST (FastAPI) para clientes
  financas.py                             cálculos financeiros (VTN, custos)
software/dashboard_web/
  app.py                                  interface Streamlit (SPA)
  model.py                                núcleo preditivo (produto técnico)
  ui/                                     componentes visuais (charts, themes)
  data/                                   carregadores de dados
  README.md                               como executar e limitações
software/aplicativo_mobile/
  app/.../MainActivity.kt                 app Android (Jetpack Compose)
  app/.../ApiService.kt                   cliente Retrofit da API
  app/build.gradle.kts                    configuração de build
software/automacao_github/
  atualiza_pam.py                         revisões da PAM via SIDRA (GitHub Actions)
  atualiza_enso.py                        atualização automática NOAA ONI
  coleta_gee_safra.py                     coleta headless de safra nova no GEE
  bot_agente_vtn.py                       coleta VTN de 144 municípios
  gera_metricas.py                        pré-calcula a validação para o painel
  gera_municipios.py                      nomes acentuados (IBGE) + coordenadas
  gera_geo_para.py                        contorno do Pará (malha do IBGE)
  gera_rios_para.py                       principais rios do Pará (Natural Earth)
```

---

## Como reproduzir

Requisitos: Python 3.10+.

```bash
pip install pandas numpy scikit-learn xgboost matplotlib openpyxl
```

**Estudo nacional** — os números da dissertação (Tabela 3) vêm dos scripts
`03`/`06`/`04`, nesta ordem:

```bash
cd pesquisa/03_analise_nacional
python 00_baixa_dados.py                 # baixa a base de von Bloh et al. (2023)
python 03_busca_hiperparametros.py       # busca em 2001–2015 → resultados_busca.json
python 06_confirma_busca.py              # confirma o topo com 7.000 registros
python 04_avalia_ajustado.py             # avalia em 2016–2020 → Tabela 3
python 05_gera_figuras_ajustado.py       # Figuras 2, 3 e 4
```

A busca é a etapa cara (cerca de uma hora em uma máquina comum). Os JSONs
versionados aqui já trazem os resultados dela, então `04_avalia_ajustado.py` e
`05_gera_figuras_ajustado.py` podem ser rodados isoladamente — as configurações
da dissertação estão escritas no próprio `04_avalia_ajustado.py`.

**Sobre reproduzir os números exatos da Tabela 3.** O SVR e o MLP reproduzem os
valores da dissertação dígito a dígito, safra a safra. O Random Forest e o
XGBoost saem 2 a 3 kg/ha melhores (474 e 479, contra 476 e 481 no texto), com os
mesmos hiperparâmetros do Quadro 6 e o mesmo protocolo. A diferença é de versão
de biblioteca: esses dois modelos não são estáveis entre versões do
scikit-learn e do XGBoost mesmo com semente fixa — o sorteio interno do
*bootstrap* e a discretização do histograma mudam —, ao passo que o SVR
(libsvm) e o MLP são. Os JSONs versionados registram as versões com que foram
gerados, no campo `ambiente`. Como o `requirements.txt` usa faixas abertas, quem
reproduzir hoje deve esperar essa margem nas duas linhas de árvore.

A busca é aleatória: reexecutá-la tende a eleger uma configuração diferente,
sem que a Tabela 3 mude de conclusão. O que ela decide com segurança é **qual
modelo vence**; a configuração exata, não — `06_confirma_busca.py` mostra que o
topo do ranking é um platô de 1,4 a 17,7 kg/ha, dentro do qual a ordem troca com
qualquer mudança de subamostra.

Para reproduzir a versão **sem** ajuste de hiperparâmetros (o ponto de partida
contra o qual o ganho é medido, não os números da Tabela 3):

```bash
python 01_treina_modelos.py "Random Forest" "XGBoost" "SVR" "MLP"
python 02_gera_figuras.py
```

**Estudo do Pará** (os dados já estão em `pesquisa/dados/`, não é preciso recoletar)

```bash
cd pesquisa/04_analise_para
python 01_compara_mascara_controlada.py  # Tabela 5 e Figura 5
python 02_gera_figuras.py
python 03_busca_hiperparametros.py       # busca aninhada → Tabela 6
python 04_gera_fig6_aninhada.py          # Figura 6
```

`01_compara_mascara_controlada.py` aborta com mensagem explícita se os baselines
dos dois cenários divergirem — isso indicaria que o controle da amostra falhou e
que o resultado não deve ser publicado.

**Recoleta dos dados do Pará** (opcional; exige conta no Google Earth Engine)

Os scripts de `pesquisa/01_coleta_dados/` foram escritos para o Google Colab. Registre um
projeto em <https://code.earthengine.google.com>, informe o ID na variável
`PROJETO_GEE` e execute. A coleta com máscara leva cerca de 20 minutos.

**Painel de estimativa** (produto técnico; ver `software/dashboard_web/README.md`)

Versão publicada: **<https://soja-para.streamlit.app>** — acessível de qualquer
dispositivo; no celular, use "Adicionar à tela inicial" para abrir como
aplicativo. No plano gratuito o app hiberna após alguns dias sem acesso:
basta clicar em "Yes, get this app back up" e aguardar cerca de um minuto.

Para executar localmente:

```bash
pip install -r software/dashboard_web/requirements.txt
streamlit run software/dashboard_web/app.py
```

Alternativa: `./run.sh` na raiz do repositório ativa o ambiente virtual
(`.venv/`) e inicia o painel automaticamente.

*Para republicar no Streamlit Community Cloud* (gratuito): acesse
<https://share.streamlit.io>, entre com a conta do GitHub, clique em
**Create app → Deploy a public app from GitHub** e informe:

- **Repository:** `engsoft7/dissertacao-soja-ia`
- **Branch:** `main`
- **Main file path:** `software/dashboard_web/app.py`

O serviço instala o `requirements.txt` da raiz e gera o link público.

**Revisão sistemática**

```bash
cd pesquisa/02_revisao_sistematica
python 01_busca_bases_abertas.py        # regenera os números do PRISMA
python 02_recupera_autoria_crossref.py  # autoria via DOI
```

Os resultados variam conforme a data da busca, pois as bases são atualizadas
continuamente. A busca reportada na dissertação foi executada em 9 de julho de 2026.

---

## Atualização automática dos dados

O workflow `.github/workflows/atualiza-dados.yml` roda todo dia 15 (e pode ser
disparado manualmente na aba **Actions → Atualiza base de dados → Run workflow**).
Ele consulta a API do SIDRA/IBGE e:

- **Revisões:** se o IBGE revisou a produtividade de alguma safra já presente na
  base do painel, abre um **pull request** com o CSV atualizado (somente o campo
  revisado muda). O merge redeploya o painel publicado automaticamente.
- **Safra nova:** quando o SIDRA publica um ano que ainda não está na base:
  - com a coleta automática ativada (abaixo), o robô coleta as variáveis
    ambientais no Earth Engine (`software/automacao_github/coleta_gee_safra.py` — mesmas
    coleções e janelas de `pesquisa/01_coleta_dados/`) e inclui a safra completa no PR;
  - sem ela (ou se a coleta falhar), abre uma **issue** com o passo a passo
    manual via Google Colab.

### Ativar a coleta automática no Earth Engine (configuração única)

1. Crie (ou reuse) um projeto no [Google Cloud](https://console.cloud.google.com)
   e registre-o para uso não comercial do Earth Engine em
   <https://code.earthengine.google.com/register> (gratuito para uso acadêmico).
2. No projeto, ative a API **Google Earth Engine** (APIs & Services → Enable APIs).
3. Crie uma *service account* (IAM & Admin → Service Accounts → Create service
   account) com o papel **Earth Engine Resource Writer**.
4. Gere uma chave JSON para essa conta (aba Keys → Add key → Create new key →
   JSON) e baixe o arquivo.
5. No GitHub: **Settings → Secrets and variables → Actions → New repository
   secret**, nome `GEE_SERVICE_ACCOUNT_JSON`, valor = todo o conteúdo do JSON.

Com o secret configurado o ciclo fica completo e **sem intervenção humana**: o
SIDRA é vigiado mensalmente, revisões e safras novas viram um PR que o próprio
robô mergeia na sequência, e o merge redeploya o painel publicado. O PR fica
como registro auditável de cada atualização; para desfazer uma, use
`git revert` no commit correspondente. Para voltar ao merge manual, remova o
passo "Mergeia o PR automaticamente" do workflow.

Para conferir a credencial na hora: **Actions → Atualiza base de dados →
Run workflow**, marque **"Testar a credencial do Earth Engine"** e rode. O log
deve terminar com "credencial e ativos do Earth Engine OK", sem alterar nada.

Somente `pesquisa/dados/soja_para_mascarado_2001_2024.csv` (a base do painel) é
atualizado — o nome do arquivo preserva o recorte original da dissertação, mas
safras posteriores são acrescentadas a ele pela automação. A base sem máscara
permanece congelada como artefato da comparação feita na dissertação. Se o
MapBiomas ainda não tiver publicado a máscara do ano-alvo, usa-se a mais
recente disponível e o PR registra a aproximação.

*Atenção:* o GitHub pausa agendamentos de repositórios sem atividade por ~60
dias e envia um e-mail avisando; basta reativar na aba Actions.

---

## Metodologia, em resumo

- **Alvo:** produtividade municipal da soja (kg/ha), da PAM/IBGE (tabela 5457).
- **Janela:** novembro do ano anterior a maio do ano de colheita (ciclo da soja no Pará).
- **Máscara:** MapBiomas Coleção 10.1, classe 39 (soja), resolução 30 m.
- **Decomposição:** produtividade = tendência tecnológica + anomalia climática.
  Os modelos preveem a anomalia; a produtividade é reconstruída somando a tendência.
- **Validação:** *leave-one-year-out* — cada safra é prevista por um modelo treinado
  sem ela, simulando a previsão de um ano futuro e evitando vazamento temporal.
- **Baseline:** média histórica do município + tendência, sem clima nem NDVI.
  É o termo de comparação que revela se as variáveis ambientais agregam informação.

---

## Fontes de dados

| Fonte | Uso | Acesso |
|---|---|---|
| IBGE / PAM (SIDRA, tabela 5457) | produtividade municipal | aberto |
| MODIS MOD13Q1 | NDVI, EVI | aberto (GEE) |
| CHIRPS | precipitação | aberto (GEE) |
| ERA5-Land | temperatura, radiação, evapotranspiração | aberto (GEE) |
| MapBiomas Coleção 10.1 | máscara de soja e área plantada | aberto (GEE) |
| von Bloh *et al.* (2023) | base nacional | aberto (GitHub) |
| OpenAlex, Crossref | revisão sistemática | aberto |

---

## Uso de ferramentas de Inteligência Artificial

Conforme declarado no Apêndice A da dissertação, ferramentas de IA generativa
foram utilizadas como apoio na redação, na formatação e na implementação dos
scripts deste repositório. A concepção do tema, as decisões metodológicas, a
coleta dos dados e a interpretação dos resultados são de responsabilidade do
autor, que revisou e validou todo o material aqui publicado.

---

## Licença

Código sob licença MIT. Os dados derivados de fontes públicas mantêm as
licenças de origem; cite as fontes originais ao reutilizá-los.

---

<!--## Como citar a dissertação

> SANTOS, M. L. dos. *Aplicação da Inteligência Artificial na previsão da
> produtividade da soja*. 2026. Dissertação (Mestrado Profissional em Computação
> Aplicada) — Universidade Federal do Pará, Tucuruí, 2026. -->

## Como citar o código e os dados

SANTOS, Maycon Lima dos. **Aplicação da Inteligência Artificial na Previsão da
Produtividade da Soja: códigos e dados**. Zenodo, 2026. Software.
DOI: 10.5281/zenodo.21286115. Disponível em: https://doi.org/10.5281/zenodo.21286115.

## 🌟 Lançamento Oficial v2.1.1 (AgroInteligência Mobile)
- **Migração Cloud-Native:** Lógica de predição isolada em servidor próprio (FastAPI / Render).
- **Interface Nativa:** Aplicativo Android 100% desenvolvido em Jetpack Compose.
- **Experiência Sensorial (Haptics):** Física elástica na inferência dos cards (*Spring Animations*) e resposta tátil profunda no processamento usando o `LocalHapticFeedback`.
- **Geovisualização Integrada:** Mapas dinâmicos da folha do satélite com auto-recorte e isolamento do município focado (*Smart Zoom* Folium-backend).
- **Offline First:** Cascatas de resiliência UI/UX operando perfeitamente sem conexão com a internet.

## 🌐 AgroInteligência Web v2.0 (Executive SPA Dashboard)
- **Single Page Application (SPA):** Navegação redesenhada para uma "Sidebar" global, fluida e com responsividade estrita. O encadeamento do painel elimina tabulações e se comporta como um SaaS nativo multi-tenant.
- **Ecossistema Modular:** Código fonte fragmentado num ecossistema elegante e sustentável, separando roteamento de manipulação do layout via Python e consumo (ETL) da web (Notícias Agrícolas / CEPEA).
- **Indicadores Econômicos Automatizados:** Injeção simultânea dos bancos de **VTN/ha (Preço da Terra Nua - Receita Federal)** por municípios diretamente nos cálculos operacionais, viabilizado por scripts independentes.
- **Visibilidade Asynchronous de AI:** Processamento dinâmico do Random Forest encapsulado em "shimmers" / Spinners UX, indicando cálculo simultâneo na simulação de cenários operacionais e previsões em tempo real do Agro-mercado do Pará.
- **Plotly Analytics (Fintech Interactivity):** Upgrade massivo das engines gráficas do Altair para o *Plotly.js*. Anotação autônoma de Zonas de Risco Climático (El Niño e La Niña Históricos mapeados via *VRects*) e regressões lineares paramétricas sobrepondo a série cronológica de produtividade, além de Full-Zoom Crosshairs.
- **Agente de Linguagem Natural (LLM Heurístico):** Um sintetizador inteligente lê as matrizes de cálculo e o fluxo de caixa final simulado, formulando sentenças interpretativas em parágrafos para o produtor. Ele transcreve a matemática dura para relatórios humanos como *"Alto risco crítico projetado"* ou *"Viabilidade Econômica Robusta de Safra"*.
- **Cobertura Autônoma de 144 Cidades (Bot VTN):** Desenvolvimento de um ecossistema JSON descentralizado em pareamento direto com o IBGE. A planta injeta o chão financeiro paramétrico de modo autônomo e transparente em 100% dos limites territoriais do Estado do Pará.
