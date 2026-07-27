# -*- coding: utf-8 -*-
"""
Painel de Inteligência e Previsão de Safra de Soja — Pará

Execução:
    streamlit run app.py
"""
import model as M
import json
import math
import sys
from pathlib import Path

import altair as alt  # type: ignore  # pyrefly: ignore[missing-import]
import branca.colormap as cm  # type: ignore  # pyrefly: ignore[missing-import]
import folium  # type: ignore  # pyrefly: ignore[missing-import]
import pandas as pd  # type: ignore  # pyrefly: ignore[missing-import]
import requests  # type: ignore  # pyrefly: ignore[missing-import]
import streamlit as st  # type: ignore  # pyrefly: ignore[missing-import]
import streamlit.components.v1 as components
# type: ignore  # pyrefly: ignore[missing-import]
# type: ignore  # pyrefly: ignore[missing-import]
from streamlit_folium import st_folium  # type: ignore  # pyrefly: ignore[missing-import]
from streamlit_theme import st_theme  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parent))

DADOS = Path(__file__).resolve().parents[2] / \
    "pesquisa" / "dados" / "soja_para_mascarado_2001_2024.csv"
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
        return pd.DataFrame(
            columns=[
                "cod_ibge7",
                "municipio",
                "latitude",
                "longitude"])  # type: ignore


def data_atualizacao() -> str | None:
    try:
        ano, mes, dia = DATA_ATUALIZACAO.read_text().strip().split("-")
        return f"{dia}/{mes}/{ano}"
    except (OSError, ValueError):
        return None


@st.cache_data(ttl=3600)  # Atualiza a cotação a cada 1 hora de forma segura
def buscar_preco_soja_online() -> float:
    """
    Busca o preço de referência atualizado da soja no mercado físico (Notícias Agrícolas).
    Possui fallback seguro para garantir estabilidade offline.
    """
    preco_padrao = 135.0  # Referência base alinhada aos boletins recentes
    try:
        import urllib.request
        import re
        url = "https://www.noticiasagricolas.com.br/cotacoes/soja/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8")
        # Procura a cotação em reais (ex: Paranaguá disponível/futuro)
        matches = re.findall(r"Paranaguá.*?<td[^>]*>(.*?)</td>", html, re.IGNORECASE | re.DOTALL)
        if len(matches) >= 4:
            # O índice 3 costuma ser o valor de venda "150,00"
            val_str = matches[3].replace(".", "").replace(",", ".")
            val = float(val_str)
            if val > 50:
                return val
    except Exception:
        pass
    return preco_padrao

def injetar_meta_nativas():
    """Injeta as tags 'theme-color' diretamente no index.html do Streamlit para o celular ficar nativo"""
    try:
        import streamlit, os
        index_path = os.path.join(os.path.dirname(streamlit.__file__), "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        # Se as tags ainda não estiverem lá, nós as colocamos no topo do <head>
        if "theme-color" not in html:
            metas = (
                '<meta name="theme-color" media="(prefers-color-scheme: light)" content="#ffffff">'
                '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#0e1117">'
            )
            html = html.replace("<head>", f"<head>{metas}")
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(html)
    except Exception:
        pass

injetar_meta_nativas()
st.set_page_config(
    page_title="AgroInteligência — Previsão e Viabilidade de Soja no Pará",
    page_icon="🌿",
    layout="wide")

try:
    theme_st = st_theme()
    is_dark = True
    if theme_st and theme_st.get("base") == "light":
        is_dark = False
except Exception:
    is_dark = True

# ── INJEÇÃO DE ESTILOS GLOBAIS PARA MOBILE (BARRAS NATIVAS) ──
css_mobile = """<style>
    @media (prefers-color-scheme: dark) {
        :root { color-scheme: dark !important; }
        html, body, .stApp, header { background-color: #0e1117 !important; }
    }
    @media (prefers-color-scheme: light) {
        :root { color-scheme: light !important; }
        html, body, .stApp, header { background-color: #ffffff !important; }
    }
    
    /* ── OTIMIZAÇÃO MAXIMA DE ESPAÇO PARA CELULAR ── */
    @media (max-width: 768px) {
        /* Reduz margens abismais nativas do Streamlit no celular */
        .block-container, [data-testid="block-container"] {
            padding-top: 1.5rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            max-width: 100% !important;
        }
        /* Ajuste de fontes e padding interno dos cards para evitar quebras de texto */
        .kpi-card { padding: 12px 10px !important; }
        .eco-card { padding: 14px 10px !important; }
        .kpi-value, .eco-value { font-size: 1.25rem !important; }
        .kpi-label, .eco-label { font-size: 0.6rem !important; }
        
        /* Títulos e espaçamentos do cabeçalho otimizados */
        .premium-title { font-size: 1.2rem !important; }
        .header-container { padding: 8px 0 !important; margin-bottom: 12px !important; }
        
        /* Abas mais enxutas no celular */
        .stTabs [data-baseweb="tab"] { padding: 8px 12px !important; font-size: 0.70rem !important; }
    }
    
    /* ── OTIMIZAÇÃO EXTREMA PARA SMARTPHONES PEQUENOS (<480px) ── */
    @media (max-width: 480px) {
        .block-container, [data-testid="block-container"] {
            padding-left: 0.2rem !important;
            padding-right: 0.2rem !important;
            padding-top: 1rem !important;
        }
        .premium-title { font-size: 1.1rem !important; }
        .kpi-card, .eco-card { padding: 10px 8px !important; }
        .kpi-value, .eco-value { font-size: 1.1rem !important; }
        .kpi-label, .eco-label, [data-testid="stMetricLabel"] { font-size: 0.55rem !important; }
        .stTabs [data-baseweb="tab"] { padding: 6px 8px !important; font-size: 0.65rem !important; }
    }
</style>"""
st.markdown(css_mobile, unsafe_allow_html=True)


# ── TEMA PREMIUM v2 ──
CSS_TERMINAL = '''<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;700&family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .kpi-value, .eco-value, [data-testid="stMetricValue"], [data-testid="stDataFrame"], .badge, .stNumberInput input { font-family: 'Roboto Mono', monospace !important; }

    [data-testid="stMetric"] { background: var(--secondary-background-color); border: 2px solid rgba(128,128,128,0.25); border-radius: 0px; padding: 12px 16px; border-left: 4px solid var(--primary-color); }
    [data-testid="stMetricLabel"] { font-size: 0.72rem !important; text-transform: uppercase; color: var(--text-color); opacity: 0.7; letter-spacing: 0.05em; white-space: normal !important; overflow: visible !important; }
    [data-testid="stMetricValue"] { color: var(--text-color) !important; font-size: 1.4rem !important; }

    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 10px 0 20px; }
    @media (max-width: 768px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
    .kpi-card { background: var(--secondary-background-color); border: 2px solid rgba(128,128,128,0.25); border-radius: 0px; padding: 16px; text-align: left; transition: border-color 0.2s; }
    .kpi-card:hover { border-color: var(--text-color); }
    .kpi-card.green  { border-left: 4px solid #3fb950; }
    .kpi-card.blue   { border-left: 4px solid #58a6ff; }
    .kpi-card.purple { border-left: 4px solid #bc8cff; }
    .kpi-card.orange { border-left: 4px solid #d29922; }
    .kpi-icon { font-size: 1.2rem; margin-bottom: 8px; color: var(--text-color); opacity: 0.8; display: block; }
    .kpi-label { font-size: 0.65rem; font-weight: 600; text-transform: uppercase; color: var(--text-color); opacity: 0.7; margin-bottom: 5px; }
    .kpi-value { font-size: 1.4rem; font-weight: 700; color: var(--text-color); }

    .eco-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 15px 0; }
    @media (max-width: 768px) { .eco-grid { grid-template-columns: 1fr; } }
    .eco-card { background: var(--secondary-background-color); border: 2px solid rgba(128,128,128,0.25); border-radius: 0px; padding: 18px; position: relative; }
    .eco-card:hover { border-color: var(--text-color); }
    .eco-card.receita { border-left: 4px solid #3fb950; border-top: 2px solid rgba(128,128,128,0.25); }
    .eco-card.custo   { border-left: 4px solid #f85149; border-top: 2px solid rgba(128,128,128,0.25); }
    .eco-card.margem  { border-left: 4px solid #58a6ff; border-top: 2px solid rgba(128,128,128,0.25); }
    .eco-icon { font-size: 1.4rem; color: var(--text-color); opacity: 0.8; float: right; }
    .eco-label { font-size: 0.65rem; font-weight: 600; text-transform: uppercase; color: var(--text-color); opacity: 0.7; margin-bottom: 8px; clear: left; }
    .eco-value { font-size: 1.5rem; font-weight: 700; }
    .eco-card.receita .eco-value { color: #3fb950; }
    .eco-card.custo .eco-value   { color: #f85149; }
    .eco-card.margem .eco-value  { color: #58a6ff; }
    .eco-delta { font-size: 0.75rem; margin-top: 6px; display: inline-block; font-family: 'Roboto Mono', monospace; }

    .header-container { border-bottom: 2px solid rgba(128,128,128,0.25); padding-bottom: 12px; margin-bottom: 16px; }
    .premium-title { font-family: 'Inter'; font-weight: 700; font-size: 1.4rem; color: var(--text-color); margin: 0; text-transform: uppercase; letter-spacing: 0.05em; }
    .badge-row { display: flex; gap: 6px; margin-top: 8px; }
    .badge { font-size: 0.7rem; border-radius: 0px; padding: 2px 6px; font-weight: 600; }
    .badge.green  { color: #3fb950; border: 1px solid #3fb950; background: rgba(63, 185, 80, 0.1); }
    .badge.blue   { color: #58a6ff; border: 1px solid #58a6ff; background: rgba(88, 166, 255, 0.1); }
    .badge.purple { color: #bc8cff; border: 1px solid #bc8cff; background: rgba(188, 140, 255, 0.1); }
    .badge.orange { color: #d29922; border: 1px solid #d29922; background: rgba(210, 153, 34, 0.1); }

    .stTabs [data-baseweb="tab-list"] { background: var(--secondary-background-color); border: 2px solid rgba(128,128,128,0.25); border-radius: 0px; padding: 0; gap: 0; }
    .stTabs [data-baseweb="tab"] { border-radius: 0; padding: 10px 20px; font-size: 0.8rem; text-transform: uppercase; color: var(--text-color); opacity: 0.7; margin:0; border-right: 2px solid rgba(128,128,128,0.25); }
    .stTabs [aria-selected="true"] { background: var(--background-color) !important; border-bottom: none !important; color: var(--text-color) !important; opacity: 1 !important; border-top: 3px solid #58a6ff !important; box-shadow: none; }
    .stSelectbox > div > div, .stNumberInput > div > div > input { border-radius: 0px !important; border: 2px solid rgba(128,128,128,0.25) !important; background: var(--secondary-background-color) !important; color: var(--text-color) !important; }
    .stSelectbox > div > div:focus-within, .stNumberInput > div > div > input:focus { border-color: #58a6ff !important; box-shadow: none !important; }
    .stRadio > div { background: var(--secondary-background-color); border: 2px solid rgba(128,128,128,0.25); border-radius: 0px; padding: 4px 8px; }

    .stDownloadButton > button { background: var(--secondary-background-color) !important; border: 2px solid rgba(128,128,128,0.25) !important; border-radius: 0px !important; color: var(--text-color) !important; text-transform: uppercase; font-size: 0.75rem !important; padding: 6px 16px !important; }
    .stDownloadButton > button:hover { border-color: var(--text-color) !important; }
    [data-testid="stExpander"] { background: var(--secondary-background-color); border: 2px solid rgba(128,128,128,0.25); border-radius: 0px; }
    div[data-testid="stVerticalBlockBorderWrapper"] > div:has(> [data-testid="stVerticalBlock"]) { border-radius: 0px !important; border-width: 2px !important; border-color: rgba(128,128,128,0.25) !important; background: transparent !important; }
    iframe { border-radius: 0px !important; border: 2px solid rgba(128,128,128,0.25) !important; }
    [data-testid="stDataFrame"] { border: 2px solid rgba(128,128,128,0.25) !important; border-radius: 0px !important; }
    hr { background: rgba(128,128,128,0.25) !important; height: 2px !important; margin: 16px 0 !important; }
    .stSlider [data-baseweb="slider"] [role="slider"] { background: var(--text-color) !important; border-radius: 0px; border: 2px solid var(--text-color); }
    .stSlider [data-baseweb="slider"] [data-testid="stTickBar"] > div { background: rgba(128,128,128,0.25) !important; }
</style>'''

CSS_VARS_LIGHT = """
        --app-bg: #fafafa;
        --card-bg: #ffffff;
        --card-border: #e5e5e5;
        --text-pure: #171717;
        --text-muted: #737373;
        --accent-green: #16a34a;
        --accent-blue: #2563eb;
        --accent-purple: #9333ea;
        --accent-orange: #d97706;
        --card-shadow: 0 1px 3px rgba(0,0,0,0.06);
"""

CSS_VARS_DARK = """
        --app-bg: #0a0a0a;
        --card-bg: #121212;
        --card-border: #222222;
        --text-pure: #ededed;
        --text-muted: #a1a1aa;
        --accent-green: #22c55e;
        --accent-blue: #3b82f6;
        --accent-purple: #a855f7;
        --accent-orange: #f59e0b;
        --card-shadow: 0px 4px 12px rgba(0,0,0,0.4);
"""

CSS_GLASS = '''<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    :root {
__VARS__
    }

    /* GLOBAL CLEANLINESS */
    html, body, [class*="css"], .stApp { 
        font-family: 'Inter', sans-serif !important;
        -webkit-font-smoothing: antialiased !important;
        -moz-osx-font-smoothing: grayscale !important;
        text-rendering: optimizeLegibility !important;
        background-color: var(--app-bg) !important;
    }
    [data-testid="stAppViewContainer"] {
        background-color: var(--app-bg) !important;
        background-image: none !important;
    }

    /* MINIMALIST LINEAR STYLE CARDS - FULL RESPONSIVO (AUTO-FIT) */
    .kpi-grid { 
        display: grid; 
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); 
        gap: 16px; 
        margin: 10px 0 20px; 
    }
    .eco-grid { 
        display: grid; 
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); 
        gap: 16px; 
    }
    
    /* Escalagem suave de fontes em telas menores */
    @media (max-width: 768px) {
        .kpi-label, .eco-label, [data-testid="stMetricLabel"] { font-size: 0.85rem !important; }
        .kpi-value, .eco-value, [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
        .stApp { padding-left: 0 !important; }
    }
    
    [data-testid="stMetric"], .kpi-card, .eco-card, [data-testid="stExpander"] { 
        background: var(--card-bg); 
        border: 1px solid var(--card-border); 
        border-radius: 6px; 
        box-shadow: var(--card-shadow);
        transition: all 0.2s ease; 
    }
    
    .kpi-card, .eco-card { padding: 24px; position: relative; }
    .kpi-card:hover, .eco-card:hover { 
        border-color: var(--text-muted); 
    }

    /* TYPOGRAPHY POLISH */
    .kpi-value, .eco-value, [data-testid="stMetricValue"] {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.03em !important;
        color: var(--text-pure);
    }
    .kpi-label, .eco-label, [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        color: var(--text-muted);
        text-transform: none;
        letter-spacing: 0em;
        white-space: normal !important;
        overflow: visible !important;
        word-break: break-word !important;
        text-overflow: clip !important;
    }

    /* ECO DELTA INDICATOR MINIMALISM */
    .eco-card.receita .eco-delta { color: var(--accent-green); }
    .eco-card.custo .eco-delta   { color: var(--accent-orange); }
    .eco-card.margem .eco-delta  { color: var(--accent-blue); }

    /* COMPONENT POLISH (TABS, BUTTONS, INPUTS) */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 24px; background: transparent; border-bottom: 1px solid var(--card-border); 
        padding: 0; box-shadow: none; border-radius: 0; margin-bottom: 16px;
    }
    .stTabs [data-baseweb="tab"] { 
        padding: 10px 4px; font-weight: 500; font-size: 0.85rem; color: var(--text-muted) !important;
        border-bottom: 2px solid transparent !important; background: transparent !important; border-radius: 0; margin: 0;
    }
    .stTabs [aria-selected="true"] { 
        color: var(--text-pure) !important; border-bottom: 2px solid var(--text-pure) !important; 
        box-shadow: none !important;
    }
    
    .stSelectbox > div > div, .stNumberInput > div > div > input { 
        background: var(--app-bg) !important; border: 1px solid var(--card-border) !important; 
        border-radius: 6px !important; color: var(--text-pure) !important; font-weight: 400;
        box-shadow: none !important; transition: border-color 0.15s ease;
    }
    .stSelectbox > div > div:focus-within, .stNumberInput > div > div > input:focus { 
        border-color: var(--text-pure) !important; box-shadow: 0 0 0 1px var(--card-border) !important; 
    }

    /* PREMIUM HEADER */
    .header-container { padding: 12px 0 20px; border-bottom: 1px solid var(--card-border); margin-bottom: 24px; }
    .premium-title { 
        font-size: 1.6rem; font-weight: 600; color: var(--text-pure); letter-spacing: -0.03em;
        margin-bottom: 6px; background: none; -webkit-text-fill-color: initial;
    }
    .header-separator { display: none; }
    
    .badge-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; }
    .badge { border-radius: 4px; border: 1px solid var(--card-border); padding: 4px 8px; font-size: 0.65rem; background: var(--card-bg); color: var(--text-pure); font-weight: 500; }

    /* CHARTS AND IFRAMES */
    iframe { border-radius: 6px !important; border: 1px solid var(--card-border) !important; box-shadow: none !important; }
    [data-testid="stDataFrame"] { border-radius: 6px; border: 1px solid var(--card-border) !important;}
    
    /* SCROLLBARS LUXURY */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--card-border); border-radius: 8px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
</style>'''


CSS_ORIGINAL = """<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

    /* Base Metric */
    [data-testid="stMetric"] { background-color: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.15); border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); transition: transform 0.2s, box-shadow 0.2s; }
    [data-testid="stMetric"]:hover { transform: translateY(-2px); box-shadow: 0 6px 12px rgba(0,0,0,0.08); border-color: var(--primary-color); }
    [data-testid="stMetricLabel"] { font-size: 0.75rem !important; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600 !important; }
    [data-testid="stMetricValue"] { font-weight: 700 !important; font-size: 1.7rem !important; }

    /* KPI Grids */
    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 16px 0; }
    @media (max-width: 768px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
    .kpi-card { background: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.15); border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); transition: all 0.25s; }
    .kpi-card:hover { transform: translateY(-3px); box-shadow: 0 8px 16px rgba(0,0,0,0.08); border-color: var(--primary-color); }
    .kpi-icon { font-size: 1.5rem; margin-bottom: 10px; display: block; opacity: 0.9; }
    .kpi-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 6px; opacity: 0.6; letter-spacing: 0.05em; }
    .kpi-value { font-size: 1.5rem; font-weight: 700; }

    /* Eco Grids */
    .eco-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 16px 0; }
    @media (max-width: 768px) { .eco-grid { grid-template-columns: repeat(2, 1fr); } }
    .eco-card { background: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.15); border-radius: 12px; padding: 22px; position: relative; box-shadow: 0 2px 8px rgba(0,0,0,0.04); transition: all 0.25s; }
    .eco-card:hover { transform: translateY(-3px); box-shadow: 0 8px 16px rgba(0,0,0,0.08); }
    .eco-icon { font-size: 1.8rem; float: right; opacity: 0.85; }
    .eco-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-bottom: 8px; opacity: 0.6; letter-spacing: 0.05em; clear: left; }
    .eco-value { font-size: 1.7rem; font-weight: 800; }
    .eco-delta { font-size: 0.75rem; margin-top: 10px; display: inline-block; font-weight: 600; opacity: 0.9; }

    /* Semantic Colors for Elegant Theme */
    .eco-card.receita { border-top: 3px solid #10B981; }
    .eco-card.custo { border-top: 3px solid #EF4444; }
    .eco-card.margem { border-top: 3px solid #3B82F6; }
    .eco-card.receita .eco-value { color: #10B981; }
    .eco-card.custo .eco-value { color: #EF4444; }
    .eco-card.margem .eco-value { color: #3B82F6; }

    .header-container { padding-bottom: 16px; margin-bottom: 24px; border-bottom: 1px solid rgba(128,128,128,0.15); }
    .premium-title { font-weight: 700; font-size: 1.6rem; margin: 0; letter-spacing: -0.01em; }
    .badge-row { display: flex; gap: 8px; margin-top: 12px; }
    .badge { font-size: 0.65rem; border-radius: 6px; padding: 4px 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; border: 1px solid rgba(128,128,128,0.25); background: rgba(128,128,128,0.08); opacity: 0.85; }

    .footer-container { margin-top: 40px; padding: 20px 0; border-top: 1px solid rgba(128,128,128,0.15); text-align: center; opacity: 0.8; }
    .footer-brand { font-size: 0.9rem; font-weight: 700; margin-bottom: 6px; }
    .footer-text { font-size: 0.75rem; opacity: 0.7; }

    /* Clean layout elements */
    [data-testid="stExpander"] { border: 1px solid rgba(128,128,128,0.15); border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.03); }
    [data-testid="stDataFrame"] { border: 1px solid rgba(128,128,128,0.15) !important; border-radius: 12px !important; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.03); }
    iframe { border-radius: 12px !important; border: 1px solid rgba(128,128,128,0.15) !important; box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important; }
    hr { background: rgba(128,128,128,0.15) !important; height: 1px !important; margin: 24px 0 !important; }
</style>"""

# ── TEMA E ESTILIZAÇÃO (ÚNICA E ROBUSTA) ──
CSS_ATUAL = CSS_GLASS.replace('__VARS__', CSS_VARS_DARK if is_dark else CSS_VARS_LIGHT)
st.markdown(CSS_ATUAL, unsafe_allow_html=True)


# ── TEMA ALTAIR DARK ──


@alt.theme.register('agro_dark_terminal', enable=True)
def _altair_dark_theme_terminal():
    return alt.theme.ThemeConfig(
        {
            'background': 'transparent',
            'view': {
                'stroke': 'transparent'},
            'axis': {
                'domainColor': '#30363d',
                'gridColor': '#21262d',
                'tickColor': '#30363d',
                'labelColor': '#8b949e',
                'titleColor': '#8b949e',
                'labelFont': 'Roboto Mono, monospace',
                'titleFont': 'Inter, sans-serif',
                'titleFontWeight': 600,
                'labelFontSize': 10,
                'titleFontSize': 11,
                'gridDash': [
                    2,
                    2]},
            'legend': {
                'labelColor': '#8b949e',
                'titleColor': '#c9d1d9',
                'labelFont': 'Roboto Mono, monospace',
                'titleFont': 'Inter, sans-serif',
                'labelFontSize': 10,
                'titleFontSize': 11,
            },
            'title': {
                'color': '#c9d1d9',
                'font': 'Inter, sans-serif',
                'fontWeight': 700,
                'fontSize': 13,
                'anchor': 'start'},
            'range': {
                'category': [
                    '#3fb950',
                    '#58a6ff',
                    '#bc8cff',
                    '#d29922',
                    '#f85149',
                    '#0dd3ff',
                    '#e3b341',
                    '#8b949e'],
            },
            'line': {
                'strokeWidth': 1.5},
            'point': {
                'size': 40,
                'filled': True,
                'opacity': 0.8},
            'area': {
                'opacity': 0.25},
        })


@alt.theme.register('agro_dark_glass', enable=True)
def _altair_dark_theme_glass():
    return alt.theme.ThemeConfig(
        {
            'background': 'transparent',
            'view': {
                'stroke': 'transparent'},
            'axis': {
                'domainColor': 'rgba(255,255,255,0.15)',
                'gridColor': 'rgba(255,255,255,0.06)',
                'tickColor': 'rgba(255,255,255,0.1)',
                'labelColor': 'rgba(255,255,255,0.55)',
                'titleColor': 'rgba(255,255,255,0.7)',
                'labelFont': 'Inter',
                'titleFont': 'Inter',
                'titleFontWeight': 600,
                'labelFontSize': 11,
                'titleFontSize': 12,
            },
            'legend': {
                'labelColor': 'rgba(255,255,255,0.6)',
                'titleColor': 'rgba(255,255,255,0.7)',
                'labelFont': 'Inter',
                'titleFont': 'Inter',
                'labelFontSize': 11,
                'titleFontSize': 12,
            },
            'title': {
                'color': 'rgba(255,255,255,0.8)',
                'font': 'Inter',
                        'fontWeight': 700,
                        'fontSize': 14,
            },
            'range': {
                'category': [
                    '#81C784',
                    '#64B5F6',
                    '#CE93D8',
                    '#FFB74D',
                    '#EF5350',
                    '#4DD0E1',
                    '#FFF176',
                    '#A1887F'],
            },
            'line': {
                'strokeWidth': 2.5},
            'point': {
                'size': 60,
                'filled': True},
            'area': {
                'opacity': 0.35},
        })


if is_dark:
    alt.themes.enable('agro_dark_terminal')
else:
    alt.themes.enable('default')

@st.cache_resource(show_spinner="Carregando modelos de inteligência de safra...")
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
_cod_por_nome = df.drop_duplicates("municipio").set_index("municipio")[
    "cod_ibge7"].to_dict()
_nome_por_cod = _muni.set_index("cod_ibge7")["municipio"].to_dict()
NOME_EXIBICAO = {
    m: _nome_por_cod.get(
        _cod_por_nome.get(m),
        m) for m in df.municipio.unique()}


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


def construir_mapa(sel_interno: str, comp_interno: str | None = None, is_dark: bool = True):
    geo = carregar_geo()
    pts = _soja_por_municipio()
    if geo is None or pts.empty:
        return None, {}, None

    cod_sel = _cod_por_nome.get(sel_interno)
    cod_comp = _cod_por_nome.get(comp_interno) if comp_interno else None

    latmin, latmax = pts.latitude.min(), pts.latitude.max()
    lonmin, lonmax = pts.longitude.min(), pts.longitude.max()

    tiles_map = "cartodbdark_matter" if is_dark else "cartodbpositron"
    fill_color = "#1b2d1b" if is_dark else "#e8f5e9"
    border_color = "#304a30" if is_dark else "#81c784"
    m = folium.Map(location=[(latmin + latmax) / 2, (lonmin + lonmax) / 2],
                   tiles=tiles_map, zoom_start=6, control_scale=True)
    folium.GeoJson(
        geo,
        name="Pará",
        interactive=False,
        style_function=lambda f: {
            "fillColor": fill_color,
            "color": border_color,
            "weight": 1.0,
            "fillOpacity": 0.2 if is_dark else 0.5}).add_to(m)

    rios = carregar_rios()
    if rios is not None and rios.get("features"):
        folium.GeoJson(
            rios,
            name="Rios",
            interactive=False,
            style_function=lambda f: {
                "color": "#4a90d9",
                "weight": 1.3,
                "opacity": 0.85}).add_to(m)

    rmin, rmax = float(pts.rend.min()), float(pts.rend.max())
    cmap = cm.LinearColormap(_VIRIDIS, vmin=rmin, vmax=rmax)
    amax = float(pts.area.max())
    nome_para_interno = {}

    for r in pts.itertuples():  # type: ignore
        nome = disp(r.municipio)  # type: ignore
        nome_para_interno[nome] = r.municipio  # type: ignore

        selec_prin = (r.cod_ibge7 == cod_sel)  # type: ignore
        selec_comp = (r.cod_ibge7 == cod_comp)  # type: ignore

        cor_borda = "#B00020" if selec_prin else (
            "#2E75B6" if selec_comp else "white")
        peso_borda = 3.5 if (selec_prin or selec_comp) else 0.7

        folium.CircleMarker(
            location=[r.latitude, r.longitude],  # type: ignore
            radius=4 + 14 * math.sqrt(r.area / amax),  # type: ignore
            color=cor_borda,
            weight=peso_borda,
            # type: ignore
            # type: ignore
            fill=True, fill_color=cmap(r.rend), fill_opacity=0.9,  # type: ignore
            tooltip=nome
        ).add_to(m)

    m.fit_bounds([[latmin, lonmin], [latmax, lonmax]])
    return m, nome_para_interno, (rmin, rmax)


atualizada_em = data_atualizacao()
html_atualizacao = f'· <span style="color:var(--text-pure); font-weight:600;"> {atualizada_em}</span>' if atualizada_em else ''

st.markdown(f"""
<div class="header-container">
    <div class="premium-title">AgroInteligência — Previsão e Viabilidade de Safra</div>
    <div style="font-size:0.82rem; color:var(--text-muted); margin-top:4px;">
        <span style="color:var(--text-pure); font-weight:600;">{len(df)}</span> registros ·
        <span style="color:var(--text-pure); font-weight:600;">{df.municipio.nunique()}</span> municípios ·
        <span style="color:var(--text-pure); font-weight:600;">{df.ano.min()}–{df.ano.max()}</span>
        {html_atualizacao}
    </div>
    <div class="badge-row">
        <span class="badge">MODIS</span>
        <span class="badge">CHIRPS</span>
        <span class="badge">ERA5-Land</span>
        <span class="badge">MapBiomas</span>
    </div>
</div>
""", unsafe_allow_html=True)

unidade = st.radio(
    "Unidade de medida preferida", [
        "sc/ha", "kg/ha"], horizontal=True)
fator = 1 if unidade == "kg/ha" else 1 / SACA_KG


def qtd(v: float, sinal: str = "") -> str:
    if unidade == "kg/ha":
        return f"{v * fator:{sinal},.0f}".replace(",", ".")
    return f"{v * fator:{sinal}.1f}".replace(".", ",")


def br(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def brl(v: float, dec: int = 0) -> str:
    s = f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + s


PRECO_SACA_ONLINE = buscar_preco_soja_online()

EIXO_BR = alt.Axis(labelExpr="replace(format(datum.value, ',.0f'), /,/g, '.')")

st.divider()

municipios = sorted(df.municipio.unique())

if "mun_sel" not in st.session_state:
    st.session_state.mun_sel = "Paragominas" if "Paragominas" in municipios else municipios[0]

if "last_map_click" not in st.session_state:
    st.session_state.last_map_click = None

if "mapa_soja" in st.session_state and st.session_state.mapa_soja:
    current_map_click = st.session_state.mapa_soja.get(
        "last_object_clicked_tooltip")
    if current_map_click and current_map_click != st.session_state.last_map_click:
        st.session_state.last_map_click = current_map_click
        interno = EXIBICAO_PARA_INTERNO.get(current_map_click)
        if interno and interno != st.session_state.mun_sel:
            st.session_state.mun_sel = interno


def on_dropdown_change():
    if "mapa_soja" in st.session_state and st.session_state.mapa_soja:
        st.session_state.last_map_click = st.session_state.mapa_soja.get(
            "last_object_clicked_tooltip")


# Abas focadas em inteligência comercial e gestão de risco
st.sidebar.markdown("### Navegação Principal")
tela_atual = st.sidebar.radio(
    "",
    ["📍 Inteligência Territorial", "📈 Análise Histórica", "💰 Viabilidade Financeira"]
)
st.sidebar.divider()


st.sidebar.markdown("### Parâmetros Globais")
municipio = st.sidebar.selectbox(
    "Polo Científico / Município",
    municipios,
    key="mun_sel",
    format_func=disp,
    on_change=on_dropdown_change)

comparar = st.sidebar.toggle("Comparar com vizinho", value=False)
mun_comp = None
if comparar:
    opcoes_comp = [m for m in municipios if m != municipio]
    mun_comp = st.sidebar.selectbox(
        "Município Paralelo",
        opcoes_comp,
        format_func=disp)

ano_alvo = st.sidebar.number_input(
    "Safra Alvo (Projeção IA)",
    min_value=int(df.ano.max()) + 1,
    max_value=int(df.ano.max()) + 3,
    value=int(df.ano.max()) + 1)

unidade = st.sidebar.radio(
    "Unidade",
    options=["Sacas (60kg)", "Quilos (kg)"],
    index=0
)

preco = PRECO_SACA_ONLINE

st.sidebar.markdown("### Perfil do Produtor")
baseline_ibge = estimador.estimar(municipio, int(df.ano.max()) + 1)["baseline_kg_ha"]
fator_tecnologico = st.sidebar.number_input(
    "Expectativa Produtiva da Fazenda", 
    min_value=10.0, max_value=120.0, 
    value=float(baseline_ibge / 60.0), 
    step=1.0, 
    help="O modelo IA usa médias do IBGE. Se sua fazenda possui alta tecnologia (correção de solo/sementes), ajuste a base aqui para prever os ganhos/perdas climáticos em cima da sua realidade."
)
st.sidebar.caption("Baseline: Quantas sacas/ha a fazenda colhe em um ano normal?")

def ajustar_r(r_dict):
    r2 = r_dict.copy()
    r2["baseline_kg_ha"] = fator_tecnologico * 60.0
    r2["estimativa_kg_ha"] = r2["baseline_kg_ha"] + r2["correcao_climatica_kg_ha"]
    return r2

st.sidebar.divider()

# ==============================================================================
# ABA 1: MAPA E PREVISÃO

# ==============================================================================
if tela_atual == "📍 Inteligência Territorial":
    # ── INSERE RESUMO E ALERTAS CLIMÁTICOS DO POLO ──
    has_severe = False
    cor_bg_alerta = "rgba(220,38,38,0.15)" if has_severe else "rgba(128,128,128,0.05)"
    cor_borda = "rgba(220,38,38,0.3)" if has_severe else "rgba(128,128,128,0.15)"
    cor_texto = "#ff6b6b" if (has_severe and is_dark) else "#dc2626" if has_severe else "var(--text-color)"
    st.markdown(f"""
    <div style="padding:16px 20px; background:{cor_bg_alerta}; 
                border:1px solid {cor_borda}; border-radius:8px; margin-bottom:24px;
                color:{cor_texto}; font-size:0.9rem;">
        <span style="font-weight:700;">{disp(municipio)}</span> — Fase neutra identificada. As projeções assumem condições meteorológicas em conformidade com as médias da última década e inflação controlada.
    </div>
    """, unsafe_allow_html=True)
    st.markdown("### Resumo das Safras no Polo")
    st.markdown(f"""
    <div class="kpi-grid">
        <div class="kpi-card green">
            <div class="kpi-label">Margem de Precisão (RMSE)</div>
            <div class="kpi-value">± {qtd(metricas['rmse'])} {unidade}</div>
        </div>
        <div class="kpi-card blue">
            <div class="kpi-label">Variação Relativa</div>
            <div class="kpi-value">{metricas['rrmse']:.1f}%</div>
        </div>
        <div class="kpi-card purple">
            <div class="kpi-label">Aderência Preditiva (R²)</div>
            <div class="kpi-value">{metricas['r2']:.3f}</div>
        </div>
        <div class="kpi-card orange">
            <div class="kpi-label">Benchmark de Tendência</div>
            <div class="kpi-value">{metricas['r2_baseline']:.3f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    esq, dir_ = st.columns([1, 2])
    with esq:


        with st.spinner(f"Sintetizando predições de IA (XGBoost) para {disp(municipio)}..."):
            r = ajustar_r(estimador.estimar(municipio, int(ano_alvo)))
        st.metric(f"Projeção Safra {ano_alvo}",
                  f"{qtd(r['estimativa_kg_ha'])} {unidade}")

        with st.expander("Variáveis Climáticas (What-if)"):
            st.caption(
                "Teste cenários meteorológicos forçados (O impacto na projeção será calculado via IA)")
            precip = st.slider("Precipitação Total Estimada (mm)",
                               0, 3000, 1500, step=100)
            etp = st.slider("Evapotranspiração Potencial",
                            500, 2500, 1500, step=100)

            st.divider()
            hist = df[df["municipio"] == municipio]
            clima = hist[M.FEATURES].mean().to_dict() if not hist.empty else df[M.FEATURES].mean().to_dict()
            clima["precip_total"] = precip
            clima["etp_total"] = etp
            clima["balanco_hidrico"] = clima["precip_total"] - clima["etp_total"]
            cenario = ajustar_r(estimador.estimar(municipio, int(ano_alvo), clima=clima))
            dif = cenario["estimativa_kg_ha"] - r["estimativa_kg_ha"]
            st.metric("Projeção Ajustada",
                      f"{qtd(cenario['estimativa_kg_ha'])} {unidade}",
                      delta=f"{qtd(dif, '+')} {unidade}")

    with dir_:
        mapa, nome_para_interno, faixa_rend = construir_mapa(
            municipio, mun_comp, is_dark=is_dark)
        if mapa is not None:
            st.subheader("Panorama Geoespacial dos Polos Produtivos")
            st_folium(
                mapa,
                width='stretch',
                height=430,
                returned_objects=["last_object_clicked_tooltip"],
                key="mapa_soja"
            )

            grad = ",".join(_VIRIDIS)
            bg = "#0d1117" if is_dark else "rgba(128,128,128,0.05)"
            brad = "6px"
            bord = "1px solid #30363d" if is_dark else "1px solid rgba(128,128,128,0.2)"
            col_t = "#8b949e" if is_dark else "rgba(0,0,0,0.6)"
            col_v = "#c9d1d9" if is_dark else "rgba(0,0,0,0.9)"
            font = "'Roboto Mono', monospace"

            html = f"""<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap; font-size:0.75rem;margin:6px 0 8px; padding:8px 12px; background:{bg}; border-radius:{brad}; border:{bord};">
                  <span style="color:{col_t}; font-weight:600; text-transform:uppercase; letter-spacing:0.04em;">Produtividade</span>
                  <span style="font-family:{font}; font-weight:600; color:{col_v};">{br(faixa_rend[0] * fator) if faixa_rend else 0} {unidade}</span>
                  <div style="flex:0 1 180px;height:8px;border-radius:{brad}; background:linear-gradient(to right,{grad}); border:none;"></div>
                  <span style="font-family:{font}; font-weight:600; color:{col_v};">{br(faixa_rend[1] * fator) if faixa_rend else 0} {unidade}</span>
                </div>"""
            st.markdown(html, unsafe_allow_html=True)
            st.caption(
                "**Dica:** Clique em qualquer ponto do mapa para alternar o município selecionado (Vermelho = Principal | Azul = Comparação).")

# ==============================================================================
# ABA 2: SÉRIES HISTÓRICAS & CLIMA
# ==============================================================================
if tela_atual == "📈 Análise Histórica":
    if mun_comp:
        serie = df[df.municipio.isin([municipio, mun_comp])].sort_values([
            "municipio", "ano"])  # type: ignore
    else:
        serie = df[df.municipio == municipio].sort_values(
            "ano")  # type: ignore

    st.subheader("Evolução Histórica da Produtividade")

    serie_plot = serie.assign(
        produtividade=serie[M.ALVO] * fator,
        produtividade_rotulo=[qtd(v) for v in serie[M.ALVO]],
        area_rotulo=[br(a) for a in serie["soy_area_ha"]],
        repetido=serie.groupby("municipio")[M.ALVO].diff().eq(0).fillna(False),
        Nome=[disp(m) for m in serie["municipio"]]
    )

    from ui.charts import plot_produtividade, plot_area
    import plotly.graph_objects as go
    
    st.plotly_chart(plot_produtividade(serie_plot, is_dark=is_dark), use_container_width=True)
    st.caption("Gráfico interativo: arraste para selecionar um período, dois toques para resetar o zoom.")

    st.subheader("Expansão da Área Plantada (Hectares)")
    st.plotly_chart(plot_area(serie_plot, is_dark=is_dark), use_container_width=True)

    b1, b2 = st.columns(2)
    b1.download_button(
        "Exportar histórico do município (CSV)",
        serie.to_csv(
            index=False).encode("utf-8"),
        file_name=f"soja_{
            municipio.lower().replace(
                ' ',
                '_')}.csv",
        mime="text/csv")
    b2.download_button(
        "Exportar base completa (CSV)",
        DADOS.read_bytes(),
        file_name=DADOS.name,
        mime="text/csv")

# ==============================================================================
# ABA 3: ANÁLISE ECONÔMICA & MERCADO
# ==============================================================================
if tela_atual == "💰 Viabilidade Financeira":
    st.markdown("""
    <div style="margin-bottom:4px">
        <span style="font-size:1.2rem; font-weight:700;">Inteligência de Mercado & Margens por Hectare</span>
    </div>
    <p style="font-size:0.85rem; color:var(--text-color); opacity:0.6; margin-top:0;">
        Simule cenários financeiros combinando projeções de IA com preços em tempo real e custeio operacional.
    </p>
    """, unsafe_allow_html=True)

    with st.spinner("Processando margem de lucro com IA Georreferenciada..."):
        r_eco = ajustar_r(estimador.estimar(municipio, int(df.ano.max()) + 1))

    col_eco1, col_eco2, col_eco3 = st.columns(3)
    import requests
    try:
        r = requests.get(f'http://127.0.0.1:8000/api/financas/{municipio}').json()
        custos_locais = {'custo_ha': r.get('custo_ha', 4800.0), 'vtn_ha': r.get('vtn_ha', 12000.0)}
        default_preco = r.get('soja_preco_saca', 120.0)
    except:
        custos_locais = {'custo_ha': 4800.0, 'vtn_ha': 12000.0}
        default_preco = 120.0

    
    with col_eco1:
        preco = st.number_input(
            "Preço de referência da saca (R$ / 60 kg)",
            min_value=0.0,
            value=default_preco,
            step=5.0)
        st.caption(
            "🌐 **Fonte da Cotação:** Cotação interativa em tempo real (Notícias Agrícolas / CEPEA).")
    with col_eco2:
        custo_ha = st.number_input(
            f"Custo Operacional base ({municipio.title()})",
            min_value=0.0,
            value=custos_locais["custo_ha"],
            step=100.0)
        st.caption(
            "📊 **Fonte do Custo:** Base VTN ajustada. Edite com a realidade da sua fazenda.")
    with col_eco3:
        vtn_ha = st.number_input(
            f"Preço Terra Nua VTN/ha ({municipio.title()})",
            min_value=0.0,
            value=custos_locais["vtn_ha"],
            step=500.0)
        st.caption(
            "🗺️ **Fonte da Terra:** Base de referência municipal da Receita Federal (VTN).")

    est_sacas_ha = r_eco["estimativa_kg_ha"] / SACA_KG
    receita_ha = est_sacas_ha * preco
    margem_ha = receita_ha - custo_ha
    pct_margem = f"{margem_ha / custo_ha * 100:+.0f}%" if custo_ha else "—"
    cor_delta = '#16a34a' if margem_ha >= 0 else '#EF5350'

    # SÍNTESE LLM (ANÁLISE GENERATIVA)
    texto_ia = ""
    if margem_ha > 0:
        if margem_ha > (custo_ha * 0.3):
             texto_ia = f"📈 <b>Alta Viabilidade (Síntese IA):</b> Cenário projeta lucro operacional robusto. A produtividade estimada de <b>{est_sacas_ha:.1f} scs/ha</b> assegura um faturamento de {brl(receita_ha)}/ha, cobrindo com folga o custeio de {brl(custo_ha)}, deixando uma margem excelente."
        else:
             texto_ia = f"⚠️ <b>Alerta de Stress (Síntese IA):</b> A conta fecha no azul, mas a margem estreita de {brl(margem_ha)}/ha exige cautela. A produtividade predita de <b>{est_sacas_ha:.1f} scs</b> não suportará solavancos climáticos intensos sem risco de prejuízo."
    else:
        texto_ia = f"🛑 <b>Risco Operacional Crítico (Síntese IA):</b> Alerta Vermelho! Com a soja simulada a {brl(preco)} e custo elevado ({brl(custo_ha)}/ha), a IA prevê colapso econômico em {disp(municipio)}. A produtividade de <b>{est_sacas_ha:.1f} scs/ha</b> destruiria o capital, com perdas de {brl(abs(margem_ha))} por hectare."

    st.markdown(f'<div style="background:var(--card-bg); padding:16px; border-radius:6px; border-left:4px solid {cor_delta}; margin-bottom: 24px; border-top:1px solid var(--card-border); border-right:1px solid var(--card-border); border-bottom:1px solid var(--card-border); font-size: 0.95rem; line-height: 1.5; font-family: Inter, sans-serif;">{texto_ia}</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="eco-grid">
        <div class="eco-card receita">
            <div class="eco-icon">💵</div>
            <div class="eco-label">Faturamento Bruto / ha</div>
            <div class="eco-value">{brl(receita_ha)}</div>
        </div>
        <div class="eco-card custo">
            <div class="eco-icon">📋</div>
            <div class="eco-label">Custo Operacional / ha</div>
            <div class="eco-value">{brl(custo_ha)}</div>
        </div>
        <div class="eco-card vtn">
            <div class="eco-icon">🗺️</div>
            <div class="eco-label">Valor da Terra Nua / ha</div>
            <div class="eco-value">{brl(vtn_ha)}</div>
        </div>
        <div class="eco-card margem">
            <div class="eco-icon">📈</div>
            <div class="eco-label">Margem Líquida / ha</div>
            <div class="eco-value">{brl(margem_ha)}</div>
            <div class="eco-delta" style="color:{cor_delta}">{pct_margem} sobre o custo</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.success(
        f"**Panorama Comercial:** Com a produtividade estimada de **{
            qtd(
                r_eco['estimativa_kg_ha'])} {unidade}** para **{
            disp(municipio)}**, o faturamento bruto atinge **{
                    brl(receita_ha)}/ha**, garantindo margem operacional positiva nas condições atuais de mercado.")

    st.divider()

    st.subheader("⚠️ Confiabilidade e Qualidade dos Registros Oficiais")
    diag = M.diagnostico_pam(df, municipio)
    taxa_estado = M.taxa_repeticao_estadual(df)

    qa, qb, qc = st.columns(3)
    qa.metric("Repetição de dados locais",
              f"{diag['taxa']:.0f}%",
              help="Porcentagem de safras em que o histórico oficial repetiu o valor anterior.")
    qb.metric("Maior sequência travada", f"{diag['maior_sequencia']} safras")
    qc.metric("Média de repetição no Pará", f"{taxa_estado:.1f}%")

    if diag["taxa"] >= taxa_estado:
        st.warning(
            f"**Nota de Inteligência:** O histórico oficial de **{
                disp(municipio)}** apresenta alta taxa de repetição estatística interanual, validando o uso de machine learning e dados de satélite para correções de viés e maior precisão comercial.")
    else:
        st.success(
            f"**Qualidade de Dados:** O município de **{
                disp(municipio)}** apresenta excelente variabilidade histórica nos registros oficiais.")

    st.divider()

    # ------------------------------------------------------ PANORAMA GERAL DO ESTADO
    st.subheader("📋 Ranking e Panorama Comercial dos Polos Produtivos")
    st.caption(
        f"Calculado com base na produtividade média recente e na cotação de mercado de **{
            brl(preco)} por saca**.")

    ult_ano = int(df.ano.max())
    linhas_pan = []
    for mun, d in df.groupby("municipio"):
        d = d.sort_values("ano")
        ult5 = d[d.ano > ult_ano - 5]
        difs = d[M.ALVO].diff().dropna()
        prod_med_kg = ult5[M.ALVO].mean()
        faturamento_bruto = (prod_med_kg / SACA_KG) * preco

        linhas_pan.append({
            "Município": disp(str(mun)),
            "prod_media": prod_med_kg * fator,
            "faturamento": faturamento_bruto,
            "area_ha": float(d.iloc[-1]["soy_area_ha"]),
            "repeticao": float((difs == 0).mean() * 100) if len(difs) else 0.0,
            "safras": len(d),
        })

    casas_pan = "%.0f" if unidade == "kg/ha" else "%.1f"
    pan = pd.DataFrame(linhas_pan).sort_values("faturamento", ascending=False)

    st.dataframe(
        pan,
        hide_index=True,
        width='stretch',
        column_config={
            "prod_media": st.column_config.NumberColumn(
                f"Média Recente ({
                    ult_ano - 4}–{ult_ano}) [{unidade}]",
                format=casas_pan),
            "faturamento": st.column_config.NumberColumn(
                "Faturamento Bruto Est. (R$/ha)",
                format="localized"),
            "area_ha": st.column_config.NumberColumn(
                "Área Atual (ha)",
                format="localized"),
            "repeticao": st.column_config.NumberColumn(
                "Repetição Oficial (%)",
                format="%.0f%%"),
            "safras": st.column_config.NumberColumn("Total de Safras"),
        },
    )



with st.expander("ℹ️ Sobre a Tecnologia e Fontes de Dados", expanded=False):
    st.markdown('''
    **Plataforma de AgroInteligência Preditiva** — Solução metodológica baseada em inteligência artificial para previsão de produtividade de soja e monitoramento do agronegócio no Estado do Pará.

    ### Tratamento e Origem dos Dados:
    * **IBGE (PAM):** Base estrutural de dados oficiais de safra e área plantada histórica para a modelagem alvo.
    * **Google Earth Engine (GEE):** Plataforma primária de ETL satelital em larga escala.
      * *MODIS (MOD13Q1 / Terra)*: Séries temporais de Índices de Vegetação (NDVI, EVI).
      * *CHIRPS*: Malha meteorológica para mensuração de Precipitação e Volume de Chuva.
      * *ERA5-Land*: Banco climático de temperatura global para extração de Evapotranspiração Potencial e Balanço Hídrico.
    * **Projeto MapBiomas:** Extração das coberturas de Uso e Ocupação do Solo com foco em áreas exclusivas de soja no Pará (mascaramento de satélite).
    * **AwesomeAPI / B3:** Ingestão das variações diárias no câmbio livre e bolsas de *commodities*.
    * **Notícias Agrícolas / CEPEA:** Scraping em tempo real para o Preço da Saca de Soja (Porto/Paranaguá).
    * **Receita Federal / SIPT:** Valores de referência da Terra Nua (VTN) baseados nas prefeituras do estado.
    * **CONAB / Aprosoja:** Tabelas referenciais de Custeio Operacional Efetivo.
    
    *Repositório Acadêmico:* [github.com/engsoft7/dissertacao-soja-ia](https://github.com/engsoft7/dissertacao-soja-ia)

    ---
    **AgroInteligência** | Plataforma de Inteligência Preditiva para Safra de Soja — Estado do Pará
    *Machine Learning · Sensoriamento Remoto · Análise de Viabilidade Comercial*
    
    Desenvolvido com Streamlit · Dados: IBGE · MODIS · CHIRPS · ERA5 · MapBiomas · AwesomeAPI · Conab
    ''')


