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
| tela pequena: Resumo abre | **falha** |  |
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
 "apk_mb": 28.0,
 "partida_fria_primeira_ms": 1181,
 "partida_fria_sem_municipio_ms": 1045.5,
 "dados_do_municipio_s": 5.3,
 "memoria_resumo_kb": 41609,
 "rolagem_resumo": {
  "quadros": 207.0,
  "lentos_pct": 84.54,
  "p50_ms": 53.0,
  "p90_ms": 101.0,
  "p99_ms": 133.0
 },
 "rolagem_historico": {
  "quadros": 167.0,
  "lentos_pct": 85.63,
  "p50_ms": 65.0,
  "p90_ms": 97.0,
  "p99_ms": 129.0
 },
 "memoria_depois_das_abas_kb": 88813,
 "partida_fria_com_municipio_ms": 962,
 "monkey": {
  "eventos": 3000,
  "falhas": 0,
  "anrs": 0
 }
}
```

## Acessibilidade pela árvore do uiautomator

- **r04_resumo_1**: alvos < 48 dp: 5277,12 (166×42 dp), View (379×30 dp); sem rótulo: nenhum
- **r04_resumo_3**: alvos < 48 dp: 152,50 (166×38 dp), 53,8 (166×38 dp); sem rótulo: nenhum
- **r04_resumo_4**: alvos < 48 dp: 152,50 (166×1 dp), 53,8 (166×1 dp); sem rótulo: nenhum
- **r05_mapa**: alvos < 48 dp: nenhum; sem rótulo: WebView em (45,465)
- **r08_sobre**: alvos < 48 dp: View (339×11 dp); sem rótulo: nenhum
- **r09_estimativa_no_campo**: alvos < 48 dp: View (347×36 dp); sem rótulo: nenhum
- **r10_tempo**: alvos < 48 dp: View (102×37 dp); sem rótulo: nenhum
- **r12_fonte_200_rolado**: alvos < 48 dp: View (120×14 dp), View (252×14 dp); sem rótulo: nenhum
