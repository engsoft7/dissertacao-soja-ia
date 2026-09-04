from financas import (get_financas, get_custos_locais, CUSTO_REFERENCIA_HA,
                      PRECO_RECEBIDO_CONAB_SACA, LEVANTAMENTO,
                      descricao_do_levantamento, nota_sobre_o_preco,
                      aviso_de_defasagem, meses_desde_o_levantamento)
from fastapi import FastAPI, HTTPException
from functools import lru_cache
from contextlib import asynccontextmanager
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import json
import requests
import sys
import threading
import time
from pathlib import Path

# Add the dashboard_web to sys path to import model
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard_web"))
import model as M

# ── Background Yahoo Finance cache ──────────────────────────────────
# Guarda apenas a cotação de bolsa, usada como comparação. O preço da
# simulação é o de porteira da CONAB, constante e definido em financas.py.
_finance_cache = {"cbot_saca": None, "usd_brl": None, "ts": 0.0}
_finance_lock = threading.Lock()

def _refresh_finance():
    """Fetch CBOT soy + USD/BRL in background, update cache."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
               'Accept': 'application/json'}
    try:
        r_cbot = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/ZS=F',
                              headers=headers, timeout=10)
        price_cents = r_cbot.json()['chart']['result'][0]['meta']['regularMarketPrice']
        usd_price_bag = (price_cents / 100) * 2.20462

        r_usd = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/BRL=X',
                             headers=headers, timeout=10)
        usd_brl = float(r_usd.json()['chart']['result'][0]['meta']['regularMarketPrice'])

        brl_price_bag = round(usd_price_bag * usd_brl, 2)
        with _finance_lock:
            _finance_cache["cbot_saca"] = brl_price_bag
            _finance_cache["usd_brl"] = usd_brl
            _finance_cache["ts"] = time.time()
        print(f"Finance cache atualizado: R$ {brl_price_bag}/sc", flush=True)
    except Exception as e:
        print(f"Finance refresh erro (usando cache): {e}", flush=True)

def _get_cached_finance():
    """Return cached finance data; refresh in background if stale (>15 min)."""
    with _finance_lock:
        data = _finance_cache.copy()
    if time.time() - data["ts"] > 900:  # 15 min
        threading.Thread(target=_refresh_finance, daemon=True).start()
    return data


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    df = M.carregar(str(DADOS_PATH))
    AppState.df = df
    AppState.estimador = M.Estimador().treinar(df)
    AppState.estimador.validar(df)  # Popula métricas de mae e rmse
    AppState.last_year = int(df["ano"].max())
    print("Modelo carregado e treinado com sucesso.", flush=True)
    # Pre-populate finance cache in background
    threading.Thread(target=_refresh_finance, daemon=True).start()
    yield

app = FastAPI(title="Agro Inteligência API", description="FastAPI for Soybean Yield Prediction System", lifespan=app_lifespan)

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

REVERSE_FORMATADOS = {v: k for k, v in MUNICIPIOS_FORMATADOS.items()}

# Enable CORS for generic clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/financas/{municipio}")
def get_financas(municipio: str):
    fin = _get_cached_finance()

    raw_municipio = REVERSE_FORMATADOS.get(municipio, municipio)
    custos = get_custos_locais(raw_municipio)
    custo_ha = custos["custo_ha"]
    
    return {
        "municipio": municipio,
        # Preço de porteira da CONAB, da mesma praça de onde vem o custo. A
        # cotação de Chicago vai ao lado, para comparação, e nunca como padrão.
        "soja_preco_saca": PRECO_RECEBIDO_CONAB_SACA,
        "soja_preco_cbot_saca": fin["cbot_saca"],
        "custo_ha": custo_ha,
        "vtn_ha": custos["vtn_ha"],
        # Rótulo e nota vêm do servidor de propósito: quando a CONAB publica
        # levantamento novo, o aplicativo passa a exibir a praça, a data e a
        # posição do preço na série corretas sem recompilar o APK. Antes eram
        # strings fixas no Kotlin, que envelheciam em silêncio.
        "fonte_preco": descricao_do_levantamento(),
        "nota_preco": nota_sobre_o_preco(),
        "levantamento": LEVANTAMENTO["levantamento"],
        # Calculado a cada requisição, nunca gravado: um levantamento estático
        # envelhece calado, e é o servidor que sabe que dia é hoje. Sem isto, o
        # aplicativo aberto daqui a dois anos exibiria o preço de 2026 como se
        # fosse o de agora.
        "defasagem_meses": meses_desde_o_levantamento(),
        "aviso_preco": aviso_de_defasagem(),
        "ano_referencia": int(AppState.last_year) if AppState.df is not None else 2024
    }

ROOT_PATH = Path(__file__).resolve().parents[2]
DADOS_PATH = ROOT_PATH / "pesquisa" / "dados" / "soja_para_mascarado_2001_2024.csv"

# In-memory cached model
class AppState:
    df = None
    estimador = None
    last_year = None

# Startup phase handled via lifespan manager in app definition

@app.get("/api/ping")
def ping():
    """Lightweight health/warm-up endpoint for mobile app cold-start."""
    return {"status": "ok", "model_loaded": AppState.df is not None}

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
    
    fin = _get_cached_finance()
    # Antes: custo_ha = preço da saca * 55 * 0,65, fórmula sem origem que fazia
    # o custo variar com a cotação. Custeio de lavoura não acompanha o preço de
    # venda. Passa a usar a referência da CONAB, a mesma do painel web.
    custo_ha = CUSTO_REFERENCIA_HA

    return {
         "soja_preco_saca": PRECO_RECEBIDO_CONAB_SACA,
         "soja_preco_cbot_saca": fin["cbot_saca"],
         "custo_ha": custo_ha,
         "fonte_preco": descricao_do_levantamento(),
         "nota_preco": nota_sobre_o_preco(),
         "levantamento": LEVANTAMENTO["levantamento"],
         "defasagem_meses": meses_desde_o_levantamento(),
         "aviso_preco": aviso_de_defasagem(),
         "ano_referencia": int(AppState.last_year)
    }

def _get_eventos_enso():
    enso_path = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "eventos_enso.json"
    if enso_path.exists():
        try:
            d = json.loads(enso_path.read_text(encoding="utf-8"))
            return (
                d.get("el_ninos", [2003, 2010, 2015, 2016, 2023, 2024]),
                d.get("la_ninas", [2000, 2008, 2011, 2021, 2022])
            )
        except Exception:
            pass
    return [2003, 2010, 2015, 2016, 2023, 2024], [2000, 2008, 2011, 2021, 2022]

@app.get("/api/previsao/{municipio}")
def get_previsao(municipio: str):
    if AppState.df is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")
    
    raw_municipio = REVERSE_FORMATADOS.get(municipio, municipio)
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
                 # Sentinela de safra ainda não divulgada pela PAM. Os clientes
                 # devem exibir traço, e não zero: um zero aqui anuncia uma
                 # colheita nula que não houve.
                 "rendimento_real": 0.0,
                 "margem_erro": float(rf["margem_kg_ha"])
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    el_ninos, la_ninas = _get_eventos_enso()
    return {
        "municipio": municipio, 
        "historico": resultado,
        "elNinos": el_ninos,
        "laNinas": la_ninas
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

    # Sem camada de tiles, como no painel web. As geometrias que importam — o
    # contorno do Pará e os rios — estão versionadas no repositório. Puxar tiles
    # do CARTO deixava o mapa do aplicativo dependendo de um terceiro em tempo
    # de execução, contradizia a legenda do painel ("o mapa não usa camada de
    # terceiros") e derrubava a tela inteira sem internet, num aplicativo que se
    # anuncia de operação predominantemente offline.
    fundo_mapa = "#12151a" if theme == "dark" else "#eef1f4"
    m = folium.Map(
        location=[(latmin + latmax) / 2, (lonmin + lonmax) / 2],
        tiles=None,
        zoom_start=6,
        min_zoom=5,
        max_zoom=12,
        max_bounds=True,
        min_lat=-10.5,
        max_lat=3.5,
        min_lon=-60.0,
        max_lon=-45.0,
        control_scale=True,
        prefer_canvas=True
    )
                   
    folium.GeoJson(
        geo,
        name="Pará",
        interactive=False,
        smooth_factor=1.0,
        style_function=lambda f: {
            "fillColor": "#1b2d1b",
            "color": "#304a30",
            "weight": 1.2,
            "fillOpacity": 0.2}).add_to(m)

    if rios is not None and rios.get("features"):
        folium.GeoJson(
            rios,
            name="Rios",
            interactive=False,
            smooth_factor=1.0,
            style_function=lambda f: {
                "color": "#4a90d9",
                "weight": 1.3,
                "opacity": 0.85}).add_to(m)

    _VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]
    rmin, rmax = float(pts["rend"].min()), float(pts["rend"].max())
    cmap = cm.LinearColormap(_VIRIDIS, vmin=rmin, vmax=rmax)
    
    amax = float(pts["area"].max())
    
    _cod_por_nome = AppState.df.drop_duplicates("municipio").set_index("municipio")["cod_ibge7"].to_dict()
    raw_municipio = REVERSE_FORMATADOS.get(municipio, municipio) if municipio else None
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
            radius=3 + 10 * math.sqrt(area / amax),
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
        <div style="text-align: center; margin-bottom: 2px; font-weight: bold; letter-spacing: 0.5px;">PRODUTIVIDADE (KG/HA)</div>
        <div style="text-align: center; margin-bottom: 5px; font-size: 10px; opacity: 0.75;">média observada das cinco últimas safras</div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-weight: 500;">
            <span>{int(rmin)}</span>
            <span>{int((rmin+rmax)/2)}</span>
            <span>{int(rmax)}</span>
        </div>
        <div style="width: 100%; height: 12px; background: linear-gradient(to right, #440154, #3b528b, #21918c, #5ec962, #fde725); border-radius: 4px;"></div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    # Sem tiles o Leaflet deixa o fundo transparente; sem isto o mapa aparece
    # branco no tema escuro.
    m.get_root().html.add_child(folium.Element(
        f"<style>.leaflet-container {{ background: {fundo_mapa} !important; }}</style>"))
    
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

@lru_cache(maxsize=1)
def _sensibilidade_clima():
    """Associação chuva-rendimento na base, calculada uma vez por processo."""
    if AppState.df is None:
        return None
    return M.sensibilidade_climatica(AppState.df)


@app.post("/api/simulacao")
def simular_cenario(req: SimulacaoRequest):
    if AppState.df is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")
    
    ano_alvo = int(AppState.last_year) + 1
    raw_municipio = REVERSE_FORMATADOS.get(req.municipio, req.municipio)
    
    hist = AppState.df[AppState.df.municipio == raw_municipio]
    if hist.empty:
        raise HTTPException(status_code=404, detail="Município não encontrado")
        
    clima = hist[M.FEATURES].mean().to_dict()
    
    # ── Optimized: compute baseline once, reuse for both scenarios ──
    from model import _baseline
    import numpy as np
    base_val = float(_baseline(
        AppState.estimador.df,
        pd.Series([raw_municipio]),
        pd.Series([ano_alvo])
    )[0])
    
    # Baseline prediction (unmodified climate)
    x_base = np.array([clima[f] for f in M.FEATURES], dtype=float)
    corr_base = float(AppState.estimador.modelo.predict(
        AppState.estimador.scaler.transform(x_base.reshape(1, -1))
    )[0])
    est_base = base_val + corr_base
    
    # Modified climate scenario
    clima_novo = clima.copy()
    clima_novo["precip_total"] *= req.precip_factor
    clima_novo["temp_mean"] += req.temp_offset
    clima_novo["temp_max"] += req.temp_offset
    clima_novo["balanco_hidrico"] = clima_novo["precip_total"] - clima_novo["etp_total"]

    # A floresta aleatória não extrapola. Sem prender o cenário à faixa vista no
    # treino, chuva zero devolvia colheita acima da média e +3 °C dava o mesmo
    # número que +6 °C. O cenário é limitado, e a interface avisa quando isso
    # acontece — o modelo só tem o que dizer onde ele viu dado.
    clima_novo, fora_da_faixa = AppState.estimador.limitar_clima(clima_novo)

    x_sim = np.array([clima_novo[f] for f in M.FEATURES], dtype=float)
    corr_sim = float(AppState.estimador.modelo.predict(
        AppState.estimador.scaler.transform(x_sim.reshape(1, -1))
    )[0])
    est_sim = base_val + corr_sim
    
    return {
        "municipio": req.municipio,
        "baseline_kg_ha": est_base,
        "estimativa_kg_ha": est_sim,
        "fora_da_faixa": fora_da_faixa,
        "delta_kg_ha": est_sim - est_base,
        # Para a interface poder dizer o que o cenário significa: a margem do
        # modelo e a força da associação medida na base. Sem isso o usuário lê
        # uma variação de dezenas de quilos como se fosse resposta agronômica.
        "margem_kg_ha": AppState.estimador.rmse,
        "sensibilidade": _sensibilidade_clima(),
    }
