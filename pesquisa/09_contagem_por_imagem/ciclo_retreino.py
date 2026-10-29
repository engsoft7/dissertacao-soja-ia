# -*- coding: utf-8 -*-
"""
Ciclo de retreino do contador de vagens com as fotos marcadas no Pará.

O contador do aplicativo foi treinado só com a YOLO POD (plantas chinesas
sobre pano escuro), e o erro nas lavouras do Pará nunca foi medido. O app já
guarda cada foto que o produtor marca e a exporta num .zip (AmostrasTreino.kt).
Este script fecha o ciclo em três passos, sem mexer nos scripts de treino e
de conversão, de que só importa as rotinas:

  junta     abre os .zip exportados, confere cada anotação e monta a base do
            Pará: só fotos de vagens, com marcação completa (a contagem que
            ficou na tela é o número de pontos; se o produtor corrigiu o número
            à mão, há vagem sem marca e a foto não serve de gabarito) e sem
            repetidas. Cada .zip entra com o nome da fazenda (--lote), e a
            separação em treino, validação e teste é por fazenda e safra, nunca
            por foto: fotos da mesma lavoura no mesmo ano se parecem, e uma
            delas no teste com a vizinha no treino mediria um erro otimista. A
            parte sai do resumo SHA-256 do par (fazenda, safra): não depende da
            ordem de chegada, e uma lavoura de teste nunca passa a treino.
  mede      roda os modelos do app (os .tflite em assets) nas fotos de teste do
            Pará, pelo mesmo caminho da foto no celular (converte_para_celular.py),
            e dá o erro da contagem e a localização das marcas. É o número que
            falta: o erro do contador nas lavouras daqui.
  retreina  parte dos pesos publicados (branch modelo-contagem-vagens) e
            ajusta com as fotos de treino do Pará, misturadas às da YOLO POD
            para o modelo não esquecer o que já sabia. Escolhe a época pelo erro
            na validação do Pará; mede no teste do Pará e no da YOLO POD, antes
            e depois. O modelo novo só vale se melhorar no Pará sem piorar na
            YOLO POD além da margem dada (--tolerancia).
  publica   com a v1 e a v2 aprovadas e já gravadas na branch
            modelo-contagem-vagens, escreve o anúncio que a API serve em
            /api/contador (software/api_backend/contador_modelo.json): versão,
            endereço preso ao commit, tamanho e SHA-256 de cada arquivo, e a
            frase que o aplicativo mostra. O aplicativo (AtualizaContador.kt)
            baixa e confere sozinho, sem versão nova. Não use Release: cada
            Release publicado gera um depósito novo no Zenodo.

Uso:
    python ciclo_retreino.py junta fotos_marcadas_2027-03-02.zip --lote "Fazenda Boa Vista" --base base_para
    python ciclo_retreino.py mede --base base_para --assets <app/src/main/assets>
    python ciclo_retreino.py retreina --base base_para --modelos <branch> --versao v1 \
        [--yolopod dados_yolopod] --saida retreino_v1
    python ciclo_retreino.py publica --versao 2 --commit <sha da branch> --pasta celular_v2 \
        --v1 retreino_v1/contador_vagens_v1.tflite --v2 retreino_v2/contador_vagens_v2.tflite \
        --nota "Aprendeu também com N fotos de lavouras do Pará, onde erra em média X%."

Fotos de pessoas, documentos ou qualquer coisa que não seja vagem de soja não
devem entrar: confira as miniaturas que `junta` grava em base_para/revisar/
antes de treinar.
"""
import argparse
import hashlib
import json
import random
import sys
import time
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

PARTES = {"teste": (0, 20), "validacao": (20, 35), "treino": (35, 100)}  # faixas do resumo, em %
ORIGENS_ACEITAS = {"produtor", "contador_conferido"}
LIMIAR = {"v1": 0.05, "v2": 0.02}   # os mesmos de ContadorVagens.kt
RAIO_MARCAS = 0.03                  # casamento de marcas, em fração do lado maior da foto


def safra_de(data: str | None) -> int | None:
    """Ano da colheita: no Pará a soja é colhida de janeiro a junho; foto de
    setembro em diante já é da safra seguinte."""
    if not data or len(data) < 7:
        return None
    ano, mes = int(data[:4]), int(data[5:7])
    return ano + 1 if mes >= 9 else ano


def parte_de(lote: str, safra) -> str:
    """Treino, validação ou teste, fixo para sempre pelo par (fazenda, safra)."""
    r = int(hashlib.sha256(f"{lote.strip().lower()}|{safra}".encode()).hexdigest()[:8], 16) % 100
    return next(p for p, (a, b) in PARTES.items() if a <= r < b)


# ── junta ────────────────────────────────────────────────────────────────────

def motivo_de_recusa(a: dict) -> str | None:
    if a.get("classe") != "vagem":
        return "não é foto de vagens"
    if a.get("origem_das_marcas", "produtor") not in ORIGENS_ACEITAS:
        return "marcas não conferidas pelo produtor"
    pts = a.get("pontos") or []
    if not pts:
        return "sem marcas"
    if a.get("contagem_informada") is not None and a["contagem_informada"] != len(pts):
        return "contagem corrigida à mão: há vagem sem marca"
    w, h = a.get("largura"), a.get("altura")
    if not w or not h or any(not (0 <= x < w and 0 <= y < h) for x, y in pts):
        return "marca fora da imagem"
    return None


def junta(zips: list[Path], lote: str, base: Path):
    (base / "imagens").mkdir(parents=True, exist_ok=True)
    (base / "revisar").mkdir(exist_ok=True)
    indice_arq = base / "anotacoes.json"
    indice = json.loads(indice_arq.read_text()) if indice_arq.exists() else {}
    recusas, novas = {}, 0
    for z in zips:
        with zipfile.ZipFile(z) as arq:
            nomes = set(arq.namelist())
            for nome in sorted(n for n in nomes if n.endswith(".json")):
                a = json.loads(arq.read(nome))
                motivo = motivo_de_recusa(a)
                if motivo is None and a.get("imagem") not in nomes:
                    motivo = "imagem ausente do .zip"
                if motivo:
                    recusas[motivo] = recusas.get(motivo, 0) + 1
                    continue
                dados = arq.read(a["imagem"])
                resumo = hashlib.sha256(dados).hexdigest()
                if resumo in indice:
                    recusas["repetida"] = recusas.get("repetida", 0) + 1
                    continue
                (base / "imagens" / f"{resumo[:16]}.jpg").write_bytes(dados)
                indice[resumo] = {
                    "imagem": f"imagens/{resumo[:16]}.jpg", "largura": a["largura"], "altura": a["altura"],
                    "pontos": a["pontos"], "lote": lote, "safra": safra_de(a.get("data")),
                    "parte": parte_de(lote, safra_de(a.get("data"))), "origem_das_marcas": a.get("origem_das_marcas"),
                    "data": a.get("data"), "versao_app": a.get("versao_app"), "zip": z.name,
                }
                miniatura(base / "imagens" / f"{resumo[:16]}.jpg", a["pontos"], base / "revisar" / f"{resumo[:16]}.jpg")
                novas += 1
    indice_arq.write_text(json.dumps(indice, indent=1, ensure_ascii=False))
    resumo_partes = {p: {"fotos": sum(1 for v in indice.values() if v["parte"] == p),
                         "lavouras": len({(v["lote"], v["safra"]) for v in indice.values() if v["parte"] == p})}
                     for p in PARTES}
    print(json.dumps({"novas": novas, "recusadas": recusas, "na_base": len(indice), "partes": resumo_partes},
                     indent=2, ensure_ascii=False))


def miniatura(origem: Path, pontos, destino: Path):
    from PIL import Image, ImageDraw
    img = Image.open(origem).convert("RGB")
    d = ImageDraw.Draw(img)
    r = max(4, max(img.size) // 150)
    for x, y in pontos:
        d.ellipse((x - r, y - r, x + r, y + r), outline=(255, 64, 64), width=max(1, r // 2))
    img.thumbnail((512, 512))
    img.save(destino, quality=80)


def carrega_base(base: Path, parte: str):
    indice = json.loads((base / "anotacoes.json").read_text())
    return [{"arquivo": base / v["imagem"], "largura": v["largura"], "altura": v["altura"],
             "caixas": [(x, y, 0, 0) for x, y in v["pontos"]], "local": "para"}
            for _, v in sorted(indice.items()) if v["parte"] == parte]


# ── mede ─────────────────────────────────────────────────────────────────────

def resume_erros(verdade, contagem) -> dict:
    v, p = np.asarray(verdade, float), np.asarray(contagem, float)
    e = p - v
    return {"fotos": int(len(v)), "vagens": int(v.sum()), "erro_absoluto_medio": round(float(np.abs(e).mean()), 2),
            "vies": round(float(e.mean()), 2),
            "erro_relativo_medio": round(float((np.abs(e[v > 0]) / v[v > 0]).mean()), 4),
            "erro_relativo_do_total": round(float(abs(p.sum() - v.sum()) / v.sum()), 4)}


def mede(base: Path, assets: Path, parte: str = "teste", saida: Path | None = None):
    from ai_edge_litert.interpreter import Interpreter
    from PIL import Image
    import converte_para_celular as cel

    itens = carrega_base(base, parte)
    if not itens:
        raise SystemExit(f"nenhuma foto de {parte} na base; rode junta antes")
    interpretes = {}
    for versao in ("v1", "v2"):
        it = Interpreter(model_path=str(assets / f"contador_vagens_{versao}.tflite"), num_threads=4)
        it.allocate_tensors()
        interpretes[versao] = (it, it.get_input_details()[0]["index"], it.get_output_details()[0]["index"])
    linhas, acertos, n_pred, n_verd = [], 0, 0, 0
    for item in itens:
        original = Image.open(item["arquivo"]).convert("RGB")
        img = cel.como_no_celular(original)
        verd = np.array([(c[0] / original.width, c[1] / original.height) for c in item["caixas"]]).reshape(-1, 2)
        res = {}
        for versao, (it, i_ent, i_sai) in interpretes.items():
            x, nw, nh, girou = cel.prepara(img, versao)
            it.set_tensor(i_ent, x)
            it.invoke()
            c, marcas = cel.interpreta(it.get_tensor(i_sai), nw, nh, cel.MODELOS[versao]["passo"], LIMIAR[versao])
            res[versao] = (c, cel.desgira(marcas, girou))
        esc = np.array([original.width, original.height]) / max(original.size)
        acertos += cel.casa(res["v2"][1] * esc, verd * esc, RAIO_MARCAS)
        n_pred += len(res["v2"][1])
        n_verd += len(verd)
        linhas.append({"arquivo": item["arquivo"].name, "verdade": len(verd), "contagem_v1": res["v1"][0],
                       "marcas_v2": len(res["v2"][1])})
    resultado = {
        "parte": parte, "modelos": str(assets),
        "contagem_v1": resume_erros([l["verdade"] for l in linhas], [l["contagem_v1"] for l in linhas]),
        "marcas_v2": {"precisao": round(acertos / max(n_pred, 1), 3), "revocacao": round(acertos / max(n_verd, 1), 3),
                      "raio_fracao_do_lado": RAIO_MARCAS},
        "referencia_teste_yolopod": "contagem v1 com 5,6% de erro relativo médio; marcas v2 com 85% de precisão e 60% de revocação",
    }
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    if saida:
        saida.mkdir(parents=True, exist_ok=True)
        (saida / f"mede_{parte}.json").write_text(json.dumps({**resultado, "por_foto": linhas}, indent=1,
                                                             ensure_ascii=False))
    return resultado


# ── retreina ─────────────────────────────────────────────────────────────────

def retreina(args):
    import torch
    import torch.nn.functional as F
    import converte_para_celular as cel
    import treina_contador_vagens as treino

    cfg = cel.MODELOS[args.versao]
    treino.PASSO = cfg["passo"]          # as rotinas de treino leem o passo do módulo
    random.seed(args.semente); np.random.seed(args.semente); torch.manual_seed(args.semente)
    saida = Path(args.saida); saida.mkdir(parents=True, exist_ok=True)

    para = {p: carrega_base(Path(args.base), p) for p in PARTES}
    if len(para["treino"]) < args.minimo or not para["validacao"] or not para["teste"]:
        raise SystemExit(f"base do Pará pequena demais: {[(p, len(v)) for p, v in para.items()]} "
                         f"(mínimo de {args.minimo} fotos de treino)")
    yolo = {"treino": [], "teste": []}
    if args.yolopod:
        raiz, _ = treino.baixa_base(Path(args.yolopod))
        partes = treino.separa(treino.le_coco(raiz), 42)
        yolo = {"treino": partes["treino"], "teste": partes["teste"]}
    cache = {p: [treino.carrega(i, cfg["lado"]) for i in v] for p, v in para.items()}
    cache_y = {p: [treino.carrega(i, cfg["lado"]) for i in v] for p, v in yolo.items()}
    escala = np.median([max(i["largura"], i["altura"]) for i in para["treino"]])
    raio = max(8.0, RAIO_MARCAS * cfg["lado"])

    modelo = cel.carrega_modelo(Path(args.modelos), args.versao)

    def mede_tudo(rotulo):
        m = {"para_validacao": treino.avalia(modelo, cache["validacao"], para["validacao"], raio)[0],
             "para_teste": treino.avalia(modelo, cache["teste"], para["teste"], raio)[0]}
        if cache_y["teste"]:
            m["yolopod_teste"] = treino.avalia(modelo, cache_y["teste"], yolo["teste"], raio)[0]
        print(rotulo, {k: round(v["erro_relativo_medio"], 4) for k, v in m.items()}, flush=True)
        return m

    antes = mede_tudo("antes")
    # O Pará pesa args.peso_para vezes mais no sorteio; a YOLO POD entra para o
    # modelo não esquecer o que aprendeu com 1.448 fotos.
    conjunto = treino.Recortes(cache["treino"] + cache_y["treino"], args.recorte)
    pesos = [args.peso_para] * len(cache["treino"]) + [1.0] * len(cache_y["treino"])
    n_lote = max(len(cache["treino"]) * 4, args.lote * 10)
    sorteio = torch.utils.data.WeightedRandomSampler(pesos, num_samples=n_lote, replacement=True)
    carregador = torch.utils.data.DataLoader(conjunto, batch_size=args.lote, sampler=sorteio, drop_last=True)
    cabeca = [p for n, p in modelo.named_parameters() if not n.startswith("ate")]
    corpo = [p for n, p in modelo.named_parameters() if n.startswith("ate")]
    # Ajuste fino: taxas dez vezes menores que as do treino original.
    otim = torch.optim.AdamW([{"params": corpo, "lr": 3e-5}, {"params": cabeca, "lr": 1e-4}], weight_decay=1e-4)
    melhor = antes["para_validacao"]["mae"]
    torch.save(modelo.state_dict(), saida / "contador_vagens.pt")
    historico, inicio = [], time.time()
    for epoca in range(1, args.epocas + 1):
        modelo.train()
        perdas = []
        for x, alvo in carregador:
            pred = modelo(x)
            perda = F.mse_loss(pred, alvo) + 0.03 * F.l1_loss(pred.sum((1, 2, 3)), alvo.sum((1, 2, 3)))
            otim.zero_grad(); perda.backward(); otim.step()
            perdas.append(perda.item())
        mv, _ = treino.avalia(modelo, cache["validacao"], para["validacao"], raio)
        historico.append({"epoca": epoca, "perda": float(np.mean(perdas)), "val_para_mae": mv["mae"]})
        print(f"época {epoca}: perda {np.mean(perdas):.4f}, MAE na validação do Pará {mv['mae']:.2f}", flush=True)
        if mv["mae"] < melhor:
            melhor = mv["mae"]
            torch.save(modelo.state_dict(), saida / "contador_vagens.pt")
        if (time.time() - inicio) / 60 > args.minutos:
            break
    modelo.load_state_dict(torch.load(saida / "contador_vagens.pt"))
    modelo.eval()
    depois = mede_tudo("depois")

    melhora_para = depois["para_teste"]["erro_relativo_medio"] < antes["para_teste"]["erro_relativo_medio"]
    piora_yolo = (depois["yolopod_teste"]["erro_relativo_medio"] - antes["yolopod_teste"]["erro_relativo_medio"]
                  if "yolopod_teste" in depois else 0.0)
    aprovado = bool(melhora_para and piora_yolo <= args.tolerancia)
    resultado = {"versao": args.versao, "fotos_para": {p: len(v) for p, v in para.items()},
                 "fotos_yolopod": {p: len(v) for p, v in yolo.items()}, "lado_mediano_das_fotos_para": float(escala),
                 "antes": antes, "depois": depois, "historico": historico,
                 "aprovado": aprovado,
                 "criterio": (f"erro relativo médio menor no teste do Pará e, na YOLO POD, piora de no máximo "
                              f"{args.tolerancia:.1%}")}
    if aprovado:
        import shutil
        destino = saida / args.versao
        destino.mkdir(exist_ok=True)
        shutil.copy(saida / "contador_vagens.pt", destino / "contador_vagens.pt")
        arquivo, dif = cel.converte(modelo, args.versao, saida)
        resultado["tflite"] = {"arquivo": arquivo.name, "bytes": arquivo.stat().st_size,
                               "sha256": hashlib.sha256(arquivo.read_bytes()).hexdigest(),
                               "diferenca_maxima_para_o_pytorch": dif}
    (saida / "retreino.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False, default=str))
    print(json.dumps({k: resultado[k] for k in ("fotos_para", "aprovado", "criterio")}, indent=2, ensure_ascii=False))


def publica(args):
    """Anúncio do modelo novo para a API, com os endereços presos ao commit."""
    import re
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        raise SystemExit("--commit precisa ser o resumo inteiro (40 dígitos) do commit na branch modelo-contagem-vagens")
    destino = Path(args.anuncio)
    atual = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {"versao": 0}
    if args.versao <= atual["versao"]:
        raise SystemExit(f"a versão {args.versao} não é maior que a anunciada ({atual['versao']})")
    arquivos = {}
    for versao, caminho in (("v1", args.v1), ("v2", args.v2)):
        dados = Path(caminho).read_bytes()
        nome = f"contador_vagens_{versao}.tflite"
        arquivos[nome] = {
            "url": f"https://raw.githubusercontent.com/engsoft7/dissertacao-soja-ia/{args.commit}/"
                   f"{args.pasta.strip('/')}/{nome}",
            "sha256": hashlib.sha256(dados).hexdigest(), "bytes": len(dados)}
    anuncio = {"versao": args.versao, "app_minimo": args.app_minimo, "arquivos": arquivos, "nota": args.nota,
               "descricao": f"Versão {args.versao}, publicada por ciclo_retreino.py publica."}
    destino.write_text(json.dumps(anuncio, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(anuncio, indent=2, ensure_ascii=False))
    print("Confira os endereços (curl -I) antes de levar o anúncio à main: o aplicativo baixa o que estiver lá.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="passo", required=True)
    j = sub.add_parser("junta")
    j.add_argument("zips", nargs="+", type=Path)
    j.add_argument("--lote", required=True, help="fazenda (ou produtor) de onde vieram as fotos destes .zip")
    j.add_argument("--base", type=Path, default=Path("base_para"))
    m = sub.add_parser("mede")
    m.add_argument("--base", type=Path, default=Path("base_para"))
    m.add_argument("--assets", type=Path, required=True, help="pasta com contador_vagens_v1/v2.tflite")
    m.add_argument("--parte", choices=list(PARTES), default="teste")
    m.add_argument("--saida", type=Path)
    r = sub.add_parser("retreina")
    r.add_argument("--base", default="base_para")
    r.add_argument("--modelos", required=True, help="pasta com v1/ e v2/ da branch modelo-contagem-vagens")
    r.add_argument("--versao", choices=("v1", "v2"), default="v1")
    r.add_argument("--yolopod", default="", help="pasta da YOLO POD (baixada se vazia); omitir só para ensaio")
    r.add_argument("--saida", default="retreino")
    r.add_argument("--epocas", type=int, default=15)
    r.add_argument("--minutos", type=float, default=240)
    r.add_argument("--lote", type=int, default=8)
    r.add_argument("--recorte", type=int, default=448)
    r.add_argument("--peso-para", type=float, default=4.0)
    r.add_argument("--minimo", type=int, default=30, help="fotos de treino do Pará exigidas para retreinar")
    r.add_argument("--tolerancia", type=float, default=0.005)
    r.add_argument("--semente", type=int, default=42)
    p = sub.add_parser("publica")
    p.add_argument("--versao", type=int, required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--pasta", required=True, help="pasta dos .tflite na branch modelo-contagem-vagens")
    p.add_argument("--v1", required=True)
    p.add_argument("--v2", required=True)
    p.add_argument("--nota", required=True, help="frase sobre de onde o modelo aprendeu e quanto erra")
    p.add_argument("--app-minimo", type=int, default=23)
    p.add_argument("--anuncio", default=str(Path(__file__).resolve().parents[2] / "software" / "api_backend"
                                            / "contador_modelo.json"))
    a = ap.parse_args()
    if a.passo == "junta":
        junta(a.zips, a.lote, a.base)
    elif a.passo == "mede":
        mede(a.base, a.assets, a.parte, a.saida)
    elif a.passo == "retreina":
        retreina(a)
    else:
        publica(a)


if __name__ == "__main__":
    main()
