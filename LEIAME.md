# Contador de vagens de soja (YOLO POD)

Gerado por `pesquisa/09_contagem_por_imagem/treina_contador_vagens.py` em 24/10/2026.

## Base

YOLO POD: 1448 fotos de campo e 72709 vagens marcadas, de Chongzhou e Renshou (China).
Xiang S, Wang S, Xu M, Wang W, Liu W (2023). YOLO POD: a fast and accurate multi-task model for dense
Soybean Pod counting. *Plant Methods* 19:8. doi:10.1186/s13007-023-00985-4. Redistribuída pelo projeto
AgML no Hugging Face (Project-AgML/YOLOPOD_Soyabean_Pod_Counting_Dataset, revisão `4160b98b1cec6343313d611455cbfe396ef0ef41`), licença CC BY 4.0. O modelo é obra derivada e
mantém a atribuição.

## Resultado no teste (218 fotos que o treino não viu)

| Métrica | Modelo | Prever a média do treino |
|---|---|---|
| Erro absoluto médio (vagens por foto) | 2.8 | 20.8 |
| Erro relativo médio | 5.6% | 54.1% |
| R² | 0.969 | 0 |
| Viés (vagens por foto) | -0.4 | |
| Erro na soma de todas as fotos | 0.7% | |
| Vagens localizadas: precisão / revocação | 99.1% / 40.8% | |

Por localidade: {"chongzhou": {"imagens": 86, "mae": 1.6887766039648722, "erro_relativo_medio": 0.05483201283802292}, "renshou": {"imagens": 132, "mae": 3.5516323898777817, "erro_relativo_medio": 0.05691973430626347}}

## Limites

As fotos da base são de plantas em pé no campo, na China. As do aplicativo são de plantas
arrancadas sobre pano, no Pará. Este erro vale para a base; o erro nas fotos do aplicativo
precisa ser medido com fotos marcadas pelo produtor antes de o modelo entrar no app.

## Arquivos

- `contador_vagens.pt`: pesos (PyTorch); `contador_vagens.onnx`: o mesmo modelo em ONNX
  (entrada `imagem` 1×3×H×W normalizada pelo ImageNet, H e W múltiplos de 32; saída `densidade`
  1×1×H/8×W/8 multiplicada por 100: contagem = soma ÷ 100).
- `metricas.json`, `teste_por_imagem.json`, `exemplos/` (três melhores e três piores fotos do teste).
