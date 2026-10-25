# -*- coding: utf-8 -*-
"""
Converte o contador de vagens para o celular (LiteRT) e confere a conversão
nas fotos de teste da YOLO POD, pelo mesmo caminho que a foto faz no app.

O app usa dois modelos treinados por treina_contador_vagens.py:
  v1 (mapa 1/8, lado 768): o número de vagens, com o menor erro de contagem;
  v2 (mapa 1/4, lado 1024): as marcas sugeridas, que localizam mais vagens.

No celular a entrada tem tamanho fixo: um quadro deitado (largura = lado,
altura = 3/4 do lado). O app reduz a foto para caber no quadro, completa o
resto com zeros (o cinza médio do ImageNet, depois da normalização), e foto
em pé é girada 90 graus no sentido horário antes, para ficar deitada como as
fotos da base. Esta conferência repete exatamente isso, inclusive a redução
por metades sucessivas que o app faz, e compara com o número de vagens marcado
na base. Repete também com a foto de cabeça para baixo, para medir quanto a
contagem depende da posição em que a planta foi fotografada.

Uso (Actions, que alcança o Hugging Face):
    python converte_para_celular.py --modelos <branch modelo-contagem-vagens> --saida saida
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from scipy.ndimage import maximum_filter
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
import treina_contador_vagens as treino  # noqa: E402

MEDIA, DESVIO, FATOR = treino.MEDIA, treino.DESVIO, treino.FATOR

# Versão publicada, papel no app, mapa (passo) e lado maior da imagem no treino.
MODELOS = {
    "v1": {"papel": "contagem", "passo": 8, "lado": 768},
    "v2": {"papel": "marcas", "passo": 4, "lado": 1024},
}


def quadro(lado):
    """Largura e altura da entrada fixa no celular."""
    return lado, lado * 3 // 4


def carrega_modelo(pasta: Path, versao: str):
    cfg = MODELOS[versao]
    modelo = treino.ContadorDeVagens(pesos_imagenet=False, passo=cfg["passo"])
    pesos = torch.load(pasta / versao / "contador_vagens.pt", map_location="cpu")
    # A v1 foi treinada antes de a rede ganhar a escala 1/4: os quatro
    # primeiros blocos se chamavam ate8.0 a ate8.3. Os pesos são os mesmos.
    if not any(k.startswith("ate4.") for k in pesos):
        pesos = {(f"ate4.{k[5:]}" if k.startswith("ate8.") and int(k.split(".")[1]) < 4 else k): v
                 for k, v in pesos.items()}
    resultado = modelo.load_state_dict(pesos, strict=False)
    sobra = [k for k in resultado.missing_keys if not (cfg["passo"] == 8 and k.startswith("lat4."))]
    if sobra or resultado.unexpected_keys:
        raise SystemExit(f"{versao}: pesos não casam com a rede: {sobra} {resultado.unexpected_keys}")
    return modelo.eval()


def converte(modelo, versao, destino: Path):
    import litert_torch
    w, h = quadro(MODELOS[versao]["lado"])
    exemplo = torch.randn(1, 3, h, w)
    convertido = litert_torch.convert(modelo, (exemplo,))
    arquivo = destino / f"contador_vagens_{versao}.tflite"
    convertido.export(str(arquivo))
    with torch.no_grad():
        ref = modelo(exemplo).numpy()
    dif = float(np.abs(np.asarray(convertido(exemplo)) - ref).max())
    return arquivo, dif


# ── o caminho da foto no app (ContadorVagens.kt) ─────────────────────────────

def como_no_celular(img: Image.Image, lado_max=2048):
    """carregaFoto: o BitmapFactory lê a foto com inSampleSize, a maior
    potência de 2 que deixa o lado maior em até 2048 px."""
    amostra = 1
    while max(img.size) / amostra > lado_max:
        amostra *= 2
    return img.reduce(amostra) if amostra > 1 else img


def prepara(img: Image.Image, versao):
    """Gira, reduz e enquadra. Devolve a entrada (1×3×H×W), o tamanho útil e se girou."""
    cfg = MODELOS[versao]
    qw, qh = quadro(cfg["lado"])
    girou = img.height > img.width
    if girou:
        img = img.transpose(Image.Transpose.ROTATE_270)  # 90 graus no sentido horário
    esc = min(qw / img.width, qh / img.height)
    nw = min(qw, max(cfg["passo"], round(img.width * esc)))
    nh = min(qh, max(cfg["passo"], round(img.height * esc)))
    # Metades sucessivas (cada uma é a média de 2×2 pixels) e o resto bilinear.
    while img.width // 2 >= nw and img.height // 2 >= nh:
        img = img.reduce(2)
    img = img.resize((nw, nh), Image.BILINEAR)
    x = np.zeros((1, 3, qh, qw), dtype=np.float32)
    a = (np.asarray(img, dtype=np.float32) / 255.0 - MEDIA) / DESVIO
    x[0, :, :nh, :nw] = a.transpose(2, 0, 1)
    return x, nw, nh, girou


def interpreta(saida, nw, nh, passo, limiar):
    """Contagem e marcas (em fração da imagem enquadrada, 0 a 1)."""
    d = np.clip(saida[0, 0], 0, None) / FATOR
    d = d[: nh // passo, : nw // passo]
    m = (d == maximum_filter(d, size=3, mode="constant", cval=-1.0)) & (d > limiar)
    ys, xs = np.nonzero(m)
    marcas = np.stack([(xs + 0.5) * passo / nw, (ys + 0.5) * passo / nh], axis=1) if len(xs) else np.zeros((0, 2))
    return float(d.sum()), marcas


def desgira(marcas, girou):
    """Das frações da imagem girada para as da foto em pé (inverso do giro horário)."""
    if not girou or len(marcas) == 0:
        return marcas
    return np.stack([marcas[:, 1], 1.0 - marcas[:, 0]], axis=1)


def casa(pred, verd, raio):
    if len(pred) == 0 or len(verd) == 0:
        return 0
    dist = np.linalg.norm(pred[:, None, :] - verd[None, :, :], axis=2)
    li, co = linear_sum_assignment(dist)
    return int((dist[li, co] <= raio).sum())


def resume(linhas, chave):
    v = np.array([l["verdade"] for l in linhas], dtype=float)
    p = np.array([l[chave] for l in linhas], dtype=float)
    e = p - v
    rel = np.abs(e[v > 0]) / v[v > 0]
    sst = ((v - v.mean()) ** 2).sum()
    return {"mae": float(np.abs(e).mean()), "vies": float(e.mean()),
            "erro_relativo_medio": float(rel.mean()), "erro_relativo_mediano": float(np.median(rel)),
            "r2": float(1 - (e ** 2).sum() / sst), "erro_relativo_do_total": float(abs(p.sum() - v.sum()) / v.sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", required=True, help="pasta com v1/ e v2/ da branch modelo-contagem-vagens")
    ap.add_argument("--dados", default="dados_yolopod")
    ap.add_argument("--saida", default="saida")
    ap.add_argument("--limite", type=int, default=0, help="só as primeiras N fotos do teste (para ensaio)")
    args = ap.parse_args()
    from ai_edge_litert.interpreter import Interpreter

    modelos_dir, saida = Path(args.modelos), Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    conversao, interpretes, limiares = {}, {}, {}
    for versao in MODELOS:
        modelo = carrega_modelo(modelos_dir, versao)
        arquivo, dif = converte(modelo, versao, saida)
        metr = json.loads((modelos_dir / versao / "metricas.json").read_text())
        limiares[versao] = metr["configuracao"]["limiar_picos"]
        it = Interpreter(model_path=str(arquivo), num_threads=4)
        it.allocate_tensors()
        ent, sai = it.get_input_details()[0], it.get_output_details()[0]
        conversao[versao] = {**MODELOS[versao], "arquivo": arquivo.name, "bytes": arquivo.stat().st_size,
                             "entrada": [int(n) for n in ent["shape"]], "saida": [int(n) for n in sai["shape"]],
                             "limiar_picos": limiares[versao], "diferenca_maxima_para_o_pytorch": dif,
                             "teste_publicado": metr["teste"]}
        interpretes[versao] = (it, ent["index"], sai["index"])
        print(versao, conversao[versao]["entrada"], "->", conversao[versao]["saida"], f"dif {dif:.2e}", flush=True)

    raiz, revisao = treino.baixa_base(Path(args.dados))
    itens = treino.le_coco(raiz)
    teste = treino.separa(itens, 42)["teste"]
    if args.limite:
        teste = teste[: args.limite]
    # Raio de casamento das marcas: o mesmo do treino da v2, em fração do lado maior.
    raio = conversao["v2"]["teste_publicado"]["localizacao"]["raio_px"] / MODELOS["v2"]["lado"]

    linhas, tempos = [], {v: [] for v in MODELOS}
    acertos = {"em_pe": 0, "invertida": 0}
    n_pred = {"em_pe": 0, "invertida": 0}
    n_verd = 0
    for k, item in enumerate(teste):
        original = Image.open(item["arquivo"]).convert("RGB")
        img = como_no_celular(original)
        verd = np.array([(c[0] / original.width, c[1] / original.height) for c in item["caixas"]]).reshape(-1, 2)
        linha = {"arquivo": item["arquivo"].name, "local": item["local"], "verdade": len(verd)}
        for nome, foto in (("em_pe", img), ("invertida", img.transpose(Image.Transpose.ROTATE_180))):
            res = {}
            for versao, (it, i_ent, i_sai) in interpretes.items():
                x, nw, nh, girou = prepara(foto, versao)
                t0 = time.time()
                it.set_tensor(i_ent, x)
                it.invoke()
                tempos[versao].append(time.time() - t0)
                c, marcas = interpreta(it.get_tensor(i_sai), nw, nh, MODELOS[versao]["passo"], limiares[versao])
                res[versao] = (c, desgira(marcas, girou))
            marcas = res["v2"][1]
            if nome == "invertida":
                marcas = 1.0 - marcas if len(marcas) else marcas
            # Distância medida na proporção da foto, com o lado maior valendo 1.
            esc = np.array([original.width, original.height]) / max(original.size)
            acertos[nome] += casa(marcas * esc, verd * esc, raio)
            n_pred[nome] += len(marcas)
            linha[f"contagem_{nome}"] = res["v1"][0]
            linha[f"contagem_v2_{nome}"] = res["v2"][0]
            linha[f"marcas_{nome}"] = len(marcas)
        n_verd += len(verd)
        linhas.append(linha)
        if k % 20 == 0:
            print(f"{k + 1}/{len(teste)}  verdade {linha['verdade']}  v1 {linha['contagem_em_pe']:.1f}  "
                  f"marcas {linha['marcas_em_pe']}", flush=True)

    resultado = {
        "base": {"repositorio": treino.REPO, "revisao": revisao, "licenca": "CC BY 4.0", "fotos_de_teste": len(linhas)},
        "conversao": conversao,
        "no_celular": {
            "contagem_v1": resume(linhas, "contagem_em_pe"),
            "contagem_v2": resume(linhas, "contagem_v2_em_pe"),
            "marcas_v2": {"precisao": acertos["em_pe"] / max(n_pred["em_pe"], 1),
                          "revocacao": acertos["em_pe"] / max(n_verd, 1)},
        },
        "foto_de_cabeca_para_baixo": {
            "contagem_v1": resume(linhas, "contagem_invertida"),
            "marcas_v2": {"precisao": acertos["invertida"] / max(n_pred["invertida"], 1),
                          "revocacao": acertos["invertida"] / max(n_verd, 1)},
        },
        "segundos_por_foto_neste_computador": {v: float(np.median(t)) for v, t in tempos.items()},
    }
    (saida / "conferencia_no_celular.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False))
    (saida / "conferencia_por_foto.json").write_text(json.dumps(linhas, indent=1, ensure_ascii=False))
    print(json.dumps({k: resultado[k] for k in ("no_celular", "foto_de_cabeca_para_baixo",
                                               "segundos_por_foto_neste_computador")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
