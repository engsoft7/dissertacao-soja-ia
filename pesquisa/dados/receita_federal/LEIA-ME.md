# Valor da Terra Nua — Receita Federal

Tabela de Valores de Terra Nua (VTN) do **exercício 2026**, publicada pela
Receita Federal em 07/08/2026 e reenviada corrigida em 21/08/2026. Serve de
base de cálculo do Imposto sobre a Propriedade Territorial Rural (ITR) e é
alimentada pelas informações que os municípios encaminham à Receita.

Fonte: <https://www.gov.br/receitafederal/pt-br/canais_atendimento/fale-conosco/cidadao/imovel-rural-cadastros-e-declaracao/valor-da-terra-nua-vtn>

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `tabela_vtn_2026.pdf` | PDF nacional publicado pela Receita Federal, 54 páginas |
| `vtn_2026_para.csv` | Os 20 municípios do Pará presentes na tabela, extraídos do PDF |

## Qual coluna o painel usa

A tabela publica **seis valores por município**, por classe de aptidão agrícola:

```
lavoura aptidão boa · lavoura aptidão regular · lavoura aptidão restrita
pastagem plantada · silvicultura ou pastagem natural · preservação
```

O painel usa **lavoura de aptidão boa**, que é a classe correspondente à soja.
As demais são menores e não descrevem área de lavoura tecnificada — tomar a
média entre classes, ou o valor de pastagem, daria número bem abaixo do real.

## Cobertura

A Receita Federal publica VTN para **13 dos 38 municípios** da base do estudo.
Onde não há valor oficial, o painel informa "não publicado" em vez de estimar.

Sem VTN na tabela de 2026: Abel Figueiredo, Água Azul do Norte, Belterra,
Brejo Grande do Araguaia, Conceição do Araguaia, Curionópolis, Dom Eliseu,
Goianésia do Pará, Ipixuna do Pará, Jacareacanga, Jacundá, Monte Alegre,
Pau D'Arco, Piçarra, Placas, Rondon do Pará, Rurópolis, Santa Maria das
Barreiras, Santarém, São João do Araguaia, Sapucaia, Tailândia, Tomé-Açu,
Tucumã e Uruará.

## Observação sobre a extração

O extrator de texto do PDF perde a letra "X" em alguns nomes ("SÃO FELIX DO
XINGU" sai como "SAO FELI. DO .INGU"). Os dois casos foram corrigidos na
geração do CSV. Os valores numéricos não são afetados.
