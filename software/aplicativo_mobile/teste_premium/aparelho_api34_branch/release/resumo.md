# App de release no Android 34 (sdk_gphone64_x86_64)

| Verificação | Resultado | Detalhe |
|---|---|---|
| abre na tela de boas-vindas | ok |  |
| acha Pau D'Arco na busca | **falha** |  |
| Resumo carrega a safra em curso | **falha** |  |
| Resumo mostra a última safra do IBGE, 2025 | **falha** |  |
| abre a aba Mapa | **falha** |  |
| abre a aba Histórico | **falha** |  |
| abre a aba Mercado | **falha** |  |
| abre a aba Sobre | **falha** |  |
| fonte 200%: Resumo abre | **falha** |  |
| tela pequena: Resumo abre | **falha** |  |
| tela tablet: Resumo abre | **falha** |  |
| tela deitada: Resumo abre | **falha** |  |
| o emulador ficou sem internet | ok |  |
| sem internet: Resumo abre com os dados guardados | **falha** |  |
| sem internet: o app avisa | **falha** |  |
| sem internet: o Mapa explica | **falha** |  |
| sem internet: a Estimativa no campo abre | **falha** |  |
| a internet do emulador voltou | **falha** |  |
| monkey: sem falhas nem ANR | ok | 3000 eventos, 0 falhas, 0 ANR |

## Medidas

```
{
 "api_level": 34,
 "aparelho": "sdk_gphone64_x86_64",
 "largura_px": 1080,
 "altura_px": 2400,
 "densidade_dpi": 420,
 "apk_mb": 27.6,
 "partida_fria_primeira_ms": 1074,
 "partida_fria_sem_municipio_ms": 920.5,
 "dados_do_municipio_s": 184.4,
 "memoria_resumo_kb": 33691,
 "rolagem_resumo": {
  "quadros": 0.0,
  "lentos_pct": 0.0,
  "p50_ms": 4950.0,
  "p90_ms": 4950.0,
  "p99_ms": 4950.0
 },
 "rolagem_historico": {
  "quadros": 0.0,
  "lentos_pct": 0.0,
  "p50_ms": 4950.0,
  "p90_ms": 4950.0,
  "p99_ms": 4950.0
 },
 "memoria_depois_das_abas_kb": 35397,
 "partida_fria_com_municipio_ms": 913,
 "monkey": {
  "eventos": 3000,
  "falhas": 0,
  "anrs": 0
 }
}
```

## Acessibilidade pela árvore do uiautomator

