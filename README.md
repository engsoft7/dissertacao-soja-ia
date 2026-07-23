# Aplicação da Inteligência Artificial na Previsão da Produtividade da Soja

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21286115-1682D4?logo=doi&logoColor=white)](https://doi.org/10.5281/zenodo.21286115)
[![Painel online](https://img.shields.io/badge/painel_online-soja--para.streamlit.app-FF4B4B?logo=streamlit&logoColor=white)](https://soja-para.streamlit.app)

Códigos e dados da dissertação de Mestrado Profissional em Computação Aplicada
(PPCA/UFPA — Campus de Tucuruí).

**Painel de estimativa (produto técnico):** <https://soja-para.streamlit.app>

**Autor:** Maycon Lima dos Santos
**Orientador:** Prof. Dr. Caio Carvalho Moreira
**Ano:** 2026

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

| Recorte | Melhor modelo | RMSE | Erro relativo |
|---|---|---|---|
| Nacional | XGBoost | 472 kg/ha | 17,5% |
| Pará (com máscara) | MLP | 416 kg/ha | 13,9% |

No Pará, **as variáveis climáticas e espectrais não superaram um modelo de
referência** baseado apenas no histórico municipal e na tendência tecnológica.
A investigação da variável-alvo revelou que **40,1% dos pares de safras
consecutivas da PAM/IBGE nos municípios paraenses apresentam produtividade
rigorosamente idêntica**, o que indica imputação nos levantamentos oficiais e
impõe um teto estrutural à acurácia de qualquer modelo calibrado sobre essa base.

---

## Estrutura

```
01_coleta_dados/
  01_coleta_gee_sem_mascara.py            coleta inicial (média do município)
  02_coleta_gee_com_mascara_mapbiomas.py  versão usada nos resultados
02_revisao_sistematica/
  01_busca_bases_abertas.py               busca em OpenAlex e Crossref (PRISMA)
  02_recupera_autoria_crossref.py         autoria real via DOI, formato ABNT
  estudos_triados.csv                     70 elegíveis, com decisão e motivo
  referencias_53_estudos_abnt.txt         os 53 incluídos, em ABNT
03_analise_nacional/
  00_baixa_dados.py                       baixa a base de von Bloh et al. (2023)
  01_treina_modelos.py                    RF, XGBoost, SVR, MLP
  02_gera_figuras.py
04_analise_para/
  01_compara_mascara_e_baseline.py        com/sem máscara vs. baseline
  02_gera_figuras.py
05_artigo/
  gera_figuras_artigo.py                  figuras do artigo sobre a PAM
06_dashboard_web/
  model.py                                núcleo do painel (produto técnico)
  app.py                                  interface Streamlit
  README.md                               como executar e limitações
09_automacao_github/
  atualiza_pam.py                         revisões da PAM via SIDRA (GitHub Actions)
  coleta_gee_safra.py                     coleta headless de safra nova no GEE
  gera_metricas.py                        pré-calcula a validação para o painel
  gera_municipios.py                      nomes acentuados (IBGE) + coordenadas
  gera_geo_para.py                        contorno do Pará (malha do IBGE)
  gera_rios_para.py                       principais rios do Pará (Natural Earth)
dados/
  soja_para_mascarado_2001_2024.csv       base principal (415 registros)
  soja_para_sem_mascara_2001_2023.csv     base sem máscara (comparação)
  municipios_para.csv                     nome oficial acentuado e centroide (mapa)
  para_geo.json                           contorno do estado (fundo do mapa)
  rios_para.json                          principais rios (contexto do mapa)
```

---

## Como reproduzir

Requisitos: Python 3.10+.

```bash
pip install pandas numpy scikit-learn xgboost matplotlib openpyxl
```

**Estudo nacional**

```bash
cd 03_analise_nacional
python 00_baixa_dados.py
python 01_treina_modelos.py "Random Forest" "XGBoost" "SVR" "MLP"
python 02_gera_figuras.py
```

**Estudo do Pará** (os dados já estão em `dados/`, não é preciso recoletar)

```bash
cd 04_analise_para
python 01_compara_mascara_e_baseline.py
python 02_gera_figuras.py
```

**Recoleta dos dados do Pará** (opcional; exige conta no Google Earth Engine)

Os scripts de `01_coleta_dados/` foram escritos para o Google Colab. Registre um
projeto em <https://code.earthengine.google.com>, informe o ID na variável
`PROJETO_GEE` e execute. A coleta com máscara leva cerca de 20 minutos.

**Painel de estimativa** (produto técnico; ver `06_dashboard_web/README.md`)

Versão publicada: **<https://soja-para.streamlit.app>** — acessível de qualquer
dispositivo; no celular, use "Adicionar à tela inicial" para abrir como
aplicativo. No plano gratuito o app hiberna após alguns dias sem acesso:
basta clicar em "Yes, get this app back up" e aguardar cerca de um minuto.

Para executar localmente:

```bash
pip install -r 06_dashboard_web/requirements.txt
streamlit run 06_dashboard_web/app.py
```

Alternativa: `./run.sh` na raiz do repositório ativa o ambiente virtual
(`.venv/`) e inicia o painel automaticamente.

*Para republicar no Streamlit Community Cloud* (gratuito): acesse
<https://share.streamlit.io>, entre com a conta do GitHub, clique em
**Create app → Deploy a public app from GitHub** e informe:

- **Repository:** `engsoft7/dissertacao-soja-ia`
- **Branch:** `main`
- **Main file path:** `06_dashboard_web/app.py`

O serviço instala o `requirements.txt` da raiz e gera o link público.

**Revisão sistemática**

```bash
cd 02_revisao_sistematica
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
    ambientais no Earth Engine (`09_automacao_github/coleta_gee_safra.py` — mesmas
    coleções e janelas de `01_coleta_dados/`) e inclui a safra completa no PR;
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

Somente `dados/soja_para_mascarado_2001_2024.csv` (a base do painel) é
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

## Como citar a dissertação

> SANTOS, M. L. dos. *Aplicação da Inteligência Artificial na previsão da
> produtividade da soja*. 2026. Dissertação (Mestrado Profissional em Computação
> Aplicada) — Universidade Federal do Pará, Tucuruí, 2026.

## Como citar o código e os dados

SANTOS, Maycon Lima dos. **Aplicação da Inteligência Artificial na Previsão da
Produtividade da Soja: códigos e dados**. Zenodo, 2026. Software.
DOI: 10.5281/zenodo.21286115. Disponível em: https://doi.org/10.5281/zenodo.21286115.

## Atualizações Recentes (v1.0.2)
- Integrado cotação em tempo real da Soja (Mercado de Futuros CBOT).
- Conversão orgânica automática da cotação usando API AwesomeAPI (USD/BRL).
- Correção de codificação dos nomes das cidades, permitindo exibição correta com acentos (ex: Santarém, Paragominas).
