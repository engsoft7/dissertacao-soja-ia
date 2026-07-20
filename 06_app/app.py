# -*- coding: utf-8 -*-
"""
Painel de estimativa da produtividade da soja nos municípios do Pará.

Execução:
    streamlit run app.py
"""
import json
import math
import sys
from pathlib import Path

import altair as alt
import branca.colormap as cm
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model as M

DADOS = Path(__file__).resolve().parents[1] / "dados" / "soja_para_mascarado_2001_2024.csv"
DATA_ATUALIZACAO = DADOS.parent / "ultima_atualizacao.txt"
METRICAS_SALVAS = DADOS.parent / "metricas_validacao.json"
MUNICIPIOS = DADOS.parent / "municipios_para.csv"
GEO_PARA = DADOS.parent / "para_geo.json"
RIOS_PARA = DADOS.parent / "rios_para.json"
SACA_KG = 60  # saca de soja


@st.cache_data
def carregar_geo():
    """Contorno do Pará (GeoJSON do IBGE) para o fundo do mapa. None se faltar."""
    try:
        return json.loads(GEO_PARA.read_text(encoding="utf-8"))
    except OSError:
        return None


@st.cache_data
def carregar_rios():
    """Principais rios do Pará (Natural Earth, recortado) para o mapa. None se faltar."""
    try:
        return json.loads(RIOS_PARA.read_text(encoding="utf-8"))
    except OSError:
        return None


@st.cache_data
def carregar_municipios():
    """Nome oficial acentuado (IBGE) e centroide de cada município, por cod_ibge7.

    A base bruta vem do GAUL, sem acentos; este arquivo (gerado por
    07_automacao/gera_municipios.py) devolve a grafia oficial e as coordenadas
    para o mapa. Se faltar, o painel cai para os nomes sem acento e omite o mapa.
    """
    try:
        return pd.read_csv(MUNICIPIOS)
    except OSError:
        return pd.DataFrame(columns=["cod_ibge7", "municipio", "latitude", "longitude"])


def data_atualizacao() -> str | None:
    """Data da última atualização da base, gravada pela automação (dd/mm/aaaa)."""
    try:
        ano, mes, dia = DATA_ATUALIZACAO.read_text().strip().split("-")
        return f"{dia}/{mes}/{ano}"
    except (OSError, ValueError):
        return None

st.set_page_config(page_title="Soja no Pará — estimativa de produtividade",
                   page_icon="🌱", layout="wide")


@st.cache_resource(show_spinner="Preparando o modelo...")
def preparar():
    df = M.carregar(str(DADOS))
    est = M.Estimador().treinar(df)

    # A validação leave-one-year-out é cara (um modelo por ano-safra). A
    # automação a pré-calcula em dados/metricas_validacao.json; o painel só a
    # refaz se o arquivo estiver ausente ou defasado em relação ao CSV.
    metricas = None
    try:
        salvas = json.loads(METRICAS_SALVAS.read_text(encoding="utf-8"))
        if salvas.get("registros") == len(df):
            est.rmse, est.mae = salvas["rmse"], salvas["mae"]
            est.r2, est.r2_baseline = salvas["r2"], salvas["r2_baseline"]
            metricas = salvas
    except (OSError, ValueError, KeyError):
        metricas = None
    if metricas is None:
        metricas = est.validar(df)
    return df, est, metricas


df, estimador, metricas = preparar()

# Nome acentuado por município (interno = sem acento, vindo do GAUL). O mapa e
# a exibição usam a grafia oficial; a lógica continua usando o nome interno.
_muni = carregar_municipios()
_cod_por_nome = df.drop_duplicates("municipio").set_index("municipio")["cod_ibge7"].to_dict()
_nome_por_cod = _muni.set_index("cod_ibge7")["municipio"].to_dict()
NOME_EXIBICAO = {m: _nome_por_cod.get(_cod_por_nome.get(m), m) for m in df.municipio.unique()}

def disp(municipio: str) -> str:
    """Nome do município na grafia oficial acentuada (para exibição)."""
    return NOME_EXIBICAO.get(municipio, municipio)

_interno_por_cod = {c: n for n, c in _cod_por_nome.items()}

# Dicionário reverso para o clique do mapa funcionar sem erros de renderização
EXIBICAO_PARA_INTERNO = {disp(m): m for m in df.municipio.unique()}

@st.cache_data
def _soja_por_municipio():
    """Área plantada e produtividade médias recentes (2020+) por município, com
    coordenadas — base dos pontos do mapa. Vazio se faltarem as coordenadas."""
    if _muni.empty:
        return pd.DataFrame()
    recente = df[df.ano >= df.ano.max() - 4]
    agg = (recente.groupby("cod_ibge7")
           .agg(area=("soy_area_ha", "mean"), rend=(M.ALVO, "mean"))
           .reset_index())
    return agg.merge(_muni, on="cod_ibge7", how="inner")


_VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]


def construir_mapa(sel_interno: str):
    """Mapa interativo do Pará (Leaflet/folium): contorno + rios + municípios.

    Permite **dar zoom, arrastar e clicar** (pinça no celular) — o zoom facilita
    acertar o ponto. Cada município produtor é um círculo dimensionado pela área
    plantada e colorido pela produtividade média recente; os rios principais dão
    contexto e o selecionado ganha um anel vermelho. O Leaflet ajusta o
    enquadramento ao Pará em qualquer tela. Devolve (mapa, dict nome→interno,
    (rend_min, rend_max)) para o clique e a legenda, ou (None, {}, None) se
    faltarem os dados.
    """
    geo = carregar_geo()
    pts = _soja_por_municipio()
    if geo is None or pts.empty:
        return None, {}, None
    cod_sel = _cod_por_nome.get(sel_interno)
    latmin, latmax = pts.latitude.min(), pts.latitude.max()
    lonmin, lonmax = pts.longitude.min(), pts.longitude.max()

    m = folium.Map(location=[(latmin + latmax) / 2, (lonmin + lonmax) / 2],
                   tiles="cartodbpositron", zoom_start=6, control_scale=True)
    folium.GeoJson(geo, name="Pará", interactive=False, style_function=lambda f: {
        "fillColor": "#2E7D32", "color": "#6f9f6f", "weight": 1.2,
        "fillOpacity": 0.06}).add_to(m)
    rios = carregar_rios()
    if rios is not None and rios.get("features"):
        folium.GeoJson(rios, name="Rios", interactive=False, style_function=lambda f: {
            "color": "#4a90d9", "weight": 1.3, "opacity": 0.85}).add_to(m)

    rmin, rmax = float(pts.rend.min()), float(pts.rend.max())
    cmap = cm.LinearColormap(_VIRIDIS, vmin=rmin, vmax=rmax)
    amax = float(pts.area.max())
    nome_para_interno = {}
    for r in pts.itertuples():
        nome = disp(r.municipio)
        nome_para_interno[nome] = r.municipio
        selec = r.cod_ibge7 == cod_sel
        
        # AQUI É O SEGREDO DO CLIQUE ÚNICO: Removemos o popup, usamos só o tooltip.
        folium.CircleMarker(
            location=[r.latitude, r.longitude],
            radius=4 + 14 * math.sqrt(r.area / amax),
            color="#B00020" if selec else "white",
            weight=3 if selec else 0.7,
            fill=True, fill_color=cmap(r.rend), fill_opacity=0.9,
            tooltip=nome
        ).add_to(m)
    m.fit_bounds([[latmin, lonmin], [latmax, lonmax]])
    return m, nome_para_interno, (rmin, rmax)


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
    """Formata um valor de produtividade (kg/ha) na unidade escolhida, em pt-BR."""
    if unidade == "kg/ha":
        return f"{v * fator:{sinal},.0f}".replace(",", ".")
    return f"{v * fator:{sinal}.1f}".replace(".", ",")


def br(v: float) -> str:
    """Inteiro com separador de milhar brasileiro (ponto)."""
    return f"{v:,.0f}".replace(",", ".")


def brl(v: float, dec: int = 0) -> str:
    """Valor em reais no formato brasileiro (R$ 1.234,56)."""
    s = f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + s


# Custo de produção da soja — referência CONAB (custos de produção agrícola,
# safra 2025/26). A CONAB NÃO publica custo para o Pará; usa-se a referência
# mais próxima, no cerrado do Tocantins vizinho (Pedro Afonso-TO):
# R$ 4.248,78 variável + R$ 1.138,87 fixo por hectare. O Pará não integra o
# MATOPIBA (MA, TO, PI, BA); Tocantins é apenas o vizinho geográfico do sul do PA.
CUSTO_HA_REFERENCIA = 5388.0


# Eixos do Vega-Lite usam o padrão americano; converte o rótulo para pt-BR.
EIXO_BR = alt.Axis(labelExpr="replace(format(datum.value, ',.0f'), /,/g, '.')")


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

# ==============================================================================
# LÓGICA DE SINCRONIZAÇÃO DO MAPA COM O SELECTBOX (Evita piscar/duplo clique)
# ==============================================================================
municipios = sorted(df.municipio.unique())

if "mun_sel" not in st.session_state:
    st.session_state.mun_sel = "Paragominas" if "Paragominas" in municipios else municipios[0]

if "ultimo_clique_mapa" not in st.session_state:
    st.session_state.ultimo_clique_mapa = disp(st.session_state.mun_sel)

# Lemos o estado do mapa ANTES de renderizar a interface para sincronizar em 1 passe
if "mapa_soja" in st.session_state and st.session_state.mapa_soja:
    clicado = st.session_state.mapa_soja.get("last_object_clicked_tooltip")
    if clicado and clicado != st.session_state.ultimo_clique_mapa:
        interno = EXIBICAO_PARA_INTERNO.get(clicado)
        if interno:
            st.session_state.mun_sel = interno
            st.session_state.ultimo_clique_mapa = clicado

def ao_mudar_dropdown():
    st.session_state.ultimo_clique_mapa = disp(st.session_state.mun_sel)
# ==============================================================================

esq, dir_ = st.columns([1, 2])

with esq:
    municipio = st.selectbox("Município", municipios, key="mun_sel", format_func=disp, on_change=ao_mudar_dropdown)
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

    with st.expander("Simular cenário climático para a safra"):
        chuva = st.slider("Chuva na janela da safra (% da média do município)",
                          50, 150, 100, step=5)
        dtemp = st.slider("Temperatura (desvio da média, em °C)",
                          -2.0, 3.0, 0.0, step=0.5)
        if chuva == 100 and dtemp == 0.0:
            st.caption(
                "Mova os controles para ver o efeito de uma safra mais seca ou "
                "chuvosa, mais quente ou mais amena, sobre a estimativa."
            )
        else:
            hist = df[df.municipio == municipio]
            clima = hist[M.FEATURES].mean().to_dict()
            clima["precip_total"] *= chuva / 100
            clima["temp_mean"] += dtemp
            clima["temp_max"] += dtemp
            clima["balanco_hidrico"] = clima["precip_total"] - clima["etp_total"]
            cenario = estimador.estimar(municipio, int(ano_alvo), clima=clima)
            dif = cenario["estimativa_kg_ha"] - r["estimativa_kg_ha"]
            st.metric("Estimativa no cenário",
                      f"{qtd(cenario['estimativa_kg_ha'])} {unidade}",
                      delta=f"{qtd(dif, '+')} {unidade}")
            if abs(dif) < 0.1 * r["margem_kg_ha"]:
                st.info(
                    "**O efeito é praticamente nulo — e isso é um resultado, não um "
                    "defeito.** A correção climática que o modelo aprendeu é fraca "
                    "porque a produtividade oficial (PAM) pouco reflete o clima "
                    "observado: cerca de 40% dos valores municipais repetem a safra "
                    "anterior (seção 6.4 da dissertação). O cenário também não altera "
                    "os índices de vegetação (NDVI/EVI), que numa seca real cairiam."
                )
            st.caption(
                "O cenário altera chuva, temperatura e balanço hídrico; NDVI/EVI "
                "permanecem nas médias históricas do município."
            )

    with st.expander("Análise econômica (margem por hectare)"):
        _serie_mun = df[df.municipio == municipio].sort_values("ano")
        area_ha = float(_serie_mun.iloc[-1]["soy_area_ha"]) if len(_serie_mun) else 0.0
        est_sacas_ha = r["estimativa_kg_ha"] / SACA_KG

        preco = st.number_input(
            "Preço da soja (R$/saca de 60 kg)", min_value=0.0, value=120.0, step=5.0,
            help="Informe o preço praticado na sua região. Não há série pública de preço "
                 "ao produtor específica do Pará, por isso este valor é fornecido por você.",
        )
        custo_ha = st.number_input(
            "Custo de produção (R$/hectare)", min_value=0.0, value=CUSTO_HA_REFERENCIA, step=100.0,
            help="A CONAB não publica custo de produção para o Pará. Este valor de partida "
                 "vem da referência mais próxima — o cerrado do Tocantins vizinho (Pedro "
                 "Afonso-TO, safra 2025/26). Ajuste para a realidade do seu município.",
        )

        receita_ha = est_sacas_ha * preco
        margem_ha = receita_ha - custo_ha

        m1, m2, m3 = st.columns(3)
        m1.metric("Receita bruta/ha", brl(receita_ha))
        m2.metric("Custo/ha", brl(custo_ha))
        m3.metric("Margem/ha", brl(margem_ha),
                  delta=(f"{margem_ha / custo_ha * 100:+.0f}% sobre o custo" if custo_ha else None))

        prod_t = r["estimativa_kg_ha"] * area_ha / 1000
        prod_sacas = r["estimativa_kg_ha"] * area_ha / SACA_KG
        st.caption(
            f"**Produção estimada em {disp(municipio)} para {ano_alvo}: {br(prod_t)} t "
            f"({br(prod_sacas)} sacas).** Considera {br(area_ha)} ha da máscara MapBiomas × "
            f"a produtividade estimada. Margem total ≈ **{brl(margem_ha * area_ha)}**."
        )
        st.caption(
            "Preço informado por você; custo de referência da CONAB para o cerrado do "
            "Tocantins vizinho (o Pará não integra o MATOPIBA e não tem custo publicado). "
            "Os valores herdam a margem de erro do modelo — trate-os como ordem de grandeza."
        )

# --------------------------------------------------------- série e qualidade
serie = df[df.municipio == municipio].sort_values("ano")
diag = M.diagnostico_pam(df, municipio)

with dir_:
    mapa, nome_para_interno, faixa_rend = construir_mapa(municipio)
    if mapa is not None:
        st.subheader("Soja no Pará por município")
        
        # O MAPA COM CHAVE ESTÁTICA - Acaba de vez com a renderização em loop do st.rerun
        st_folium(
            mapa, 
            use_container_width=True, 
            height=430,
            returned_objects=["last_object_clicked_tooltip"],
            key="mapa_soja"
        )
        
        # Legenda de cor em HTML (compacta e responsiva)
        grad = ",".join(_VIRIDIS)
        st.markdown(
            f"""<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;
                 font-size:0.82rem;margin:2px 0 6px">
              <span style="opacity:.75">Produtividade</span>
              <span>{br(faixa_rend[0])}</span>
              <div style="flex:0 1 150px;height:12px;border-radius:3px;
                   background:linear-gradient(to right,{grad})"></div>
              <span>{br(faixa_rend[1])} kg/ha</span>
            </div>""",
            unsafe_allow_html=True)
        st.caption(f"**Dê zoom e clique num ponto** para escolher o município "
                   f"(ou use o menu à esquerda). **Tamanho** = área plantada, "
                   f"**cor** = produtividade; em azul, os principais rios; com "
                   f"anel vermelho, **{disp(municipio)}**.")

    st.subheader("Produtividade observada (PAM/IBGE)")
    serie_plot = serie.assign(
        produtividade=serie[M.ALVO] * fator,
        produtividade_rotulo=[qtd(v) for v in serie[M.ALVO]],
        area_rotulo=[br(a) for a in serie["soy_area_ha"]],
        repetido=serie[M.ALVO].diff().eq(0).fillna(False),
    )
    linha = alt.Chart(serie_plot).mark_line(point=True, color="#2E75B6").encode(
        x=alt.X("ano:O", title="Ano-safra"),
        y=alt.Y("produtividade:Q", title=unidade, scale=alt.Scale(zero=False), axis=EIXO_BR),
        tooltip=["ano", alt.Tooltip("produtividade_rotulo:N", title=unidade)],
    )
    marcas = alt.Chart(serie_plot[serie_plot.repetido]).mark_point(
        size=110, color="#B00020", filled=True
    ).encode(x="ano:O", y="produtividade:Q",
             tooltip=[alt.Tooltip("ano", title="Valor idêntico ao ano anterior")])
    st.altair_chart(linha + marcas, width='stretch')
    st.caption("Pontos em vermelho: safras cuja produtividade repete exatamente o valor do ano anterior.")

    st.subheader("Área de soja mapeada (MapBiomas)")
    area = alt.Chart(serie_plot).mark_area(
        color="#2E7D32", opacity=0.25, line={"color": "#2E7D32", "strokeWidth": 2},
    ).encode(
        x=alt.X("ano:O", title="Ano-safra"),
        y=alt.Y("soy_area_ha:Q", title="hectares", axis=EIXO_BR),
        tooltip=["ano", alt.Tooltip("area_rotulo:N", title="hectares")],
    )
    st.altair_chart(area, width='stretch')
    st.caption("Área com soja identificada pela máscara anual do MapBiomas dentro do município.")

    # Restaurados os botões de download!
    b1, b2 = st.columns(2)
    b1.download_button("Baixar série do município (CSV)",
                       serie.to_csv(index=False).encode("utf-8"),
                       file_name=f"soja_{municipio.lower().replace(' ', '_')}.csv",
                       mime="text/csv", width='stretch')
    b2.download_button("Baixar base completa (CSV)", DADOS.read_bytes(),
                       file_name=DADOS.name, mime="text/csv", width='stretch')

st.divider()

# ------------------------------------------------- alerta de qualidade do dado
# Restaurado integralmente o alerta de qualidade
st.subheader("Qualidade da variável oficial")
taxa_estado = M.taxa_repeticao_estadual(df)

a, b, c = st.columns(3)
a.metric("Repetição neste município", f"{diag['taxa']:.0f}%",
         help="Proporção de safras consecutivas com produtividade idêntica.")
b.metric("Maior sequência", f"{diag['maior_sequencia']} anos")
c.metric("Média do estado", f"{taxa_estado:.1f}%")

if diag["taxa"] >= taxa_estado:
    st.warning(
        f"**Atenção.** Em {disp(municipio)}, {diag['repetidos']} de {diag['pares']} pares de safras "
        f"consecutivas registram produtividade rigorosamente idêntica "
        f"(anos: {', '.join(map(str, diag['anos_repetidos']))}). "
        "A Produção Agrícola Municipal não mede a produtividade: ela é estimada pelo agente de "
        "coleta do IBGE a partir de contatos locais. Onde a rede de informantes é rarefeita, é "
        "plausível que o valor da safra anterior seja reconduzido. **Trate a estimativa deste "
        "município com cautela adicional**, pois o modelo é calibrado sobre esses valores."
    )
else:
    st.success(
        f"Em {disp(municipio)}, a repetição de valores ({diag['taxa']:.0f}%) está abaixo da média "
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

st.divider()

# ------------------------------------------------------ panorama do estado
st.subheader("Panorama dos municípios")
ult_ano = int(df.ano.max())
linhas_pan = []
for mun, d in df.groupby("municipio"):
    d = d.sort_values("ano")
    ult5 = d[d.ano > ult_ano - 5]
    difs = d[M.ALVO].diff().dropna()
    linhas_pan.append({
        "Município": disp(mun),
        "prod_media": ult5[M.ALVO].mean() * fator,
        "area_ha": float(d.iloc[-1]["soy_area_ha"]),
        "repeticao": float((difs == 0).mean() * 100) if len(difs) else 0.0,
        "safras": len(d),
    })
casas_pan = "%.0f" if unidade == "kg/ha" else "%.1f"
pan = pd.DataFrame(linhas_pan).sort_values("prod_media", ascending=False)
st.dataframe(
    pan, hide_index=True, width='stretch',
    column_config={
        "prod_media": st.column_config.NumberColumn(
            f"Produtividade média {ult_ano - 4}–{ult_ano} ({unidade})", format=casas_pan),
        "area_ha": st.column_config.NumberColumn("Área de soja recente (ha)", format="localized"),
        "repeticao": st.column_config.NumberColumn("Repetição na PAM (%)", format="%.0f%%"),
        "safras": st.column_config.NumberColumn("Safras na base"),
    },
)
st.caption(
    "Clique nos cabeçalhos para ordenar. Produtividade média das últimas cinco "
    "safras disponíveis; área de soja do ano mais recente do município (MapBiomas)."
)

# Restaurado integralmente o texto de autoria
with st.expander("Sobre este painel"):
    st.markdown(
        """
Produto técnico da dissertação **Aplicação da Inteligência Artificial na
Previsão da Produtividade da Soja** — Mestrado Profissional em Computação
Aplicada (PPCA/UFPA, Campus de Tucuruí).

**Autor:** Maycon Lima dos Santos · **Orientador:** Prof. Dr. Caio Carvalho
Moreira · **Ano:** 2026

**Metodologia, em resumo:** a estimativa combina a média histórica do município
e a tendência tecnológica com uma correção climática aprendida por rede neural
(MLP) sobre NDVI/EVI (MODIS), chuva (CHIRPS) e clima (ERA5-Land), restritos à
área de soja da máscara anual do MapBiomas. A validação é temporal
(*leave-one-year-out*) e a margem de erro exibida é o RMSE dessa validação.
Detalhes na seção 6 da dissertação.

**Código e dados:** [github.com/engsoft7/dissertacao-soja-ia](https://github.com/engsoft7/dissertacao-soja-ia)
· DOI [10.5281/zenodo.21286115](https://doi.org/10.5281/zenodo.21286115)

**Como citar:** SANTOS, Maycon Lima dos. *Aplicação da Inteligência Artificial
na Previsão da Produtividade da Soja: códigos e dados*. Zenodo, 2026.
DOI: 10.5281/zenodo.21286115.
"""
    )

st.caption(
    "Código e dados: https://github.com/engsoft7/dissertacao-soja-ia · "
    "Este painel não substitui levantamentos de campo."
)
