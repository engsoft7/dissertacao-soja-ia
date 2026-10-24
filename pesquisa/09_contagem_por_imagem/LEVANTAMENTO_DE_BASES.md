# Bases de imagens para a contagem automática de vagens e plantas

Levantamento de 24/10/2026 para a Estimativa no campo do aplicativo. Interessa
saber quais bases podem treinar o contador **sem pedir autorização**: licença
aberta que permita uso num aplicativo gratuito, com citação.

Como foi feito:

- `confere_bases_de_imagens.py`: licença e conteúdo das bases conhecidas
  (GitHub, Hugging Face, Kaggle, Zenodo, Figshare, Wikimedia Commons).
- `varre_literatura.py`: 67 trabalhos do OpenAlex (2015 em diante) sobre contar
  vagens, grãos ou plantas de soja por imagem, com a declaração de
  disponibilidade de dados lida no texto completo aberto.
- `confere_inacessiveis.py`: os 37 trabalhos cujo texto não abriu na varredura
  (MDPI, Elsevier, Wiley, IEEE). 20 foram lidos pela CDN de PDFs da MDPI e pelo
  PDF aberto. Os outros 17 foram conferidos por busca na web, e nenhum deles
  traz base publicada de vagens ou plantas no campo.

## Bases que podem entrar no treino com citação

| Base | Conteúdo | Licença | Uso |
|---|---|---|---|
| YOLO POD (Xiang et al., 2023, *Plant Methods*), cópia do AgML no Hugging Face | 1.448 fotos de campo, 72.709 vagens (retângulos) | CC BY 4.0 | treino do contador de vagens (`treina_contador_vagens.py`) |
| GrowingSoy (Steinmetz et al., 2024) | ~1.000 imagens de lavoura, contorno de cada planta de soja e das daninhas | MIT | candidata para contar plantas na linha |
| MTL-PlotCounter (Xue et al., 2025, *Remote Sensing*) | 54 parcelas por drone, 5.932 plântulas | Apache-2.0 | estande por drone (etapa futura) |
| SP-YOLO (Zenodo 18898644, 2026) | código e uma amostra da base | CC BY 4.0 | amostra pequena; complemento |
| Wikimedia Commons | 47 fotos de vagens em close, sem marcação | CC BY 2.0 | só ilustração |

## Bases publicadas, mas sem licença aberta (dependem de autorização)

| Trabalho | Onde estão os dados | Situação |
|---|---|---|
| SoybeanNet (Li et al., 2024, *Comput. Electron. Agric.*) | Kaggle `jiajiali/uav-based-soybean-pod-images` | licença "Unknown"; código MIT |
| Jiang Guo (2026) | GitHub `JiangGuo921/soybean-pod-dataset` | sem licença |
| PodNet (*Plant Phenomics*, 2025) | formulário, citado em `Boatsure/PodNet` | repositório Apache-2.0, dados por formulário |
| P2PNet-Soy (Zhao et al., 2023) | formulário | sem licença |
| Vagens em campo e laboratório (Jiang et al., ECCVw 2024) | Google Drive, a partir de `SkyCol/soybean_phenotyping_platform` | sem licença; reúne imagens da P2PNet-Soy e da YOLO POD |
| Contagem com câmera de profundidade (*Sensors*, 2023) | GitHub `jithin8mathew/...` | sem licença |
| Flores e vagens (*Frontiers*, 2022) | Baidu Pan com senha | sem licença |
| DEKR-SPrior (*Plant Phenomics*, 2024) | código no GitHub; dados por contato | sem licença |

## Não publicadas (sob pedido, não disponíveis ou sem declaração)

- **Contagem de vagens.** Estas bases são as maiores da área, e um pedido aos autores pode valer a pena.
  - Por pedido:
    - SPCN e BeanCount-1500, com 24.684 imagens e 987 mil vagens; o repositório diz "code will be available soon";
    - SmartPod;
    - DARFP (vagens aglomeradas);
    - PodFormer;
    - YOLOv8n-POD.
  - Não disponíveis:
    - YOLOv8-VEW;
    - YOLOv5 de floração e vagem;
    - YOLOv5 dinâmico.
  - Sem declaração ou sem nada publicado:
    - FEI-YOLO;
    - vagens de soja-hortaliça;
    - TCNN-seed;
    - EdgeSoybeanNet;
    - SoybeanNet leve (SHS);
    - BeanpodNet;
    - vagens e ramos (*Plant Breeding*);
    - vagens sintéticas (CVPRW);
    - ISCF.
- **Plântulas e estande.**
  - Por pedido:
    - SSDNet;
    - plântulas densas por drone.
  - Não disponível: GD-YOLOv10n-Seg.
  - Dados contidos no artigo: YOLOv11-Seg-SSC.
  - Nada publicado:
    - FEL-YoloV8;
    - contagem por drone (*Agronomy Journal*, 2026);
    - contagem por drone (SSRN).
- **Fora do tema** (sementes em laboratório ou máquina):
  - grãos em queda;
  - SMPTS (código no CodeOcean, MIT);
  - VGG-Two;
  - VGG-T;
  - grãos colhidos;
  - sementes danificadas;
  - plântulas de laboratório (*Journal of Seed Science*);
  - dosador de sementes.

## Conclusão

Para vagens, a YOLO POD é a única base pública com licença aberta. Para
plantas na linha, a GrowingSoy. As demais dependem de autorização. Em todos os
casos, o erro nas fotos do aplicativo, de plantas arrancadas sobre pano no
Pará, só se mede com fotos marcadas pelo produtor, que o app já guarda e
exporta.
