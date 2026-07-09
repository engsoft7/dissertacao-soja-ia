# Aplicação da Inteligência Artificial na Previsão da Produtividade da Soja

Códigos e dados da dissertação de Mestrado Profissional em Computação Aplicada
(PPCA/UFPA — Campus de Tucuruí).

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
06_app/
  model.py                                núcleo do painel (produto técnico)
  app.py                                  interface Streamlit
  README.md                               como executar e limitações
dados/
  soja_para_mascarado_2001_2024.csv       base principal (415 registros)
  soja_para_sem_mascara_2001_2023.csv     base sem máscara (comparação)
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

**Revisão sistemática**

```bash
cd 02_revisao_sistematica
python 01_busca_bases_abertas.py        # regenera os números do PRISMA
python 02_recupera_autoria_crossref.py  # autoria via DOI
```

Os resultados variam conforme a data da busca, pois as bases são atualizadas
continuamente. A busca reportada na dissertação foi executada em 9 de julho de 2026.

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

## Como citar

> SANTOS, M. L. dos. *Aplicação da Inteligência Artificial na previsão da
> produtividade da soja*. 2026. Dissertação (Mestrado Profissional em Computação
> Aplicada) — Universidade Federal do Pará, Tucuruí, 2026.
