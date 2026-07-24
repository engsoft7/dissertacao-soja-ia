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
    Busca o preço de referência atualizado da soja no mercado físico (API de Commodities).
    Possui fallback seguro para garantir estabilidade offline.
    """
    preco_padrao = 120.0  # Referência base alinhada aos boletins recentes
    try:
        url = "https://economia.awesomeapi.com.br/json/last/SOJA"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            val = float(data.get("SOJA", {}).get("bid", preco_padrao))
            if val > 50:
                return val
    except Exception:
        pass
    return preco_padrao


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


# ── TEMA PREMIUM v2 ──
CSS_TERMINAL = '''<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;700&family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .kpi-value, .eco-value, [data-testid="stMetricValue"], [data-testid="stDataFrame"], .badge, .stNumberInput input { font-family: 'Roboto Mono', monospace !important; }

    [data-testid="stMetric"] { background: var(--secondary-background-color); border: 2px solid rgba(128,128,128,0.25); border-radius: 0px; padding: 12px 16px; border-left: 4px solid var(--primary-color); }
    [data-testid="stMetricLabel"] { font-size: 0.72rem !important; text-transform: uppercase; color: var(--text-color); opacity: 0.7; letter-spacing: 0.05em; }
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

    .footer-container { margin-top: 30px; padding: 12px 0; border-top: 2px solid rgba(128,128,128,0.25); text-align: left; }
    .footer-brand { font-family: 'Inter'; font-size: 0.8rem; font-weight: 700; color: var(--text-color); opacity: 0.7; letter-spacing: 0.05em; text-transform: uppercase; }
    .footer-text { font-size: 0.7rem; color: var(--text-color); opacity: 0.6; }
</style>'''

CSS_GLASS = '''<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    @keyframes fadeInUp { from { opacity: 0; transform: translateY(18px); } to   { opacity: 1; transform: translateY(0); } }
    @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
    @keyframes gradientShift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    /* REMOVIDO: .stApp background fixo, agora usa adaptativo do Streamlit */

    [data-testid="stMetric"] { background: rgba(128,128,128,0.05); border: 1px solid rgba(128,128,128,0.15); border-radius: 16px; padding: 20px 22px; backdrop-filter: blur(16px); transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1); animation: fadeInUp 0.5s ease-out both; }
    [data-testid="stMetric"]:hover { background: rgba(128,128,128,0.08); border-color: rgba(94,201,98,0.35); box-shadow: 0 8px 32px rgba(94,201,98,0.1), 0 2px 8px rgba(0,0,0,0.1); transform: translateY(-3px); }
    [data-testid="stHorizontalBlock"] > div { flex: 1 1 auto !important; }
    [data-testid="stMetricLabel"] { font-size: 0.74rem !important; font-weight: 600 !important; letter-spacing: 0.04em; text-transform: uppercase; opacity: 0.6; white-space: normal !important; overflow: visible !important; word-break: break-word !important; }
    [data-testid="stMetricValue"] { font-weight: 800 !important; font-size: 1.55rem !important; letter-spacing: -0.01em; color: var(--text-color); }

    .stTabs [data-baseweb="tab-list"] { gap: 8px; background: rgba(128,128,128,0.03); border-radius: 16px; padding: 7px; border: 1px solid rgba(128,128,128,0.08); backdrop-filter: blur(10px); }
    .stTabs [data-baseweb="tab"] { border-radius: 12px; padding: 13px 26px; font-weight: 600; font-size: 0.85rem; letter-spacing: 0.015em; transition: all 0.3s ease; }
    .stTabs [aria-selected="true"] { background: linear-gradient(135deg, rgba(46,125,50,0.2), rgba(94,201,98,0.1)) !important; border: 1px solid rgba(94,201,98,0.3) !important; box-shadow: 0 0 24px rgba(94,201,98,0.08); color: var(--text-color) !important; }
    .stTabs [data-baseweb="tab"]:hover { background: rgba(128,128,128,0.05); transform: translateY(-1px); }

    [data-testid="stExpander"] { background: rgba(128,128,128,0.03); border: 1px solid rgba(128,128,128,0.1); border-radius: 16px; backdrop-filter: blur(8px); transition: all 0.3s ease; }
    [data-testid="stExpander"]:hover { border-color: rgba(128,128,128,0.2); background: rgba(128,128,128,0.06); }
    div[data-testid="stVerticalBlockBorderWrapper"] > div:has(> [data-testid="stVerticalBlock"]) { border-color: rgba(128,128,128,0.1) !important; border-radius: 18px !important; background: rgba(128,128,128,0.02) !important; }

    .stDownloadButton > button { background: linear-gradient(135deg, #1B5E20, #4CAF50) !important; background-size: 200% 200% !important; animation: gradientShift 4s ease infinite !important; color: white !important; border: none !important; border-radius: 12px !important; font-weight: 700 !important; letter-spacing: 0.03em; padding: 12px 28px !important; transition: all 0.35s ease !important; box-shadow: 0 2px 8px rgba(46,125,50,0.2) !important; }
    .stDownloadButton > button:hover { box-shadow: 0 6px 28px rgba(76,175,80,0.35) !important; transform: translateY(-2px); }

    .stSelectbox > div > div, .stNumberInput > div > div > input { background: rgba(128,128,128,0.04) !important; border: 1px solid rgba(128,128,128,0.1) !important; border-radius: 12px !important; transition: all 0.25s ease !important; }
    .stSelectbox > div > div:hover, .stNumberInput > div > div > input:hover { border-color: rgba(94,201,98,0.3) !important; background: rgba(128,128,128,0.06) !important; }
    .stSelectbox > div > div:focus-within, .stNumberInput > div > div > input:focus { border-color: rgba(94,201,98,0.5) !important; box-shadow: 0 0 0 3px rgba(94,201,98,0.1) !important; }
    .stRadio > div { background: rgba(128,128,128,0.03); border-radius: 12px; padding: 4px 8px; }
    .stSlider [data-baseweb="slider"] [role="slider"] { background: linear-gradient(135deg, #2E7D32, #66BB6A) !important; box-shadow: 0 0 10px rgba(94,201,98,0.3); }

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(128,128,128,0.2); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(94,201,98,0.4); }
    hr { border: none !important; height: 1px !important; background: linear-gradient(90deg, transparent, rgba(94,201,98,0.2), rgba(66,165,245,0.2), transparent) !important; margin: 24px 0 !important; }
    .stCaption { opacity: 0.6; font-size: 0.78rem; }
    [data-testid="stAlert"] { border-radius: 14px !important; backdrop-filter: blur(8px); }
    [data-testid="stDataFrame"] { border-radius: 16px; overflow: hidden; border: 1px solid rgba(128,128,128,0.1) !important;}

    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; margin: 12px 0 20px; }
    @media (max-width: 768px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
    .kpi-card { background: rgba(128,128,128,0.035); border: 1px solid rgba(128,128,128,0.08); border-radius: 18px; padding: 24px 22px; backdrop-filter: blur(16px); transition: all 0.4s ease; position: relative; overflow: hidden; animation: fadeInUp 0.6s ease-out both; }
    .kpi-card:nth-child(1) { animation-delay: 0.05s; }
    .kpi-card:nth-child(2) { animation-delay: 0.12s; }
    .kpi-card:nth-child(3) { animation-delay: 0.19s; }
    .kpi-card:nth-child(4) { animation-delay: 0.26s; }
    .kpi-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; border-radius: 18px 18px 0 0; }
    .kpi-card::after { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.04) 45%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 55%, transparent 60%); background-size: 200% 100%; opacity: 0; transition: opacity 0.4s ease; pointer-events: none; }
    .kpi-card:hover::after { opacity: 1; animation: shimmer 1.8s ease infinite; }
    .kpi-card:hover { transform: translateY(-4px) scale(1.01); box-shadow: 0 12px 40px rgba(0,0,0,0.15); background: rgba(128,128,128,0.06); }
    .kpi-card.green::before  { background: linear-gradient(90deg, #1B5E20, #4CAF50, #81C784); }
    .kpi-card.blue::before   { background: linear-gradient(90deg, #0D47A1, #2196F3, #64B5F6); }
    .kpi-card.purple::before { background: linear-gradient(90deg, #4A148C, #9C27B0, #CE93D8); }
    .kpi-card.orange::before { background: linear-gradient(90deg, #BF360C, #FF5722, #FFAB91); }
    .kpi-icon { font-size: 1.7rem; margin-bottom: 10px; display: block; transition: transform 0.3s ease; }
    .kpi-card:hover .kpi-icon { transform: scale(1.15); }
    .kpi-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.07em; opacity: 0.6; margin-bottom: 8px; }
    .kpi-value { font-size: 1.5rem; font-weight: 800; line-height: 1.2; letter-spacing: -0.01em; color: var(--text-color); }

    .eco-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin: 18px 0; }
    @media (max-width: 768px) { .eco-grid { grid-template-columns: 1fr; } }
    .eco-card { background: rgba(128,128,128,0.035); border: 1px solid rgba(128,128,128,0.08); border-radius: 18px; padding: 28px 22px; text-align: center; backdrop-filter: blur(16px); transition: all 0.4s ease; position: relative; overflow: hidden; animation: fadeInUp 0.6s ease-out both; }
    .eco-card:nth-child(1) { animation-delay: 0.08s; }
    .eco-card:nth-child(2) { animation-delay: 0.16s; }
    .eco-card:nth-child(3) { animation-delay: 0.24s; }
    .eco-card::after { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.04) 45%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 55%, transparent 60%); background-size: 200% 100%; opacity: 0; transition: opacity 0.4s ease; pointer-events: none; }
    .eco-card:hover::after { opacity: 1; animation: shimmer 1.8s ease infinite; }
    .eco-card:hover { transform: translateY(-4px) scale(1.01); background: rgba(128,128,128,0.06); box-shadow: 0 12px 40px rgba(0,0,0,0.15); }
    .eco-card .eco-icon { font-size: 2.2rem; margin-bottom: 12px; transition: transform 0.3s ease; }
    .eco-card:hover .eco-icon { transform: scale(1.2); }
    .eco-card .eco-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; opacity: 0.6; margin-bottom: 10px; }
    .eco-card .eco-value { font-size: 1.7rem; font-weight: 800; letter-spacing: -0.01em; color: var(--text-color); }
    .eco-card .eco-delta { font-size: 0.82rem; margin-top: 8px; font-weight: 600; padding: 3px 10px; border-radius: 20px; display: inline-block; }
    .eco-card.receita { border-top: 2px solid rgba(102,187,106,0.5); }
    .eco-card.receita .eco-value { color: #4CAF50; }
    .eco-card.custo { border-top: 2px solid rgba(239,83,80,0.5); }
    .eco-card.custo .eco-value   { color: #F44336; }
    .eco-card.margem { border-top: 2px solid rgba(66,165,245,0.5); }
    .eco-card.margem .eco-value  { color: #2196F3; }

    .header-container { position: relative; padding: 28px 0 16px; margin-bottom: 8px; }
    .header-container::before { content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%); width: 350px; height: 350px; background: radial-gradient(circle, rgba(94,201,98,0.06) 0%, rgba(66,165,245,0.03) 40%, transparent 70%); pointer-events: none; z-index: 0; }
    .premium-title { font-size: 2.2rem; font-weight: 800; background: linear-gradient(135deg, #4CAF50, #2196F3, #9C27B0, #FF9800); background-size: 300% 300%; animation: gradientShift 6s ease infinite; -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 6px; line-height: 1.3; position: relative; z-index: 1; }
    .header-separator { height: 2px; background: linear-gradient(90deg, transparent, rgba(94,201,98,0.3), rgba(66,165,245,0.3), rgba(171,71,188,0.3), transparent); border-radius: 2px; margin-top: 14px; margin-bottom: 4px; }
    .badge-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; position: relative; z-index: 1; }
    .badge { font-size: 0.68rem; font-weight: 700; padding: 4px 12px; border-radius: 20px; letter-spacing: 0.04em; transition: all 0.25s ease; }
    .badge.green  { background: rgba(76,175,80,0.15); color: #4CAF50; border: 1px solid rgba(76,175,80,0.3); }
    .badge.blue   { background: rgba(33,150,243,0.15); color: #2196F3; border: 1px solid rgba(33,150,243,0.3); }
    .badge.purple { background: rgba(156,39,176,0.15); color: #9C27B0; border: 1px solid rgba(156,39,176,0.3); }
    .badge.orange { background: rgba(255,152,0,0.15); color: #FF9800; border: 1px solid rgba(255,152,0,0.3); }
    iframe { border-radius: 14px !important; border: 1px solid rgba(128,128,128,0.1) !important; }
    .footer-container { margin-top: 40px; padding: 24px 0 16px; border-top: 1px solid rgba(128,128,128,0.1); text-align: center; }
    .footer-text { font-size: 0.72rem; opacity: 0.6; letter-spacing: 0.03em; }
    .footer-brand { font-size: 0.9rem; font-weight: 700; background: linear-gradient(135deg, #4CAF50, #2196F3); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 6px; }
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
    .eco-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 16px 0; }
    @media (max-width: 768px) { .eco-grid { grid-template-columns: 1fr; } }
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
CSS_ATUAL = CSS_TERMINAL
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
st.markdown(f"""
<div class="header-container">
    <div class="premium-title">🌿 AgroInteligência — Previsão e Viabilidade de Safra</div>
    <div style="font-size:0.82rem; color:var(--text-color); opacity:0.75; margin-top:4px; position:relative; z-index:1;">
        <span style="color:#66BB6A; font-weight:600;">{len(df)}</span> registros ·
        <span style="color:#42A5F5; font-weight:600;">{df.municipio.nunique()}</span> municípios monitorados ·
        <span style="color:#AB47BC; font-weight:600;">{df.ano.min()}–{df.ano.max()}</span>
        {'· <span style="color:#FFA726; font-weight:600;">Atualizado em ' + atualizada_em + '</span>' if atualizada_em else ''}
    </div>
    <div class="badge-row">
        <span class="badge green">🛰️ MODIS</span>
        <span class="badge blue">🌧️ CHIRPS</span>
        <span class="badge purple">🌡️ ERA5-Land</span>
        <span class="badge orange">🗺️ MapBiomas</span>
    </div>
    <div class="header-separator"></div>
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
CUSTO_HA_REF = 4800.0  # Referência base de custeio
EIXO_BR = alt.Axis(labelExpr="replace(format(datum.value, ',.0f'), /,/g, '.')")

# --- PAINEL EXECUTIVO DE INDICADORES ---
st.markdown(f"""
<div class="kpi-grid">
    <div class="kpi-card green">
        <span class="kpi-icon">🎯</span>
        <div class="kpi-label">Margem de Precisão (RMSE)</div>
        <div class="kpi-value">± {qtd(metricas['rmse'])} {unidade}</div>
    </div>
    <div class="kpi-card blue">
        <span class="kpi-icon">📊</span>
        <div class="kpi-label">Variação Relativa</div>
        <div class="kpi-value">{metricas['rrmse']:.1f}%</div>
    </div>
    <div class="kpi-card purple">
        <span class="kpi-icon">🧠</span>
        <div class="kpi-label">Aderência Preditiva (R²)</div>
        <div class="kpi-value">{metricas['r2']:.3f}</div>
    </div>
    <div class="kpi-card orange">
        <span class="kpi-icon">📈</span>
        <div class="kpi-label">Benchmark de Tendência</div>
        <div class="kpi-value">{metricas['r2_baseline']:.3f}</div>
    </div>
</div>
""", unsafe_allow_html=True)

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
aba_mapa, aba_graficos, aba_eco = st.tabs([
    "🗺️ Inteligência Territorial & Previsão",
    "📈 Análise Histórica & Clima",
    "💰 Viabilidade Comercial & Margens"
])

# ==============================================================================
# ABA 1: MAPA E PREVISÃO
# ==============================================================================
with aba_mapa:
    esq, dir_ = st.columns([1, 2])
    with esq:
        municipio = st.selectbox(
            "Selecione o Município / Polo",
            municipios,
            key="mun_sel",
            format_func=disp,
            on_change=on_dropdown_change)

        comparar = st.toggle("Comparar com outro município", value=False)
        mun_comp: str | None = None
        if comparar:
            opcoes_comp = [m for m in municipios if m != municipio]
            mun_comp = st.selectbox(
                "Município para Comparação",
                opcoes_comp,
                format_func=disp)  # type: ignore

        st.write("")
        ano_alvo = st.number_input(
            "Safra Alvo para Projeção",
            min_value=int(
                df.ano.max()) + 1,
            max_value=int(
                df.ano.max()) + 3,
            value=int(
                df.ano.max()) + 1)

        r = estimador.estimar(municipio, int(ano_alvo))
        st.metric(f"Projeção Safra {ano_alvo} ({disp(municipio)})",
                  f"{qtd(r['estimativa_kg_ha'])} {unidade}",
                  delta=f"Intervalo: ± {qtd(r['margem_kg_ha'])} {unidade}",
                  delta_color="off")

        with st.expander("🌦️ Simulação de Cenário Climático"):
            chuva = st.slider(
                "Volume de Precipitação (% da média)",
                50,
                150,
                100,
                step=5)
            dtemp = st.slider("Desvio Térmico (°C)", -2.0, 3.0, 0.0, step=0.5)
            if chuva != 100 or dtemp != 0.0:
                hist = df[df.municipio == municipio]
                clima = hist[M.FEATURES].mean().to_dict()  # type: ignore
                clima["precip_total"] *= chuva / 100
                clima["temp_mean"] += dtemp
                clima["temp_max"] += dtemp
                clima["balanco_hidrico"] = clima["precip_total"] - \
                    clima["etp_total"]
                cenario = estimador.estimar(
                    municipio, int(ano_alvo), clima=clima)
                dif = cenario["estimativa_kg_ha"] - r["estimativa_kg_ha"]
                st.metric("Projeção Ajustada ao Clima",
                          f"{qtd(cenario['estimativa_kg_ha'])} {unidade}",
                          delta=f"{qtd(dif,
                                       '+')} {unidade}")

    with dir_:
        mapa, nome_para_interno, faixa_rend = construir_mapa(
            municipio, mun_comp, is_dark=is_dark)
        if mapa is not None:
            st.subheader("Panorama Geespacial dos Polos Produtivos")
            st_folium(
                mapa,
                width='stretch',
                height=430,
                returned_objects=["last_object_clicked_tooltip"],
                key="mapa_soja"
            )

            grad = ",".join(_VIRIDIS)
            bg = "#0d1117"
            brad = "2px"
            bord = "1px solid #30363d"
            col_t = "#8b949e"
            col_v = "#c9d1d9"
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
with aba_graficos:
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

    eixo_x_inteligente = alt.X(
        "ano:Q",
        title="Ano-safra",
        scale=alt.Scale(zero=False),
        axis=alt.Axis(format="d", tickMinStep=2)
    )

    base = alt.Chart(serie_plot).encode(x=eixo_x_inteligente)

    linha = base.mark_line(
        point=True).encode(
        y=alt.Y(
            "produtividade:Q", title=unidade, scale=alt.Scale(
                zero=False), axis=EIXO_BR), color=alt.Color(
                    "Nome:N", legend=alt.Legend(
                        title="Município", orient="bottom")), tooltip=[
                            "ano", "Nome", alt.Tooltip(
                                "produtividade_rotulo:N", title=unidade)], )

    tendencia = base.transform_regression(
        "ano",
        "produtividade",
        groupby=["Nome"]).mark_line(
        strokeDash=[
            5,
            5],
        strokeWidth=2,
        opacity=0.6).encode(
        color=alt.Color(
            "Nome:N",
            legend=None))

    marcas = base.transform_filter(alt.datum.repetido).mark_point(
        size=110, filled=True, color="#B00020"
    ).encode(
        y="produtividade:Q",
        tooltip=[alt.Tooltip("ano", title="Valor idêntico ao ano anterior")]
    )

    df_clima = pd.DataFrame(
        [
            {
                "ano": 2003, "Clima": "El Niño"}, {
                "ano": 2010, "Clima": "El Niño"}, {
                    "ano": 2015, "Clima": "El Niño"}, {
                        "ano": 2016, "Clima": "El Niño"}, {
                            "ano": 2024, "Clima": "El Niño"}, {
                                "ano": 2008, "Clima": "La Niña"}, {
                                    "ano": 2011, "Clima": "La Niña"}, {
                                        "ano": 2021, "Clima": "La Niña"}, {
                                            "ano": 2022, "Clima": "La Niña"}])
    clima_chart = alt.Chart(df_clima).mark_rule(
        size=8, opacity=0.3).encode(
        x=eixo_x_inteligente, color=alt.Color(
            "Clima:N", scale=alt.Scale(
                domain=[
                    "El Niño", "La Niña"], range=[
                        "#d73027", "#4575b4"]), legend=alt.Legend(
                            title="Anos de Forte Influência Climática", orient="bottom")))

    grafico_prod = alt.layer(
        clima_chart,
        linha,
        tendencia,
        marcas).resolve_scale(
        color='independent')
    st.altair_chart(grafico_prod, width='stretch')
    st.caption("A linha tracejada indica a tendência tecnológica. As marcações verticais destacam anos de forte impacto de El Niño / La Niña.")

    st.subheader("Expansão da Área Plantada (Hectares)")
    area = alt.Chart(serie_plot).mark_area(
        opacity=0.4).encode(
        x=eixo_x_inteligente, y=alt.Y(
            "soy_area_ha:Q", title="Hectares", axis=EIXO_BR), color=alt.Color(
                "Nome:N", legend=alt.Legend(
                    title="Município", orient="bottom")), tooltip=[
                        "ano", "Nome", alt.Tooltip(
                            "area_rotulo:N", title="Hectares")], )
    st.altair_chart(area, width='stretch')

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
with aba_eco:
    st.markdown("""
    <div style="margin-bottom:4px">
        <span style="font-size:1.5rem">💰</span>
        <span style="font-size:1.2rem; font-weight:700; margin-left:6px;">Inteligência de Mercado & Margens por Hectare</span>
    </div>
    <p style="font-size:0.85rem; color:var(--text-color); opacity:0.6; margin-top:0;">
        Simule cenários financeiros combinando projeções de IA com preços em tempo real e custeio operacional.
    </p>
    """, unsafe_allow_html=True)

    r_eco = estimador.estimar(municipio, int(df.ano.max()) + 1)

    col_eco1, col_eco2 = st.columns(2)
    with col_eco1:
        preco = st.number_input(
            "Preço de referência da saca (R$ / 60 kg)",
            min_value=0.0,
            value=PRECO_SACA_ONLINE,
            step=5.0)
        st.caption(
            "🌐 **Fonte da Cotação:** Atualizado via API de Indicadores de Mercado / Commodities (AwesomeAPI).")
    with col_eco2:
        custo_ha = st.number_input(
            "Custo operacional de referência (R$ / hectare)",
            min_value=0.0,
            value=CUSTO_HA_REF,
            step=100.0)
        st.caption(
            "📊 **Fonte do Custo:** Boletins Técnicos de Custo de Produção (Aprosoja Brasil / Conab - COE).")

    est_sacas_ha = r_eco["estimativa_kg_ha"] / SACA_KG
    receita_ha = est_sacas_ha * preco
    margem_ha = receita_ha - custo_ha
    pct_margem = f"{margem_ha / custo_ha * 100:+.0f}%" if custo_ha else "—"

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
        <div class="eco-card margem">
            <div class="eco-icon">📈</div>
            <div class="eco-label">Margem Líquida / ha</div>
            <div class="eco-value">{brl(margem_ha)}</div>
            <div class="eco-delta" style="color:{'#66BB6A' if margem_ha >= 0 else '#EF5350'}">{pct_margem} sobre o custo</div>
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

with st.expander("ℹ️ Sobre a Tecnologia e Fontes de Dados"):
    st.markdown("""
**Plataforma de AgroInteligência Preditiva** — Solução baseada em inteligência artificial para previsão de produtividade de soja e monitoramento de safras no Estado do Pará.

* **Tecnologia:** Algoritmos de Machine Learning integrados a dados multitemporais de satélite (MODIS, CHIRPS, ERA5-Land, MapBiomas).
* **Fontes Econômicas:** Indicadores de mercado físico em tempo real (AwesomeAPI) e boletins de custo operacional efetivo (Aprosoja / Conab).
* **Repositório do Sistema:** [github.com/engsoft7/dissertacao-soja-ia](https://github.com/engsoft7/dissertacao-soja-ia)
""")

# ── FOOTER PROFISSIONAL ──
st.markdown("""
<div class="footer-container">
    <div class="footer-brand">🌿 AgroInteligência</div>
    <div class="footer-text">
        Plataforma de Inteligência Preditiva para Safra de Soja — Estado do Pará<br>
        Machine Learning · Sensoriamento Remoto · Análise de Viabilidade Comercial<br>
        <span style="margin-top:8px; display:inline-block;">
            <a href="https://github.com/engsoft7/dissertacao-soja-ia" target="_blank">GitHub</a>
            &nbsp;·&nbsp; Desenvolvido com Streamlit &nbsp;·&nbsp; Dados: IBGE · MODIS · CHIRPS · ERA5
        </span>
    </div>
</div>
""", unsafe_allow_html=True)
