# -*- coding: utf-8 -*-
"""
Painel de Inteligência e Previsão de Safra de Soja — Pará

Execução:
    streamlit run app.py
"""
import model as M
import json
import math
import re
import sys
from datetime import date
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
EVENTOS_ENSO = DADOS.parent / "eventos_enso.json"
SACA_KG = 60  # saca de soja

# ── LEVANTAMENTO DA CONAB (preço, custo, praça e data) ───────────────────────
# Vem de pesquisa/dados/conab/levantamento_atual.json, o MESMO arquivo que a
# API lê, gerado dos CSVs da extração por
# software/automacao_github/gera_levantamento_conab.py e atualizado pelo
# workflow mensal. Painel, API e aplicativo passam a não poder discordar sobre
# qual levantamento está em uso, e as legendas acompanham a CONAB sozinhas:
# antes a praça e a data estavam escritas por extenso em cada legenda, e
# envelheciam em silêncio.
#
# Lê o arquivo direto, sem importar financas.py, de propósito: o painel tem que
# abrir mesmo quando aquele módulo não importa (foi o que o derrubou em
# 30/08/2026), e um dado de arquivo não deve depender de um import opcional.
LEVANTAMENTO_JSON = DADOS.parent / "conab" / "levantamento_atual.json"

# Reserva de emergência, com o levantamento de março de 2026, para o painel
# abrir com números corretos se o arquivo faltar no deploy. Não é segunda fonte
# da verdade: test_robustez_painel.py confere que continua igual ao JSON.
# reserva-conab-inicio (reescrita por gera_levantamento_conab.py)
LEVANTAMENTO_CONAB_RESERVA = {
    "praca": "Pedro Afonso (TO)",
    "levantamento": "MAR-2026",
    "levantamento_extenso": "março de 2026",
    "preco_recebido_saca": 105.09,
    "custo_operacional_saca": 109.94,
    "produtividade_referencia_kg_ha": 2880.0,
    "produtividade_referencia_sc_ha": 48.0,
    "custo_operacional_ha": 5277.12,
    "custo_total_ha": 5714.88,
    "renda_fatores_ha": 437.76,
    "serie": {
        "levantamentos": 13,
        "periodo": "março de 2023 a março de 2026",
        "periodo_curto": "mar/2023 a mar/2026",
        "menor_saca": 105.09,
        "menor_levantamento": "MAR-2026",
        "menor_levantamento_extenso": "março de 2026",
        "maior_saca": 146.35,
        "maior_levantamento": "MAR-2023",
        "maior_levantamento_extenso": "março de 2023",
        "mediana_saca": 116.91,
        "media_saca": 118.89,
        "posicao_do_atual": 1,
        "levantamentos_negativos": [
            "MAI-2023",
            "MAR-2026"
        ]
    },
    "textos": {
        "descricao": "CONAB, Pedro Afonso (TO), março de 2026",
        "nota_preco": "R$ 105,09/sc é o menor dos 13 levantamentos da praça (mar/2023 a mar/2026, mediana R$ 116,91). Cenário conservador, não previsão de preço.",
        "nota_custo": "Custo operacional de R$ 109,94/sc, convertido para R$ 5.277,12/ha pela produtividade de referência do próprio levantamento (2.880 kg/ha, 48 sc/ha)."
    }
}
# reserva-conab-fim


def _carregar_levantamento_conab() -> dict:
    """Levantamento em vigor, com a reserva como rede de segurança.

    Nunca levanta exceção: é lido na importação do módulo, e um JSON ausente ou
    corrompido não pode impedir o painel de abrir.
    """
    try:
        dados = json.loads(LEVANTAMENTO_JSON.read_text(encoding="utf-8"))
        faltando = [c for c in LEVANTAMENTO_CONAB_RESERVA if c not in dados]
        faltando += [f"serie.{c}" for c in LEVANTAMENTO_CONAB_RESERVA["serie"]
                     if c not in dados.get("serie", {})]
        if faltando:
            raise KeyError(", ".join(faltando))
        return dados
    except Exception as e:  # noqa: BLE001 — abrir o painel vale mais
        print(f"[painel] levantamento da CONAB indisponivel "
              f"({type(e).__name__}: {e}); usando a reserva", flush=True)
        return LEVANTAMENTO_CONAB_RESERVA


LEVANTAMENTO_CONAB = _carregar_levantamento_conab()

# Nomes mantidos por serem usados em todo o arquivo; o valor agora é derivado.
CUSTO_OPERACIONAL_PADRAO_HA = LEVANTAMENTO_CONAB["custo_operacional_ha"]
CUSTO_TOTAL_PADRAO_HA = LEVANTAMENTO_CONAB["custo_total_ha"]
PRECO_RECEBIDO_CONAB_PADRAO_SACA = LEVANTAMENTO_CONAB["preco_recebido_saca"]
# Produtividade de referência do levantamento, base da conversão do custo por
# saca para custo por hectare. O custo por hectare está preso a ela.
PRODUTIVIDADE_REFERENCIA_CONAB_SC = LEVANTAMENTO_CONAB["produtividade_referencia_sc_ha"]
# Preço e custo operacional POR SACA na praça de referência, para a interface
# poder mostrar o resultado que o próprio levantamento apurou.
PRECO_RECEBIDO_CONAB_SACA_REF = LEVANTAMENTO_CONAB["preco_recebido_saca"]
CUSTO_OPERACIONAL_CONAB_SACA_REF = LEVANTAMENTO_CONAB["custo_operacional_saca"]
# Rótulo pronto para as legendas: "Pedro Afonso (TO), levantamento de março de
# 2026".
PRACA_CONAB = LEVANTAMENTO_CONAB["praca"]
LEVANTAMENTO_CONAB_EXTENSO = LEVANTAMENTO_CONAB["levantamento_extenso"]

# ── IDADE DO LEVANTAMENTO ────────────────────────────────────────────────────
# Sem isto, um painel aberto daqui a dois anos exibiria o preço de março de
# 2026 como se fosse o de hoje: o levantamento é um arquivo estático, e a
# automação depende de alguém manter o repositório. A idade é calculada a cada
# carregamento da página, nunca gravada, e por isso o produto se denuncia
# sozinho, sem rede e sem manutenção.
#
# Espelha financas.aviso_de_defasagem, porque o painel não pode depender de
# importar aquele módulo — foi um import quebrado que o derrubou em 30/08/2026.
# test_robustez_painel.py confere que os dois dizem exatamente a mesma frase.
MESES_SIGLA_CONAB = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
                     "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11,
                     "DEZ": 12}
MESES_PARA_AVISAR_CONAB = 5
MESES_PARA_ALERTAR_CONAB = 12


def meses_desde_o_levantamento(hoje: date | None = None) -> int | None:
    """Meses entre o levantamento em uso e hoje. None se o rótulo não for lido."""
    rotulo = str(LEVANTAMENTO_CONAB.get("levantamento", ""))
    sigla, _, ano = rotulo.partition("-")
    if sigla.upper() not in MESES_SIGLA_CONAB or not ano.isdigit():
        return None
    hoje = hoje or date.today()
    return (hoje.year - int(ano)) * 12 + (hoje.month - MESES_SIGLA_CONAB[sigla.upper()])


def aviso_de_defasagem(hoje: date | None = None) -> str | None:
    """Frase a exibir quando o levantamento está velho, ou None se está em dia."""
    meses = meses_desde_o_levantamento(hoje)
    if meses is None or meses < MESES_PARA_AVISAR_CONAB:
        return None
    quando = LEVANTAMENTO_CONAB.get("levantamento_extenso", "data desconhecida")
    if meses < MESES_PARA_ALERTAR_CONAB:
        return (f"Este levantamento é de {quando}, há {meses} meses. A CONAB "
                f"publica a cada dois meses, então provavelmente já há um mais "
                f"recente — confira antes de decidir por este preço.")
    anos = meses // 12
    tempo = "mais de um ano" if anos == 1 else f"mais de {anos} anos"
    return (f"Este levantamento é de {quando}, há {meses} meses ({tempo}). "
            f"Trate o preço como referência histórica, não como cotação atual, "
            f"e edite o campo com o preço que você recebe hoje.")



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


@st.cache_data
def fase_enso(ano: int) -> str:
    """Fase do ENSO para a safra, pelo Oceanic Niño Index da NOAA.

    É o mesmo arquivo que pinta as faixas do gráfico histórico. Devolve
    "El Niño", "La Niña" ou "neutra" — e "neutra" também quando o arquivo
    não está disponível, que é a hipótese conservadora."""
    try:
        d = json.loads(EVENTOS_ENSO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "neutra"
    if ano in d.get("el_ninos", []):
        return "El Niño"
    if ano in d.get("la_ninas", []):
        return "La Niña"
    return "neutra"


def data_atualizacao() -> str | None:
    try:
        ano, mes, dia = DATA_ATUALIZACAO.read_text().strip().split("-")
        return f"{dia}/{mes}/{ano}"
    except (OSError, ValueError):
        return None


# Faixa plausível para a saca de 60 kg. Serve para uma falha de parsing não
# entrar na simulação disfarçada de cotação.
PRECO_SACA_MIN, PRECO_SACA_MAX = 60.0, 400.0


def extrair_preco_paranagua(html: str) -> float | None:
    """Tira da página o preço físico da saca em Paranaguá.

    A tabela da fonte muda de formato de tempos em tempos, então em vez de
    confiar numa posição fixa de coluna, varre as células da linha e aceita
    o primeiro número que se pareça com preço em reais e caia na faixa
    plausível. Assim uma coluna de variação ("-2,15") ou um total em
    milhares não entram no lugar da cotação.
    """
    for achado_nome in re.finditer("Paranaguá", html, re.IGNORECASE):
        linha = html[achado_nome.end():achado_nome.end() + 800].split("</tr>")[0]
        for celula in re.findall(r"<td[^>]*>(.*?)</td>", linha, re.DOTALL):
            texto = re.sub(r"<[^>]+>", " ", celula)
            for numero in re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto):
                valor = float(numero.replace(".", "").replace(",", "."))
                if PRECO_SACA_MIN <= valor <= PRECO_SACA_MAX:
                    return valor
    return None


@st.cache_data(ttl=3600)  # Atualiza a cotação a cada 1 hora de forma segura
def buscar_preco_soja_online() -> float | None:
    """Preço físico da saca em Paranaguá (Notícias Agrícolas).

    Devolve None quando não consegue um número plausível, para quem chama
    poder recorrer à cotação seguinte em vez de exibir um valor inventado
    como se fosse cotação do dia.
    """
    try:
        import urllib.request
        url = "https://www.noticiasagricolas.com.br/cotacoes/soja/"
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8")
    except Exception:
        return None
    return extrair_preco_paranagua(html)

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


# Paleta enxuta: cinzas neutros para quase tudo e cor só onde ela significa
# alguma coisa (sinal da margem, fase climática, marca). Quatro matizes
# concorrendo em quatro cartões de validação era ruído, não hierarquia.
CSS_VARS_LIGHT = """
        --app-bg: #fbfbfd;
        --card-bg: #ffffff;
        --card-border: rgba(0,0,0,0.08);
        --card-border-forte: rgba(0,0,0,0.16);
        --text-pure: #1d1d1f;
        --text-muted: #6e6e73;
        --text-faint: #6e6e73;   /* 5,07:1 sobre branco */
        --accent: #1a7f37;
        --accent-suave: rgba(26,127,55,0.10);
        --positivo: #1a7f37;
        --negativo: #c9252d;
        --card-shadow: 0 1px 2px rgba(0,0,0,0.04);
        --card-shadow-hover: 0 4px 16px rgba(0,0,0,0.08);
"""

CSS_VARS_DARK = """
        --app-bg: #000000;
        --card-bg: #141416;
        --card-border: rgba(255,255,255,0.09);
        --card-border-forte: rgba(255,255,255,0.20);
        --text-pure: #f5f5f7;
        --text-muted: #a1a1a6;
        --text-faint: #98989d;   /* 6,41:1 sobre o cartão */
        --accent: #30d158;
        --accent-suave: rgba(48,209,88,0.14);
        --positivo: #30d158;
        --negativo: #ff453a;
        --card-shadow: none;
        --card-shadow-hover: 0 4px 20px rgba(0,0,0,0.6);
"""

CSS_GLASS = '''<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
__VARS__
        --raio: 12px;
        --raio-pequeno: 9px;
    }

    /* ── BASE ────────────────────────────────────────────────────────── */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        -webkit-font-smoothing: antialiased !important;
        -moz-osx-font-smoothing: grayscale !important;
        text-rendering: optimizeLegibility !important;
        background-color: var(--app-bg) !important;
        color: var(--text-pure);
    }
    [data-testid="stAppViewContainer"] {
        background-color: var(--app-bg) !important;
        background-image: none !important;
    }
    /* O Streamlit reserva um vão enorme no topo antes do primeiro elemento. */
    .block-container { padding-top: 2.5rem !important; max-width: 1180px; }
    [data-testid="stAppDeployButton"] { display: none; }
    [data-testid="stHeader"] { background: transparent !important; }

    /* Números alinham coluna a coluna, como em planilha. */
    .kpi-value, .eco-value, [data-testid="stMetricValue"],
    [data-testid="stDataFrame"], .stNumberInput input {
        font-variant-numeric: tabular-nums !important;
        font-feature-settings: "tnum" 1 !important;
    }

    /* ── CARTÕES ─────────────────────────────────────────────────────── */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 14px;
        margin: 16px 0 28px;
    }
    .eco-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 14px;
        margin-bottom: 8px;
    }

    [data-testid="stMetric"], .kpi-card, .eco-card, [data-testid="stExpander"] {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: var(--raio);
        box-shadow: var(--card-shadow);
        transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
    }
    .kpi-card, .eco-card { padding: 20px 22px 22px; position: relative; }
    .kpi-card:hover, .eco-card:hover, [data-testid="stMetric"]:hover {
        border-color: var(--card-border-forte);
        box-shadow: var(--card-shadow-hover);
        transform: translateY(-1px);
    }

    /* ── TIPOGRAFIA DOS CARTÕES ──────────────────────────────────────── */
    .kpi-label, .eco-label, [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        color: var(--text-muted) !important;
        letter-spacing: 0 !important;
        line-height: 1.4 !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    [data-testid="stMetricLabel"] p { font-size: 0.75rem !important; }
    .kpi-value, .eco-value, [data-testid="stMetricValue"] {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 1.75rem !important;
        line-height: 1.15 !important;
        letter-spacing: -0.025em !important;
        color: var(--text-pure) !important;
        display: block;
        margin-top: 10px;
    }
    .eco-delta {
        font-size: 0.75rem; font-weight: 500;
        margin-top: 8px; display: block; color: var(--text-muted);
    }
    .kpi-hint {
        font-size: 0.72rem; line-height: 1.45; color: var(--text-muted);
        margin-top: 10px;
    }

    /* ── NÚMERO PRINCIPAL ────────────────────────────────────────────── */
    .hero-card {
        background: var(--card-bg); border: 1px solid var(--card-border);
        border-radius: var(--raio); box-shadow: var(--card-shadow);
        padding: 24px 26px 22px; margin-bottom: 14px;
    }
    .hero-label {
        font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em;
        text-transform: uppercase; color: var(--text-faint);
    }
    .hero-value {
        font-size: 3.1rem; font-weight: 600; letter-spacing: -0.04em;
        line-height: 1.05; color: var(--text-pure); margin-top: 10px;
        font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1;
    }
    .hero-unit {
        font-size: 1.1rem; font-weight: 500; letter-spacing: -0.01em;
        color: var(--text-muted); margin-left: 8px;
    }
    .hero-foot {
        font-size: 0.78rem; color: var(--text-muted); margin-top: 12px;
        padding-top: 12px; border-top: 1px solid var(--card-border);
    }

    /* Ponto de cor no rótulo: identifica o cartão sem pintar uma barra
       inteira. Nas métricas de validação não há cor nenhuma — verde ou roxo
       não querem dizer nada a respeito de um RMSE. */
    .eco-label::before {
        content: ""; display: inline-block;
        width: 6px; height: 6px; border-radius: 50%;
        margin-right: 7px; vertical-align: middle;
        background: var(--text-faint);
    }
    .eco-card.receita .eco-label::before { background: var(--positivo); }
    .eco-card.custo   .eco-label::before { background: #d97706; }
    .eco-card.margem  .eco-label::before { background: var(--text-pure); }


    /* ── CABEÇALHO ───────────────────────────────────────────────────── */
    .header-container {
        padding: 0 0 22px; border-bottom: 1px solid var(--card-border);
        margin-bottom: 28px;
    }
    .premium-title {
        font-size: 2rem; font-weight: 600; color: var(--text-pure);
        letter-spacing: -0.035em; line-height: 1.15; margin-bottom: 10px;
        background: none; -webkit-text-fill-color: initial;
    }
    .header-separator { display: none; }
    .badge-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 14px; }
    .badge {
        border-radius: 999px; border: 1px solid var(--card-border);
        padding: 3px 10px; font-size: 0.68rem; background: transparent;
        color: var(--text-muted); font-weight: 500; letter-spacing: 0.01em;
    }

    /* ── TÍTULOS DE SEÇÃO ────────────────────────────────────────────── */
    h3, [data-testid="stHeading"] h3 {
        font-size: 1.3rem !important; font-weight: 600 !important;
        letter-spacing: -0.02em !important; color: var(--text-pure) !important;
        margin-top: 8px !important;
    }
    [data-testid="stCaptionContainer"] p {
        color: var(--text-muted) !important; font-size: 0.82rem !important;
        line-height: 1.5 !important;
    }

    /* ── BARRA LATERAL ───────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: var(--card-bg) !important;
        border-right: 1px solid var(--card-border);
    }
    [data-testid="stSidebar"] h3 {
        font-size: 0.72rem !important; font-weight: 600 !important;
        text-transform: uppercase !important; letter-spacing: 0.07em !important;
        color: var(--text-faint) !important; margin-bottom: 4px !important;
    }
    [data-testid="stSidebar"] label { font-size: 0.8rem !important; }

    /* ── CONTROLES ───────────────────────────────────────────────────── */
    .stSelectbox > div > div,
    .stNumberInput > div > div > input,
    .stTextInput > div > div > input {
        background: var(--app-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: var(--raio-pequeno) !important;
        color: var(--text-pure) !important; font-weight: 400;
        box-shadow: none !important; transition: border-color .15s ease;
    }
    .stSelectbox > div > div:focus-within,
    .stNumberInput > div > div > input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px var(--accent-suave) !important;
    }
    .stButton > button, [data-testid="stDownloadButton"] > button {
        border-radius: var(--raio-pequeno) !important;
        border: 1px solid var(--card-border) !important;
        background: var(--card-bg) !important; color: var(--text-pure) !important;
        font-weight: 500 !important; font-size: 0.84rem !important;
        padding: 8px 16px !important; transition: all .15s ease;
    }
    .stButton > button:hover, [data-testid="stDownloadButton"] > button:hover {
        border-color: var(--card-border-forte) !important;
        background: var(--app-bg) !important;
    }
    [data-baseweb="radio"] { font-size: 0.85rem; }

    .stTabs [data-baseweb="tab-list"] {
        gap: 24px; background: transparent; border-bottom: 1px solid var(--card-border);
        padding: 0; box-shadow: none; border-radius: 0; margin-bottom: 16px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 4px; font-weight: 500; font-size: 0.85rem; color: var(--text-muted) !important;
        border-bottom: 2px solid transparent !important; background: transparent !important;
        border-radius: 0; margin: 0;
    }
    .stTabs [aria-selected="true"] {
        color: var(--text-pure) !important; border-bottom: 2px solid var(--text-pure) !important;
        box-shadow: none !important;
    }

    /* ── SUPERFÍCIES ─────────────────────────────────────────────────── */
    iframe { border-radius: var(--raio) !important; border: 1px solid var(--card-border) !important; box-shadow: none !important; }
    /* O detector de tema é um iframe de 2px de altura; com borda ele virava
       um risco atravessando a página logo acima do título. */
    iframe[title="streamlit_theme.st_theme"] { border: none !important; }
    [data-testid="stDataFrame"] { border-radius: var(--raio); border: 1px solid var(--card-border) !important; }
    [data-testid="stExpander"] summary { font-size: 0.85rem !important; font-weight: 500 !important; }
    [data-testid="stExpander"] details { border: none !important; }
    hr { border-color: var(--card-border) !important; margin: 32px 0 !important; }

    /* O st.metric nativo herdava o cartão sem padding nenhum e o rótulo
       encostava na borda de cima. */
    [data-testid="stMetric"] { padding: 18px 20px 20px !important; }

    /* Alertas nativos no mesmo idioma visual dos demais avisos: sem bloco
       de cor chapada, só uma barra lateral. */
    [data-testid="stAlert"] {
        background: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: var(--raio) !important;
        color: var(--text-muted) !important;
        padding: 14px 18px !important;
    }
    [data-testid="stAlert"] p { font-size: 0.88rem !important; line-height: 1.6 !important; }
    [data-testid="stAlertContainer"] { background: transparent !important; }

    /* ── TELAS ESTREITAS ─────────────────────────────────────────────── */
    @media (max-width: 768px) {
        .premium-title { font-size: 1.5rem; }
        .kpi-value, .eco-value, [data-testid="stMetricValue"] { font-size: 1.45rem !important; }
        .kpi-card, .eco-card { padding: 16px 18px 18px; }
        .stApp { padding-left: 0 !important; }
    }

    /* ── ROLAGEM ─────────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 9px; height: 9px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--card-border-forte); border-radius: 9px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--text-faint); }
</style>'''


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
def preparar(cache_buster='v3'):
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


df, estimador, metricas = preparar(cache_buster='v3')

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

    # Sem basemap de terceiro: o mapa é desenhado só com as geometrias que já
    # estão versionadas no repositório (contorno do Pará e rios). Os tiles do
    # CartoDB passaram a responder "API key required" e derrubaram o mapa do app
    # publicado; qualquer outro provedor gratuito é a mesma aposta, sujeita à
    # mudança de política de quem hospeda. Sem tiles, o painel não depende de
    # serviço externo em tempo de execução para desenhar o panorama.
    fundo_mapa = "#12151a" if is_dark else "#eef1f4"
    fill_color = "#1b2d1b" if is_dark else "#e3efe4"
    border_color = "#3f5f3f" if is_dark else "#7cb17f"
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
            "fillColor": fill_color,
            "color": border_color,
            "weight": 1.4,
            "fillOpacity": 1.0}).add_to(m)

    rios = carregar_rios()
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
            radius=3 + 10 * math.sqrt(r.area / amax),  # type: ignore
            color=cor_borda,
            weight=peso_borda,
            # type: ignore
            # type: ignore
            fill=True, fill_color=cmap(r.rend), fill_opacity=0.9,  # type: ignore
            tooltip=nome
        ).add_to(m)

    m.fit_bounds([[latmin, lonmin], [latmax, lonmax]])
    m.get_root().html.add_child(folium.Element(
        "<style>"
        ".leaflet-control-attribution { font-size: 8px !important;"
        " transform: scale(0.65); transform-origin: bottom right;"
        " opacity: 0.5; background: transparent !important; }"
        f".leaflet-container {{ background: {fundo_mapa} !important; }}"
        "</style>"))
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

def qtd(v: float, sinal: str = "") -> str:
    if unidade == "kg/ha":
        return f"{v * fator:{sinal},.0f}".replace(",", ".")
    return f"{v * fator:{sinal}.1f}".replace(".", ",")


def br(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def dec(v: float, casas: int = 1) -> str:
    """Número decimal com vírgula, como o resto da interface."""
    return f"{v:.{casas}f}".replace(".", ",")


def esc_md(texto: str) -> str:
    """Escapa o cifrão em texto vindo do levantamento da CONAB.

    Mesma razão de brl_md: o Streamlit lê "$...$" como LaTeX, e a nota sobre o
    preço traz dois valores em reais na mesma frase — sem escapar, o trecho
    entre eles vira fórmula em monoespaçado.
    """
    return texto.replace("$", r"\$")


def brl_md(v: float, dec: int = 0) -> str:
    """brl() para markdown puro.

    O Streamlit trata $...$ como LaTeX, então dois valores em reais na mesma
    string viram uma fórmula com o texto do meio em monoespaçado. Dentro de
    HTML (unsafe_allow_html) isso não acontece e brl() serve direto.
    """
    return brl(v, dec).replace("$", r"\$")


def brl(v: float, dec: int = 0) -> str:
    """Sinal antes do símbolo, como se escreve em português, e sem
    produzir "-R$ 0" para um valor que arredonda a zero."""
    s = f"{abs(v):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    negativo = v < 0 and float(f"{abs(v):.{dec}f}") > 0
    return f"{'-' if negativo else ''}R$ {s}"


PRECO_SACA_ONLINE = buscar_preco_soja_online()

EIXO_BR = alt.Axis(labelExpr="replace(format(datum.value, ',.0f'), /,/g, '.')")

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
    "Tela",
    ["📍 Inteligência Territorial", "📈 Análise Histórica", "💰 Viabilidade Financeira"],
    label_visibility="collapsed")
st.sidebar.divider()


st.sidebar.markdown("### Parâmetros Globais")
municipio = st.sidebar.selectbox(
    "Polo Científico / Município",
    municipios,
    key="mun_sel",
    format_func=disp,
    on_change=on_dropdown_change)

comparar = st.sidebar.toggle("Comparar com outro município", value=False)
mun_comp = None
if comparar:
    opcoes_comp = [m for m in municipios if m != municipio]
    mun_comp = st.sidebar.selectbox(
        "Município para Comparação",
        opcoes_comp,
        format_func=disp)

ano_alvo = st.sidebar.number_input(
    "Safra Alvo (Projeção IA)",
    min_value=int(df.ano.max()) + 1,
    max_value=int(df.ano.max()) + 3,
    value=int(df.ano.max()) + 1)

unidade = st.sidebar.radio(
    "Unidade de medida",
    ["sc/ha", "kg/ha"],
    horizontal=True,
    help="Vale para todos os números do painel: cartões, gráficos e tabelas.")
fator = 1 if unidade == "kg/ha" else 1 / SACA_KG

st.sidebar.markdown("### Perfil do Produtor")
baseline_ibge = estimador.estimar(municipio, int(df.ano.max()) + 1)["baseline_kg_ha"]
fator_tecnologico = st.sidebar.number_input(
    "Expectativa Produtiva da Fazenda", 
    min_value=10.0, max_value=120.0, 
    value=float(baseline_ibge / 60.0), 
    step=1.0,
    format="%.1f",
    help="O modelo IA usa médias do IBGE. Se sua fazenda possui alta tecnologia (correção de solo/sementes), ajuste a base aqui para prever os ganhos/perdas climáticos em cima da sua realidade."
)
st.sidebar.caption("Baseline: Quantas sacas/ha a fazenda colhe em um ano normal?")

def ajustar_r(r_dict):
    """Troca a média do IBGE pela expectativa que o produtor informou.

    A expectativa é declarada para uma safra normal, e `baseline_ibge` é a
    do mesmo ano de referência. A tendência tecnológica que o modelo projeta
    daquele ano até a safra alvo continua valendo em cima dela — sem isso, o
    seletor de Safra Alvo mudava o rótulo e devolvia sempre o mesmo número.
    """
    r2 = r_dict.copy()
    deriva_da_tendencia = r_dict["baseline_kg_ha"] - baseline_ibge
    r2["baseline_kg_ha"] = fator_tecnologico * 60.0 + deriva_da_tendencia
    r2["estimativa_kg_ha"] = r2["baseline_kg_ha"] + r2["correcao_climatica_kg_ha"]
    return r2

st.sidebar.divider()

# ==============================================================================
# ABA 1: MAPA E PREVISÃO

# ==============================================================================
if tela_atual == "📍 Inteligência Territorial":
    # ── FASE CLIMÁTICA DA SAFRA ALVO ──
    # Antes este bloco tinha has_severe fixo em False e anunciava "fase neutra"
    # em qualquer safra. Agora consulta o mesmo índice da NOAA que pinta as
    # faixas do gráfico histórico.
    fase = fase_enso(int(ano_alvo))
    if fase == "El Niño":
        cor_faixa, texto_fase = "#d97706", (
            "safra classificada como <b>El Niño</b> pelo Oceanic Niño Index (NOAA). "
            "No histórico do Pará, anos de El Niño concentram as maiores quebras.")
    elif fase == "La Niña":
        cor_faixa, texto_fase = "#2563eb", (
            "safra classificada como <b>La Niña</b> pelo Oceanic Niño Index (NOAA). "
            "A projeção abaixo já considera o clima observado, não a fase em si.")
    else:
        cor_faixa, texto_fase = "#737373", (
            "safra sem El Niño ou La Niña registrado pelo Oceanic Niño Index (NOAA). "
            "A projeção assume condições próximas das médias da última década.")
    st.markdown(f"""
    <div style="padding:15px 18px; background:var(--card-bg);
                border:1px solid var(--card-border); border-left:3px solid {cor_faixa};
                border-radius:var(--raio); margin-bottom:30px; font-size:0.88rem;
                line-height:1.55; color:var(--text-muted);">
        <b style="color:var(--text-pure);">{disp(municipio)}</b>, {ano_alvo} — {texto_fase}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Qualidade do modelo de previsão")
    st.caption(
        f"Validação temporal deixando um ano de fora por vez, sobre "
        f"{metricas['n']} safras de {df.municipio.nunique()} municípios.")
    st.markdown(f"""
    <div class="kpi-grid">
        <div class="kpi-card" title="Erro típico da previsão, na mesma unidade da produtividade. Quanto menor, melhor.">
            <div class="kpi-label">Erro típico (RMSE)</div>
            <div class="kpi-value">± {qtd(metricas['rmse'])} {unidade}</div>
            <div class="kpi-hint">margem de erro usual da previsão</div>
        </div>
        <div class="kpi-card" title="O mesmo erro expresso como porcentagem da produtividade média (rRMSE).">
            <div class="kpi-label">Erro relativo (rRMSE)</div>
            <div class="kpi-value">{dec(metricas['rrmse'])}%</div>
            <div class="kpi-hint">o mesmo erro, em % da produtividade média</div>
        </div>
        <div class="kpi-card" title="Quanto da variação entre safras o modelo consegue explicar. 1,000 seria uma previsão perfeita.">
            <div class="kpi-label">R² do modelo</div>
            <div class="kpi-value">{dec(metricas['r2'], 3)}</div>
            <div class="kpi-hint">quanto da variação entre safras ele explica</div>
        </div>
        <div class="kpi-card" title="O mesmo cálculo para a tendência histórica sozinha, sem satélite nem clima. Se os dois R² empatam, o modelo não superou a tendência.">
            <div class="kpi-label">R² da tendência (referência)</div>
            <div class="kpi-value">{dec(metricas['r2_baseline'], 3)}</div>
            <div class="kpi-hint">o mesmo cálculo só com a tendência histórica</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    esq, dir_ = st.columns([1, 2])
    with esq:


        with st.spinner(f"Calculando a projeção para {disp(municipio)}..."):
            r = ajustar_r(estimador.estimar(municipio, int(ano_alvo)))
        # É o número principal da tela; até aqui saía do mesmo tamanho de um
        # cartão de validação qualquer.
        st.markdown(f"""
        <div class="hero-card">
            <div class="hero-label">Projeção · safra {ano_alvo}</div>
            <div class="hero-value">{qtd(r['estimativa_kg_ha'])}<span
                 class="hero-unit">{unidade}</span></div>
            <div class="hero-foot">{disp(municipio)} · erro típico de
                ± {qtd(metricas['rmse'])} {unidade}</div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("Simular outro cenário climático"):
            # Os limites saem da faixa observada na base. Fora dela a floresta
            # aleatória não extrapola: devolve o valor da folha extrema, e a
            # simulação deixa de significar alguma coisa — com chuva zero a
            # projeção chegava a subir.
            hist = df[df["municipio"] == municipio]
            base_clima = hist if not hist.empty else df
            fp = estimador.faixas.get("precip_total")
            fe = estimador.faixas.get("etp_total")
            p_min, p_max = (int(fp[0]), int(fp[1])) if fp else (0, 3000)
            e_min, e_max = (int(fe[0]), int(fe[1])) if fe else (500, 2500)
            st.caption(
                f"Os limites são a faixa observada nos {len(df)} registros da "
                f"base: {br(p_min)} a {br(p_max)} mm de chuva. O modelo não tem "
                "o que dizer fora dela.")
            precip = st.slider("Precipitação total da safra (mm)", p_min, p_max,
                               int(base_clima["precip_total"].mean()), step=25)
            etp = st.slider("Evapotranspiração potencial (mm)", e_min, e_max,
                            int(base_clima["etp_total"].mean()), step=25)

            st.divider()
            clima = base_clima[M.FEATURES].mean().to_dict()
            clima["precip_total"] = precip
            clima["etp_total"] = etp
            clima["balanco_hidrico"] = clima["precip_total"] - clima["etp_total"]
            cenario = ajustar_r(estimador.estimar(municipio, int(ano_alvo), clima=clima))
            dif = cenario["estimativa_kg_ha"] - r["estimativa_kg_ha"]
            st.metric("Projeção ajustada",
                      f"{qtd(cenario['estimativa_kg_ha'])} {unidade}",
                      delta=f"{qtd(dif, '+')} {unidade}")
            sens = M.sensibilidade_climatica(df)
            virg = lambda v, c: f"{v:.{c}f}".replace(".", ",")
            st.caption(
                "**O que este número vale.** A associação entre chuva e "
                "produtividade nesta base não é distinguível de zero "
                f"(r = {virg(sens['r'], 3)}; p = {virg(sens['p'], 3)}; "
                f"n = {sens['n']}), e a diferença entre o terço mais seco e o "
                f"mais chuvoso é de {br(round(sens['amplitude_kg_ha']))} kg/ha — "
                f"contra margem de erro do modelo de "
                f"{br(round(estimador.rmse or 0))} kg/ha. A variação acima está "
                "dentro do ruído, e é assim que deve ser lida.")

    with dir_:
        mapa, nome_para_interno, faixa_rend = construir_mapa(
            municipio, mun_comp, is_dark=is_dark)
        if mapa is not None:
            st.subheader("Panorama geoespacial")
            st_folium(
                mapa,
                width='stretch',
                height=430,
                returned_objects=["last_object_clicked_tooltip"],
                key="mapa_soja"
            )

            grad = ",".join(_VIRIDIS)
            html = f"""<div style="display:flex; align-items:center; gap:12px;
                        flex-wrap:wrap; font-size:0.75rem; margin:12px 0 6px;
                        padding:10px 14px; background:var(--card-bg);
                        border:1px solid var(--card-border); border-radius:var(--raio);">
                  <span style="color:var(--text-faint); font-weight:600;
                               text-transform:uppercase; letter-spacing:0.06em;">Produtividade</span>
                  <span style="font-weight:600; color:var(--text-pure);
                               font-variant-numeric:tabular-nums;">{br(faixa_rend[0] * fator) if faixa_rend else 0}</span>
                  <div style="flex:1 1 160px; height:6px; border-radius:999px;
                              background:linear-gradient(to right,{grad});"></div>
                  <span style="font-weight:600; color:var(--text-pure);
                               font-variant-numeric:tabular-nums;">{br(faixa_rend[1] * fator) if faixa_rend else 0}</span>
                  <span style="color:var(--text-muted);">{unidade}</span>
                </div>"""
            st.markdown(html, unsafe_allow_html=True)
            st.caption(
                "**Dica:** Clique em qualquer ponto do mapa para alternar o município selecionado (Vermelho = Principal | Azul = Comparação).")
            st.caption(
                "**Geometrias:** contorno do estado da malha municipal do IBGE e "
                "rios do Natural Earth, ambos versionados em `pesquisa/dados/`. "
                "O mapa não usa camada de terceiros em tempo de execução.")

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

    st.subheader("Evolução histórica da produtividade")

    serie_plot = serie.assign(
        produtividade=serie[M.ALVO] * fator,
        produtividade_rotulo=[qtd(v) for v in serie[M.ALVO]],
        area_rotulo=[br(a) for a in serie["soy_area_ha"]],
        repetido=serie.groupby("municipio")[M.ALVO].diff().eq(0).fillna(False),
        Nome=[disp(m) for m in serie["municipio"]]
    )

    from ui.charts import plot_produtividade, plot_area
    import plotly.graph_objects as go
    
    st.plotly_chart(
        plot_produtividade(serie_plot, is_dark=is_dark, unidade=unidade),
        use_container_width=True)
    st.caption("Gráfico interativo: arraste para selecionar um período, dois toques para resetar o zoom.")

    st.subheader("Expansão da área plantada")
    st.plotly_chart(plot_area(serie_plot, is_dark=is_dark), use_container_width=True)

    b1, b2 = st.columns(2)
    b1.download_button(
        "Exportar histórico do município (CSV)",
        serie.to_csv(
            index=False).encode("utf-8"),
        file_name=f"soja_{municipio.lower().replace(' ', '_')}.csv",
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
    st.markdown("### Simulador de viabilidade financeira")
    st.caption(
        "Os dois campos abaixo partem de referências regionais e podem ser "
        "editados. Para um cenário realista, ajuste também a "
        "**Expectativa Produtiva da Fazenda**, na barra lateral, com a "
        "produtividade que a sua propriedade colhe em um ano normal.")

    with st.spinner("Processando margem de lucro com IA Georreferenciada..."):
        r_eco = ajustar_r(estimador.estimar(municipio, int(df.ano.max()) + 1))

    col_eco1, col_eco2 = st.columns(2)
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api_backend"))
        from financas import get_financas, CUSTO_REFERENCIA_HA
        r = get_financas(municipio)
        custos_locais = {'custo_ha': r.get('custo_ha'), 'vtn_ha': r.get('vtn_ha')}
        preco_referencia = r.get('soja_preco_saca',
                                 PRECO_RECEBIDO_CONAB_PADRAO_SACA)
        preco_cbot = r.get('soja_preco_cbot_saca')
    except Exception as e:
        # O nome importado no try não existe aqui: o fallback usa a constante de
        # módulo. Foi exatamente isso que derrubou o app publicado em 30/08/2026.
        print(f"[painel] base de custos indisponivel: {type(e).__name__}: {e}",
              flush=True)
        st.caption(
            "A base de custos não pôde ser consultada agora. O custo abaixo é a "
            "referência da CONAB adotada pelo produto, o VTN não é exibido e "
            "todos os campos continuam editáveis.")
        custos_locais = {'custo_ha': CUSTO_OPERACIONAL_PADRAO_HA, 'vtn_ha': None}
        preco_referencia = PRECO_RECEBIDO_CONAB_PADRAO_SACA
        preco_cbot = None

    # O padrão é preço de PORTEIRA, da mesma praça de onde vem o custo, para a
    # margem não sair inflada. Paranaguá (porto) e CBOT (bolsa) ficam como
    # comparação: os dois estão acima do que se recebe no Pará.
    default_preco = float(preco_referencia)
    comparacoes = []
    if PRECO_SACA_ONLINE is not None:
        comparacoes.append(f"físico em Paranaguá hoje, {brl_md(PRECO_SACA_ONLINE, 2)}")
    if preco_cbot:
        comparacoes.append(f"futuro em Chicago convertido, {brl_md(preco_cbot, 2)}")
    # A frase que situa o preço na série vem do levantamento gerado, não
    # escrita aqui: sem ela o usuário lê o padrão como "o preço da soja",
    # quando ele pode ser o piso do triênio — e a margem é quase toda dirigida
    # por esse único parâmetro. Série em
    # pesquisa/dados/conab/serie_pedro_afonso_to.csv.
    fonte_preco = (f"**Cotação:** CONAB, preço recebido pelo produtor em "
                   f"{PRACA_CONAB}, levantamento de {LEVANTAMENTO_CONAB_EXTENSO} "
                   f"— preço de porteira, e da mesma praça de onde vem o custo "
                   f"abaixo. {esc_md(LEVANTAMENTO_CONAB['textos']['nota_preco'])}")
    if comparacoes:
        fonte_preco += (" Para comparação: " + "; ".join(comparacoes) +
                        ". São preços de porto e de bolsa, acima do que se "
                        "recebe na porteira no Pará.")


    # O aviso vem antes dos campos, e não como nota de rodapé: se o preço está
    # velho, quem vai ler a margem precisa saber disso antes de lê-la.
    _aviso_conab = aviso_de_defasagem()
    if _aviso_conab:
        st.warning(f"**Preço possivelmente desatualizado.** {_aviso_conab}")

    with col_eco1:
        preco = st.number_input(
            "Preço de referência da saca (R$ / 60 kg)",
            min_value=0.0,
            value=default_preco,
            step=5.0)
        st.caption(fonte_preco)
    with col_eco2:
        custo_ha = st.number_input(
            f"Custo Operacional base ({municipio.title()})",
            min_value=0,
            value=int(custos_locais["custo_ha"]),
            step=100)
        st.caption(
            f"**Custo:** CONAB, custo operacional da soja em {PRACA_CONAB}, "
            f"levantamento de {LEVANTAMENTO_CONAB_EXTENSO}. "
            f"{esc_md(LEVANTAMENTO_CONAB['textos']['nota_custo'])} O Pará não tem "
            f"levantamento próprio. **Atenção:** este é um custo por hectare "
            f"fixo, preso à produtividade de referência — ele não cresce junto "
            f"com a produtividade projetada, então parte da colheita, secagem e "
            f"frete das sacas acima de "
            f"{PRODUTIVIDADE_REFERENCIA_CONAB_SC:.0f} sc/ha não está sendo "
            f"cobrada.")
    # O Valor da Terra Nua sai dos campos editáveis e do grid de resultados.
    # Era um campo que o usuário podia alterar sem que nada na tela mudasse,
    # porque o VTN não entra em cálculo nenhum, e um cartão de patrimônio no
    # meio de três cartões de fluxo por safra, todos rotulados "R$/ha". Passa a
    # ser nota de contexto, abaixo, com o que ele de fato é: referência fiscal.
    vtn_publicado = custos_locais["vtn_ha"]

    est_sacas_ha = r_eco["estimativa_kg_ha"] / SACA_KG
    receita_ha = est_sacas_ha * preco
    margem_ha = receita_ha - custo_ha
    pct_margem = f"{margem_ha / custo_ha * 100:+.0f}%" if custo_ha else "—"
    cor_delta = 'var(--positivo)' if margem_ha >= 0 else 'var(--negativo)'
    # 'margem_incerta' é definida logo abaixo e reajusta esta cor.

    # O painel anuncia o erro típico do modelo lá em cima e depois apresentava
    # a receita como número exato. A mesma margem de erro, convertida em
    # dinheiro, é o que separa um cenário viável de um duvidoso.
    erro_sacas = metricas["rmse"] / SACA_KG
    erro_reais = erro_sacas * preco
    receita_min, receita_max = receita_ha - erro_reais, receita_ha + erro_reais
    margem_min, margem_max = margem_ha - erro_reais, margem_ha + erro_reais
    faixa_receita = f"{brl(receita_min)} a {brl(receita_max)}"
    faixa_margem = f"{brl(margem_min)} a {brl(margem_max)}"
    margem_incerta = margem_min < 0 < margem_max

    # SÍNTESE LLM (ANÁLISE GENERATIVA)
    # Quando o resultado muda de sinal dentro do erro do modelo, a síntese não
    # pode afirmar que a conta fecha no azul — era o que ela fazia, contradizendo
    # o próprio aviso logo abaixo.
    if margem_incerta:
        cor_delta = '#d97706'
    texto_ia = ""
    if margem_incerta:
        texto_ia = (
            f"<b>Resultado inconclusivo (Síntese IA):</b> a projeção central é de "
            f"{brl(margem_ha)}/ha, mas o erro típico do modelo leva o resultado de "
            f"{brl(margem_min)} a {brl(margem_max)} por hectare — a margem muda de "
            f"sinal. Com a produtividade predita de <b>{dec(est_sacas_ha)} sc/ha</b>, "
            f"o cenário não permite afirmar se a lavoura fecha no azul ou no "
            f"vermelho. Ajuste preço, custo ou a expectativa produtiva da fazenda "
            f"para um cenário conclusivo.")
    elif margem_ha > 0:
        if margem_ha > (custo_ha * 0.3):
             texto_ia = f"<b>Alta Viabilidade (Síntese IA):</b> Cenário projeta lucro operacional robusto. A produtividade estimada de <b>{dec(est_sacas_ha)} sc/ha</b> assegura um faturamento de {brl(receita_ha)}/ha, cobrindo com folga o custeio de {brl(custo_ha)}, deixando uma margem excelente."
        else:
             texto_ia = f"<b>Alerta de Stress (Síntese IA):</b> A conta fecha no azul, mas a margem estreita de {brl(margem_ha)}/ha exige cautela. A produtividade predita de <b>{dec(est_sacas_ha)} sc/ha</b> não suportará solavancos climáticos intensos sem risco de prejuízo."
    else:
        texto_ia = f"<b>Risco Operacional Crítico (Síntese IA):</b> Alerta Vermelho! Com a soja simulada a {brl(preco)} e custo elevado ({brl(custo_ha)}/ha), a IA prevê colapso econômico em {disp(municipio)}. A produtividade de <b>{dec(est_sacas_ha)} sc/ha</b> destruiria o capital, com perdas de {brl(abs(margem_ha))} por hectare."

    st.markdown(
        f'<div style="background:var(--card-bg); border:1px solid var(--card-border);'
        f' border-left:3px solid {cor_delta}; border-radius:var(--raio);'
        f' padding:16px 18px; margin:22px 0 18px; font-size:0.9rem;'
        f' line-height:1.6; color:var(--text-muted);">{texto_ia}</div>',
        unsafe_allow_html=True)

    st.markdown(f"""
    <div class="eco-grid">
        <div class="eco-card receita" title="Produtividade projetada multiplicada pelo preço da saca.">
            <div class="eco-label">Receita bruta projetada (R$/ha)</div>
            <div class="eco-value">{brl(receita_ha)}</div>
            <div class="eco-delta">{faixa_receita}</div>
        </div>
        <div class="eco-card custo" title="Custo de custeio da lavoura por hectare, editável acima.">
            <div class="eco-label">Custo operacional (R$/ha)</div>
            <div class="eco-value">{brl(custo_ha)}</div>
        </div>
        <div class="eco-card margem" title="Receita bruta menos custo operacional. Não desconta terra, impostos nem financiamento.">
            <div class="eco-label">Margem operacional (R$/ha)</div>
            <div class="eco-value" style="color:{cor_delta}">{brl(margem_ha)}</div>
            <div class="eco-delta" style="color:{cor_delta}">{pct_margem} sobre o custo</div>
            <div class="eco-delta">{faixa_margem}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.caption(
        f"As faixas vêm do erro típico do modelo (± {dec(erro_sacas)} sc/ha, "
        f"o mesmo do cartão de validação), convertido a {brl_md(preco)} por saca: "
        f"± {brl_md(erro_reais)}/ha. A faixa cobre só o erro do modelo na "
        f"produtividade — não cobre variação de preço nem de custo, que na "
        f"prática pesam mais. A margem é receita bruta menos custo operacional: "
        f"não desconta terra, impostos nem financiamento, e o custo por hectare "
        f"não cresce junto com a produtividade projetada.")

    # Duas leituras que o número principal não entrega sozinho: quanto sobra
    # depois de remunerar terra e capital, e o que o próprio levantamento de
    # referência apurou. Sem elas a margem operacional é fácil de ler como lucro.
    renda_fatores_ha = CUSTO_TOTAL_PADRAO_HA - CUSTO_OPERACIONAL_PADRAO_HA
    margem_total = margem_ha - renda_fatores_ha
    st.caption(
        f"**A custo total:** a margem acima é operacional e não remunera o "
        f"patrimônio empregado. Descontando também a renda de fatores da CONAB "
        f"({brl_md(renda_fatores_ha, 2)}/ha, que remunera terra e capital), "
        f"sobram {brl_md(margem_total)}/ha.")
    resultado_ref = (PRECO_RECEBIDO_CONAB_SACA_REF
                     - CUSTO_OPERACIONAL_CONAB_SACA_REF) * PRODUTIVIDADE_REFERENCIA_CONAB_SC
    st.caption(
        f"**Na praça de referência:** no mesmo levantamento da CONAB, em "
        f"{PRACA_CONAB}, o preço recebido ({brl_md(PRECO_RECEBIDO_CONAB_SACA_REF, 2)}"
        f"/sc) ficou abaixo do custo operacional "
        f"({brl_md(CUSTO_OPERACIONAL_CONAB_SACA_REF, 2)}/sc): a lavoura apurou "
        f"{brl_md(resultado_ref)}/ha ali. O resultado positivo aqui depende de a "
        f"produtividade projetada ({dec(est_sacas_ha)} sc/ha) superar a de "
        f"referência do levantamento ({PRODUTIVIDADE_REFERENCIA_CONAB_SC:.0f} sc/ha), "
        f"já que o custo por hectare não acompanha essa diferença.")
    if vtn_publicado is None:
        st.caption(
            f"**Valor da Terra Nua ({disp(municipio)}):** a Receita Federal não "
            f"publica VTN para este município na tabela do exercício 2026. O "
            f"painel informa isso em vez de estimar um valor.")
    else:
        st.caption(
            # duas casas: a Receita publica o VTN ao centavo e a nota existe para ser
            # conferida contra a tabela oficial
            f"**Valor da Terra Nua ({disp(municipio)}):** {brl_md(vtn_publicado, 2)}"
            f"/ha — Receita Federal, tabela do exercício 2026, classe lavoura de "
            f"aptidão boa. É referência fiscal, base de cálculo do ITR, e não "
            f"preço de mercado. É patrimônio: não entra na margem e não é campo "
            f"de simulação.")

    st.divider()

    st.subheader("Confiabilidade dos registros oficiais")
    diag = M.diagnostico_pam(df, municipio)
    taxa_estado = M.taxa_repeticao_estadual(df)

    qa, qb, qc = st.columns(3)
    qa.metric("Repetição de dados locais",
              f"{diag['taxa']:.0f}%",
              help="Porcentagem de safras em que o histórico oficial repetiu o valor anterior.")
    qb.metric("Maior sequência travada", f"{diag['maior_sequencia']} safras")
    qc.metric("Média de repetição no Pará", f"{dec(taxa_estado)}%")

    if diag["taxa"] >= taxa_estado:
        cor_qa, texto_qa = "#d97706", (
            f"<b>Repetição acima da média do estado.</b> O histórico oficial de "
            f"{disp(municipio)} repete o valor da safra anterior com frequência "
            f"maior que a média do Pará, o que reforça a necessidade de corrigir "
            f"viés com satélite e clima.")
    else:
        cor_qa, texto_qa = "var(--positivo)", (
            f"<b>Repetição abaixo da média do estado.</b> O histórico oficial de "
            f"{disp(municipio)} varia mais entre safras que a média do Pará.")
    st.markdown(
        f'<div style="background:var(--card-bg); border:1px solid var(--card-border);'
        f' border-left:3px solid {cor_qa}; border-radius:var(--raio);'
        f' padding:15px 18px; margin-top:6px; font-size:0.88rem; line-height:1.6;'
        f' color:var(--text-muted);">{texto_qa}</div>',
        unsafe_allow_html=True)

    st.divider()

    # ------------------------------------------------------ PANORAMA GERAL DO ESTADO
    st.subheader("Ranking dos polos produtivos")
    st.caption(
        f"Calculado com base na produtividade média recente e na cotação de "
        f"**{brl_md(preco)} por saca**. A ordenação é por faturamento, então "
        f"compare sempre com a coluna **Total de Safras**: parte dos municípios "
        f"do topo tem uma ou duas safras no histórico oficial, e ali a \"média "
        f"recente\" é um único registro do IBGE, não uma média. Nesses casos a "
        f"repetição aparece como traço, porque não há série para medir.")

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
            "area_ha": round(float(d.iloc[-1]["soy_area_ha"])),
            # Sem pelo menos duas safras não há diferença para medir. Antes isso
            # virava 0%, indistinguível de uma série que de fato varia — e o
            # município ia para o topo do ranking parecendo o mais confiável.
            # Texto pronto, não número: verificou-se que o NumberColumn desta
            # versão do Streamlit desenha nulo como a palavra "None" na célula,
            # com ou sem 'format'. Só o TextColumn deixa a célula limpa. Sem pelo
            # menos duas safras não há diferença entre safras para medir, e o
            # traço diz isso — antes virava 0%, indistinguível de uma série que
            # de fato varia, e o município subia ao topo parecendo confiável.
            "repeticao": (f"{(difs == 0).mean() * 100:.0f}%" if len(difs) else "—"),
            "safras": len(d),
        })

    # Arredonda no dado e deixa o Streamlit formatar pelo idioma do navegador,
    # para a coluna não destoar das vizinhas com ponto decimal.
    casas_pan = 0 if unidade == "kg/ha" else 1
    pan = pd.DataFrame(linhas_pan).sort_values("faturamento", ascending=False)
    pan["prod_media"] = pan["prod_media"].round(casas_pan)
    # Sem isso a coluna mostrava frações de centavo (6.204,163). Só não aparecia
    # antes porque o preço padrão era redondo e os produtos davam inteiros.
    pan["faturamento"] = pan["faturamento"].round(0)

    st.dataframe(
        pan,
        hide_index=True,
        width='stretch',
        column_config={
            "prod_media": st.column_config.NumberColumn(
                f"Média Recente ({ult_ano - 4}–{ult_ano}) [{unidade}]",
                format="localized"),
            "faturamento": st.column_config.NumberColumn(
                "Faturamento Bruto Est. (R$/ha)",
                format="localized"),
            "area_ha": st.column_config.NumberColumn(
                "Área Atual (ha)",
                format="localized"),
            "repeticao": st.column_config.TextColumn(
                "Repetição Oficial",
                help="Traço quando o município tem menos de duas safras: não há "
                     "diferença entre safras para medir."),
            "safras": st.column_config.NumberColumn("Total de Safras"),
        },
    )



with st.expander("Sobre a tecnologia e as fontes de dados", expanded=False):
    st.markdown('''
    **Plataforma de AgroInteligência Preditiva** — Solução metodológica baseada em inteligência artificial para previsão de produtividade de soja e monitoramento do agronegócio no Estado do Pará.

    ### Tratamento e Origem dos Dados:
    * **IBGE (PAM):** Base estrutural de dados oficiais de safra e área plantada histórica para a modelagem alvo.
    * **Google Earth Engine (GEE):** Plataforma primária de ETL satelital em larga escala.
      * *MODIS (MOD13Q1 / Terra)*: Séries temporais de Índices de Vegetação (NDVI, EVI).
      * *CHIRPS*: Malha meteorológica para mensuração de Precipitação e Volume de Chuva.
      * *ERA5-Land*: Banco climático de temperatura global para extração de Evapotranspiração Potencial e Balanço Hídrico.
    * **Projeto MapBiomas:** Extração das coberturas de Uso e Ocupação do Solo com foco em áreas exclusivas de soja no Pará (mascaramento de satélite).

    ### Dados econômicos do simulador
''' + f'''    * **Preço recebido pelo produtor (CONAB):** {brl_md(LEVANTAMENTO_CONAB['preco_recebido_saca'], 2)} por saca no
      levantamento de {PRACA_CONAB}, de {LEVANTAMENTO_CONAB_EXTENSO}. É a cotação que o
      simulador usa por padrão, por ser preço de porteira e por vir da mesma
      praça de onde sai o custo — receita e custo passam a nascer do mesmo
      levantamento. O campo é editável.
      {esc_md(LEVANTAMENTO_CONAB['textos']['nota_preco'])} Na série completa da praça
      ({LEVANTAMENTO_CONAB['serie']['periodo']}), a média é
      {brl_md(LEVANTAMENTO_CONAB['serie']['media_saca'], 2)} e o maior preço foi
      {brl_md(LEVANTAMENTO_CONAB['serie']['maior_saca'], 2)}, em
      {LEVANTAMENTO_CONAB['serie']['maior_levantamento_extenso']}. A série está em
      `pesquisa/dados/conab/serie_pedro_afonso_to.csv`, e é atualizada pelo
      workflow mensal. Preço e custo têm de vir do mesmo levantamento — usar a
      mediana da série com o custo de {LEVANTAMENTO_CONAB_EXTENSO} misturaria
      dois momentos e inflaria a margem.
''' + '''    * **Notícias Agrícolas:** preço físico da saca em Paranaguá, relido a cada
      hora, exibido como comparação. É preço de porto, no Paraná: o produtor no
      Pará recebe menos, por causa de frete e base.
    * **Yahoo Finance (CBOT `ZS=F` e `BRL=X`):** contrato futuro de Chicago
      convertido para reais por saca de 60 kg, também exibido como comparação.
      É cotação de bolsa e fica acima do preço físico brasileiro.
''' + f'''    * **Custo operacional (CONAB):** levantamento de custos de produção da soja
      no município de {PRACA_CONAB}, de {LEVANTAMENTO_CONAB_EXTENSO} — ponto de coleta da
      CONAB no cerrado do Tocantins. O Pará não integra o MATOPIBA e não tem
      custo de soja levantado, por isso adota-se o cerrado vizinho.
      {esc_md(LEVANTAMENTO_CONAB['textos']['nota_custo'])} É um valor de referência
      igual para todos os municípios, lido de
      `pesquisa/dados/conab/levantamento_atual.json` e editável no campo acima.
''' + '''    * **Valor da Terra Nua (Receita Federal):** Tabela de Valores de Terra Nua do
      exercício 2026, publicada em 07/08/2026 e reenviada corrigida em
      21/08/2026. A tabela traz seis valores por município, por classe de
      aptidão agrícola; usa-se "Lavoura — Aptidão Boa", que é a classe da soja.
      A Receita Federal publica VTN para 13 dos 38 municípios da base — nos
      demais o painel informa que não há valor oficial, em vez de estimar. É
      referência fiscal, base de cálculo do ITR, e não preço de mercado: por
      isso aparece como nota de contexto, não é campo de simulação e não entra
      no cálculo da margem. O PDF nacional e a extração dos municípios
      paraenses estão em `pesquisa/dados/receita_federal/`.
    
    *Repositório Acadêmico:* [github.com/engsoft7/dissertacao-soja-ia](https://github.com/engsoft7/dissertacao-soja-ia)

    ---
    **AgroInteligência** | Plataforma de Inteligência Preditiva para Safra de Soja — Estado do Pará
    *Machine Learning · Sensoriamento Remoto · Análise de Viabilidade Comercial*
    
    Desenvolvido com Streamlit · Dados: IBGE · MODIS · CHIRPS · ERA5-Land · MapBiomas
    ''')


