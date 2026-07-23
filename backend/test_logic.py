import requests

try:
    r_cbot = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/ZS=F', headers={'User-Agent': 'Mozilla/5.0'})
    price_cents = r_cbot.json()['chart']['result'][0]['meta']['regularMarketPrice']
    usd_price_bag = (price_cents / 100) * 2.20462
    
    # Puxa Dólar
    r_usd = requests.get('https://economia.awesomeapi.com.br/last/USD-BRL')
    usd_brl = float(r_usd.json()['USDBRL']['bid'])
    
    brl_price_bag = round(usd_price_bag * usd_brl, 2)
    custo_ha = round((brl_price_bag * 55) * 0.65, 2)
    
    print("Preço Real:", brl_price_bag)
    print("Custo por HA:", custo_ha)
except Exception as e:
    print(e)
