# -*- coding: utf-8 -*-
"""
Painel de estimativa da produtividade da soja nos municípios do Pará.

Execução:
    streamlit run app.py
"""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model as M

DADOS = Path(__file__).resolve().parents[1] / "dados" / "soja_para_mascarado_2001_2024.csv"
DATA_ATUALIZACAO = DADOS.parent / "ultima_atualizacao.txt"
SACA_KG = 60  # saca de soja


def data_atualizacao() -> str | None:
    """Data da última atualização da base, gravada pela automação (dd/mm/aaaa)."""
    try:
        ano, mes, dia = DATA_ATUALIZACAO.read_text().strip().split("-")
        return f"{dia}/{mes}/{ano}"
    except (OSError, ValueError):
        return None

st.set_page_config(page_title="Soja no Pará — estimativa de produtividade",
                   page_icon="🌱", layout="wide")


@st.cache_resource(show_spinner="Treinando e validando o modelo...")
def preparar():
    df = M.carregar(str(DADOS))
    est = M.Estimador().treinar(df)
    metricas = est.validar(df)
    return df, est, metricas


df, estimador, metricas = preparar()

# ------------------------------------------------------------------ cabeçalho
st.title("Estimativa da produtividade da soja — municípios do Pará")
atualizada_em = data_atualizacao()
st.caption(
    f"Base de {len(df)} registros município-safra · {df.municipio.nunique()} municípios · "
    f"{df.ano.min()}–{df.ano.max()} · Fontes: IBGE (PAM), MODIS, CHIRPS, ERA5-Land, MapBiomas"
    + (f" · Dados atualizados em {atualizada_em}" if atualizada_em else "")
)

unidade = st.radio(
    "Unidade de produtividade", ["kg/ha", "sc/ha"], horizontal=True,
    help="sc/ha = sacas de 60 kg por hectare. A conversão é apenas de exibição; "
         "o modelo opera em kg/ha.",
)
fator = 1 if unidade == "kg/ha" else 1 / SACA_KG


def qtd(v: float, sinal: str = "") -> str:
    """Formata um valor de produtividade (kg/ha) na unidade escolhida."""
    casas = 0 if unidade == "kg/ha" else 1
    return f"{v * fator:{sinal}.{casas}f}"


c1, c2, c3, c4 = st.columns(4)
c1.metric("Erro do modelo (RMSE)", f"{qtd(metricas['rmse'])} {unidade}",
          help="Validação leave-one-year-out: cada safra é prevista por um modelo treinado sem ela.")
c2.metric("Erro relativo", f"{metricas['rrmse']:.1f}%")
c3.metric("R²", f"{metricas['r2']:.3f}")
c4.metric("R² do baseline", f"{metricas['r2_baseline']:.3f}",
          help="Baseline: média histórica do município + tendência, sem clima nem NDVI.")

if abs(metricas["r2"] - metricas["r2_baseline"]) < 0.01:
    st.info(
        "**Leitura honesta dos resultados.** As variáveis climáticas e espectrais não superam "
        "o modelo de referência, construído apenas com o histórico de cada município e a "
        "tendência temporal. A causa está documentada abaixo: parte expressiva da variação "
        "interanual da produtividade oficial não é sinal agronômico."
    )

st.divider()

# ------------------------------------------------------------------- seleção
municipios = sorted(df.municipio.unique())
padrao = municipios.index("Paragominas") if "Paragominas" in municipios else 0
esq, dir_ = st.columns([1, 2])

with esq:
    municipio = st.selectbox("Município", municipios, index=padrao)
    ano_alvo = st.number_input("Safra a estimar", min_value=int(df.ano.max()) + 1,
                               max_value=int(df.ano.max()) + 3, value=int(df.ano.max()) + 1)

    r = estimador.estimar(municipio, int(ano_alvo))
    st.metric(f"Estimativa para {ano_alvo}", f"{qtd(r['estimativa_kg_ha'])} {unidade}",
              delta=f"± {qtd(r['margem_kg_ha'])} {unidade}", delta_color="off")
    st.caption(
        f"Intervalo: **{qtd(r['intervalo'][0])} a {qtd(r['intervalo'][1])} {unidade}**. "
        f"Variáveis ambientais: {r['origem_das_variaveis']}. "
        "A margem corresponde ao RMSE observado na validação temporal."
    )

    with st.expander("Como esta estimativa é composta"):
        st.write(f"- Referência (histórico + tendência): **{qtd(r['baseline_kg_ha'])} {unidade}**")
        st.write(f"- Correção climática do modelo: **{qtd(r['correcao_climatica_kg_ha'], '+')} {unidade}**")
        st.caption(
            "Sem dados climáticos da safra corrente, o modelo usa as médias históricas do "
            "município e a correção tende a zero. Para uso operacional, colete o NDVI e o "
            "clima da safra em curso com as rotinas de `01_coleta_dados/`."
        )

# --------------------------------------------------------- série e qualidade
serie = df[df.municipio == municipio].sort_values("ano")
diag = M.diagnostico_pam(df, municipio)

with dir_:
    st.subheader("Produtividade observada (PAM/IBGE)")
    fmt_grafico = ".0f" if unidade == "kg/ha" else ".1f"
    serie_plot = serie.assign(
        produtividade=serie[M.ALVO] * fator,
        repetido=serie[M.ALVO].diff().eq(0).fillna(False),
    )
    linha = alt.Chart(serie_plot).mark_line(point=True, color="#2E75B6").encode(
        x=alt.X("ano:O", title="Ano-safra"),
        y=alt.Y("produtividade:Q", title=unidade, scale=alt.Scale(zero=False)),
        tooltip=["ano", alt.Tooltip("produtividade", title=unidade, format=fmt_grafico)],
    )
    marcas = alt.Chart(serie_plot[serie_plot.repetido]).mark_point(
        size=110, color="#B00020", filled=True
    ).encode(x="ano:O", y="produtividade:Q",
             tooltip=[alt.Tooltip("ano", title="Valor idêntico ao ano anterior")])
    st.altair_chart(linha + marcas, width='stretch')
    st.caption("Pontos em vermelho: safras cuja produtividade repete exatamente o valor do ano anterior.")

st.divider()

# ------------------------------------------------- alerta de qualidade do dado
st.subheader("Qualidade da variável oficial")
taxa_estado = M.taxa_repeticao_estadual(df)

a, b, c = st.columns(3)
a.metric("Repetição neste município", f"{diag['taxa']:.0f}%",
         help="Proporção de safras consecutivas com produtividade idêntica.")
b.metric("Maior sequência", f"{diag['maior_sequencia']} anos")
c.metric("Média do estado", f"{taxa_estado:.1f}%")

if diag["taxa"] >= taxa_estado:
    st.warning(
        f"**Atenção.** Em {municipio}, {diag['repetidos']} de {diag['pares']} pares de safras "
        f"consecutivas registram produtividade rigorosamente idêntica "
        f"(anos: {', '.join(map(str, diag['anos_repetidos']))}). "
        "A Produção Agrícola Municipal não mede a produtividade: ela é estimada pelo agente de "
        "coleta do IBGE a partir de contatos locais. Onde a rede de informantes é rarefeita, é "
        "plausível que o valor da safra anterior seja reconduzido. **Trate a estimativa deste "
        "município com cautela adicional**, pois o modelo é calibrado sobre esses valores."
    )
else:
    st.success(
        f"Em {municipio}, a repetição de valores ({diag['taxa']:.0f}%) está abaixo da média "
        f"estadual ({taxa_estado:.1f}%). A série oficial apresenta variação interanual mais "
        "consistente com a variabilidade agronômica esperada."
    )

with st.expander("Por que este alerta existe"):
    st.markdown(
        f"""
Nos municípios paraenses, **{taxa_estado:.1f}%** dos pares de safras consecutivas da PAM/IBGE
apresentam produtividade rigorosamente idêntica — taxa cerca de três vezes superior à dos
estados produtores consolidados (12,9%) e situada a 11,8 desvios-padrão do esperado sob
aleatoriedade.

Nenhum modelo preditivo recupera variação que não existe no dado de referência. Por isso este
painel exibe a margem de erro em toda estimativa e sinaliza os municípios cuja série oficial
apresenta maior indício de recondução de valores.

Detalhamento na dissertação, seção 6.4, e no artigo correspondente.
"""
    )

st.caption(
    "Código e dados: https://github.com/engsoft7/dissertacao-soja-ia · "
    "Este painel não substitui levantamentos de campo."
)
