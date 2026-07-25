import streamlit as st
import geopandas as gpd
import pandas as pd
import json

@st.cache_data
def carregar_geo():
    with open("software/dashboard_web/mapas_pa.geojson", "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def carregar_rios():
    return gpd.read_file("software/dashboard_web/rios.geojson")

@st.cache_data
def carregar_municipios():
    return gpd.read_file("software/dashboard_web/sedes_municipais.geojson")

@st.cache_data(ttl=3600)
def data_atualizacao() -> str | None:
    try:
        import urllib.request
        import re
        url = "https://github.com/engsoft7/dissertacao-soja-ia/commits/main/software/dados"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8")
        padrao = r'<relative-time[^>]*datetime="([^"]+)"'
        match = re.search(padrao, html)
        if match:
            dt_iso = match.group(1)
            dt = pd.to_datetime(dt_iso)
            return dt.strftime("%d/%m/%Y")
    except Exception:
        pass
    return None

@st.cache_data(ttl=3600)
def buscar_preco_soja_online() -> float:
    preco_padrao = 135.0
    try:
        import urllib.request
        import re
        url = "https://www.noticiasagricolas.com.br/cotacoes/soja/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8")
        matches = re.findall(r"Paranaguá.*?<td[^>]*>(.*?)</td>", html, re.IGNORECASE | re.DOTALL)
        if len(matches) >= 4:
            val_str = matches[3].replace(".", "").replace(",", ".")
            val = float(val_str)
            if val > 50:
                return val
    except Exception:
        pass
    return preco_padrao
