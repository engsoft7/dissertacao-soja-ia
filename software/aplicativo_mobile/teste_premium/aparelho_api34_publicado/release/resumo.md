# App de release no Android 34 (sdk_gphone64_x86_64)

| Verificação | Resultado | Detalhe |
|---|---|---|
| abre na tela de boas-vindas | ok |  |
| acha Pau D'Arco na busca | ok |  |
| Resumo carrega a safra em curso | ok | Resumo Agronômico (safra 2027) |
| Resumo mostra a última safra do IBGE, 2025 | **falha** |  |
| abre a aba Mapa | ok |  |
| abre a aba Histórico | ok |  |
| abre a aba Mercado | ok |  |
| abre a aba Sobre | ok |  |
| fonte 200%: Resumo abre | **falha** |  |
| tela pequena: Resumo abre | ok |  |
| tela tablet: Resumo abre | ok |  |
| tela deitada: Resumo abre | **falha** |  |
| sem internet: Resumo abre com os dados guardados | ok |  |
| sem internet: o app avisa | ok |  |
| sem internet: o Mapa explica | ok |  |
| sem internet: a Estimativa no campo abre | ok |  |
| monkey: sem falhas nem ANR | ok | 3000 eventos, 0 falhas, 0 ANR |

## Medidas

```
{
 "api_level": 34,
 "aparelho": "sdk_gphone64_x86_64",
 "largura_px": 320,
 "altura_px": 640,
 "densidade_dpi": 160,
 "apk_mb": 38.6,
 "partida_fria_primeira_ms": 2576,
 "partida_fria_sem_municipio_ms": 1278.0,
 "dados_do_municipio_s": 6.5,
 "memoria_resumo_kb": 57522,
 "rolagem_resumo": {
  "quadros": 422.0,
  "lentos_pct": 10.66,
  "p50_ms": 16.0,
  "p90_ms": 25.0,
  "p99_ms": 117.0
 },
 "rolagem_historico": {
  "quadros": 590.0,
  "lentos_pct": 5.93,
  "p50_ms": 16.0,
  "p90_ms": 16.0,
  "p99_ms": 26.0
 },
 "memoria_depois_das_abas_kb": 100952,
 "partida_fria_com_municipio_ms": 686,
 "monkey": {
  "eventos": 3000,
  "falhas": 0,
  "anrs": 0
 }
}
```

## Acessibilidade pela árvore do uiautomator

- **r05_mapa**: alvos < 48 dp: nenhum; sem rótulo: WebView em (17,177)
- **r08_sobre**: alvos < 48 dp: View (248×42 dp), View (248×46 dp); sem rótulo: nenhum
- **r16_tela_tablet**: alvos < 48 dp: 5277,12 (360×11 dp); sem rótulo: nenhum
