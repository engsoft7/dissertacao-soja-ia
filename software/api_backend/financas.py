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

BASE_CUSTO_PA = {
    "PARAGOMINAS": {"custo_ha": 4850.0, "vtn_ha": 15000.0},
    "DOM ELISEU": {"custo_ha": 4800.0, "vtn_ha": 14000.0},
    "ULIANOPOLIS": {"custo_ha": 4820.0, "vtn_ha": 14200.0},
    "RONDON DO PARA": {"custo_ha": 4750.0, "vtn_ha": 13800.0},
    "SANTANA DO ARAGUAIA": {"custo_ha": 4650.0, "vtn_ha": 12500.0},
    "CONCEICAO DO ARAGUAIA": {"custo_ha": 4500.0, "vtn_ha": 11000.0},
    "REDENCAO": {"custo_ha": 4600.0, "vtn_ha": 11500.0},
}

def get_custos_locais(municipio: str):
    mun = REV_MUNICIPIOS.get(municipio, municipio).upper()
    return BASE_CUSTO_PA.get(mun, {"custo_ha": 4800.0, "vtn_ha": 12000.0})

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
