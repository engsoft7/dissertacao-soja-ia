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
    try:
        return json.loads(GEO_PARA.read_text(encoding="utf-8"))
    except OSError:
        return None

@st.cache_data
def carregar_rios():
    try:
        return json.loads(RIOS_PARA.read_text(encoding="utf-8"))
    except OSError:
        return None

@st.cache_data
def carregar_municipios():
    try:
        return pd.read_csv(MUNICIPIOS)
    except OSError:
        return pd.DataFrame(columns=["cod_ibge7", "municipio", "latitude", "longitude"])


def data_atualizacao() -> str | None:
    try:
        ano, mes, dia = DATA_ATUALIZACAO.read_text().strip().split("-")
        return f"{dia}/{mes}/{ano}"
    except (OSError, ValueError):
        return None

st.set_page_config(page_title="Soja no Pará — estimativa de produtividade", page_icon="🌱", layout="wide")

# Correção visual otimizada para tablets e telas menores (evita cortes nas métricas)
st.markdown("""
<style>
    [data-testid="stMetricLabel"] {
        font-size: 0.78rem !important;
        white-space: normal !important;
        overflow: visible !important;
        word-break: break-word !important;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner="Preparando o painel agrícola...")
def preparar():
    df = M.carregar(str(DADOS))
    est = M.Estimador().treinar(df)
    metricas = None
    try:
        salvas = json.loads(METRICAS_SALVAS.read_text(encoding="utf-8"))
        if salvas.get("registros") == len(df):
            est.rmse, est.mae = salvas["rmse"], salvas["mae"]
            est.r2, est.r2_baseline = salvas["r2"], salvas["r2_baseline"]
            metricas = salvas
    except (OSError, ValueError, KeyError):
        pass
    if metricas is None:
        metricas = est.validar(df)
    return df, est, metricas

df, estimador, metricas = preparar()

_muni = carregar_municipios()
_cod_por_nome = df.drop_duplicates("municipio").set_index("municipio")["cod_ibge7"].to_dict()
_nome_por_cod = _muni.set_index("cod_ibge7")["municipio"].to_dict()
NOME_EXIBICAO = {m: _nome_por_cod.get(_cod_por_nome.get(m), m) for m in df.municipio.unique()}

def disp(municipio: str) -> str:
    return NOME_EXIBICAO.get(municipio, municipio)

EXIBICAO_PARA_INTERNO = {disp(m): m for m in df.municipio.unique()}

@st.cache_data
def _soja_por_municipio():
    if _muni.empty:
        return pd.DataFrame()
    recente = df[df.ano >= df.ano.max() - 4]
    agg = (recente.groupby("cod_ibge7")
           .agg(area=("soy_area_ha", "mean"), rend=(M.ALVO, "mean"))
           .reset_index())
    return agg.merge(_muni, on="cod_ibge7", how="inner")

_VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]

def construir_mapa(sel_interno: str, comp_interno: str = None):
    geo = carregar_geo()
    pts = _soja_por_municipio()
    if geo is None or pts.empty:
        return None, {}, None
    
    cod_sel = _cod_por_nome.get(sel_interno)
    cod_comp = _cod_por_nome.get(comp_interno) if comp_interno else None
    
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
        
        selec_prin = (r.cod_ibge7 == cod_sel)
        selec_comp = (r.cod_ibge7 == cod_comp)
        
        cor_borda = "#B00020" if selec_prin else ("#2E75B6" if selec_comp else "white")
        peso_borda = 3.5 if (selec_prin or selec_comp) else 0.7
        
        folium.CircleMarker(
            location=[r.latitude, r.longitude],
            radius=4 + 14 * math.sqrt(r.area / amax),
            color=cor_borda,
            weight=peso_borda,
            fill=True, fill_color=cmap(r.rend), fill_opacity=0.9,
            tooltip=nome
        ).add_to(m)
        
    m.fit_bounds([[latmin, lonmin], [latmax, lonmax]])
    return m, nome_para_interno, (rmin, rmax)


st.title("🌱 Painel de Produtividade e Viabilidade da Soja — Pará")
atualizada_em = data_atualizacao()
st.caption(
    f"Base com {len(df)} registros · {df.municipio.nunique()} municípios analisados ({df.ano.min()}–{df.ano.max()}) · "
    f"Fontes: IBGE, MODIS, CHIRPS, ERA5-Land, MapBiomas"
    + (f" · Atualizado em {atualizada_em}" if atualizada_em else "")
)

unidade = st.radio("Unidade de medida preferida", ["sc/ha", "kg/ha"], horizontal=True)
fator = 1 if unidade == "kg/ha" else 1 / SACA_KG

def qtd(v: float, sinal: str = "") -> str:
    if unidade == "kg/ha": return f"{v * fator:{sinal},.0f}".replace(",", ".")
    return f"{v * fator:{sinal}.1f}".replace(".", ",")

def br(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")

def brl(v: float, dec: int = 0) -> str:
    s = f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + s

CUSTO_HA_REFERENCIA = 5388.0
EIXO_BR = alt.Axis(labelExpr="replace(format(datum.value, ',.0f'), /,/g, '.')")

# --- RESUMO EXECUTIVO PARA O PRODUTOR ---
with st.container(border=True):
    st.markdown("##### 🚜 Indicadores Gerais da Ferramenta")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Precisão Média (Margem de Erro)", f"± {qtd(metricas['rmse'])} {unidade}")
    c2.metric("Variação Média Relativa", f"{metricas['rrmse']:.1f}%")
    c3.metric("Aderência Histórica (R²)", f"{metricas['r2']:.3f}")
    c4.metric("Tendência Base", f"{metricas['r2_baseline']:.3f}")

st.divider()

# Sincronização limpa do mapa
municipios = sorted(df.municipio.unique())

if "mun_sel" not in st.session_state:
    st.session_state.mun_sel = "Paragominas" if "Paragominas" in municipios else municipios[0]

if "last_map_click" not in st.session_state:
    st.session_state.last_map_click = None

if "mapa_soja" in st.session_state and st.session_state.mapa_soja:
    current_map_click = st.session_state.mapa_soja.get("last_object_clicked_tooltip")
    if current_map_click and current_map_click != st.session_state.last_map_click:
        st.session_state.last_map_click = current_map_click
        interno = EXIBICAO_PARA_INTERNO.get(current_map_click)
        if interno and interno != st.session_state.mun_sel:
            st.session_state.mun_sel = interno

def on_dropdown_change():
    if "mapa_soja" in st.session_state and st.session_state.mapa_soja:
        st.session_state.last_map_click = st.session_state.mapa_soja.get("last_object_clicked_tooltip")

# Abas focadas na experiência do produtor
aba_mapa, aba_graficos, aba_eco = st.tabs([
    "🗺️ Mapa & Estimativa de Safra", 
    "📈 Histórico & Impacto Climático", 
    "💰 Contas da Lavoura & Confiabilidade"
])

# ==============================================================================
# ABA 1: MAPA E ESTIMATIVA
# ==============================================================================
with aba_mapa:
    esq, dir_ = st.columns([1, 2])
    with esq:
        municipio = st.selectbox("Escolha o Município", municipios, key="mun_sel", format_func=disp, on_change=on_dropdown_change)
        
        comparar = st.toggle("Comparar com outro município", value=False)
        mun_comp = None
        if comparar:
            opcoes_comp = [m for m in municipios if m != municipio]
            mun_comp = st.selectbox("Município para Comparação", opcoes_comp, format_func=disp)
        
        st.write("") 
        ano_alvo = st.number_input("Safra que deseja estimar", min_value=int(df.ano.max()) + 1, max_value=int(df.ano.max()) + 3, value=int(df.ano.max()) + 1)

        r = estimador.estimar(municipio, int(ano_alvo))
        st.metric(f"Previsão para {ano_alvo} ({disp(municipio)})", f"{qtd(r['estimativa_kg_ha'])} {unidade}", delta=f"Margem: ± {qtd(r['margem_kg_ha'])} {unidade}", delta_color="off")

        with st.expander("🌦️ Simular Clima na Safra"):
            chuva = st.slider("Volume de Chuva (% em relação à média)", 50, 150, 100, step=5)
            dtemp = st.slider("Desvio de Temperatura (°C)", -2.0, 3.0, 0.0, step=0.5)
            if chuva != 100 or dtemp != 0.0:
                hist = df[df.municipio == municipio]
                clima = hist[M.FEATURES].mean().to_dict()
                clima["precip_total"] *= chuva / 100
                clima["temp_mean"] += dtemp
                clima["temp_max"] += dtemp
                clima["balanco_hidrico"] = clima["precip_total"] - clima["etp_total"]
                cenario = estimador.estimar(municipio, int(ano_alvo), clima=clima)
                dif = cenario["estimativa_kg_ha"] - r["estimativa_kg_ha"]
                st.metric("Previsão Ajustada ao Clima", f"{qtd(cenario['estimativa_kg_ha'])} {unidade}", delta=f"{qtd(dif, '+')} {unidade}")

    with dir_:
        mapa, nome_para_interno, faixa_rend = construir_mapa(municipio, mun_comp)
        if mapa is not None:
            st.subheader("Panorama Produtivo no Estado")
            st_folium(
                mapa, 
                use_container_width=True, 
                height=430,
                returned_objects=["last_object_clicked_tooltip"],
                key="mapa_soja"
            )
            
            grad = ",".join(_VIRIDIS)
            st.markdown(
                f"""<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap; font-size:0.82rem;margin:2px 0 6px">
                  <span style="opacity:.75">Produtividade</span>
                  <span>{br(faixa_rend[0] * fator)} {unidade}</span>
                  <div style="flex:0 1 150px;height:12px;border-radius:3px; background:linear-gradient(to right,{grad})"></div>
                  <span>{br(faixa_rend[1] * fator)} {unidade}</span>
                </div>""",
                unsafe_allow_html=True)
            st.caption(f"**Dica:** Clique em qualquer bolinha no mapa para alternar o município selecionado (Vermelho = Principal | Azul = Comparação).")

# ==============================================================================
# ABA 2: SÉRIES HISTÓRICAS & CLIMA
# ==============================================================================
with aba_graficos:
    if mun_comp:
        serie = df[df.municipio.isin([municipio, mun_comp])].sort_values(["municipio", "ano"])
    else:
        serie = df[df.municipio == municipio].sort_values("ano")

    st.subheader("Evolução da Produtividade ao Longo dos Anos")
    
    serie_plot = serie.assign(
        produtividade=serie[M.ALVO] * fator,
        produtividade_rotulo=[qtd(v) for v in serie[M.ALVO]],
        area_rotulo=[br(a) for a in serie["soy_area_ha"]],
        repetido=serie.groupby("municipio")[M.ALVO].diff().eq(0).fillna(False),
        Nome=[disp(m) for m in serie["municipio"]]
    )

    eixo_x_inteligente = alt.X(
        "ano:Q", 
        title="Ano-safra", 
        scale=alt.Scale(zero=False), 
        axis=alt.Axis(format="d", tickMinStep=2)
    )

    base = alt.Chart(serie_plot).encode(x=eixo_x_inteligente)
    
    linha = base.mark_line(point=True).encode(
        y=alt.Y("produtividade:Q", title=unidade, scale=alt.Scale(zero=False), axis=EIXO_BR),
        color=alt.Color("Nome:N", legend=alt.Legend(title="Município", orient="bottom")),
        tooltip=["ano", "Nome", alt.Tooltip("produtividade_rotulo:N", title=unidade)],
    )
    
    tendencia = base.transform_regression("ano", "produtividade", groupby=["Nome"]).mark_line(
        strokeDash=[5, 5], strokeWidth=2, opacity=0.6
    ).encode(
        color=alt.Color("Nome:N", legend=None)
    )
    
    marcas = base.transform_filter(alt.datum.repetido == True).mark_point(
        size=110, filled=True, color="#B00020"
    ).encode(
        y="produtividade:Q",
        tooltip=[alt.Tooltip("ano", title="Valor idêntico ao ano anterior")]
    )

    df_clima = pd.DataFrame([
        {"ano": 2003, "Clima": "El Niño"}, {"ano": 2010, "Clima": "El Niño"},
        {"ano": 2015, "Clima": "El Niño"}, {"ano": 2016, "Clima": "El Niño"}, {"ano": 2024, "Clima": "El Niño"},
        {"ano": 2008, "Clima": "La Niña"}, {"ano": 2011, "Clima": "La Niña"}, 
        {"ano": 2021, "Clima": "La Niña"}, {"ano": 2022, "Clima": "La Niña"}
    ])
    clima_chart = alt.Chart(df_clima).mark_rule(size=8, opacity=0.3).encode(
        x=eixo_x_inteligente,
        color=alt.Color("Clima:N", scale=alt.Scale(domain=["El Niño", "La Niña"], range=["#d73027", "#4575b4"]), legend=alt.Legend(title="Anos de Forte Influência Climática", orient="bottom"))
    )

    grafico_prod = alt.layer(clima_chart, linha, tendencia, marcas).resolve_scale(color='independent')
    st.altair_chart(grafico_prod, use_container_width=True)
    st.caption("A linha tracejada mostra a evolução tecnológica da lavoura. As faixas destacam anos marcados por El Niño ou La Niña.")

    st.subheader("Crescimento da Área Plantada (Hectares)")
    area = alt.Chart(serie_plot).mark_area(opacity=0.4).encode(
        x=eixo_x_inteligente,
        y=alt.Y("soy_area_ha:Q", title="Hectares", axis=EIXO_BR),
        color=alt.Color("Nome:N", legend=alt.Legend(title="Município", orient="bottom")),
        tooltip=["ano", "Nome", alt.Tooltip("area_rotulo:N", title="Hectares")],
    )
    st.altair_chart(area, use_container_width=True)

    b1, b2 = st.columns(2)
    b1.download_button("Baixar histórico do município (CSV)", serie.to_csv(index=False).encode("utf-8"), file_name=f"soja_{municipio.lower().replace(' ', '_')}.csv", mime="text/csv", use_container_width=True)
    b2.download_button("Baixar base geral do estado (CSV)", DADOS.read_bytes(), file_name=DADOS.name, mime="text/csv", use_container_width=True)

# ==============================================================================
# ABA 3: ANÁLISE ECONÔMICA & QUALIDADE PAM
# ==============================================================================
with aba_eco:
    st.subheader("💰 Viabilidade Econômica por Hectare")
    r_eco = estimador.estimar(municipio, int(df.ano.max()) + 1)
    
    col_eco1, col_eco2 = st.columns(2)
    with col_eco1:
        preco = st.number_input("Preço de venda da saca (R$ / 60 kg)", min_value=0.0, value=120.0, step=5.0)
    with col_eco2:
        custo_ha = st.number_input("Custo estimado de produção (R$ / hectare)", min_value=0.0, value=CUSTO_HA_REFERENCIA, step=100.0)

    est_sacas_ha = r_eco["estimativa_kg_ha"] / SACA_KG
    receita_ha = est_sacas_ha * preco
    margem_ha = receita_ha - custo_ha

    m1, m2, m3 = st.columns(3)
    m1.metric("Faturamento Bruto / ha", brl(receita_ha))
    m2.metric("Custo Total / ha", brl(custo_ha))
    m3.metric("Margem Líquida / ha", brl(margem_ha), delta=(f"{margem_ha / custo_ha * 100:+.0f}% sobre o custo" if custo_ha else None))

    if margem_ha > 0:
        st.success(f"**Análise Financeira Prática:** Com base na produtividade estimada de **{qtd(r_eco['estimativa_kg_ha'])} {unidade}**, a lavoura em **{disp(municipio)}** cobre os custos operacionais e gera folga financeira estimada em **{brl(margem_ha)} por hectare**.")
    else:
        st.warning(f"**Atenção aos Custos:** No cenário atual de preços e custos informados, a margem para **{disp(municipio)}** fica no vermelho. É recomendado reavaliar negociações de insumos ou travar preços futuros.")

    st.divider()

    st.subheader("⚠️ Confiabilidade dos Dados Oficiais da Região")
    diag = M.diagnostico_pam(df, municipio)
    taxa_estado = M.taxa_repeticao_estadual(df)

    qa, qb, qc = st.columns(3)
    qa.metric("Repetição de dados locais", f"{diag['taxa']:.0f}%", help="Porcentagem de safras em que o órgão oficial repetiu o valor anterior sem variação.")
    qb.metric("Maior sequência travada", f"{diag['maior_sequencia']} safras")
    qc.metric("Média de repetição no Pará", f"{taxa_estado:.1f}%")

    if diag["taxa"] >= taxa_estado:
        st.warning(f"**Aviso Técnico:** Em **{disp(municipio)}**, os relatórios oficiais de órgãos do governo apresentam histórico com forte repetição mecânica de números. Utilize as estimativas com cautela analítica.")
    else:
        st.success(f"**Boa Qualidade de Registro:** Em **{disp(municipio)}**, a série oficial apresenta boa variação de safra para safra, ficando abaixo da média estadual de repetição.")

st.divider()

# ------------------------------------------------------ PANORAMA GERAL DO ESTADO COM RENTABILIDADE
st.subheader("📋 Panorama Geral e Ranking de Faturamento dos Polos Produtivos")
st.caption(f"Calculado com base no preço de referência de **{brl(preco)} por saca** informado na aba econômica.")

ult_ano = int(df.ano.max())
linhas_pan = []
for mun, d in df.groupby("municipio"):
    d = d.sort_values("ano")
    ult5 = d[d.ano > ult_ano - 5]
    difs = d[M.ALVO].diff().dropna()
    prod_med_kg = ult5[M.ALVO].mean()
    faturamento_bruto = (prod_med_kg / SACA_KG) * preco
    
    linhas_pan.append({
        "Município": disp(mun),
        "prod_media": prod_med_kg * fator,
        "faturamento": faturamento_bruto,
        "area_ha": float(d.iloc[-1]["soy_area_ha"]),
        "repeticao": float((difs == 0).mean() * 100) if len(difs) else 0.0,
        "safras": len(d),
    })

casas_pan = "%.0f" if unidade == "kg/ha" else "%.1f"
pan = pd.DataFrame(linhas_pan).sort_values("faturamento", ascending=False)

st.dataframe(
    pan, hide_index=True, width='stretch',
    column_config={
        "prod_media": st.column_config.NumberColumn(f"Média Recente ({ult_ano-4}–{ult_ano}) [{unidade}]", format=casas_pan),
        "faturamento": st.column_config.NumberColumn("Faturamento Bruto Est. (R$/ha)", format="localized"),
        "area_ha": st.column_config.NumberColumn("Área Atual (ha)", format="localized"),
        "repeticao": st.column_config.NumberColumn("Repetição Oficial (%)", format="%.0f%%"),
        "safras": st.column_config.NumberColumn("Total de Safras"),
    },
)

with st.expander("ℹ️ Sobre o Projeto e Metodologia"):
    st.markdown("""
Produto técnico da dissertação **Aplicação da Inteligência Artificial na Previsão da Produtividade da Soja** — Mestrado Profissional em Computação Aplicada (PPCA/UFPA).

**Autor:** Maycon Lima dos Santos · **Orientador:** Prof. Dr. Caio Carvalho Moreira · **Ano:** 2026

**Repositório Oficial:** [github.com/engsoft7/dissertacao-soja-ia](https://github.com/engsoft7/dissertacao-soja-ia)
""")
