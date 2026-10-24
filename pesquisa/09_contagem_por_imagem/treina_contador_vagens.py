# -*- coding: utf-8 -*-
"""
Treina o contador de vagens de soja da Estimativa no campo com a base YOLO POD.

Base: YOLO POD (Xiang et al., 2023, Plant Methods 19, doi:10.1186/s13007-023-00985-4),
redistribuída pelo projeto AgML no Hugging Face (Project-AgML/YOLOPOD_Soyabean_Pod_Counting_Dataset)
sob licença CC BY 4.0: 1.448 fotos de campo, de duas localidades (Chongzhou e
Renshou, China), com 72.709 vagens marcadas por retângulo.

Modelo: contagem por mapa de densidade. Cada vagem vira um ponto (o centro do
retângulo, o mesmo tipo de marca que o produtor faz tocando na foto), o ponto
vira uma pequena gaussiana num mapa oito vezes menor que a imagem, e a rede
aprende a desenhar esse mapa. A soma do mapa é a contagem; os máximos locais
são as vagens, que o app pode mostrar como marcas sugeridas para o produtor
conferir.

A rede é a MobileNetV3-Large do torchvision (licença BSD, pesos do ImageNet)
com uma cabeça leve que junta as escalas 1/8 e 1/16. Não usa a biblioteca
Ultralytics: a licença dela (AGPL-3.0) alcançaria o aplicativo.

Avaliação: separação fixa (semente 42) de 70/15/15 por localidade; o modelo
escolhido é o de menor erro absoluto médio na validação, e o teste só é
tocado no fim. Relata erro absoluto e relativo da contagem, R², viés,
erro por localidade, a referência ingênua (prever a média do treino) e a
localização das vagens (precisão e revocação com casamento um a um).

Roda no GitHub Actions (CPU). Uso:
    python treina_contador_vagens.py --saida saida [--epocas 40] [--minutos 270]
"""
import argparse
import json
import math
import os
import platform
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
from PIL import Image, ImageDraw, ImageEnhance
from scipy.ndimage import gaussian_filter, maximum_filter
from scipy.optimize import linear_sum_assignment

REPO = "Project-AgML/YOLOPOD_Soyabean_Pod_Counting_Dataset"
PASSO = 8          # o mapa de densidade tem 1/8 da resolução da imagem
FATOR = 100.0      # escala do mapa no treino; a contagem é soma / FATOR
MEDIA = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DESVIO = np.array([0.229, 0.224, 0.225], dtype=np.float32)


# ── dados ────────────────────────────────────────────────────────────────────

def baixa_base(pasta: Path):
    from huggingface_hub import HfApi, snapshot_download
    revisao = HfApi().dataset_info(REPO).sha
    raiz = Path(snapshot_download(repo_id=REPO, repo_type="dataset", revision=revisao, local_dir=str(pasta)))
    return raiz, revisao


def le_coco(raiz: Path):
    coco = json.loads((raiz / "annotations.json").read_text())
    por_imagem = {}
    for a in coco["annotations"]:
        x, y, w, h = a["bbox"]
        por_imagem.setdefault(a["image_id"], []).append((x + w / 2, y + h / 2, w, h))
    itens = []
    for im in coco["images"]:
        caminho = None
        for c in (raiz / im["file_name"], raiz / "images" / im["file_name"]):
            if c.exists():
                caminho = c
                break
        if caminho is None:
            continue
        partes = [p.lower() for p in caminho.parts]
        local = "chongzhou" if "chongzhou" in partes else "renshou" if "renshou" in partes else "outro"
        itens.append({"arquivo": caminho, "largura": im["width"], "altura": im["height"],
                      "caixas": por_imagem.get(im["id"], []), "local": local})
    return itens


def estatisticas(itens):
    contagens = np.array([len(i["caixas"]) for i in itens])
    larguras = np.array([i["largura"] for i in itens])
    lados = np.array([max(c[2], c[3]) for i in itens for c in i["caixas"]])
    locais = {}
    for i in itens:
        locais[i["local"]] = locais.get(i["local"], 0) + 1
    e = {
        "imagens": len(itens), "vagens": int(contagens.sum()), "por_local": locais,
        "vagens_por_imagem": {"media": float(contagens.mean()), "mediana": float(np.median(contagens)),
                              "min": int(contagens.min()), "max": int(contagens.max())},
        "largura_imagem_px": {"min": int(larguras.min()), "mediana": float(np.median(larguras)), "max": int(larguras.max())},
        "lado_maior_da_vagem_px": {"p10": float(np.percentile(lados, 10)), "mediana": float(np.median(lados)),
                                   "p90": float(np.percentile(lados, 90))},
    }
    print(json.dumps(e, indent=2, ensure_ascii=False))
    return e


def separa(itens, semente=42):
    rng = random.Random(semente)
    partes = {"treino": [], "validacao": [], "teste": []}
    for local in sorted({i["local"] for i in itens}):
        grupo = sorted([i for i in itens if i["local"] == local], key=lambda i: str(i["arquivo"]))
        rng.shuffle(grupo)
        n = len(grupo)
        a, b = int(round(0.70 * n)), int(round(0.85 * n))
        partes["treino"] += grupo[:a]
        partes["validacao"] += grupo[a:b]
        partes["teste"] += grupo[b:]
    return partes


def carrega(item, lado):
    """Imagem reduzida para o lado maior = lado e os pontos na mesma escala."""
    img = Image.open(item["arquivo"]).convert("RGB")
    esc = lado / max(img.size)
    nova = (max(PASSO, round(img.width * esc)), max(PASSO, round(img.height * esc)))
    img = img.resize(nova, Image.BILINEAR)
    pts = np.array([(c[0] * esc, c[1] * esc) for c in item["caixas"]], dtype=np.float32).reshape(-1, 2)
    return np.asarray(img), pts


def mapa_de_densidade(pts, altura, largura, sigma=1.0):
    """Um por vaga, espalhado bilinearmente no mapa 1/8 e suavizado."""
    h, w = altura // PASSO, largura // PASSO
    d = np.zeros((h, w), dtype=np.float32)
    for x, y in pts:
        gx, gy = x / PASSO - 0.5, y / PASSO - 0.5
        x0, y0 = int(math.floor(gx)), int(math.floor(gy))
        fx, fy = gx - x0, gy - y0
        for dx, dy, peso in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                             (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
            xx, yy = min(max(x0 + dx, 0), w - 1), min(max(y0 + dy, 0), h - 1)
            d[yy, xx] += peso
    return gaussian_filter(d, sigma, mode="constant")


def tensor(img):
    x = (img.astype(np.float32) / 255.0 - MEDIA) / DESVIO
    return torch.from_numpy(x.transpose(2, 0, 1).copy())


class Recortes(torch.utils.data.Dataset):
    """Recortes aleatórios com espelhamento e variação de luz, para o treino."""

    def __init__(self, cache, recorte):
        self.cache, self.recorte = cache, recorte

    def __len__(self):
        return len(self.cache)

    def __getitem__(self, k):
        img, pts = self.cache[k]
        h, w = img.shape[:2]
        r = self.recorte
        if h < r or w < r:  # completa com borda preta
            nova = np.zeros((max(h, r), max(w, r), 3), dtype=np.uint8)
            nova[:h, :w] = img
            img, (h, w) = nova, nova.shape[:2]
        y0, x0 = random.randint(0, h - r), random.randint(0, w - r)
        img = img[y0:y0 + r, x0:x0 + r]
        p = pts - np.array([x0, y0], dtype=np.float32)
        p = p[(p[:, 0] >= 0) & (p[:, 0] < r) & (p[:, 1] >= 0) & (p[:, 1] < r)] if len(p) else p
        if random.random() < 0.5:
            img = img[:, ::-1]
            if len(p):
                p = p.copy(); p[:, 0] = r - 1 - p[:, 0]
        if random.random() < 0.8:  # a foto do celular do produtor não tem a luz da base
            pil = Image.fromarray(np.ascontiguousarray(img))
            pil = ImageEnhance.Brightness(pil).enhance(random.uniform(0.7, 1.3))
            pil = ImageEnhance.Contrast(pil).enhance(random.uniform(0.7, 1.3))
            pil = ImageEnhance.Color(pil).enhance(random.uniform(0.7, 1.3))
            img = np.asarray(pil)
        alvo = mapa_de_densidade(p, r, r) * FATOR
        return tensor(np.ascontiguousarray(img)), torch.from_numpy(alvo)[None]


# ── modelo ───────────────────────────────────────────────────────────────────

class ContadorDeVagens(nn.Module):
    def __init__(self, pesos_imagenet=True):
        super().__init__()
        pesos = torchvision.models.MobileNet_V3_Large_Weights.IMAGENET1K_V2 if pesos_imagenet else None
        f = torchvision.models.mobilenet_v3_large(weights=pesos).features
        self.ate8 = f[:7]      # 40 canais, 1/8
        self.ate16 = f[7:13]   # 112 canais, 1/16
        self.lat8 = nn.Conv2d(40, 64, 1)
        self.lat16 = nn.Conv2d(112, 64, 1)
        self.cabeca = nn.Sequential(
            nn.Conv2d(64, 64, 3, padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(64, 32, 3, padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(32, 1, 1),
        )

    def train(self, modo=True):
        # As normalizações (BatchNorm) do corpo ficam congeladas com as
        # estatísticas do ImageNet: com lotes de 8 recortes elas oscilam no
        # treino, e o modelo que acertava em modo de treino errava tudo em modo
        # de avaliação (conferido com dados sintéticos antes de rodar a base).
        super().train(modo)
        for m in list(self.ate8.modules()) + list(self.ate16.modules()):
            if isinstance(m, nn.BatchNorm2d):
                m.eval()
        return self

    def forward(self, x):
        c8 = self.ate8(x)
        c16 = self.ate16(c8)
        p = self.lat8(c8) + F.interpolate(self.lat16(c16), size=c8.shape[-2:], mode="bilinear", align_corners=False)
        return self.cabeca(p)  # densidade × FATOR; negativos são cortados na inferência


@torch.no_grad()
def prediz(modelo, img):
    """Densidade (1/8) e contagem de uma imagem inteira já reduzida."""
    h, w = img.shape[:2]
    H, W = math.ceil(h / 32) * 32, math.ceil(w / 32) * 32
    x = torch.zeros(1, 3, H, W)
    x[0, :, :h, :w] = tensor(img)
    d = modelo(x)[0, 0].clamp(min=0).numpy() / FATOR
    d = d[: h // PASSO, : w // PASSO]
    return d, float(d.sum())


def picos(d, limiar=0.08):
    """Vagens localizadas: máximos locais do mapa, em pixels da imagem reduzida."""
    m = (d == maximum_filter(d, size=3)) & (d > limiar)
    ys, xs = np.nonzero(m)
    return np.stack([(xs + 0.5) * PASSO, (ys + 0.5) * PASSO], axis=1) if len(xs) else np.zeros((0, 2))


def casa(pred, verd, raio):
    if len(pred) == 0 or len(verd) == 0:
        return 0
    dist = np.linalg.norm(pred[:, None, :] - verd[None, :, :], axis=2)
    linhas, colunas = linear_sum_assignment(dist)
    return int((dist[linhas, colunas] <= raio).sum())


def avalia(modelo, cache, itens, raio, limiar=0.08):
    modelo.eval()
    linhas = []
    acertos = n_pred = n_verd = 0
    for (img, pts), item in zip(cache, itens):
        d, c = prediz(modelo, img)
        pk = picos(d, limiar)
        acertos += casa(pk, pts, raio)
        n_pred += len(pk)
        n_verd += len(pts)
        linhas.append({"arquivo": item["arquivo"].name, "local": item["local"], "verdade": len(pts),
                       "contagem": c, "picos": len(pk)})
    v = np.array([l["verdade"] for l in linhas], dtype=float)
    p = np.array([l["contagem"] for l in linhas], dtype=float)
    e = p - v
    rel = np.abs(e[v > 0]) / v[v > 0]
    sst = ((v - v.mean()) ** 2).sum()
    m = {
        "imagens": len(v), "vagens": int(v.sum()),
        "mae": float(np.abs(e).mean()), "rmse": float(np.sqrt((e ** 2).mean())), "vies": float(e.mean()),
        "erro_relativo_medio": float(rel.mean()), "erro_relativo_mediano": float(np.median(rel)),
        "r2": float(1 - (e ** 2).sum() / sst) if sst > 0 else float("nan"),
        "erro_relativo_do_total": float(abs(p.sum() - v.sum()) / v.sum()),
        "localizacao": {"precisao": acertos / max(n_pred, 1), "revocacao": acertos / max(n_verd, 1),
                        "raio_px": raio, "limiar": limiar},
    }
    return m, linhas


def desenha(img, pts, pk, contagem, destino):
    pil = Image.fromarray(img)
    dr = ImageDraw.Draw(pil)
    for x, y in pts:
        dr.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(0, 220, 0), width=2)
    for x, y in pk:
        dr.line([x - 5, y - 5, x + 5, y + 5], fill=(255, 40, 40), width=2)
        dr.line([x - 5, y + 5, x + 5, y - 5], fill=(255, 40, 40), width=2)
    dr.rectangle([0, 0, 520, 30], fill=(0, 0, 0))
    dr.text((8, 8), f"marcadas: {len(pts)}   contagem do modelo: {contagem:.0f}   (verde: marcadas; vermelho: modelo)",
            fill=(255, 255, 255))
    pil.save(destino, quality=88)


# ── principal ────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="saida")
    ap.add_argument("--dados", default="dados_yolopod")
    ap.add_argument("--lado", type=int, default=768)
    ap.add_argument("--recorte", type=int, default=384)
    ap.add_argument("--lote", type=int, default=8)
    ap.add_argument("--epocas", type=int, default=40)
    ap.add_argument("--minutos", type=float, default=270)
    ap.add_argument("--semente", type=int, default=42)
    args = ap.parse_args()

    inicio = time.time()
    random.seed(args.semente); np.random.seed(args.semente); torch.manual_seed(args.semente)
    torch.set_num_threads(os.cpu_count() or 4)
    saida = Path(args.saida); (saida / "exemplos").mkdir(parents=True, exist_ok=True)

    raiz, revisao = baixa_base(Path(args.dados))
    itens = le_coco(raiz)
    est = estatisticas(itens)
    partes = separa(itens, args.semente)
    print({k: len(v) for k, v in partes.items()})

    escala_vagem = est["lado_maior_da_vagem_px"]["mediana"] * args.lado / est["largura_imagem_px"]["mediana"]
    raio = max(8.0, 0.6 * escala_vagem)
    print(f"vagem mediana na escala de treino: {escala_vagem:.1f} px; raio de casamento {raio:.1f} px")

    cache = {k: [carrega(i, args.lado) for i in v] for k, v in partes.items()}
    print(f"imagens carregadas em {time.time() - inicio:.0f} s")

    modelo = ContadorDeVagens()
    cabeca = [p for n, p in modelo.named_parameters() if not n.startswith("ate")]
    corpo = [p for n, p in modelo.named_parameters() if n.startswith("ate")]
    otim = torch.optim.AdamW([{"params": corpo, "lr": 3e-4}, {"params": cabeca, "lr": 1e-3}], weight_decay=1e-4)
    agenda = torch.optim.lr_scheduler.CosineAnnealingLR(otim, T_max=args.epocas)
    carregador = torch.utils.data.DataLoader(Recortes(cache["treino"], args.recorte), batch_size=args.lote,
                                             shuffle=True, num_workers=0, drop_last=True)

    melhor, historico = float("inf"), []
    for epoca in range(1, args.epocas + 1):
        t0 = time.time()
        modelo.train()
        perdas = []
        for x, alvo in carregador:
            pred = modelo(x)
            perda = F.mse_loss(pred, alvo) + 0.01 * F.l1_loss(pred.sum((1, 2, 3)), alvo.sum((1, 2, 3)))
            otim.zero_grad()
            perda.backward()
            otim.step()
            perdas.append(perda.item())
        agenda.step()
        mv, _ = avalia(modelo, cache["validacao"], partes["validacao"], raio)
        historico.append({"epoca": epoca, "perda": float(np.mean(perdas)), "val_mae": mv["mae"],
                          "val_erro_relativo": mv["erro_relativo_medio"], "segundos": time.time() - t0})
        print(f"época {epoca:3d}  perda {np.mean(perdas):.4f}  val MAE {mv['mae']:.2f}  "
              f"val erro relativo {mv['erro_relativo_medio']:.1%}  ({time.time() - t0:.0f} s)", flush=True)
        if mv["mae"] < melhor:
            melhor = mv["mae"]
            torch.save(modelo.state_dict(), saida / "contador_vagens.pt")
        if (time.time() - inicio) / 60 > args.minutos:
            print(f"tempo esgotado na época {epoca}")
            break

    modelo.load_state_dict(torch.load(saida / "contador_vagens.pt"))
    # O limiar dos picos é escolhido na validação, nunca no teste.
    melhor_lim, melhor_f1 = 0.08, -1
    for lim in (0.03, 0.05, 0.08, 0.12, 0.16, 0.2):
        mv, _ = avalia(modelo, cache["validacao"], partes["validacao"], raio, lim)
        p, r = mv["localizacao"]["precisao"], mv["localizacao"]["revocacao"]
        f1 = 2 * p * r / (p + r) if p + r else 0
        if f1 > melhor_f1:
            melhor_lim, melhor_f1 = lim, f1
    mval, _ = avalia(modelo, cache["validacao"], partes["validacao"], raio, melhor_lim)
    mtes, linhas = avalia(modelo, cache["teste"], partes["teste"], raio, melhor_lim)

    media_treino = float(np.mean([len(p) for _, p in cache["treino"]]))
    v = np.array([l["verdade"] for l in linhas], dtype=float)
    ingenuo = {"mae": float(np.abs(media_treino - v).mean()),
               "erro_relativo_medio": float((np.abs(media_treino - v[v > 0]) / v[v > 0]).mean())}
    por_local = {}
    for local in sorted({l["local"] for l in linhas}):
        sel = [l for l in linhas if l["local"] == local]
        e = np.array([l["contagem"] - l["verdade"] for l in sel])
        vv = np.array([l["verdade"] for l in sel], dtype=float)
        por_local[local] = {"imagens": len(sel), "mae": float(np.abs(e).mean()),
                            "erro_relativo_medio": float((np.abs(e[vv > 0]) / vv[vv > 0]).mean())}

    # exemplos: os três melhores e os três piores do teste, para ver onde erra
    ordem = sorted(range(len(linhas)), key=lambda k: abs(linhas[k]["contagem"] - linhas[k]["verdade"]))
    for k in ordem[:3] + ordem[-3:]:
        img, pts = cache["teste"][k]
        d, c = prediz(modelo, img)
        desenha(img, pts, picos(d, melhor_lim), c, saida / "exemplos" / f"teste_{k:03d}_{linhas[k]['local']}.jpg")

    # ONNX num arquivo só, conferido contra o PyTorch: é dele que sai a versão
    # para o celular (LiteRT).
    modelo.eval()
    exemplo = torch.zeros(1, 3, 576, 768)
    torch.onnx.export(modelo, exemplo, saida / "contador_vagens.onnx", input_names=["imagem"],
                      output_names=["densidade"], opset_version=17, external_data=False,
                      dynamic_axes={"imagem": {2: "altura", 3: "largura"}, "densidade": {2: "a8", 3: "l8"}})
    try:
        import onnxruntime as ort
        x = torch.randn(1, 3, 576, 768)
        ref = modelo(x).detach().numpy()
        out = ort.InferenceSession(str(saida / "contador_vagens.onnx")).run(None, {"imagem": x.numpy()})[0]
        diferenca_onnx = float(np.abs(out - ref).max())
    except Exception as e:  # sem onnxruntime, o arquivo fica sem conferência
        diferenca_onnx = f"não conferido: {type(e).__name__}"
    print(f"ONNX × PyTorch, maior diferença: {diferenca_onnx}")

    metricas = {
        "base": {"repositorio": REPO, "revisao": revisao, "licenca": "CC BY 4.0",
                 "citacao": "Xiang S, Wang S, Xu M, Wang W, Liu W (2023). YOLO POD: a fast and accurate multi-task "
                            "model for dense Soybean Pod counting. Plant Methods 19:8. doi:10.1186/s13007-023-00985-4"},
        "estatisticas": est, "separacao": {k: len(v) for k, v in partes.items()},
        "configuracao": vars(args) | {"passo": PASSO, "fator": FATOR, "raio_px": raio, "limiar_picos": melhor_lim},
        "validacao": mval, "teste": mtes, "teste_por_local": por_local,
        "referencia_ingenua_teste": ingenuo | {"media_do_treino": media_treino},
        "historico": historico, "onnx_diferenca_maxima": diferenca_onnx,
        "ambiente": {"python": platform.python_version(), "torch": torch.__version__,
                     "torchvision": torchvision.__version__, "numpy": np.__version__},
        "minutos": (time.time() - inicio) / 60,
    }
    (saida / "metricas.json").write_text(json.dumps(metricas, indent=2, ensure_ascii=False))
    (saida / "teste_por_imagem.json").write_text(json.dumps(linhas, indent=1, ensure_ascii=False))
    print(json.dumps({k: metricas[k] for k in ("validacao", "teste", "teste_por_local", "referencia_ingenua_teste")},
                     indent=2, ensure_ascii=False))

    lt = mtes["localizacao"]
    (saida / "LEIAME.md").write_text(f"""# Contador de vagens de soja (YOLO POD)

Gerado por `pesquisa/09_contagem_por_imagem/treina_contador_vagens.py` em {time.strftime('%d/%m/%Y')}.

## Base

YOLO POD: {est['imagens']} fotos de campo e {est['vagens']} vagens marcadas, de Chongzhou e Renshou (China).
Xiang S, Wang S, Xu M, Wang W, Liu W (2023). YOLO POD: a fast and accurate multi-task model for dense
Soybean Pod counting. *Plant Methods* 19:8. doi:10.1186/s13007-023-00985-4. Redistribuída pelo projeto
AgML no Hugging Face ({REPO}, revisão `{revisao}`), licença CC BY 4.0. O modelo é obra derivada e
mantém a atribuição.

## Resultado no teste ({mtes['imagens']} fotos que o treino não viu)

| Métrica | Modelo | Prever a média do treino |
|---|---|---|
| Erro absoluto médio (vagens por foto) | {mtes['mae']:.1f} | {ingenuo['mae']:.1f} |
| Erro relativo médio | {mtes['erro_relativo_medio']:.1%} | {ingenuo['erro_relativo_medio']:.1%} |
| R² | {mtes['r2']:.3f} | 0 |
| Viés (vagens por foto) | {mtes['vies']:+.1f} | |
| Erro na soma de todas as fotos | {mtes['erro_relativo_do_total']:.1%} | |
| Vagens localizadas: precisão / revocação | {lt['precisao']:.1%} / {lt['revocacao']:.1%} | |

Por localidade: {json.dumps(por_local, ensure_ascii=False)}

## Limites

As fotos da base são de plantas em pé no campo, na China. As do aplicativo são de plantas
arrancadas sobre pano, no Pará. Este erro vale para a base; o erro nas fotos do aplicativo
precisa ser medido com fotos marcadas pelo produtor antes de o modelo entrar no app.

## Arquivos

- `contador_vagens.pt`: pesos (PyTorch); `contador_vagens.onnx`: o mesmo modelo em ONNX
  (entrada `imagem` 1×3×H×W normalizada pelo ImageNet, H e W múltiplos de 32; saída `densidade`
  1×1×H/8×W/8 multiplicada por {FATOR:.0f}: contagem = soma ÷ {FATOR:.0f}).
- `metricas.json`, `teste_por_imagem.json`, `exemplos/` (três melhores e três piores fotos do teste).
""", encoding="utf-8")

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("## Contador de vagens (YOLO POD, teste)\n\n| Métrica | Modelo | Média do treino |\n|---|---|---|\n")
            f.write(f"| Erro absoluto médio (vagens/imagem) | {mtes['mae']:.2f} | {ingenuo['mae']:.2f} |\n")
            f.write(f"| Erro relativo médio | {mtes['erro_relativo_medio']:.1%} | {ingenuo['erro_relativo_medio']:.1%} |\n")
            f.write(f"| R² | {mtes['r2']:.3f} | 0 |\n| Viés (vagens/imagem) | {mtes['vies']:+.2f} | |\n")
            f.write(f"| Erro no total do teste | {mtes['erro_relativo_do_total']:.1%} | |\n")
            f.write(f"| Localização: precisão / revocação | {mtes['localizacao']['precisao']:.1%} / "
                    f"{mtes['localizacao']['revocacao']:.1%} | |\n")


if __name__ == "__main__":
    main()
