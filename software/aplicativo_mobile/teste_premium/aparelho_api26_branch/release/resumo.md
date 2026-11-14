# App de release no Android 26 (Android SDK built for x86_64)

| Verificação | Resultado | Detalhe |
|---|---|---|
| abre na tela de boas-vindas | **falha** |  |
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
| roteiro completo | **falha** | TimeoutExpired: Command '['adb', 'wait-for-device']' timed out after 60 seconds |

## Medidas

```
{
 "api_level": 26,
 "aparelho": "Android SDK built for x86_64",
 "largura_px": 1080,
 "altura_px": 2400,
 "densidade_dpi": 420,
 "apk_mb": 27.6,
 "partida_fria_primeira_ms": 624,
 "partida_fria_sem_municipio_ms": 645,
 "dados_do_municipio_s": 185.0,
 "memoria_resumo_kb": null,
 "rolagem_resumo": {
  "quadros": null,
  "lentos_pct": null,
  "p50_ms": null,
  "p90_ms": null,
  "p99_ms": null
 },
 "rolagem_historico": {
  "quadros": null,
  "lentos_pct": null,
  "p50_ms": null,
  "p90_ms": null,
  "p99_ms": null
 },
 "memoria_depois_das_abas_kb": null,
 "partida_fria_com_municipio_ms": null
}
```

## Acessibilidade pela árvore do uiautomator

