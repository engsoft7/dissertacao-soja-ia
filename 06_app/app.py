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

@st.cache_resource(show_spinner="Preparando o modelo...")
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


st.title("Estimativa da produtividade da soja — municípios do Pará")
atualizada_em = data_atualizacao()
st.caption(
    f"Base de {len(df)} registros município-safra · {df.municipio.nunique()} municípios · "
    f"{df.ano.min()}–{df.ano.max()} · Fontes: IBGE (PAM), MODIS, CHIRPS, ERA5-Land, MapBiomas"
    + (f" · Dados atualizados em {atualizada_em}" if atualizada_em else "")
)

unidade = st.radio("Unidade de produtividade", ["kg/ha", "sc/ha"], horizontal=True)
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

c1, c2, c3, c4 = st.columns(4)
c1.metric("Erro do modelo (RMSE)", f"{qtd(metricas['rmse'])} {unidade}")
c2.metric("Erro relativo", f"{metricas['rrmse']:.1f}%")
c3.metric("R²", f"{metricas['r2']:.3f}")
c4.metric("R² do baseline", f"{metricas['r2_baseline']:.3f}")

if abs(metricas["r2"] - metricas["r2_baseline"]) < 0.01:
    st.info("**Leitura honesta dos resultados.** As variáveis climáticas não superam o modelo de referência, construído apenas com histórico e tendência.")

st.divider()

# ==============================================================================
# LÓGICA DE SINCRONIZAÇÃO LIMPA E SEM CONFLITOS
# ==============================================================================
municipios = sorted(df.municipio.unique())

if "mun_sel" not in st.session_state:
    st.session_state.mun_sel = "Paragominas" if "Paragominas" in municipios else municipios[0]

# Se houver um clique pendente vindo do mapa, aplica no seletor antes dele renderizar
if "_clique_mapa" in st.session_state:
    st.session_state.mun_sel = st.session_state.pop("_clique_mapa")

esq, dir_ = st.columns([1, 2])

with esq:
    # O on_change conflituoso foi removido. O Selectbox funciona livremente.
    municipio = st.selectbox("Município Principal", municipios, key="mun_sel", format_func=disp)
    
    comparar = st.toggle("Comparar com outro município", value=False)
    mun_comp = None
    if comparar:
        opcoes_comp = [m for m in municipios if m != municipio]
        mun_comp = st.selectbox("Município Secundário", opcoes_comp, format_func=disp)
    
    st.write("") 
    ano_alvo = st.number_input("Safra a estimar (Mun. Principal)", min_value=int(df.ano.max()) + 1, max_value=int(df.ano.max()) + 3, value=int(df.ano.max()) + 1)

    r = estimador.estimar(municipio, int(ano_alvo))
    st.metric(f"Estimativa para {ano_alvo}", f"{qtd(r['estimativa_kg_ha'])} {unidade}", delta=f"± {qtd(r['margem_kg_ha'])} {unidade}", delta_color="off")

    with st.expander("Simular cenário climático"):
        chuva = st.slider("Chuva na janela da safra (% da média)", 50, 150, 100, step=5)
        dtemp = st.slider("Temperatura (desvio da média, em °C)", -2.0, 3.0, 0.0, step=0.5)
        if chuva != 100 or dtemp != 0.0:
            hist = df[df.municipio == municipio]
            clima = hist[M.FEATURES].mean().to_dict()
            clima["precip_total"] *= chuva / 100
            clima["temp_mean"] += dtemp
            clima["temp_max"] += dtemp
            clima["balanco_hidrico"] = clima["precip_total"] - clima["etp_total"]
            cenario = estimador.estimar(municipio, int(ano_alvo), clima=clima)
            dif = cenario["estimativa_kg_ha"] - r["estimativa_kg_ha"]
            st.metric("Estimativa no cenário", f"{qtd(cenario['estimativa_kg_ha'])} {unidade}", delta=f"{qtd(dif, '+')} {unidade}")

    with st.expander("Análise econômica (margem por hectare)"):
        _serie_mun = df[df.municipio == municipio].sort_values("ano")
        area_ha = float(_serie_mun.iloc[-1]["soy_area_ha"]) if len(_serie_mun) else 0.0
        est_sacas_ha = r["estimativa_kg_ha"] / SACA_KG

        preco = st.number_input("Preço da soja (R$/saca de 60 kg)", min_value=0.0, value=120.0, step=5.0)
        custo_ha = st.number_input("Custo de produção (R$/hectare)", min_value=0.0, value=CUSTO_HA_REFERENCIA, step=100.0)

        receita_ha = est_sacas_ha * preco
        margem_ha = receita_ha - custo_ha

        m1, m2, m3 = st.columns(3)
        m1.metric("Receita bruta/ha", brl(receita_ha))
        m2.metric("Custo/ha", brl(custo_ha))
        m3.metric("Margem/ha", brl(margem_ha), delta=(f"{margem_ha / custo_ha * 100:+.0f}% sobre o custo" if custo_ha else None))


if mun_comp:
    serie = df[df.municipio.isin([municipio, mun_comp])].sort_values(["municipio", "ano"])
else:
    serie = df[df.municipio == municipio].sort_values("ano")

diag = M.diagnostico_pam(df, municipio)

with dir_:
    mapa, nome_para_interno, faixa_rend = construir_mapa(municipio, mun_comp)
    if mapa is not None:
        st.subheader("Soja no Pará por município")
        
        saida = st_folium(
            mapa, 
            use_container_width=True, 
            height=430,
            returned_objects=["last_object_clicked_tooltip"],
            key="mapa_soja"
        )
        
        # AQUI O SEGREDO: Só atualiza se o mapa tiver gerado um clique NOVO
        clicado = (saida or {}).get("last_object_clicked_tooltip")
        if clicado:
            if clicado != st.session_state.get("last_processed_map_click"):
                st.session_state["last_processed_map_click"] = clicado
                interno = nome_para_interno.get(clicado)
                if interno and interno != st.session_state.mun_sel:
                    st.session_state["_clique_mapa"] = interno
                    st.rerun()
        
        grad = ",".join(_VIRIDIS)
        st.markdown(
            f"""<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap; font-size:0.82rem;margin:2px 0 6px">
              <span style="opacity:.75">Produtividade</span>
              <span>{br(faixa_rend[0])}</span>
              <div style="flex:0 1 150px;height:12px;border-radius:3px; background:linear-gradient(to right,{grad})"></div>
              <span>{br(faixa_rend[1])} kg/ha</span>
            </div>""",
            unsafe_allow_html=True)
        st.caption(f"**Clique num ponto** para selecioná-lo como município principal.")

    st.subheader("Produtividade observada (PAM/IBGE)")
    
    serie_plot = serie.assign(
        produtividade=serie[M.ALVO] * fator,
        produtividade_rotulo=[qtd(v) for v in serie[M.ALVO]],
        area_rotulo=[br(a) for a in serie["soy_area_ha"]],
        repetido=serie.groupby("municipio")[M.ALVO].diff().eq(0).fillna(False),
        Nome=[disp(m) for m in serie["municipio"]]
    )

    # GRÁFICO CORRIGIDO (O zero=False resolve o bug que espremia tudo na direita)
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
        color=alt.Color("Clima:N", scale=alt.Scale(domain=["El Niño", "La Niña"], range=["#d73027", "#4575b4"]), legend=alt.Legend(title="Eventos Climáticos", orient="bottom"))
    )

    grafico_prod = alt.layer(clima_chart, linha, tendencia, marcas).resolve_scale(color='independent')
    st.altair_chart(grafico_prod, use_container_width=True)
    
    st.caption("A linha tracejada indica a tendência tecnológica histórica. Faixas verticais marcam anos de fortes fenômenos climáticos. Pontos vermelhos indicam repetição cega de dados do IBGE.")

    st.subheader("Área de soja mapeada (MapBiomas)")
    area = alt.Chart(serie_plot).mark_area(opacity=0.4).encode(
        x=eixo_x_inteligente,
        y=alt.Y("soy_area_ha:Q", title="hectares", axis=EIXO_BR),
        color=alt.Color("Nome:N", legend=alt.Legend(title="Município", orient="bottom")),
        tooltip=["ano", "Nome", alt.Tooltip("area_rotulo:N", title="hectares")],
    )
    st.altair_chart(area, use_container_width=True)

    b1, b2 = st.columns(2)
    b1.download_button("Baixar série do município (CSV)", serie.to_csv(index=False).encode("utf-8"), file_name=f"soja_{municipio.lower().replace(' ', '_')}.csv", mime="text/csv", use_container_width=True)
    b2.download_button("Baixar base completa (CSV)", DADOS.read_bytes(), file_name=DADOS.name, mime="text/csv", use_container_width=True)

st.divider()

st.subheader("Qualidade da variável oficial (Mun. Principal)")
taxa_estado = M.taxa_repeticao_estadual(df)

a, b, c = st.columns(3)
a.metric("Repetição neste município", f"{diag['taxa']:.0f}%", help="Proporção de safras consecutivas com produtividade idêntica.")
b.metric("Maior sequência", f"{diag['maior_sequencia']} anos")
c.metric("Média do estado", f"{taxa_estado:.1f}%")

if diag["taxa"] >= taxa_estado:
    st.warning(f"**Atenção.** Em {disp(municipio)}, a Produção Agrícola Municipal apresenta forte recondução de valores (repetição de dados). Trate as estimativas históricas com cautela.")
else:
    st.success(f"Em {disp(municipio)}, a série oficial apresenta variação interanual consistente e abaixo da média estadual de repetição cega.")

st.divider()

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
        "prod_media": st.column_config.NumberColumn(f"Produtividade média {ult_ano - 4}–{ult_ano} ({unidade})", format=casas_pan),
        "area_ha": st.column_config.NumberColumn("Área de soja recente (ha)", format="localized"),
        "repeticao": st.column_config.NumberColumn("Repetição na PAM (%)", format="%.0f%%"),
        "safras": st.column_config.NumberColumn("Safras na base"),
    },
)

with st.expander("Sobre este painel"):
    st.markdown("""
Produto técnico da dissertação **Aplicação da Inteligência Artificial na Previsão da Produtividade da Soja** — Mestrado Profissional em Computação Aplicada (PPCA/UFPA).

**Autor:** Maycon Lima dos Santos · **Orientador:** Prof. Dr. Caio Carvalho Moreira · **Ano:** 2026

**Código e dados:** [github.com/engsoft7/dissertacao-soja-ia](https://github.com/engsoft7/dissertacao-soja-ia)
""")
