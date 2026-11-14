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
| a internet do emulador voltou | ok |  |
| monkey: sem falhas nem ANR | ok | 3000 eventos, 0 falhas, 0 ANR |

## Medidas

```
{
 "api_level": 26,
 "aparelho": "Android SDK built for x86_64",
 "largura_px": 1080,
 "altura_px": 2400,
 "densidade_dpi": 420,
 "apk_mb": 28.0,
 "partida_fria_primeira_ms": 647,
 "partida_fria_sem_municipio_ms": 655.5,
 "dados_do_municipio_s": 3.7,
 "memoria_resumo_kb": 34211,
 "rolagem_resumo": {
  "quadros": 470.0,
  "lentos_pct": 96.17,
  "p50_ms": 53.0,
  "p90_ms": 69.0,
  "p99_ms": 81.0
 },
 "rolagem_historico": {
  "quadros": 340.0,
  "lentos_pct": 97.35,
  "p50_ms": 48.0,
  "p90_ms": 65.0,
  "p99_ms": 77.0
 },
 "memoria_depois_das_abas_kb": 79996,
 "partida_fria_com_municipio_ms": 732,
 "monkey": {
  "eventos": 3000,
  "falhas": 0,
  "anrs": 0
 }
}
```

## Acessibilidade pela árvore do uiautomator

- **r03_resumo**: alvos < 48 dp: View (379×37 dp); sem rótulo: nenhum
- **r04_resumo_1**: alvos < 48 dp: 5277,12 (166×2 dp), View (379×30 dp); sem rótulo: nenhum
- **r05_mapa**: alvos < 48 dp: nenhum; sem rótulo: WebView em (45,465)
- **r08_sobre**: alvos < 48 dp: View (339×15 dp); sem rótulo: nenhum
- **r09_estimativa_no_campo**: alvos < 48 dp: View (347×12 dp); sem rótulo: View em (84,2032)
- **r10_tempo**: alvos < 48 dp: View (100×13 dp); sem rótulo: View em (123,2029)
- **r18_sem_internet**: alvos < 48 dp: View (154×45 dp), View (166×45 dp); sem rótulo: nenhum
