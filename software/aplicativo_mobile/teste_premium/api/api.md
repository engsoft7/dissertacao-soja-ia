# API em produção: robustez e desempenho (https://agrointeligencia-api.onrender.com)

| Verificação | Resultado | Detalhe |
|---|---|---|
| API responde | ok | 200 em 227 ms |
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
| 30 requisições simultâneas sem erro | ok | p95 1062 ms |
| HTTP sem criptografia redireciona para HTTPS | ok | 301 |

## Rotas (duas passadas de aquecimento antes)

| Rota | n | erros | p50 (ms) | p95 (ms) | KB | comprimido |
|---|---|---|---|---|---|---|
| previsao | 38 | 0 | 104.0 | 120.0 | 2.1 | 38/38 |
| financas | 38 | 0 | 102.0 | 502.0 | 1.0 | 38/38 |
| municipios | 5 | 0 | 93.0 | 101.0 | 0.6 | 5/5 |
| kpis_economia | 5 | 0 | 87.0 | 92.0 | 0.9 | 5/5 |
| mercado 1d | 5 | 0 | 83.0 | 94.0 | 7.8 | 5/5 |
| mercado 1mo | 3 | 0 | 86.0 | 103.0 | 4.4 | 3/3 |
| contador | 5 | 0 | 85.0 | 87.0 | 1.1 | 5/5 |
| avisos (geocode) | 3 | 0 | 90.0 | 127.0 | 0.1 | 3/3 |
| avisos (lat/lon) | 3 | 0 | 85.0 | 95.0 | 0.1 | 3/3 |
| mapa/render | 5 | 0 | 108.0 | 123.0 | 88.0 | 5/5 |

## Outras medidas

```
{
 "ping_inicial_ms": 227,
 "entradas_estranhas": [
  {
   "caso": "município inexistente",
   "status": "404",
   "ms": 81
  },
  {
   "caso": "nome com 5.000 letras",
   "status": "404",
   "ms": 83
  },
  {
   "caso": "aspas e ponto e vírgula",
   "status": "403",
   "ms": 94
  },
  {
   "caso": "caminho com ../",
   "status": "404",
   "ms": 88
  },
  {
   "caso": "emoji",
   "status": "404",
   "ms": 82
  },
  {
   "caso": "finanças de município inexistente",
   "status": "200",
   "ms": 79
  },
  {
   "caso": "avisos sem parâmetros",
   "status": "400",
   "ms": 91
  },
  {
   "caso": "avisos com lat não numérica",
   "status": "422",
   "ms": 90
  },
  {
   "caso": "avisos fora da Terra",
   "status": "200",
   "ms": 83
  },
  {
   "caso": "avisos com geocode estranho",
   "status": "200",
   "ms": 88
  },
  {
   "caso": "mercado com período inválido",
   "status": "400",
   "ms": 83
  },
  {
   "caso": "simulação sem corpo",
   "status": "422",
   "ms": 78
  },
  {
   "caso": "simulação com tipos errados",
   "status": "422",
   "ms": 85
  },
  {
   "caso": "simulação com fator enorme",
   "status": "200",
   "ms": 113
  },
  {
   "caso": "simulação de município inexistente",
   "status": "404",
   "ms": 89
  },
  {
   "caso": "rota inexistente",
   "status": "404",
   "ms": 84
  }
 ],
 "simultaneas_30": {
  "erros": 0,
  "total_ms": 1163,
  "p50_ms": 950.0,
  "p95_ms": 1062.0,
  "max_ms": 1153
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
