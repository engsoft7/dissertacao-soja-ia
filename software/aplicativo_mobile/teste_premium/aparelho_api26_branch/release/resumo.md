# App de release no Android 26 (Android SDK built for x86_64)

| Verificação | Resultado | Detalhe |
|---|---|---|
| abre na tela de boas-vindas | ok |  |
| acha Pau D'Arco na busca | ok |  |
| Resumo carrega a safra em curso | ok | Resumo Agronômico (safra 2027) |
| Resumo mostra a última safra do IBGE, 2025 | ok |  |
| abre a aba Mapa | ok |  |
| abre a aba Histórico | ok |  |
| abre a aba Mercado | ok |  |
| abre a aba Sobre | ok |  |
| fonte 200%: Resumo abre | ok |  |
| tela pequena: Resumo abre | ok |  |
| tela tablet: Resumo abre | ok |  |
| tela deitada: Resumo abre | ok |  |
| o emulador ficou sem internet | ok |  |
| sem internet: Resumo abre com os dados guardados | ok |  |
| sem internet: o app avisa | ok |  |
| sem internet: o Mapa explica | ok |  |
| sem internet: a Estimativa no campo abre | ok |  |
| a internet do emulador voltou | **falha** |  |
| monkey: sem falhas nem ANR | ok | 3000 eventos, 0 falhas, 0 ANR |

## Medidas

```
{
 "api_level": 26,
 "aparelho": "Android SDK built for x86_64",
 "largura_px": 1080,
 "altura_px": 2400,
 "densidade_dpi": 420,
 "apk_mb": 27.6,
 "partida_fria_primeira_ms": 983,
 "partida_fria_sem_municipio_ms": 1001.5,
 "dados_do_municipio_s": 3.8,
 "memoria_resumo_kb": 32838,
 "rolagem_resumo": {
  "quadros": 386.0,
  "lentos_pct": 98.45,
  "p50_ms": 65.0,
  "p90_ms": 85.0,
  "p99_ms": 93.0
 },
 "rolagem_historico": {
  "quadros": 216.0,
  "lentos_pct": 97.69,
  "p50_ms": 65.0,
  "p90_ms": 93.0,
  "p99_ms": 105.0
 },
 "memoria_depois_das_abas_kb": 81953,
 "partida_fria_com_municipio_ms": 1105,
 "monkey": {
  "eventos": 3000,
  "falhas": 0,
  "anrs": 0
 }
}
```

## Acessibilidade pela árvore do uiautomator

- **r04_resumo_1**: alvos < 48 dp: 152,50 (166×26 dp), 53,8 (166×26 dp); sem rótulo: nenhum
- **r05_mapa**: alvos < 48 dp: nenhum; sem rótulo: WebView em (45,465)
- **r08_sobre**: alvos < 48 dp: View (339×33 dp), View (339×44 dp), View (339×46 dp); sem rótulo: nenhum
- **r09_estimativa_no_campo**: alvos < 48 dp: View (347×32 dp); sem rótulo: nenhum
