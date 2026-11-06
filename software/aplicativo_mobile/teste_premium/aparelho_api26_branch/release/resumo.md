# App de release no Android 26 (Android SDK built for x86_64)

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
| sem internet: o app avisa | **falha** |  |
| sem internet: o Mapa explica | **falha** |  |
| sem internet: a Estimativa no campo abre | ok |  |
| monkey: sem falhas nem ANR | ok | 3000 eventos, 0 falhas, 0 ANR |

## Medidas

```
{
 "api_level": 26,
 "aparelho": "Android SDK built for x86_64",
 "largura_px": 320,
 "altura_px": 640,
 "densidade_dpi": 160,
 "apk_mb": 27.6,
 "partida_fria_primeira_ms": 658,
 "partida_fria_sem_municipio_ms": 699.0,
 "dados_do_municipio_s": 3.7,
 "memoria_resumo_kb": 29474,
 "rolagem_resumo": {
  "quadros": 867.0,
  "lentos_pct": 6.34,
  "p50_ms": 5.0,
  "p90_ms": 8.0,
  "p99_ms": 20.0
 },
 "rolagem_historico": {
  "quadros": 776.0,
  "lentos_pct": 0.0,
  "p50_ms": 5.0,
  "p90_ms": 6.0,
  "p99_ms": 8.0
 },
 "memoria_depois_das_abas_kb": 79088,
 "partida_fria_com_municipio_ms": 750,
 "monkey": {
  "eventos": 3000,
  "falhas": 0,
  "anrs": 0
 }
}
```

## Acessibilidade pela árvore do uiautomator

- **r04_resumo_2**: alvos < 48 dp: 5277,12 (120×4 dp); sem rótulo: nenhum
- **r05_mapa**: alvos < 48 dp: nenhum; sem rótulo: WebView em (17,177)
- **r08_sobre**: alvos < 48 dp: View (248×24 dp), View (248×46 dp); sem rótulo: nenhum
- **r12_fonte_200_rolado**: alvos < 48 dp: View (288×7 dp); sem rótulo: View em (16,24)
