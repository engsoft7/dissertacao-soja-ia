# Aplicação da Inteligência Artificial na Previsão da Produtividade da Soja

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21286115-1682D4?logo=doi&logoColor=white)](https://doi.org/10.5281/zenodo.21286115)
[![Painel online](https://img.shields.io/badge/painel_online-soja--para.streamlit.app-FF4B4B?logo=streamlit&logoColor=white)](https://soja-para.streamlit.app)
[![Download App (Android)](https://img.shields.io/badge/Download_APK-Android_Nativo-3DDC84?logo=android&logoColor=white)](https://github.com/engsoft7/dissertacao-soja-ia/releases/latest)

<!--Códigos e dados da dissertação de Mestrado Profissional em Computação Aplicada
(PPCA/UFPA — Campus de Tucuruí).-->

> ### 🚀 Produtos Técnicos (Acesso Direto)
> 
> 📱 **Aplicativo Mobile Oficial:** [Baixar APK Android (última versão)](https://github.com/engsoft7/dissertacao-soja-ia/releases/latest)  
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
  baselines coincidem (406 kg/ha nos dois) e o efeito real da máscara aparece,
  concentrado nos métodos de árvore: o XGBoost sobe de R² 0,102 para 0,162 e o
  Random Forest, de 0,165 para 0,179, enquanto SVR e MLP ficam estáveis. É
  agronomicamente coerente: a máscara restringe o sinal espectral à lavoura
  efetiva, e os modelos de árvore são os que mais se beneficiam de preditores
  menos ruidosos.
- **Nenhum modelo supera o baseline mesmo após busca aninhada.** Uma objeção
  natural é que os modelos poderiam vencer se fossem melhor ajustados.
  `03_busca_hiperparametros.py` responde com validação cruzada aninhada: os
  hiperparâmetros são escolhidos dentro de cada dobra, sem jamais ver a safra
  avaliada. Nenhum modelo supera o baseline (416 kg/ha, R² 0,216): o MLP **iguala**
  o baseline (416 kg/ha, R² 0,216 — aprende a prever resíduo aproximadamente
  nulo), o SVR fica logo atrás (418, R² 0,208) e os métodos de árvore degradam o
  desempenho (Random Forest 432, XGBoost 440). As variáveis ambientais não
  acrescentam capacidade preditiva à informação já contida no histórico do
  município somado à tendência.

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
python 00_baixa_dados.py                            # base de von Bloh et al. (2023)
python 01_treina_modelos.py "Random Forest" "XGBoost" "SVR" "MLP"   # versão sem ajuste

# a busca recebe um modelo por vez (o 2º argumento é o nº de configurações, padrão 15)
python 03_busca_hiperparametros.py "Random Forest"
python 03_busca_hiperparametros.py "XGBoost"
python 03_busca_hiperparametros.py "SVR"
python 03_busca_hiperparametros.py "MLP"

python 06_confirma_busca.py              # reavalia o topo com 7.000 registros
python 04_avalia_ajustado.py             # avalia em 2016–2020 → Tabela 3
python 05_gera_figuras_ajustado.py       # Figuras 2, 3 e 4
```

`04_avalia_ajustado.py` fecha com um comparativo entre a versão sem ajuste e a
ajustada, que depende de `01_treina_modelos.py` ter rodado antes — é ele quem
gera `results/all_results.json`. Sem esse arquivo o comparativo é omitido, e os
resultados ajustados são gravados do mesmo jeito.

A busca é a etapa cara (cerca de uma hora em uma máquina comum). Os JSONs
versionados aqui já trazem os resultados dela, então `04_avalia_ajustado.py` e
`05_gera_figuras_ajustado.py` podem ser rodados isoladamente — as configurações
da dissertação estão escritas no próprio `04_avalia_ajustado.py`.

Os JSONs versionados ao lado dos scripts (`resultados_busca.json`,
`confirmacao_7000.json`, `resultados_ajustados.json`) são o **registro** dos
resultados que a dissertação reporta. Os scripts escrevem a saída de uma nova
execução em `results/`, que não é versionado — assim dá para comparar o que a
sua máquina produz com o que está no texto, sem sobrescrever o registro.

**Sobre reproduzir os números exatos.** O SVR e o MLP reproduzem os valores da
dissertação dígito a dígito, safra a safra, e a importância por permutação da
Figura 4 sai idêntica até a casa decimal. Três dos quatro modelos, portanto, não
dependem do ambiente. O Random Forest depende, e o XGBoost fica em aberto.

**Random Forest — resolvido pelo pin.** A partir do scikit-learn 1.9 o Random
Forest muda de resultado mesmo com `random_state` fixo, e a linha da Tabela 3 cai
de 476,0 para 473,7 kg/ha. As versões 1.3.2, 1.4.2, 1.5.0, 1.5.2 e 1.8.0 foram
testadas e todas devolvem 476,0 / 353,5 / 0,387, exatamente o registrado. Por
isso o `requirements.txt` fixa `scikit-learn>=1.3,<1.9`. Verificado de ponta a
ponta: rodando `04_avalia_ajustado.py` com scikit-learn 1.8.0, três das quatro
linhas da Tabela 3 — SVR, Random Forest e MLP — saem idênticas às registradas.

**XGBoost — divergência em aberto, de 1,3 kg/ha.** A linha do XGBoost sai 479,3
em vez dos 480,6 registrados. Foram testadas vinte versões, e o valor de fato
muda entre elas — mas nenhuma chega a 480,6:

| versão do XGBoost | RMSE |
|---|---|
| 1.5.0, 1.5.2, 1.6.2, 1.7.6 | 479,0 |
| 2.0.0, 2.0.1, 2.0.2, 2.0.3 | 479,3 |
| 2.1.0, 2.1.1, 2.1.2 | 476,5 |
| 2.1.3, 2.1.4 | 479,3 |
| 3.0.0, 3.0.2, 3.0.5, 3.1.0, 3.1.1, 3.2.0 | 479,3 |

Também não é contagem de threads: `n_jobs` de 1 a 16 devolve sempre o mesmo
valor. A diferença aparece espalhada pelas cinco safras com sinais alternados
(−7,8 a +2,6 kg/ha), o que indica um ajuste de modelo distinto e não um desvio
sistemático. A hipótese que resta é a do ambiente de compilação: a ordem de
redução em ponto flutuante na construção do histograma depende do conjunto de
instruções da CPU, e isso não se reproduz noutra máquina.

Quem reproduzir deve esperar um valor entre 476,5 e 479,3 nessa linha, e apenas
nela. A conclusão do capítulo não muda: o XGBoost é o terceiro colocado nos dois
casos, atrás de SVR e Random Forest.

A busca de hiperparâmetros é aleatória: reexecutá-la tende a eleger uma
configuração diferente, sem que a conclusão mude. O que ela decide com segurança
é **qual modelo vence**; a configuração exata, não — `06_confirma_busca.py`
reavalia o topo do ranking com 7.000 registros justamente para mostrar isso.

**Estudo do Pará** (os dados já estão em `pesquisa/dados/`, não é preciso recoletar)

```bash
cd pesquisa/04_analise_para
python 01_compara_mascara_controlada.py  # Tabela 5 e Figura 5
python 02_gera_figuras.py

# a busca aninhada também recebe um alvo por vez
python 03_busca_hiperparametros.py baseline
python 03_busca_hiperparametros.py "Random Forest"
python 03_busca_hiperparametros.py "XGBoost"
python 03_busca_hiperparametros.py "SVR"
python 03_busca_hiperparametros.py "MLP"

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
python 02_recupera_autoria_crossref.py  # autoria via DOI
```

`01_busca_bases_abertas.py`, que regenera os números do PRISMA, foi escrito para
o **Google Colab** e começa com `!pip install` — não roda com `python` direto.
Cole-o em uma célula do Colab, como os scripts de `pesquisa/01_coleta_dados/`.

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
- **Classificação climática:** consulta o Oceanic Niño Index do Climate
  Prediction Center (NOAA) e atualiza `pesquisa/dados/eventos_enso.json`, que o
  painel usa para a faixa de fase climática da safra alvo e para as barras de
  El Niño e La Niña do gráfico histórico. Se a NOAA não responder, o arquivo
  existente é preservado e nenhum PR é aberto por isso.
- **Custos e preço da CONAB:** o levantamento de custos de produção da soja em
  Pedro Afonso (TO) é publicado a cada dois meses e alimenta o preço e o custo
  do simulador. O ciclo consolida os CSVs em
  `pesquisa/dados/conab/levantamento_atual.json` e propaga o resultado para o
  painel, a API e o aplicativo de uma vez — inclusive a praça, a data e a frase
  que diz onde o preço está na série histórica. Nada disso é literal no código:
  trocar o levantamento é trocar o CSV. O coletor **procura a fonte
  sozinho**: consulta o catálogo federal de
  dados abertos e a página do portal, e tenta as candidatas até uma delas
  ter o cabeçalho de uma planilha da CONAB — o que não for reconhecido é
  descartado, nunca gravado. `CONAB_CUSTOS_URL` continua valendo e vai na
  frente da fila, mas deixou de ser necessária. Se nada for encontrado, o
  workflow verifica quantos meses tem o levantamento em uso e abre uma
  **issue** quando ele passa de quatro meses.
- **O produto declara a própria idade.** A issue serve a quem mantém o
  repositório; o usuário do aplicativo não a vê. Por isso o painel e o
  aplicativo calculam, **a cada leitura**, quantos meses separam o levantamento
  em uso da data de hoje, e avisam em tela quando ele passa da cadência da
  CONAB. Passado um ano, o aviso muda de tom e pede que o preço seja tratado
  como referência histórica. A idade nunca é gravada em arquivo: um número
  congelado na geração já nasceria errado no dia seguinte. É o que impede este
  produto, aberto daqui a dois anos sem ninguém ter mantido nada, de exibir o
  preço de 2026 como se fosse o de hoje.
- **Os três números que decidem a margem são do produtor.** Produtividade,
  preço e custeio são o que o fazendeiro, o produtor rural e o técnico que usam
  este produto conhecem melhor que qualquer levantamento ou modelo: eles
  pesaram a carga, receberam o pagamento e pagaram as notas. Os três são
  editáveis no painel e no aplicativo, e o aplicativo os guarda com a data em
  que foram informados — digitar o próprio custeio e perdê-lo ao fechar o app é
  defeito, não economia de tela. O padrão existe para a tela abrir com algo
  plausível, e passa a ser exibido como comparação assim que houver número do
  produtor. A produtividade importa em especial: a estimativa sai da PAM, que
  esta pesquisa mostrou arredondar para sacas inteiras e travar em platôs, de
  modo que calcular a margem de quem colheu 65 sacas sobre as 55 registradas
  não serve a ninguém.
- **O preço é do produtor, e o aplicativo o guarda.** Custo é grandeza de
  levantamento; preço é grandeza de mercado. A CONAB publica a cada dois meses
  e o preço da soja muda todo dia, então nenhum padrão vindo de levantamento
  chega em dia, por melhor que seja a coleta. Quem sabe o preço é quem vendeu:
  o aplicativo guarda o valor informado com a data e passa a abrir com ele, e o
  padrão da CONAB vira ponto de partida. Passados 45 dias, pede confirmação —
  e o aviso de idade troca de assunto para o custo, que continua vindo do
  levantamento. Ao lado, o físico em Paranaguá, relido de hora em hora, dá a
  única referência diária do produto: é preço de porto, no Paraná, e serve para
  o usuário julgar se o número no campo ainda faz sentido.

### Atualizar o levantamento da CONAB à mão (um comando)

Baixe as três planilhas em CSV do [Portal de Informações
Agropecuárias](https://portaldeinformacoes.conab.gov.br/custos-de-producao.html)
— série histórica de Pedro Afonso (TO), custo por município e produtividade por
município — e rode:

```bash
python software/automacao_github/atualiza_conab.py \
  --arquivo serie.csv --arquivo municipios.csv --arquivo produtividade.csv
```

O script identifica cada planilha pelo cabeçalho (o portal exporta tudo como
`dados.csv`), acrescenta o levantamento sem apagar a série, recusa conteúdo que
não seja planilha da CONAB, e chama
`software/automacao_github/gera_levantamento_conab.py`, que recalcula custo por
hectare, posição do preço na série e as legendas, e sincroniza as cópias de
emergência de `financas.py` e `app.py`. Não há número para editar à mão nem APK
para recompilar: as legendas do aplicativo vêm da API.

Duas regras que o gerador não deixa violar: preço e custo saem sempre do **mesmo
levantamento** (se a CONAB publicar custo sem divulgar preço, ele fica no último
com cotação em vez de misturar dois momentos), e as três planilhas têm de vir da
**mesma extração** (o custo variável por saca é conferido entre elas).

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

Duas situações escapam do merge automático de propósito, porque mexem em números
que a dissertação reporta: quando a revisão do IBGE altera as métricas de
validação (Tabela 6 e subseção 4.9), e quando a CONAB revisa um levantamento já
publicado. Nesses casos o PR fica aberto para conferência humana. Levantamento
**novo** da CONAB entra sozinho — o produto declara em tela qual está usando.

Para conferir a credencial na hora: **Actions → Atualiza base de dados →
Run workflow**, marque **"Testar a credencial do Earth Engine"** e rode. O log
deve terminar com "credencial e ativos do Earth Engine OK", sem alterar nada —
nesse modo os passos que consultam o SIDRA e a NOAA ficam desligados, para o
teste não abrir PR nem tocar na base.

### A base evolui; a dissertação não

O ciclo acima mantém `pesquisa/dados/` acompanhando as revisões do IBGE. Isso
significa que o `main` deste repositório pode divergir dos números impressos na
dissertação: se o IBGE revisar uma safra, a base muda e as métricas do painel
são recalculadas, enquanto as tabelas do texto continuam reportando o
levantamento vigente na época da escrita.

Para reproduzir exatamente os valores das tabelas da dissertação, use a
**versão arquivada no Zenodo** indicada pelo DOI, e não o `main`. O DOI aponta
para um instantâneo imutável; o `main` é a versão viva do produto técnico.

Somente `pesquisa/dados/soja_para_mascarado_2001_2024.csv` (a base do painel) é
atualizado — o nome do arquivo preserva o recorte original da dissertação, mas
safras posteriores são acrescentadas a ele pela automação. A base sem máscara
permanece congelada como artefato da comparação feita na dissertação. Se o
MapBiomas ainda não tiver publicado a máscara do ano-alvo, usa-se a mais
recente disponível e o PR registra a aproximação.

*Atenção:* o GitHub pausa agendamentos de repositórios sem atividade por ~60
dias e envia um e-mail avisando; basta reativar na aba Actions.

---

## Testes automáticos

O workflow `.github/workflows/testes.yml` roda `pytest` a cada push e a cada
pull request. Para rodar localmente, da raiz do repositório:

```bash
pip install pytest pandas requests
python -m pytest software -q
```

Os testes são poucos e específicos, cada um preso a um erro que já aconteceu:

- `software/automacao_github/test_atualiza_pam_paths.py` — os caminhos que a
  automação escreve são os que o painel lê.
- `software/dashboard_web/test_robustez_painel.py` — nenhum bloco `except` lê
  um nome que só o `try` cria (esse defeito derrubou o app publicado uma vez);
  a cópia do custo de referência no painel bate com a fonte da verdade em
  `financas.py`; e o `requirements.txt` do painel declara o que `financas.py`
  importa, em vez de depender de dependência transitiva.

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
- **Geovisualização Integrada:** Mapa interativo (Folium) com enquadramento automático no recorte da base e destaque do município selecionado e do comparado. O desenho usa apenas geometrias versionadas no repositório — contorno do estado (malha do IBGE) e rios (Natural Earth) —, sem camada de terceiros em tempo de execução e sem imagem de satélite: MODIS, CHIRPS, ERA5-Land e MapBiomas alimentam o modelo, não o fundo do mapa.
- **Offline First:** Cascatas de resiliência UI/UX operando perfeitamente sem conexão com a internet.

## 🌐 AgroInteligência Web v2.0 (Executive SPA Dashboard)
- **Single Page Application (SPA):** Navegação redesenhada para uma "Sidebar" global, fluida e com responsividade estrita. O encadeamento do painel elimina tabulações e se comporta como um SaaS nativo multi-tenant.
- **Ecossistema Modular:** Código fonte fragmentado num ecossistema elegante e sustentável, separando roteamento de manipulação do layout via Python e consumo (ETL) da cotação física em Paranaguá (Notícias Agrícolas), exibida como comparação — a referência da simulação é o preço recebido pelo produtor no levantamento da CONAB, que é preço de porteira.
- **Parâmetros econômicos com fonte declarada:** o custo operacional vem do levantamento da CONAB para Pedro Afonso (TO), de março de 2026, e o Valor da Terra Nua da tabela da Receita Federal do exercício 2026, classe lavoura de aptidão boa. O preço recebido no mesmo levantamento, R$ 105,09 por saca, é o menor dos 13 levantamentos da praça desde março de 2023 (mediana R$ 116,91); o produto informa essa posição na série, para o padrão ser lido como cenário conservador e não como previsão de preço. São tabelas estáticas versionadas em `pesquisa/dados/`, não coleta em tempo real. Preço e custo são editáveis na interface, porque entram na conta da margem; o Valor da Terra Nua não, porque é referência fiscal (base de cálculo do ITR) e não preço de mercado — aparece como nota de contexto. A Receita Federal publica VTN para 13 dos 38 municípios; nos demais o painel informa que não há valor oficial.
- **Visibilidade Asynchronous de AI:** Processamento dinâmico do Random Forest encapsulado em "shimmers" / Spinners UX, indicando cálculo simultâneo na simulação de cenários operacionais e previsões em tempo real do Agro-mercado do Pará.
- **Plotly Analytics (Fintech Interactivity):** Upgrade massivo das engines gráficas do Altair para o *Plotly.js*. Anotação autônoma de Zonas de Risco Climático (El Niño e La Niña Históricos mapeados via *VRects*) e regressões lineares paramétricas sobrepondo a série cronológica de produtividade, além de Full-Zoom Crosshairs.
- **Agente de Linguagem Natural (LLM Heurístico):** Um sintetizador inteligente lê as matrizes de cálculo e o fluxo de caixa final simulado, formulando sentenças interpretativas em parágrafos para o produtor. Ele transcreve a matemática dura para relatórios humanos como *"Alto risco crítico projetado"* ou *"Viabilidade Econômica Robusta de Safra"*.
