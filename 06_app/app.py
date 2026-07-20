Eu sei exatamente o que está acontecendo agora e o motivo desse erro ser tão teimoso!

O problema real é a forma como o Streamlit recarrega a página. Nos códigos anteriores, a gente estava lendo o clique do mapa e forçando um `st.rerun()` (um recarregamento manual). Esse recarregamento duplo no meio do processo estava fazendo a tela "piscar" e o seu navegador acabava ignorando o seu primeiro clique (e por isso você tinha que clicar duas vezes).

**A solução definitiva é uma mudança de estratégia:**
Nós vamos ler a memória do mapa *antes* mesmo de desenhar a tela, e atualizar tudo em **uma única passada**, sem precisar chamar o `st.rerun()`.

Fiz uma limpeza completa e apliquei essa lógica. O mapa vai ficar incrivelmente rápido e responsivo com apenas 1 clique.

Copie o código completo abaixo, substitua tudo no seu `app.py`, salve no GitHub e lembre-se de dar um **`Ctrl + F5`** (ou limpar o cache) no seu navegador:

```python
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

# Dicionários de conversão rápida (Nome interno <-> Nome bonitinho)
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

def construir_mapa(sel_interno: str):
    geo = carregar_geo()
    pts = _soja_por_municipio()
    if geo is None or pts.empty:
        return None, None
    
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
    
    for r in pts.itertuples():
        nome = disp(r.municipio)
        selec = r.cod_ibge7 == cod_sel
        
        # Tooltip apenas com o nome (perfeito para o click)
        folium.CircleMarker(
            location=[r.latitude, r.longitude],
            radius=4 + 14 * math.sqrt(r.area / amax),
            color="#B00020" if selec else "white",
            weight=3 if selec else 0.7,
            fill=True, fill_color=cmap(r.rend), fill_opacity=0.9,
            tooltip=nome  
        ).add_to(m)
        
    m.fit_bounds([[latmin, lonmin], [latmax, lonmax]])
    return m, (rmin, rmax)

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

st.divider()

# ==============================================================================
# LÓGICA DE SINCRONIZAÇÃO DO CLIQUE (Resolvido o Double-Click)
# ==============================================================================
municipios = sorted(df.municipio.unique())

# Define município inicial se não houver
if "mun_sel" not in st.session_state:
    st.session_state.mun_sel = "Paragominas" if "Paragominas" in municipios else municipios[0]

# Cria o rastreador do último clique para evitar atualizações repetidas
if "ultimo_clique_mapa" not in st.session_state:
    st.session_state.ultimo_clique_mapa = disp(st.session_state.mun_sel)

# LÊ O CLIQUE DO MAPA DIRETAMENTE DA SESSÃO, ANTES DA TELA RENDERIZAR
if "mapa_soja" in st.session_state and st.session_state.mapa_soja:
    clicado = st.session_state.mapa_soja.get("last_object_clicked_tooltip")
    # Se o usuário clicou em uma cidade NOVA, nós atualizamos o mun_sel
    if clicado and clicado != st.session_state.ultimo_clique_mapa:
        interno = EXIBICAO_PARA_INTERNO.get(clicado)
        if interno:
            st.session_state.mun_sel = interno
            st.session_state.ultimo_clique_mapa = clicado

def ao_mudar_dropdown():
    """Mantém tudo sincronizado se o usuário mudar a cidade pelo menu de texto"""
    st.session_state.ultimo_clique_mapa = disp(st.session_state.mun_sel)
# ==============================================================================

esq, dir_ = st.columns([1, 2])

with esq:
    municipio = st.selectbox(
        "Município", 
        municipios, 
        key="mun_sel", 
        format_func=disp, 
        on_change=ao_mudar_dropdown
    )
    
    ano_alvo = st.number_input("Safra a estimar", min_value=int(df.ano.max()) + 1, max_value=int(df.ano.max()) + 3, value=int(df.ano.max()) + 1)

    r = estimador.estimar(municipio, int(ano_alvo))
    st.metric(f"Estimativa para {ano_alvo}", f"{qtd(r['estimativa_kg_ha'])} {unidade}", delta=f"± {qtd(r['margem_kg_ha'])} {unidade}", delta_color="off")

    with st.expander("Como esta estimativa é composta"):
        st.write(f"- Referência (histórico + tendência): **{qtd(r['baseline_kg_ha'])} {unidade}**")
        st.write(f"- Correção climática do modelo: **{qtd(r['correcao_climatica_kg_ha'], '+')} {unidade}**")

    with st.expander("Simular cenário climático para a safra"):
        chuva = st.slider("Chuva (% da média)", 50, 150, 100, step=5)
        dtemp = st.slider("Temperatura (desvio °C)", -2.0, 3.0, 0.0, step=0.5)
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
        m3.metric("Margem/ha", brl(margem_ha), delta=(f"{margem_ha / custo_ha * 100:+.0f}%" if custo_ha else None))

serie = df[df.municipio == municipio].sort_values("ano")
diag = M.diagnostico_pam(df, municipio)

with dir_:
    mapa, faixa_rend = construir_mapa(municipio)
    if mapa is not None:
        st.subheader("Soja no Pará por município")
        
        # O MAPA AGORA NÃO GERA MAIS RERUNS DUPLOS!
        st_folium(
            mapa, 
            use_container_width=True, 
            height=430,
            returned_objects=["last_object_clicked_tooltip"],
            key="mapa_soja" 
        )

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
        st.caption(f"**Clique num ponto** para escolher o município.")

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

    st.subheader("Área de soja mapeada (MapBiomas)")
    area = alt.Chart(serie_plot).mark_area(
        color="#2E7D32", opacity=0.25, line={"color": "#2E7D32", "strokeWidth": 2},
    ).encode(
        x=alt.X("ano:O", title="Ano-safra"),
        y=alt.Y("soy_area_ha:Q", title="hectares", axis=EIXO_BR),
        tooltip=["ano", alt.Tooltip("area_rotulo:N", title="hectares")],
    )
    st.altair_chart(area, width='stretch')

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
        "prod_media": st.column_config.NumberColumn(f"Média {ult_ano - 4}–{ult_ano}", format=casas_pan),
        "area_ha": st.column_config.NumberColumn("Área (ha)"),
        "repeticao": st.column_config.NumberColumn("Repetição (%)", format="%.0f%%"),
        "safras": st.column_config.NumberColumn("Safras"),
    },
)

```
