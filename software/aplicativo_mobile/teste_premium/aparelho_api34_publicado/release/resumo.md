# App de release no Android 34 (sdk_gphone64_x86_64)

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
 "api_level": 34,
 "aparelho": "sdk_gphone64_x86_64",
 "largura_px": 1080,
 "altura_px": 2400,
 "densidade_dpi": 420,
 "apk_mb": 27.6,
 "partida_fria_primeira_ms": 1197,
 "partida_fria_sem_municipio_ms": 1187.5,
 "dados_do_municipio_s": 5.5,
 "memoria_resumo_kb": 36987,
 "rolagem_resumo": {
  "quadros": 193.0,
  "lentos_pct": 84.46,
  "p50_ms": 61.0,
  "p90_ms": 101.0,
  "p99_ms": 150.0
 },
 "rolagem_historico": {
  "quadros": 154.0,
  "lentos_pct": 87.66,
  "p50_ms": 61.0,
  "p90_ms": 97.0,
  "p99_ms": 129.0
 },
 "memoria_depois_das_abas_kb": 90269,
 "partida_fria_com_municipio_ms": 855,
 "monkey": {
  "eventos": 3000,
  "falhas": 0,
  "anrs": 0
 }
}
```

## Acessibilidade pela árvore do uiautomator

- **r04_resumo_3**: alvos < 48 dp: 152,50 (166×1 dp), 53,8 (166×1 dp); sem rótulo: nenhum
- **r04_resumo_4**: alvos < 48 dp: 152,50 (166×1 dp), 53,8 (166×1 dp); sem rótulo: nenhum
- **r05_mapa**: alvos < 48 dp: nenhum; sem rótulo: WebView em (45,465)
- **r08_sobre**: alvos < 48 dp: View (339×11 dp); sem rótulo: nenhum
