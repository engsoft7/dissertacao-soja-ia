# Contador de vagens de soja (YOLO POD)

Gerado por `pesquisa/09_contagem_por_imagem/treina_contador_vagens.py` em 25/10/2026:
lado 1024 px, mapa 1/4, sigma 6 px, 36 épocas.

## Base

YOLO POD: 1448 fotos de campo e 72709 vagens marcadas, de Chongzhou e Renshou (China).
Xiang S, Wang S, Xu M, Wang W, Liu W (2023). YOLO POD: a fast and accurate multi-task model for dense
Soybean Pod counting. *Plant Methods* 19:8. doi:10.1186/s13007-023-00985-4. Redistribuída pelo projeto
AgML no Hugging Face (Project-AgML/YOLOPOD_Soyabean_Pod_Counting_Dataset, revisão `4160b98b1cec6343313d611455cbfe396ef0ef41`), licença CC BY 4.0. O modelo é obra derivada e
mantém a atribuição.

## Resultado no teste (218 fotos que o treino não viu)

| Métrica | Modelo | Prever a média do treino |
|---|---|---|
| Erro absoluto médio (vagens por foto) | 3.5 | 20.8 |
| Erro relativo médio | 8.3% | 54.1% |
| R² | 0.955 | 0 |
| Viés (vagens por foto) | -0.7 | |
| Erro na soma de todas as fotos | 1.5% | |
| Vagens localizadas: precisão / revocação | 84.3% / 61.3% | |

Por localidade: {"chongzhou": {"imagens": 86, "mae": 2.608196169831032, "erro_relativo_medio": 0.1064208621271161}, "renshou": {"imagens": 132, "mae": 4.160060477979256, "erro_relativo_medio": 0.06765212943909038}}

## Limites

As fotos da base são de plantas arrancadas e deitadas sobre pano escuro, como pede a tela do
aplicativo, mas de cultivares e câmeras da China. Este erro vale para a base; o erro nas fotos do aplicativo
precisa ser medido com fotos marcadas pelo produtor antes de o modelo entrar no app.

## Arquivos

- `contador_vagens.pt`: pesos (PyTorch); `contador_vagens.onnx`: o mesmo modelo em ONNX
  (entrada `imagem` 1×3×H×W normalizada pelo ImageNet, H e W múltiplos de 32; saída `densidade`
  1×1×H/4×W/4 multiplicada por 100: contagem = soma ÷ 100).
- `metricas.json`, `teste_por_imagem.json`, `exemplos/` (três melhores e três piores fotos do teste).
