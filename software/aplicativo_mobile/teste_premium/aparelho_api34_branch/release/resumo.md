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
 "apk_mb": 28.0,
 "partida_fria_primeira_ms": 1176,
 "partida_fria_sem_municipio_ms": 1028.5,
 "dados_do_municipio_s": 5.3,
 "memoria_resumo_kb": 38277,
 "rolagem_resumo": {
  "quadros": 200.0,
  "lentos_pct": 92.0,
  "p50_ms": 57.0,
  "p90_ms": 105.0,
  "p99_ms": 150.0
 },
 "rolagem_historico": {
  "quadros": 156.0,
  "lentos_pct": 91.03,
  "p50_ms": 73.0,
  "p90_ms": 113.0,
  "p99_ms": 150.0
 },
 "memoria_depois_das_abas_kb": 89714,
 "partida_fria_com_municipio_ms": 1189,
 "monkey": {
  "eventos": 3000,
  "falhas": 0,
  "anrs": 0
 }
}
```

## Acessibilidade pela árvore do uiautomator

- **r03_resumo**: alvos < 48 dp: View (379×36 dp); sem rótulo: nenhum
- **r04_resumo_1**: alvos < 48 dp: View (379×40 dp); sem rótulo: nenhum
- **r05_mapa**: alvos < 48 dp: nenhum; sem rótulo: WebView em (45,530)
- **r09_estimativa_no_campo**: alvos < 48 dp: View (347×11 dp); sem rótulo: View em (84,2097)
- **r10_tempo**: alvos < 48 dp: View (102×13 dp); sem rótulo: View em (123,2094)
- **r14_escuro_resumo**: alvos < 48 dp: View (379×36 dp); sem rótulo: nenhum
- **r18_sem_internet**: alvos < 48 dp: View (154×44 dp), View (167×44 dp); sem rótulo: nenhum
