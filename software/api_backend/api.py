from fastapi import FastAPI, HTTPException
from functools import lru_cache
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import json
import requests
import sys
from pathlib import Path

# Add the dashboard_web to sys path to import model
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard_web"))
import model as M

app = FastAPI(title="Agro Inteligência API", description="FastAPI for Soybean Yield Prediction System")

# Enable CORS for generic clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


MUNICIPIOS_FORMATADOS = {
    'Conceicao Do Araguaia': 'Conceição do Araguaia', 'Floresta Do Araguaia': 'Floresta do Araguaia',
    'Paragominas': 'Paragominas', 'Redencao': 'Redenção', 'Santarem': 'Santarém',
    'Belterra': 'Belterra', 'Dom Eliseu': 'Dom Eliseu', 'Ulianopolis': 'Ulianópolis',
    'Santana Do Araguaia': 'Santana do Araguaia', 'Monte Alegre': 'Monte Alegre',
    'Novo Progresso': 'Novo Progresso', 'Santa Maria Das Barreiras': 'Santa Maria das Barreiras',
    'Uruara': 'Uruará', 'Agua Azul Do Norte': 'Água Azul do Norte', 'Rondon Do Para': 'Rondon do Pará',
    'Altamira': 'Altamira', 'Cumaru Do Norte': 'Cumaru do Norte', 'Placas': 'Placas',
    'Rio Maria': 'Rio Maria', 'Ruropolis': 'Rurópolis', 'Tailandia': 'Tailândia',
    'Abel Figueiredo': 'Abel Figueiredo', 'Ipixuna Do Para': 'Ipixuna do Pará',
    'Goianesia Do Para': 'Goianésia do Pará', "Pau D'arco": "Pau D'Arco",
    'Sao Felix Do Xingu': 'São Félix do Xingu', 'Tucuma': 'Tucumã',
    'Xinguara': 'Xinguara', 'Brejo Grande Do Araguaia': 'Brejo Grande do Araguaia',
    'Maraba': 'Marabá', 'Sao Joao Do Araguaia': 'São João do Araguaia',
    'Breu Branco': 'Breu Branco', 'Curionopolis': 'Curionópolis',
    'Jacareacanga': 'Jacareacanga', 'Jacunda': 'Jacundá', 'Picarra': 'Piçarra',
    'Sapucaia': 'Sapucaia', 'Tome-acu': 'Tomé-Açu'
}
REV_MUNICIPIOS = {v: k for k, v in MUNICIPIOS_FORMATADOS.items()}

ROOT_PATH = Path(__file__).resolve().parents[2]
DADOS_PATH = ROOT_PATH / "pesquisa" / "dados" / "soja_para_mascarado_2001_2024.csv"

# In-memory cached model
class AppState:
    df = None
    estimador = None
    last_year = None

@app.on_event("startup")
def load_model():
    df = M.carregar(str(DADOS_PATH))
    AppState.df = df
    AppState.estimador = M.Estimador().treinar(df)
    AppState.estimador.validar(df)  # Popula métricas de mae e rmse
    AppState.last_year = int(df["ano"].max())
    print("Modelo carregado e treinado com sucesso.", flush=True)

class PrevisaoRequest(BaseModel):
    municipio: str

@app.get("/api/municipios")
def list_municipios():
    if AppState.df is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")
    muns = AppState.df["municipio"].unique().tolist()
    muns_formatados = sorted([MUNICIPIOS_FORMATADOS.get(m, m) for m in muns])
    return {"municipios": muns_formatados}

@app.get("/api/kpis_economia")
def get_kpis_economia():
    if AppState.df is None:
         raise HTTPException(status_code=503, detail="Modelo não carregado")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 
            'Accept': 'application/json'
        }
        r_cbot = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/ZS=F', headers=headers)
        price_cents = r_cbot.json()['chart']['result'][0]['meta']['regularMarketPrice']
        usd_price_bag = (price_cents / 100) * 2.20462
        
        r_usd = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/BRL=X', headers=headers)
        usd_brl = float(r_usd.json()['chart']['result'][0]['meta']['regularMarketPrice'])
        
        brl_price_bag = round(usd_price_bag * usd_brl, 2)
        custo_ha = round((brl_price_bag * 55) * 0.65, 2)
        
        return {
             "soja_preco_saca": brl_price_bag,
             "custo_ha": custo_ha,
             "ano_referencia": int(AppState.last_year)
        }
    except Exception as e:
        print("Erro online KPIs:", e, flush=True)
        return {
             "soja_preco_saca": 120.0,
             "custo_ha": 3500.0,
             "ano_referencia": int(AppState.last_year)
        }

@app.get("/api/previsao/{municipio}")
def get_previsao(municipio: str):
    if AppState.df is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")
    
    raw_municipio = REV_MUNICIPIOS.get(municipio, municipio)
    df_mun = AppState.df[AppState.df["municipio"] == raw_municipio].copy()
    if df_mun.empty:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    
    try:
        mae = float(AppState.estimador.mae)
        resultado = []
        # Histórico passado
        for _, row in df_mun.iterrows():
            ano = int(row["ano"])
            real = float(row["rendimento_kg_ha"])
            # Simulando o predito no passado apenas como espelho + noise ou rodando modelo referência
            # Mas podemos focar na simulação para o ano futuro, e botar null para "predito" antigo
            # ou mockar o estimar no passado
            r = AppState.estimador.estimar(raw_municipio, ano)
            pred = float(r["estimativa_kg_ha"])
            resultado.append({
                "ano": ano,
                "rendimento_predito": pred,
                "rendimento_real": real,
                "margem_erro": mae
            })
        
        # Futuro projetado (Próximos 3 anos)
        ano_max = int(df_mun["ano"].max())
        for delta in range(1, 4):
            ano_futuro = ano_max + delta
            rf = AppState.estimador.estimar(raw_municipio, ano_futuro)
            resultado.append({
                 "ano": ano_futuro,
                 "rendimento_predito": float(rf["estimativa_kg_ha"]),
                 "rendimento_real": 0.0, # Indisponível
                 "margem_erro": float(rf["margem_kg_ha"])
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {
        "municipio": municipio, 
        "historico": resultado,
        "elNinos": [2003, 2010, 2015, 2016, 2023, 2024],
        "laNinas": [2008, 2011, 2021, 2022]
    }

@app.get("/api/mapa/geo")
def get_mapa_geo():
    geo_path = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "para_geo.json"
    try:
        geo = json.loads(geo_path.read_text(encoding="utf-8"))
        return geo
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Erro ao carregar mapa: {str(e)}")

@lru_cache(maxsize=128)
def _generate_map_html_cached(municipio: str, theme: str) -> str:
    import folium
    import branca.colormap as cm
    import math

    geo_path = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "para_geo.json"
    rios_path = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "rios_para.json"
    mun_path = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "municipios_para.csv"
    
    try:
        geo = json.loads(geo_path.read_text(encoding="utf-8"))
        rios = json.loads(rios_path.read_text(encoding="utf-8")) if rios_path.exists() else None
        pts_coords = pd.read_csv(mun_path)
    except Exception as e:
        return HTMLResponse(f"Erro ao carregar dados geográficos: {str(e)}", status_code=500)
    
    last_year = int(AppState.df["ano"].max())
    recente = AppState.df[AppState.df["ano"] >= last_year - 4]
    
    agg = recente.groupby("cod_ibge7").agg(
        area=("soy_area_ha", "mean"),
        rend=("rendimento_kg_ha", "mean")
    ).reset_index()
    
    pts = pd.merge(agg, pts_coords, on="cod_ibge7", how="inner")
    
    latmin, latmax = pts["latitude"].min(), pts["latitude"].max()
    lonmin, lonmax = pts["longitude"].min(), pts["longitude"].max()

    m = folium.Map(location=[(latmin + latmax) / 2, (lonmin + lonmax) / 2],
                   tiles="cartodbdark_matter" if theme == "dark" else "cartodbpositron", zoom_start=6, control_scale=True)
                   
    folium.GeoJson(
        geo,
        name="Pará",
        interactive=False,
        style_function=lambda f: {
            "fillColor": "#1b2d1b",
            "color": "#304a30",
            "weight": 1.0,
            "fillOpacity": 0.2}).add_to(m)

    if rios is not None and rios.get("features"):
        folium.GeoJson(
            rios,
            name="Rios",
            interactive=False,
            style_function=lambda f: {
                "color": "#4a90d9",
                "weight": 1.3,
                "opacity": 0.85}).add_to(m)

    _VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]
    rmin, rmax = float(pts["rend"].min()), float(pts["rend"].max())
    cmap = cm.LinearColormap(_VIRIDIS, vmin=rmin, vmax=rmax)
    
    
    amax = float(pts["area"].max())
    
    _cod_por_nome = AppState.df.drop_duplicates("municipio").set_index("municipio")["cod_ibge7"].to_dict()
    raw_municipio = REV_MUNICIPIOS.get(municipio, municipio) if municipio else None
    cod_sel = _cod_por_nome.get(raw_municipio)

    lat_sel, lon_sel = None, None
    for _, r in pts.iterrows():
        cod = r["cod_ibge7"]
        lat = r["latitude"]
        lon = r["longitude"]
        if cod == cod_sel:
            lat_sel, lon_sel = lat, lon
        area = r["area"]
        rend = r["rend"]
        nome = next((k for k, v in _cod_por_nome.items() if v == cod), str(cod))
        
        selec_prin = (cod == cod_sel)
        cor_borda = "#B00020" if selec_prin else "white"
        peso_borda = 3.5 if selec_prin else 0.7

        folium.CircleMarker(
            location=[lat, lon],
            radius=4 + 14 * math.sqrt(area / amax),
            color=cor_borda,
            weight=peso_borda,
            fill=True, fill_color=cmap(rend), fill_opacity=0.9,
            tooltip=nome
        ).add_to(m)


    # Custom responsive HTML legend for mobile
    bg_color = "rgba(0,0,0,0.75)" if theme == "dark" else "rgba(255,255,255,0.85)"
    text_color = "white" if theme == "dark" else "black"
    legend_html = f'''
    <div style="position: fixed; bottom: 25px; left: 50%; transform: translateX(-50%); 
                width: 75%; max-width: 320px; background: {bg_color}; padding: 8px 12px; 
                border-radius: 8px; z-index: 9999; color: {text_color}; 
                font-family: Arial, sans-serif; font-size: 13px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        <div style="text-align: center; margin-bottom: 5px; font-weight: bold; letter-spacing: 0.5px;">PRODUTIVIDADE (KG/HA)</div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-weight: 500;">
            <span>{int(rmin)}</span>
            <span>{int((rmin+rmax)/2)}</span>
            <span>{int(rmax)}</span>
        </div>
        <div style="width: 100%; height: 12px; background: linear-gradient(to right, #440154, #3b528b, #21918c, #5ec962, #fde725); border-radius: 4px;"></div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    if lat_sel is not None and lon_sel is not None:
        m.fit_bounds([[lat_sel - 0.7, lon_sel - 0.7], [lat_sel + 0.7, lon_sel + 0.7]])
    else:
        m.fit_bounds([[latmin, lonmin], [latmax, lonmax]])

    html_content = m.get_root().render()
    

    
    return html_content

@app.get("/api/mapa/render", response_class=HTMLResponse)
def render_mapa(municipio: str = None, theme: str = "dark"):
    try:
        html = _generate_map_html_cached(municipio, theme)
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(f"Erro ao gerar mapa: {str(e)}", status_code=500)


class SimulacaoRequest(BaseModel):
    municipio: str
    precip_factor: float
    temp_offset: float

@app.post("/api/simulacao")
def simular_cenario(req: SimulacaoRequest):
    if AppState.df is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")
    
    ano_alvo = int(AppState.last_year) + 1
    raw_municipio = REV_MUNICIPIOS.get(req.municipio, req.municipio)
    
    hist = AppState.df[AppState.df.municipio == raw_municipio]
    if hist.empty:
        raise HTTPException(status_code=404, detail="Município não encontrado")
        
    clima = hist[M.FEATURES].mean().to_dict()
    
    # Baseline normal (apenas média histórica)
    result_base = AppState.estimador.estimar(raw_municipio, ano_alvo, clima=clima)
    
    # Aplicar modificadores no clima
    clima_novo = clima.copy()
    clima_novo["precip_total"] *= req.precip_factor
    clima_novo["temp_mean"] += req.temp_offset
    clima_novo["temp_max"] += req.temp_offset
    clima_novo["balanco_hidrico"] = clima_novo["precip_total"] - clima_novo["etp_total"]
    
    result_sim = AppState.estimador.estimar(raw_municipio, ano_alvo, clima=clima_novo)
    
    return {
        "municipio": req.municipio,
        "baseline_kg_ha": float(result_base["estimativa_kg_ha"]),
        "estimativa_kg_ha": float(result_sim["estimativa_kg_ha"]),
        "delta_kg_ha": float(result_sim["estimativa_kg_ha"] - result_base["estimativa_kg_ha"])
    }
