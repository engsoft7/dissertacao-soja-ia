import requests

REV_MUNICIPIOS = {
    "Goianesia Do Para": "GOIANESIA DO PARA",
    "Dom Eliseu": "DOM ELISEU",
    "Ulianopolis": "ULIANOPOLIS",
    "Paragominas": "PARAGOMINAS",
    "Rondon Do Para": "RONDON DO PARA",
    "Santana Do Araguaia": "SANTANA DO ARAGUAIA",
    "Conceicao Do Araguaia": "CONCEICAO DO ARAGUAIA",
    "Redencao": "REDENCAO",
}

# ── CUSTO DE PRODUÇÃO ────────────────────────────────────────────────────────
# Fonte: CONAB, Custos de Produção — Soja, município de Pedro Afonso (TO),
# levantamento de março de 2026. É o ponto de coleta da CONAB no cerrado do
# Tocantins. O Pará não integra o MATOPIBA e não tem custo de soja levantado,
# por isso adota-se o cerrado vizinho como referência, conforme registrado em
# software/dashboard_web/README.md e na subseção 4.9 da dissertação.
#
# A CONAB publica o custo por saca comercializada. A conversão para hectare usa
# a produtividade de referência do próprio levantamento, 2.880 kg/ha (48 sc/ha):
#
#   custo variável (custeio)      R$  85,03/sc  ->  R$ 4.081,44/ha
#   custo fixo                    R$  24,91/sc  ->  R$ 1.195,68/ha
#   custo operacional (var+fixo)  R$ 109,94/sc  ->  R$ 5.277,12/ha   <- usado
#   renda de fatores              R$   9,12/sc  ->  R$   437,76/ha
#   custo total                   R$ 119,06/sc  ->  R$ 5.714,88/ha
#
# Usa-se o custo OPERACIONAL porque é o que a CONAB define como variável mais
# fixo, e é o que o campo "Custo Operacional" do painel representa. Para simular
# apenas o desembolso de custeio, trocar por CUSTO_VARIAVEL_HA.
#
# Valor único para todos os municípios: a tabela anterior trazia sete valores
# escalonados a partir do preço da terra (correlação de 0,985 com o VTN), o que
# não tem base agronômica — fertilizante e defensivo não custam mais onde o
# hectare é mais caro.
CUSTO_VARIAVEL_HA   = 4081.44
CUSTO_OPERACIONAL_HA = 5277.12
CUSTO_TOTAL_HA      = 5714.88
CUSTO_REFERENCIA_HA = CUSTO_OPERACIONAL_HA

# ── VALOR DA TERRA NUA ───────────────────────────────────────────────────────
# Continua sem fonte apurada: são referências fixas por município, mantidas do
# levantamento anterior e editáveis na interface. Não entram no cálculo da
# margem, apenas informam o capital imobilizado.
VTN_POR_MUNICIPIO = {
    "PARAGOMINAS": 15000.0,
    "DOM ELISEU": 14000.0,
    "ULIANOPOLIS": 14200.0,
    "RONDON DO PARA": 13800.0,
    "SANTANA DO ARAGUAIA": 12500.0,
    "CONCEICAO DO ARAGUAIA": 11000.0,
    "REDENCAO": 11500.0,
}
VTN_PADRAO_HA = 12000.0

def get_custos_locais(municipio: str):
    mun = REV_MUNICIPIOS.get(municipio, municipio).upper()
    return {"custo_ha": CUSTO_REFERENCIA_HA,
            "vtn_ha": VTN_POR_MUNICIPIO.get(mun, VTN_PADRAO_HA)}

def get_financas(municipio: str):
    headers = {'User-Agent': 'Mozilla/5.0'}
    brl_price_bag = 120.0
    try:
        r_cbot = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/ZS=F', headers=headers)
        price_cents = r_cbot.json()['chart']['result'][0]['meta']['regularMarketPrice']
        usd_price_bag = (price_cents / 100) * 2.20462
        
        r_usd = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/BRL=X', headers=headers)
        usd_brl = float(r_usd.json()['chart']['result'][0]['meta']['regularMarketPrice'])
        brl_price_bag = round(usd_price_bag * usd_brl, 2)
    except Exception as e:
        print("Erro online financas:", e, flush=True)
        pass

    raw_municipio = REV_MUNICIPIOS.get(municipio, municipio)
    custos = get_custos_locais(raw_municipio)
    
    custo_ha = custos["custo_ha"]
    
    return {
        "soja_preco_saca": brl_price_bag,
        "custo_ha": custo_ha,
        "vtn_ha": custos["vtn_ha"],
        "margem_ebitda_estimada": 0.0,
        "risco_direto": "MODERADO"
    }
