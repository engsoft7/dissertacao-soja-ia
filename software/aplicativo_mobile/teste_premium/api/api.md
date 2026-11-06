# API em produção: robustez e desempenho (https://agrointeligencia-api.onrender.com)

| Verificação | Resultado | Detalhe |
|---|---|---|
| API responde | ok | 200 em 162 ms |
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
| entrada estranha: aspas e ponto e vírgula | **falha** | HTTP 403: <!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-w |
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
| 30 requisições simultâneas sem erro | ok | p95 29612 ms |
| HTTP sem criptografia redireciona para HTTPS | ok | 301 |

## Rotas (duas passadas de aquecimento antes)

| Rota | n | erros | p50 (ms) | p95 (ms) | KB | comprimido |
|---|---|---|---|---|---|---|
| previsao | 38 | 0 | 1101.0 | 1912.0 | 2.1 | 38/38 |
| financas | 38 | 0 | 101.0 | 201.0 | 1.3 | 38/38 |
| municipios | 5 | 0 | 107.0 | 182.0 | 0.6 | 5/5 |
| kpis_economia | 5 | 0 | 112.0 | 211.0 | 1.2 | 5/5 |
| mercado 1d | 5 | 0 | 104.0 | 192.0 | 7.5 | 5/5 |
| mercado 1mo | 3 | 0 | 101.0 | 108.0 | 4.5 | 3/3 |
| contador | 5 | 0 | 112.0 | 170.0 | 0.9 | 5/5 |
| avisos (geocode) | 3 | 0 | 101.0 | 105.0 | 0.1 | 3/3 |
| avisos (lat/lon) | 3 | 0 | 101.0 | 102.0 | 0.1 | 3/3 |
| mapa/render | 5 | 0 | 404.0 | 518.0 | 88.0 | 5/5 |

## Outras medidas

```
{
 "ping_inicial_ms": 162,
 "entradas_estranhas": [
  {
   "caso": "município inexistente",
   "status": "404",
   "ms": 93
  },
  {
   "caso": "nome com 5.000 letras",
   "status": "404",
   "ms": 106
  },
  {
   "caso": "aspas e ponto e vírgula",
   "status": "403",
   "ms": 32
  },
  {
   "caso": "caminho com ../",
   "status": "404",
   "ms": 94
  },
  {
   "caso": "emoji",
   "status": "404",
   "ms": 106
  },
  {
   "caso": "finanças de município inexistente",
   "status": "200",
   "ms": 99
  },
  {
   "caso": "avisos sem parâmetros",
   "status": "400",
   "ms": 94
  },
  {
   "caso": "avisos com lat não numérica",
   "status": "422",
   "ms": 92
  },
  {
   "caso": "avisos fora da Terra",
   "status": "200",
   "ms": 96
  },
  {
   "caso": "avisos com geocode estranho",
   "status": "200",
   "ms": 100
  },
  {
   "caso": "mercado com período inválido",
   "status": "400",
   "ms": 95
  },
  {
   "caso": "simulação sem corpo",
   "status": "422",
   "ms": 96
  },
  {
   "caso": "simulação com tipos errados",
   "status": "422",
   "ms": 95
  },
  {
   "caso": "simulação com fator enorme",
   "status": "200",
   "ms": 116
  },
  {
   "caso": "simulação de município inexistente",
   "status": "404",
   "ms": 92
  },
  {
   "caso": "rota inexistente",
   "status": "404",
   "ms": 97
  }
 ],
 "simultaneas_30": {
  "erros": 0,
  "total_ms": 29706,
  "p50_ms": 25448.0,
  "p95_ms": 29612.0,
  "max_ms": 29671
 },
 "cabecalhos_ping": {
  "access-control-allow-credentials": "true",
  "access-control-allow-origin": "https://exemplo.org",
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
