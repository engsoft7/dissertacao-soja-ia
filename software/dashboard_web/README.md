# Painel de estimativa da produtividade da soja — Pará

Produto técnico da dissertação *Aplicação da Inteligência Artificial na previsão
da produtividade da soja* (PPCA/UFPA).

## Acessar

Versão publicada: **<https://soja-para.streamlit.app>**

Para executar localmente:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## O que o painel faz

- Estima a produtividade municipal da soja para a próxima safra, **sempre com a
  margem de erro** (± 416 kg/ha, ou 13,9% da média).
- Exibe os valores em **kg/ha** ou em **sacas de 60 kg por hectare (sc/ha)**,
  à escolha do usuário; a conversão é apenas de exibição, o modelo opera em kg/ha.
- Permite **simular cenários climáticos** (chuva e temperatura da safra) e ver o
  efeito sobre a estimativa — que é quase nulo, demonstrando na prática o achado
  central da dissertação: a produtividade oficial pouco reflete o clima
  observado, e o painel explica isso ao usuário em vez de esconder.
- Mostra a **evolução da área de soja** do município (máscara MapBiomas) e
  oferece **download em CSV** da série do município e da base completa.
- Exibe um **mapa do Pará** com o contorno do estado (IBGE) e os **principais
  rios** (Natural Earth): cada município produtor é um ponto **dimensionado pela
  área plantada** e **colorido pela produtividade média** recente, com o
  selecionado destacado. O mapa é responsivo (bom no celular) e estático — não
  arrasta nem dá zoom; a seleção do município é feita pelo menu.
- Usa a **grafia oficial acentuada** dos nomes de município (IBGE) — a base
  bruta vem do GAUL, sem acentos.
- Traz um **panorama ordenável dos 38 municípios** (produtividade recente, área,
  repetição na PAM) e um bloco **"Sobre este painel"** com metodologia, autoria,
  DOI e instrução de citação.
- Estima a **produção total** (toneladas e sacas = produtividade × área MapBiomas)
  e faz uma **análise econômica** (receita, custo e **margem por hectare**). O
  preço parte do preço recebido pelo produtor no levantamento da CONAB
  (R$ 105,09/saca), que é preço de porteira e vem da mesma praça de onde sai o
  custo. Esse valor é o **menor dos 13 levantamentos** da praça entre março de
  2023 e março de 2026 (mediana R$ 116,91, máximo R$ 146,35), e a interface diz
  isso: o padrão é um cenário conservador, não uma previsão de preço, e o campo
  é editável. Preço, custo, praça, data e essa frase não são literais no
  código — saem de `pesquisa/dados/conab/levantamento_atual.json`, que o
  workflow mensal atualiza; quando a CONAB publica levantamento novo, as
  legendas acompanham sozinhas. E o painel calcula a idade do levantamento a
  cada carregamento: passada a cadência da CONAB, avisa em tela que o preço
  pode estar desatualizado, em vez de exibi-lo calado. A cotação física em Paranaguá (Notícias Agrícolas) e o futuro de
  Chicago são exibidos apenas como comparação: são preços de porto e de bolsa,
  acima do que se recebe no Pará, e não há série pública de preço ao produtor
  paraense. O custo vem do levantamento da CONAB para Pedro Afonso (TO), de
  março de 2026, porque o Pará não integra o MATOPIBA e não tem custo
  publicado; é um custo por hectare fixo, preso à produtividade de referência
  de 48 sc/ha, que não cresce junto com a produtividade projetada. Preço e
  custo são editáveis, porque entram na margem. O Valor da
  Terra Nua vem da tabela da Receita Federal de 2026, classe lavoura de aptidão
  boa, disponível para 13 dos 38 municípios; é exibido como nota de contexto e
  não como campo editável, por ser referência fiscal (base de cálculo do ITR) e
  não preço de mercado — não entra na margem.
- Mostra a série histórica oficial (PAM/IBGE), destacando em vermelho as safras
  cuja produtividade repete exatamente o valor do ano anterior.
- Alerta quando a série de um município apresenta repetição acima da média
  estadual (40,1%), sinalizando menor confiabilidade do dado de referência.

## O que o painel deliberadamente NÃO faz

**Não projeta produtividade para dez anos à frente.** Uma projeção decenal exigiria
prever o clima de cada safra futura, o que os dados não permitem. Extrapolações
desse tipo, comuns em painéis agrícolas, produzem uma reta de crescimento de área
multiplicada por uma média fixa de produtividade — não uma previsão.

**Não usa amostragem aleatória para validar.** Como cada município aparece em
várias safras, um `train_test_split` aleatório coloca o mesmo município no treino
e no teste; o modelo memoriza sua média histórica e a métrica resultante é
otimista e inválida. Nos dados desta base, o split aleatório eleva o R² de −0,02
para 0,12 sem qualquer ganho real de capacidade preditiva. A validação aqui é
**leave-one-year-out**: cada safra é prevista por um modelo treinado sem ela.

## Limitação central

As variáveis climáticas e espectrais **não superam** o modelo de referência
(histórico municipal + tendência): R² de 0,216 em ambos os casos. A causa está
documentada na seção 6.4 da dissertação — cerca de 40% das transições interanuais
da PAM nos municípios paraenses são valores repetidos, e nenhum modelo recupera
variação que não existe na variável-alvo.

Por isso o painel é honesto quanto ao que entrega: uma estimativa útil, com
incerteza declarada, e um diagnóstico da qualidade do dado que a sustenta.

## Estrutura

```
model.py   núcleo: baseline, correção climática, validação temporal, diagnóstico da PAM
app.py     interface Streamlit
```

Para atualizar a base com a safra corrente, use as rotinas de `../01_coleta_dados/`.
