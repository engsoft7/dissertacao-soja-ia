from financas import (get_financas, get_custos_locais, CUSTO_REFERENCIA_HA,
                      PRECO_RECEBIDO_CONAB_SACA, LEVANTAMENTO,
                      descricao_do_levantamento, nota_sobre_o_preco,
                      aviso_de_defasagem, meses_desde_o_levantamento,
                      aviso_sobre_o_custo)
from validacao import metricas_validacao
import validacao
import estados
import historico_oficial
import mercado
import precos_para
import avisos_inmet
import plantio
from fastapi import FastAPI, HTTPException
from functools import lru_cache
from contextlib import asynccontextmanager
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import copy
import hashlib
import joblib
import json
import sklearn
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

    # A cotação física por praça vinha da Notícias Agrícolas, que desde
    # 12/11/2026 barra acesso automático (issue #187) e saiu do produto. Os
    # campos preco_fisico, precos_fisicos e soja_preco_paranagua_saca seguem
    # nas respostas, vazios, porque o aplicativo já instalado os conhece.

def _get_cached_finance():
    """Return cached finance data; refresh in background if stale (>15 min)."""
    with _finance_lock:
        data = _finance_cache.copy()
    if time.time() - data["ts"] > 900:  # 15 min
        threading.Thread(target=_refresh_finance, daemon=True).start()
    return data


class EstadoCarregado:
    """Base, modelo treinado, métricas e série oficial de um estado."""

    def __init__(self, e: "estados.Estado") -> None:
        self.estado = e
        self.df = M.carregar(str(e.base))
        self.estimador = M.Estimador().treinar(self.df)
        self.metricas = self.estimador.validar(self.df)  # Popula métricas de mae e rmse
        self.last_year = int(self.df["ano"].max())
        self.pam = historico_oficial.carrega_pam(e.pam)
        self.historicos: dict = {}
        self.sedes = estados.sedes(e)
        # De onde o estado veio nesta subida, em /api/estados: é o que mostra,
        # de fora, se o Render rodou prepara_estados.py na build.
        self.origem = "treinado na subida"

    def nome_na_base(self, municipio: str) -> str:
        """O nome como está na base: no Pará, sem acento (do GAUL); nos outros, o oficial."""
        return REVERSE_FORMATADOS.get(municipio, municipio) if self.estado.uf == "PA" else municipio

    def nome_exibido(self, municipio: str) -> str:
        return MUNICIPIOS_FORMATADOS.get(municipio, municipio) if self.estado.uf == "PA" else municipio


# ── Estados prontos na build ───────────────────────────────────────────────
# Treinar Mato Grosso, Maranhão, Tocantins e Rondônia e preparar os históricos
# leva uns 90 s de CPU numa máquina comum, o que no décimo de CPU do Render
# gratuito dá na ordem de 15 minutos, a cada deploy ou reinício. Nesse tempo os
# quatro respondem 503 ("modelo em preparação") e dividem a CPU com as
# respostas do Pará; na leitura de 13/11/2026 às 16h34 UTC, logo depois do
# deploy, nenhum dos quatro estava pronto. A build do Render roda
# prepara_estados.py, que grava cada estado pronto em CACHE_ESTADOS, e a subida
# só lê o arquivo. O cache vale para a base, o arquivo do IBGE e a lista de
# sedes com que foi feito (assinatura); com qualquer um diferente, ou sem o
# arquivo, treina como antes.
CACHE_ESTADOS = Path(__file__).resolve().parent / "cache"
CACHE_VERSAO = 1


def _assinatura_do_estado(e: "estados.Estado") -> str:
    h = hashlib.sha256(f"{CACHE_VERSAO}|{sklearn.__version__}|{pd.__version__}".encode())
    for arquivo in (e.base, e.pam, e.municipios):
        if arquivo.exists():
            h.update(arquivo.read_bytes())
    return h.hexdigest()


def _arquivo_do_cache(e: "estados.Estado") -> Path:
    return CACHE_ESTADOS / f"{e.uf}.joblib"


def prepara_estado(e: "estados.Estado") -> "EstadoCarregado":
    """Treina o estado, prepara o histórico de cada município e grava tudo no cache."""
    ce = EstadoCarregado(e)
    for raw in ce.df["municipio"].unique():
        _historico_do_municipio(raw, ce.df[ce.df["municipio"] == raw], ce)
    CACHE_ESTADOS.mkdir(exist_ok=True)
    joblib.dump({"assinatura": _assinatura_do_estado(e), "estado": ce}, _arquivo_do_cache(e))
    return ce


def carrega_estado(e: "estados.Estado") -> "EstadoCarregado":
    """O estado pronto do cache, se é o desta base; senão, treinado agora."""
    arquivo = _arquivo_do_cache(e)
    if arquivo.exists():
        try:
            guardado = joblib.load(arquivo)
            if guardado.get("assinatura") == _assinatura_do_estado(e):
                print(f"{e.nome}: pronto, do cache da build.", flush=True)
                ce = guardado["estado"]
                ce.estado = e  # os caminhos desta máquina, e não os da build
                ce.origem = "cache da build"
                return ce
            print(f"{e.nome}: o cache é de outra base; treinando.", flush=True)
        except Exception as erro:  # arquivo de outra versão das bibliotecas, cortado…
            print(f"{e.nome}: cache ilegível ({type(erro).__name__}); treinando.", flush=True)
    return EstadoCarregado(e)


def _carrega_outros_estados() -> None:
    """Os outros estados depois do Pará, sem atrasar a subida da API."""
    for e in estados.disponiveis():
        if e.uf in AppState.estados:
            continue
        try:
            AppState.estados[e.uf] = carrega_estado(e)
            print(f"{e.nome}: modelo pronto ({len(AppState.estados[e.uf].df)} registros).", flush=True)
            _aquece_historicos(e.uf)
        except Exception as erro:  # um estado com problema não derruba os outros
            print(f"{e.nome} não carregado: {type(erro).__name__}: {erro}", flush=True)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    pa = carrega_estado(estados.ESTADOS["PA"])
    AppState.estados = {"PA": pa}
    AppState.df = pa.df
    AppState.estimador = pa.estimador
    AppState.metricas = pa.metricas
    AppState.last_year = pa.last_year
    AppState.pam = pa.pam
    AppState.historicos = pa.historicos
    print("Modelo carregado e treinado com sucesso.", flush=True)
    # Prepara o histórico dos municípios em segundo plano, para a primeira
    # abertura de cada um não esperar as estimativas; depois, os outros estados.
    threading.Thread(target=lambda: (_aquece_historicos("PA"), _carrega_outros_estados()), daemon=True).start()
    # Pre-populate finance cache in background
    threading.Thread(target=_refresh_finance, daemon=True).start()
    yield

app = FastAPI(title="AgroInteligência API", description="FastAPI for Soybean Yield Prediction System", lifespan=app_lifespan)

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

# Enable CORS for generic clients. Sem credenciais: a API não usa cookie nem
# login, e "*" com credenciais fazia o Starlette ecoar a origem de qualquer site.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _componentes_do_custo() -> dict:
    """Componentes do custo do levantamento em uso; nulos se o levantamento não os tiver."""
    c = LEVANTAMENTO.get("custo_por_componente") or {}
    return {"custo_area_ha": c.get("area_ha"),
            "custo_transporte_saca": c.get("transporte_saca"),
            "taxa_cessr": c.get("taxa_receita")}


def _financas_de_outro_estado(municipio: str, ce: "EstadoCarregado", fin: dict) -> dict:
    """O mesmo formato do Pará, com preço e custo da praça da CONAB no estado."""
    cod = next((c for c, (nome, _, _) in ce.sedes.items() if nome == municipio), None)
    sede = ce.sedes[cod][1:] if cod is not None else None
    praca_csv, rotulo = estados.praca_conab(ce.estado, sede)
    lev = estados.levantamento_da_praca(praca_csv, rotulo, LEVANTAMENTO["levantamento"],
                                        LEVANTAMENTO["levantamento_extenso"])
    comp = lev.get("custo_por_componente") or {}
    return {
        "municipio": municipio,
        "uf": ce.estado.uf,
        "soja_preco_saca": lev["preco_recebido_saca"],
        "soja_preco_cbot_saca": fin["cbot_saca"],
        "soja_preco_paranagua_saca": fin.get("paranagua_saca"),
        "preco_fisico": fin.get("fisico"),
        "precos_fisicos": fin.get("cotacoes") or [],
        "custo_ha": lev["custo_operacional_ha"],
        "custo_variavel_saca": lev["custo_variavel_saca"],
        "custo_fixo_ha": lev["custo_fixo_saca"] * lev["produtividade_referencia_sc_ha"],
        "produtividade_referencia_sc": lev["produtividade_referencia_sc_ha"],
        # Sem o custo aberto por item, o aplicativo usa os dois rateios; só Pedro
        # Afonso (Tocantins), o levantamento do Pará, traz os itens.
        "custo_area_ha": comp.get("area_ha"), "custo_transporte_saca": comp.get("transporte_saca"),
        "taxa_cessr": comp.get("taxa_receita"),
        # A tabela de VTN da Receita Federal no produto é só a do Pará.
        "vtn_ha": None,
        "fonte_preco": lev["textos"]["descricao"],
        "nota_preco": lev["textos"]["nota_preco"],
        "levantamento": lev["levantamento"],
        "defasagem_meses": meses_desde_o_levantamento(),
        "aviso_preco": aviso_de_defasagem(),
        "aviso_custo": aviso_sobre_o_custo(),
        "ano_referencia": int(ce.last_year),
    }


@app.get("/api/financas/{municipio}")
def get_financas(municipio: str, uf: str | None = None):
    fin = _get_cached_finance()
    ce = _estado_carregado(uf)
    if ce.estado.uf != "PA":
        if municipio not in set(ce.df["municipio"]):
            raise HTTPException(status_code=404, detail="Município não encontrado")
        return _financas_de_outro_estado(municipio, ce, fin)

    raw_municipio = REVERSE_FORMATADOS.get(municipio, municipio)
    custos = get_custos_locais(raw_municipio)
    custo_ha = custos["custo_ha"]
    
    return {
        "municipio": municipio,
        # Preço de porteira da CONAB, da mesma praça de onde vem o custo. A
        # cotação de Chicago vai ao lado, para comparação, e nunca como padrão.
        "soja_preco_saca": PRECO_RECEBIDO_CONAB_SACA,
        "soja_preco_cbot_saca": fin["cbot_saca"],
        "soja_preco_paranagua_saca": fin.get("paranagua_saca"),
        # Cotação física diária da praça mais próxima do usuário, e a lista
        # inteira do que a fonte publicou. É a única referência diária do
        # produto: o padrão vem de levantamento bimestral. Porto e terminal
        # não são preço de porteira — daí a praça e o tipo virem junto, para
        # a tela dizer de onde o número veio.
        "preco_fisico": fin.get("fisico"),
        "precos_fisicos": fin.get("cotacoes") or [],
        "custo_ha": custo_ha,
        # Componentes do custo. Com o custo aberto por item (planilha da série
        # histórica da CONAB), custo_area_ha, custo_transporte_saca e taxa_cessr
        # dão o resultado de um valor só; os campos por saca abaixo ficam para o
        # APK antigo e para o caso de o levantamento não ter os itens, em que o
        # resultado volta aos dois rateios extremos do custo variável.
        "custo_variavel_saca": LEVANTAMENTO["custo_variavel_saca"],
        "custo_fixo_ha": LEVANTAMENTO["custo_fixo_saca"] * LEVANTAMENTO["produtividade_referencia_sc_ha"],
        "produtividade_referencia_sc": LEVANTAMENTO["produtividade_referencia_sc_ha"],
        **_componentes_do_custo(),
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
        "aviso_custo": aviso_sobre_o_custo(),
        "ano_referencia": int(AppState.last_year) if AppState.df is not None else 2024
    }

ROOT_PATH = Path(__file__).resolve().parents[2]
DADOS_PATH = ROOT_PATH / "pesquisa" / "dados" / "soja_para_painel.csv"

# In-memory cached model
class AppState:
    # O Pará, como antes; os outros estados ficam em "estados", junto com ele.
    df = None
    estimador = None
    metricas = None
    last_year = None
    pam = {}
    historicos: dict = {}
    estados: dict = {}


def _estado_carregado(uf: str | None) -> "EstadoCarregado":
    """O estado pedido, já com o modelo treinado; 404 se não é atendido, 503 enquanto carrega."""
    e = estados.estado(uf)
    if e is None:
        raise HTTPException(status_code=404, detail="Estado não atendido")
    ce = AppState.estados.get(e.uf)
    if ce is None:
        if e.base.exists():
            raise HTTPException(status_code=503, detail=f"{e.nome}: modelo em preparação, tente em instantes")
        raise HTTPException(status_code=404, detail="Estado não atendido")
    return ce

# Startup phase handled via lifespan manager in app definition

@app.get("/api/ping")
def ping():
    """Lightweight health/warm-up endpoint for mobile app cold-start."""
    return {"status": "ok", "model_loaded": AppState.df is not None}

class PrevisaoRequest(BaseModel):
    municipio: str

@app.get("/api/estados")
def list_estados():
    """Os estados que o produto cobre, com quantos municípios e se o modelo já está pronto."""
    saida = []
    for e in estados.disponiveis():
        ce = AppState.estados.get(e.uf)
        saida.append({"uf": e.uf, "nome": e.nome, "carregado": ce is not None,
                      "municipios": int(ce.df["municipio"].nunique()) if ce is not None else None,
                      "origem": getattr(ce, "origem", None)})
    return {"estados": saida, "padrao": estados.PADRAO}


@app.get("/api/municipios")
def list_municipios(uf: str | None = None, com_sedes: bool = False):
    if AppState.df is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")
    ce = _estado_carregado(uf)
    muns = ce.df["municipio"].unique().tolist()
    muns_formatados = sorted([ce.nome_exibido(m) for m in muns])
    resposta = {"municipios": muns_formatados}
    if uf is not None or com_sedes:
        resposta["uf"] = ce.estado.uf
    if com_sedes:
        # A sede de cada município, para o aplicativo achar o mais perto e
        # buscar a previsão do tempo; o código IBGE vai para os avisos do INMET.
        codigos = ce.df.drop_duplicates("municipio").set_index("municipio")["cod_ibge7"].to_dict()
        resposta["sedes"] = [
            {"nome": ce.nome_exibido(m), "cod_ibge7": int(codigos[m]),
             "latitude": ce.sedes[int(codigos[m])][1], "longitude": ce.sedes[int(codigos[m])][2]}
            for m in sorted(muns, key=ce.nome_exibido) if int(codigos[m]) in ce.sedes]
    return resposta

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
         "soja_preco_paranagua_saca": fin.get("paranagua_saca"),
         # Cotação física diária da praça mais próxima do usuário, e a lista
         # inteira do que a fonte publicou. É a única referência diária do
         # produto: o padrão vem de levantamento bimestral. Porto e terminal
         # não são preço de porteira — daí a praça e o tipo virem junto, para
         # a tela dizer de onde o número veio.
         "preco_fisico": fin.get("fisico"),
         "precos_fisicos": fin.get("cotacoes") or [],
         "custo_ha": custo_ha,
         # Componentes do custo. Com o custo aberto por item (planilha da série
         # histórica da CONAB), custo_area_ha, custo_transporte_saca e taxa_cessr
         # dão o resultado de um valor só; os campos por saca abaixo ficam para o
         # APK antigo e para o caso de o levantamento não ter os itens, em que o
         # resultado volta aos dois rateios extremos do custo variável.
         "custo_variavel_saca": LEVANTAMENTO["custo_variavel_saca"],
         "custo_fixo_ha": LEVANTAMENTO["custo_fixo_saca"] * LEVANTAMENTO["produtividade_referencia_sc_ha"],
         "produtividade_referencia_sc": LEVANTAMENTO["produtividade_referencia_sc_ha"],
         **_componentes_do_custo(),
         "fonte_preco": descricao_do_levantamento(),
         "nota_preco": nota_sobre_o_preco(),
         "levantamento": LEVANTAMENTO["levantamento"],
         "defasagem_meses": meses_desde_o_levantamento(),
         "aviso_preco": aviso_de_defasagem(),
         "aviso_custo": aviso_sobre_o_custo(),
         "ano_referencia": int(AppState.last_year)
    }

def _get_eventos_enso():
    enso_path = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "eventos_enso.json"
    if enso_path.exists():
        try:
            d = json.loads(enso_path.read_text(encoding="utf-8"))
            return d.get("el_ninos", []), d.get("la_ninas", [])
        except Exception:
            pass
    # Sem o arquivo, nenhuma safra marcada: uma lista fixa aqui já marcou safras
    # erradas (classificação por ano do calendário, e não pela safra).
    return [], []

@app.get("/api/mercado")
def get_mercado(periodo: str = "1d", uf: str | None = None):
    """Soja na CBOT em R$/saca ao longo do período, com as referências físicas.

    A cotação de bolsa vem com atraso de 10 a 15 minutos (ver mercado.py). As
    referências situam o número: o físico do dia na praça mais próxima do Pará
    e o preço de porteira do levantamento da CONAB, que é o padrão da simulação.

    "pracas_para" traz a cotação diária de cada praça do Pará na Agrolink.
    "para" traz a estimativa do preço no Pará (ver precos_para.py): cada vela
    ganha "pa", a cotação de Chicago daquele instante somada à base do Pará no
    mês, e o bloco traz a série mensal de onde a base sai.
    """
    if periodo not in mercado.PERIODOS:
        raise HTTPException(status_code=400,
                            detail=f"período deve ser um de {sorted(mercado.PERIODOS)}")
    fin = _get_cached_finance()
    cotacao = mercado.cotacao(periodo)
    ce = _estado_carregado(uf)
    if ce.estado.uf != "PA":
        # Fora do Pará, Chicago e as praças da Agrolink no estado; a estimativa
        # pela base mensal (precos_para.py) é só do Pará.
        praca_csv, rotulo = estados.praca_conab(ce.estado, None)
        lev = estados.levantamento_da_praca(praca_csv, rotulo, LEVANTAMENTO["levantamento"],
                                            LEVANTAMENTO["levantamento_extenso"])
        return {
            "cotacao": cotacao, "para": None, "uf": ce.estado.uf,
            "pracas_para": [], "pracas": precos_para.pracas_do_estado(ce.estado.uf),
            "pracas_fonte": precos_para.FONTE_PRACAS,
            "fisico": fin.get("fisico"),
            "conab_saca": lev["preco_recebido_saca"], "conab_fonte": lev["textos"]["descricao"],
        }
    para = precos_para.estima(cotacao, precos_para.serie_mensal())
    if para is not None:
        pa = para.pop("velas_pa")
        if cotacao and pa:
            cotacao = {**cotacao, "velas": [{**v, "pa": p} for v, p in zip(cotacao["velas"], pa)]}
    return {
        "cotacao": cotacao,
        "para": para,
        # Cotação diária de cada praça do Pará (Agrolink), com a data da última
        # atualização: o número real do dia, ao lado da estimativa.
        "pracas_para": precos_para.pracas_do_para(),
        "pracas_fonte": precos_para.FONTE_PRACAS,
        "fisico": fin.get("fisico"),
        "conab_saca": PRECO_RECEBIDO_CONAB_SACA,
        "conab_fonte": descricao_do_levantamento(),
    }

@app.get("/api/contador")
def get_contador():
    """Anúncio do modelo do contador de vagens que o aplicativo deve usar.

    O aplicativo (AtualizaContador.kt) consulta uma vez por dia e, se a versão
    for mais nova que a dele, baixa os .tflite dos endereços, presos a um
    commit, e confere tamanho e SHA-256 antes de adotar. Lido a cada requisição:
    publicar um modelo novo é só trocar contador_modelo.json.
    """
    with open(Path(__file__).resolve().parent / "contador_modelo.json", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/avisos")
def get_avisos(lat: float | None = None, lon: float | None = None, geocode: str | None = None):
    """Avisos meteorológicos do INMET que atingem o lugar (ver avisos_inmet.py).

    O aplicativo manda o ponto (a sede do município ou o GPS da fazenda) e,
    quando há, o geocódigo IBGE do município. A previsão do tempo em si o
    aplicativo busca direto no Open-Meteo: não depende desta API acordar.
    """
    if (lat is None or lon is None) and not geocode:
        raise HTTPException(status_code=400, detail="informe lat e lon, ou geocode")
    return avisos_inmet.avisos(lat, lon, geocode)

@app.get("/api/plantio/{municipio}")
def get_plantio(municipio: str, uf: str | None = None):
    """Janela de plantio da soja no município (plantio.py).

    O calendário de semeadura e o vazio sanitário da Portaria SDA/MAPA nº
    1.579/2026, na região do estado a que o município pertence, e os riscos do
    ZARC por grupo de cultivar e classe de água disponível no solo. As contas
    das janelas ficam no aplicativo e no painel, que trocam grupo e solo sem
    voltar ao servidor.
    """
    if AppState.df is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")
    ce = _estado_carregado(uf)
    raw_municipio = ce.nome_na_base(municipio)
    linhas = ce.df[ce.df["municipio"] == raw_municipio]
    if linhas.empty:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    dados = plantio.para_municipio(ce.estado.uf, int(linhas["cod_ibge7"].iloc[0]))
    if dados is None:
        raise HTTPException(status_code=503, detail="Janela de plantio indisponível")
    dados["municipio"] = ce.nome_exibido(raw_municipio)
    return dados


def _historico_do_municipio(raw_municipio: str, df_mun, ce: "EstadoCarregado | None" = None) -> list[dict]:
    """Histórico, safras do IBGE fora da base e projeções de um município.

    Só muda quando o processo recarrega a base, o arquivo do IBGE e o modelo,
    então fica guardado por município: cada chamada fazia dezenas de
    estimativas, e 30 celulares abrindo o app juntos esperavam até 30 s.
    """
    ce = ce or AppState.estados["PA"]
    guardado = ce.historicos.get(raw_municipio)
    if guardado is not None:
        return copy.deepcopy(guardado)
    mae = float(ce.estimador.mae)
    resultado = []
    # Histórico passado
    for _, row in df_mun.iterrows():
        ano = int(row["ano"])
        real = float(row["rendimento_kg_ha"])
        r = ce.estimador.estimar(raw_municipio, ano)
        pred = float(r["estimativa_kg_ha"])
        resultado.append({
            "ano": ano,
            "rendimento_predito": pred,
            "rendimento_real": real,
            "margem_erro": mae
        })

    # Safras que o IBGE publicou e a base não tem (sem soja na máscara do
    # MapBiomas naquele ano; ver historico_oficial.py): entram com o valor
    # oficial e a estimativa do modelo, marcadas, para o histórico e a
    # "última safra do IBGE" não pararem anos atrás.
    pam = ce.pam or {}
    ultimo_publicado = historico_oficial.ultima_safra_publicada(ce.last_year, pam)
    oficiais = pam.get(int(df_mun["cod_ibge7"].iloc[0]), {})
    anos_base = set(df_mun["ano"].astype(int))
    for ano, real in historico_oficial.safras_fora_da_base(oficiais, anos_base, ultimo_publicado):
        r = ce.estimador.estimar(raw_municipio, ano)
        resultado.append({
            "ano": ano,
            "rendimento_predito": float(r["estimativa_kg_ha"]),
            "rendimento_real": real,
            "margem_erro": mae,
            "fora_do_modelo": True,
        })
    resultado.sort(key=lambda h: h["ano"])

    # Futuro projetado: as três safras depois da última publicada, a mesma
    # para todos os municípios. Antes partia da última safra do município na
    # base, e quem saiu da máscara em 2017 recebia a projeção de 2018 a 2020.
    ano_max = int(ultimo_publicado)
    for delta in range(1, 4):
        ano_futuro = ano_max + delta
        rf = ce.estimador.estimar(raw_municipio, ano_futuro)
        resultado.append({
             "ano": ano_futuro,
             "rendimento_predito": float(rf["estimativa_kg_ha"]),
             # Sentinela de safra ainda não divulgada pela PAM. Os clientes
             # devem exibir traço, e não zero: um zero aqui anuncia uma
             # colheita nula que não houve.
             "rendimento_real": 0.0,
             "margem_erro": float(rf["margem_kg_ha"])
        })
    ce.historicos[raw_municipio] = resultado
    return copy.deepcopy(resultado)


def _aquece_historicos(uf: str = "PA") -> None:
    ce = AppState.estados[uf]
    for raw in ce.df["municipio"].unique():
        if raw in ce.historicos:  # já veio pronto do cache da build
            continue
        try:
            _historico_do_municipio(raw, ce.df[ce.df["municipio"] == raw], ce)
        except Exception as e:  # um município ruim não impede os outros
            print(f"histórico de {raw} ({uf}) não preparado: {e}", flush=True)


def _metricas_do_estado(ce: "EstadoCarregado") -> dict | None:
    # O arquivo de métricas gravado é o do Pará; os outros estados usam as calculadas na subida.
    arquivo = validacao.ARQUIVO if ce.estado.uf == "PA" else validacao.ARQUIVO.with_name(
        f"metricas_validacao_{ce.estado.uf}.json")
    return metricas_validacao(len(ce.df), ce.df["municipio"].nunique(), ce.metricas, arquivo)


@app.get("/api/previsao/{municipio}")
def get_previsao(municipio: str, uf: str | None = None):
    if AppState.df is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")
    ce = _estado_carregado(uf)
    
    raw_municipio = ce.nome_na_base(municipio)
    df_mun = ce.df[ce.df["municipio"] == raw_municipio].copy()
    if df_mun.empty:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    
    try:
        resultado = _historico_do_municipio(raw_municipio, df_mun, ce)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    el_ninos, la_ninas = _get_eventos_enso()
    resposta = {
        "municipio": municipio, 
        "historico": resultado,
        "elNinos": el_ninos,
        "laNinas": la_ninas,
        # Métricas da validação, para o aplicativo não precisar tê-las escritas
        # no código: acompanham a base a cada safra nova, como no painel web.
        "validacao": _metricas_do_estado(ce),
    }
    if uf is not None:
        resposta["uf"] = ce.estado.uf
    return resposta

@app.get("/api/mapa/geo")
def get_mapa_geo():
    geo_path = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "para_geo.json"
    try:
        geo = json.loads(geo_path.read_text(encoding="utf-8"))
        return geo
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Erro ao carregar mapa: {str(e)}")

@lru_cache(maxsize=256)
def _generate_map_html_cached(municipio: str, theme: str, uf: str = "PA") -> str:
    import folium
    import branca.colormap as cm
    import math

    ce = AppState.estados[uf]
    e = ce.estado
    geo_path, rios_path, mun_path = e.geo, e.rios, e.municipios
    
    try:
        # Sem o contorno (estado montado sem acesso à malha do IBGE), o mapa sai só com os pontos.
        geo = json.loads(geo_path.read_text(encoding="utf-8")) if geo_path.exists() else None
        rios = json.loads(rios_path.read_text(encoding="utf-8")) if rios_path and rios_path.exists() else None
        pts_coords = pd.read_csv(mun_path)
    except Exception as erro:
        return HTMLResponse(f"Erro ao carregar dados geográficos: {str(erro)}", status_code=500)
    
    last_year = int(ce.df["ano"].max())
    recente = ce.df[ce.df["ano"] >= last_year - 4]
    
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
    # Os limites do Pará, como sempre foram; nos outros estados, os pontos com folga.
    limites = ((-10.5, 3.5, -60.0, -45.0) if uf == "PA" else
               (latmin - 3, latmax + 3, lonmin - 4, lonmax + 4))
    m = folium.Map(
        location=[(latmin + latmax) / 2, (lonmin + lonmax) / 2],
        tiles=None,
        zoom_start=6,
        min_zoom=5,
        max_zoom=12,
        max_bounds=True,
        min_lat=limites[0],
        max_lat=limites[1],
        min_lon=limites[2],
        max_lon=limites[3],
        control_scale=True,
        prefer_canvas=True
    )
                   
    if geo is not None:
        folium.GeoJson(
            geo,
            name=e.nome,
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
    
    _cod_por_nome = ce.df.drop_duplicates("municipio").set_index("municipio")["cod_ibge7"].to_dict()
    raw_municipio = ce.nome_na_base(municipio) if municipio else None
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
def render_mapa(municipio: str = None, theme: str = "dark", uf: str | None = None):
    ce = _estado_carregado(uf)
    try:
        html = _generate_map_html_cached(municipio, theme, ce.estado.uf)
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(f"Erro ao gerar mapa: {str(e)}", status_code=500)


class SimulacaoRequest(BaseModel):
    municipio: str
    precip_factor: float
    temp_offset: float
    # A safra do cenário. O app manda a safra em curso, a mesma do Resumo; sem
    # ela (versões antigas), vale a seguinte à última publicada.
    ano: int | None = None
    # Sem estado, o Pará, como nas versões antigas.
    uf: str | None = None

@lru_cache(maxsize=8)
def _sensibilidade_clima(uf: str = "PA"):
    """Associação chuva-rendimento na base, calculada uma vez por processo e estado."""
    ce = AppState.estados.get(uf)
    if ce is None:
        return None
    return M.sensibilidade_climatica(ce.df)


@app.post("/api/simulacao")
def simular_cenario(req: SimulacaoRequest):
    if AppState.df is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado")
    
    ce = _estado_carregado(req.uf)
    # As safras que a API projeta: as três seguintes à última publicada.
    ultimo = historico_oficial.ultima_safra_publicada(ce.last_year, ce.pam or {})
    ano_alvo = req.ano if req.ano is not None and ultimo < req.ano <= ultimo + 3 else ultimo + 1
    raw_municipio = ce.nome_na_base(req.municipio)
    
    hist = ce.df[ce.df.municipio == raw_municipio]
    if hist.empty:
        raise HTTPException(status_code=404, detail="Município não encontrado")
        
    clima = hist[M.FEATURES].mean().to_dict()
    
    # ── Optimized: compute baseline once, reuse for both scenarios ──
    from model import _baseline
    import numpy as np
    base_val = float(_baseline(
        ce.estimador.df,
        pd.Series([raw_municipio]),
        pd.Series([ano_alvo])
    )[0])
    
    # Baseline prediction (unmodified climate)
    x_base = np.array([clima[f] for f in M.FEATURES], dtype=float)
    corr_base = float(ce.estimador.modelo.predict(
        ce.estimador.scaler.transform(x_base.reshape(1, -1))
    )[0])
    est_base = base_val + corr_base

    # O cenário sai do que a base mostra (model.associacao_climatica): quanto
    # a produtividade fugiu da referência por 1% de chuva e por 1 °C acima do
    # normal do município, só com o coeficiente de IC95 sem o zero, e preso à
    # faixa de anomalias observada no estado. Antes a rede respondia à chuva
    # mudada com todo o resto no normal, uma combinação que quase não existe nos
    # dados, e no Maranhão dava mais soja com menos chuva.
    efeito = ce.estimador.cenario(req.precip_factor, req.temp_offset)
    fora_da_faixa = efeito["fora_da_faixa"]
    est_sim = est_base + efeito["delta_kg_ha"]

    return {
        "municipio": req.municipio,
        "ano": ano_alvo,
        "baseline_kg_ha": est_base,
        "estimativa_kg_ha": est_sim,
        "fora_da_faixa": fora_da_faixa,
        "delta_kg_ha": est_sim - est_base,
        # Para a interface poder dizer o que o cenário significa: a margem do
        # modelo e a força da associação medida na base. Sem isso o usuário lê
        # uma variação de dezenas de quilos como se fosse resposta agronômica.
        "margem_kg_ha": ce.estimador.rmse,
        "sensibilidade": _sensibilidade_clima(ce.estado.uf),
        # O que o cenário usou: o efeito por 1% de chuva e por 1 °C, com o IC95,
        # se vale (IC95 sem o zero) e a faixa de anomalias observada no estado.
        "associacao": ce.estimador.associacao,
    }
