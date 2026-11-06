# Auditoria do aplicativo 2.7.3: 16 KB e números

Primeira rodada em 06/11/2026 (auditoria-app.yml, run 42263602506), sobre a
API em produção e o AAB/APK da v2.4.18. A segunda e a terceira rodadas, no fim
deste relatório, conferem a correção na branch e em produção; as tabelas
completas desta pasta, `fontes.md` (API × fontes) e `telas.csv` (o que cada
tela mostra, município a município), são da terceira.

## Páginas de 16 KB (Android 15 e a Play Store): conforme

As 8 bibliotecas nativas do AAB (contador de vagens, `libtensorflowlite_jni.so`,
e `libandroidx.graphics.path.so`, nas 4 arquiteturas) têm os segmentos LOAD
alinhados a 16 KB (0x4000). No APK arm64, estão guardadas sem compressão e
começam em múltiplos de 16 KB.

## API × fontes

| Grupo | Resultado |
|---|---|
| Praças do Pará (Agrolink) | Barcarena, Redenção e Paragominas iguais à fonte, valor e data |
| Chicago (CBOT) | R$ 143,90 no app, R$ 143,93 no Yahoo (−0,02%); conversão da API exata |
| Média do Pará estimada | Chicago + base do mês, exata |
| Custo e preço (CONAB) | os 5 campos iguais ao levantamento MAR-2026; levantamento igual à série do portal; componentes somam o custo |
| Avisos (INMET) | 6 municípios, mesmos avisos que o INMET lista pelo geocódigo |
| Produtividade (IBGE) | as 451 safras da base iguais ao SIDRA; **mais de 40 safras publicadas pelo IBGE ausentes do app** |

## Telas × telas (código do app, 38 municípios)

36 municípios sem divergência: Resumo, Viabilidade, Histórico e Estimativa no
campo mostram a mesma safra, o mesmo preço, o mesmo custo e o mesmo lucro, e o
ponto de equilíbrio combina com o sinal do lucro.

## Defeitos

| Gravidade | Defeito | Onde |
|---|---|---|
| Alta | Pau D'Arco mostra "Produtividade esperada na safra **2020**" e "Safra **2017**, IBGE"; o IBGE publicou até 2025 (3.700 kg/ha em 2025). Os cartões de 2018 a 2020 dizem "IBGE ainda não divulgou", e 2020 foi divulgado | API (`/api/previsao`) |
| Média | São João do Araguaia mostra a safra 2026 no lugar de 2027 e "Safra 2023, IBGE" | API |
| Média | Safras publicadas pelo IBGE faltam no histórico do app: pelo menos 40 em 8 municípios (o relatório desta rodada lista só as 40 primeiras), como Altamira de 2001 a 2010, Marabá em 9 safras e Pau D'Arco de 2020 a 2025. Mais 3 municípios têm lacunas longas no meio da série, a confrontar com o IBGE na próxima rodada: Monte Alegre (2006 a 2023), Goianésia do Pará (2018 a 2023) e Água Azul do Norte (2009 a 2016) | base do produto |

**Causa.** A base do produto só guarda as safras em que a máscara de soja do
MapBiomas acha soja no município, porque o modelo precisa das variáveis de
satélite. O IBGE publica a produtividade mesmo quando o satélite não acha. A
API projeta as três safras seguintes à **última safra do município na base**, e
não à última safra da base.

**Correção** (nesta branch; a API em produção muda com o merge na main):

1. A API projeta as três safras seguintes à última safra publicada (hoje 2025),
   a mesma para todos os municípios. O painel faz o mesmo. Corrige os dois
   primeiros defeitos: os 38 municípios passam a ter projeção de 2026 a 2028, e
   o Resumo mostra a safra 2027.
2. A API completa o histórico com as safras do IBGE que a base não tem, lidas
   de `pesquisa/dados/pam_soja_para.csv` (521 safras de 38 municípios; as 451 da
   base têm o mesmo valor), marcadas `fora_do_modelo`. Pau D'Arco passa a mostrar
   a safra 2025 do IBGE, 3.700 kg/ha. A base do modelo e as métricas não mudam.
3. `atualiza_pam.py` regrava esse arquivo a cada execução mensal, e a
   atualização mensal (`atualiza-dados.yml`, dia 15) voltou a ser agendada.

As lacunas que continuam no histórico são safras que o IBGE também não publicou
(Goianésia do Pará de 2018 a 2023, por exemplo).

## Segunda rodada, com a correção (API da branch)

Run 42266503173, mesmo dia, com a API desta branch rodando no job. Os arquivos
`fontes.md`, `fontes.json`, `telas.csv` e `telas_falhas.txt` desta pasta
foram desta rodada até a terceira.

| Grupo | Resultado |
|---|---|
| Produtividade (IBGE) | as 521 safras do app iguais ao SIDRA; nenhuma safra publicada ausente |
| Telas × telas | nenhuma divergência nos 38 municípios; todos na safra 2027 |
| Pau D'Arco | safra 2027, 3.227 kg/ha; última do IBGE 2025, 3.700 kg/ha |
| São João do Araguaia | safra 2027; última do IBGE 2023 (o IBGE não publicou 2024 nem 2025) |
| Praças, Chicago, CONAB, INMET | iguais às fontes, como na primeira rodada |

## Terceira rodada, em produção

Run 42270355684, depois do merge do PR #180 e do deploy no Render: as 521
safras do app iguais ao SIDRA, nenhuma divergência entre telas nos 38
municípios, Pau D'Arco na safra 2027 e com a safra 2025 do IBGE. Os arquivos
desta pasta são agora desta rodada.

Para conferir de novo: aba Actions > "Auditoria do aplicativo" > Run workflow (com "API da
branch" marcado antes do merge), ou `[auditoria]` / `[auditoria-branch]` no
commit.
