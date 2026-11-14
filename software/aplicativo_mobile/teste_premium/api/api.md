# API em produção: robustez e desempenho (https://agrointeligencia-api.onrender.com)

| Verificação | Resultado | Detalhe |
|---|---|---|
| API responde | ok | 200 em 84 ms |
| API serve a correção da main (Pau D'Arco projeta 2026–2028) | ok |  |
| lista com os 38 municípios | ok | 38 |
| previsao: sem erro | ok | 0 de 38 |
| financas: sem erro | ok | 0 de 38 |
| municipios: sem erro | ok | 0 de 5 |
| kpis_economia: sem erro | ok | 0 de 5 |
| mercado 1d: sem erro | ok | 0 de 5 |
| mercado 1mo: sem erro | ok | 0 de 3 |
| contador: sem erro | ok | 0 de 5 |
| avisos (geocode): sem erro | ok | 0 de 3 |
| avisos (lat/lon): sem erro | ok | 0 de 3 |
| mapa/render: sem erro | ok | 0 de 5 |
| entrada estranha: município inexistente | ok | HTTP 404 |
| entrada estranha: nome com 5.000 letras | ok | HTTP 404 |
| entrada estranha: aspas e ponto e vírgula | ok | HTTP 403 |
| entrada estranha: caminho com ../ | ok | HTTP 404 |
| entrada estranha: emoji | ok | HTTP 404 |
| entrada estranha: finanças de município inexistente | ok | HTTP 200 |
| entrada estranha: avisos sem parâmetros | ok | HTTP 400 |
| entrada estranha: avisos com lat não numérica | ok | HTTP 422 |
| entrada estranha: avisos fora da Terra | ok | HTTP 200 |
| entrada estranha: avisos com geocode estranho | ok | HTTP 200 |
| entrada estranha: mercado com período inválido | ok | HTTP 400 |
| entrada estranha: simulação sem corpo | ok | HTTP 422 |
| entrada estranha: simulação com tipos errados | ok | HTTP 422 |
| entrada estranha: simulação com fator enorme | ok | HTTP 200 |
| entrada estranha: simulação de município inexistente | ok | HTTP 404 |
| entrada estranha: rota inexistente | ok | HTTP 404 |
| mapa não reflete HTML vindo da URL | ok | 200 |
| 30 requisições simultâneas sem erro | ok | p95 938 ms |
| HTTP sem criptografia redireciona para HTTPS | ok | 301 |

## Rotas (duas passadas de aquecimento antes)

| Rota | n | erros | p50 (ms) | p95 (ms) | KB | comprimido |
|---|---|---|---|---|---|---|
| previsao | 38 | 0 | 34.0 | 63.0 | 2.1 | 38/38 |
| financas | 38 | 0 | 103.0 | 1198.0 | 1.0 | 38/38 |
| municipios | 5 | 0 | 30.0 | 33.0 | 0.6 | 5/5 |
| kpis_economia | 5 | 0 | 33.0 | 36.0 | 0.9 | 5/5 |
| mercado 1d | 5 | 0 | 35.0 | 36.0 | 7.8 | 5/5 |
| mercado 1mo | 3 | 0 | 31.0 | 33.0 | 4.4 | 3/3 |
| contador | 5 | 0 | 29.0 | 57.0 | 1.1 | 5/5 |
| avisos (geocode) | 3 | 0 | 28.0 | 29.0 | 0.1 | 3/3 |
| avisos (lat/lon) | 3 | 0 | 29.0 | 29.0 | 0.1 | 3/3 |
| mapa/render | 5 | 0 | 48.0 | 55.0 | 88.0 | 5/5 |

## Outras medidas

```
{
 "ping_inicial_ms": 84,
 "entradas_estranhas": [
  {
   "caso": "município inexistente",
   "status": "404",
   "ms": 31
  },
  {
   "caso": "nome com 5.000 letras",
   "status": "404",
   "ms": 31
  },
  {
   "caso": "aspas e ponto e vírgula",
   "status": "403",
   "ms": 36
  },
  {
   "caso": "caminho com ../",
   "status": "404",
   "ms": 33
  },
  {
   "caso": "emoji",
   "status": "404",
   "ms": 29
  },
  {
   "caso": "finanças de município inexistente",
   "status": "200",
   "ms": 28
  },
  {
   "caso": "avisos sem parâmetros",
   "status": "400",
   "ms": 34
  },
  {
   "caso": "avisos com lat não numérica",
   "status": "422",
   "ms": 32
  },
  {
   "caso": "avisos fora da Terra",
   "status": "200",
   "ms": 36
  },
  {
   "caso": "avisos com geocode estranho",
   "status": "200",
   "ms": 30
  },
  {
   "caso": "mercado com período inválido",
   "status": "400",
   "ms": 30
  },
  {
   "caso": "simulação sem corpo",
   "status": "422",
   "ms": 30
  },
  {
   "caso": "simulação com tipos errados",
   "status": "422",
   "ms": 34
  },
  {
   "caso": "simulação com fator enorme",
   "status": "200",
   "ms": 38
  },
  {
   "caso": "simulação de município inexistente",
   "status": "404",
   "ms": 31
  },
  {
   "caso": "rota inexistente",
   "status": "404",
   "ms": 28
  }
 ],
 "simultaneas_30": {
  "erros": 0,
  "total_ms": 968,
  "p50_ms": 852.0,
  "p95_ms": 938.0,
  "max_ms": 940
 },
 "cabecalhos_ping": {
  "access-control-allow-origin": "*",
  "Server": "cloudflare",
  "x-render-origin-server": "uvicorn"
 },
 "mapa_hosts_externos": [
  "cdn.jsdelivr.net",
  "cdnjs.cloudflare.com",
  "code.jquery.com",
  "netdna.bootstrapcdn.com"
 ]
}
```
