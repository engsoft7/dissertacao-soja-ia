# -*- coding: utf-8 -*-
"""Envia o pacote (.aab) de um Release à Google Play, pela API oficial.

Chamado por publica-apk.yml depois de assinar o pacote, e por envia-play.yml,
que reenvia o .aab de um Release já publicado sem compilar de novo. Só age
quando o segredo PLAY_SERVICE_ACCOUNT_JSON está configurado. Sem ele, não faz
nada: o Release continua com o .aab anexado, para o envio manual pelo Play
Console.

O que o autor configura uma vez:
  1. No Google Cloud, uma conta de serviço com uma chave em JSON.
  2. No Play Console (Usuários e permissões), essa conta convidada com permissão
     para lançar versões do AgroInteligência.
  3. No GitHub (Settings > Secrets and variables > Actions), o segredo
     PLAY_SERVICE_ACCOUNT_JSON com o conteúdo do JSON.

A faixa de envio é a mais alta em que o app já tem versão lançada: quem está no
teste fechado recebe ali as versões novas, e quem já lançou em produção, em
produção. O envio nunca sobe de faixa sozinho: conta pessoal nova não lança em
produção antes de um teste fechado com 12 testadores por 14 dias, e a primeira
versão de produção é lançada pelo Play Console; as seguintes vão por aqui. A
variável PLAY_FAIXA (internal, alpha, beta, production), se existir, manda.

A API segue o roteiro do Play Console: abre uma edição, envia o pacote, põe a
versão na faixa com as notas da versão e confirma a edição. Uma falha em
qualquer passo deixa a edição sem confirmar, e nada muda na loja. Quando a loja
recusa o pacote ou a faixa, o log diz o que ela respondeu, quais faixas o app
tem e o que fazer.

A ficha da loja (nome, breve descrição e descrição completa em português) vem
de software/aplicativo_mobile/loja/textos_da_loja.txt: com --ficha, o script
mostra o que mudaria na loja; com --ficha e --aplica, grava. Uma ficha editada
só no Play Console é sobrescrita na próxima atualização: a fonte é o arquivo.

As imagens da ficha (as capturas de celular e a imagem de destaque) saem das
telas reais do app, desenhadas por CapturasDeTelaTest (os testes loja_*) com
as respostas da API do dia: com --imagens PASTA, o script mostra o que mudaria;
com --aplica, troca. O publica-apk.yml faz isso a cada versão nova. O vídeo e o
ícone ficam como estão, e --midia só mostra o vídeo e as imagens da ficha.

Uso:  python envia_play.py ARQUIVO.aab "Notas da versão" [--faixa alpha]
      python envia_play.py --faixas      só lista as faixas do app; não envia nada
      python envia_play.py --ficha textos_da_loja.txt [--aplica]
      python envia_play.py --midia       só mostra o vídeo e as imagens da ficha
      python envia_play.py --baixa-imagens PASTA   baixa as imagens que a ficha tem hoje
      python envia_play.py --imagens PASTA [--aplica]
"""
import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

PACOTE = "com.agrointeligencia.app"
ESCOPO = "https://www.googleapis.com/auth/androidpublisher"
# O Play aceita até 500 caracteres de notas por idioma.
LIMITE_NOTAS = 500
NOMES = {"production": "produção", "beta": "teste aberto", "alpha": "teste fechado", "internal": "teste interno"}
# Da faixa mais restrita à mais aberta. Uma faixa de nome próprio é um teste fechado.
ORDEM = ["internal", "alpha", "beta", "production"]
# As seções de textos_da_loja.txt, o campo de cada uma na API e o limite do Play
# (os mesmos de confere_textos_da_loja.py). A descrição completa vai até o fim.
SECOES_DA_FICHA = {"NOME DO APP": ("title", 30), "BREVE DESCRIÇÃO": ("shortDescription", 80),
                   "DESCRIÇÃO COMPLETA": ("fullDescription", 4000)}
IDIOMA_DA_FICHA = "pt-BR"
# O vídeo da ficha, opcional, numa seção VÍDEO no começo de textos_da_loja.txt,
# antes de NOME DO APP (o confere_textos_da_loja.py só lê as três seções acima).
# Sem a seção, o vídeo da loja fica como está.
SECAO_VIDEO = "VÍDEO"
VIDEO_DO_YOUTUBE = re.compile(r"^https://(www\.youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]{11}$")


def notas_da_versao(texto: str) -> str:
    """As notas no limite do Play, cortadas numa palavra inteira."""
    texto = " ".join(texto.split())
    if len(texto) <= LIMITE_NOTAS:
        return texto
    corte = texto[: LIMITE_NOTAS - 1].rsplit(" ", 1)[0]
    return corte.rstrip(",;:") + "…"


def cliente(credencial_json: str):
    """O cliente da API da Play, com a chave da conta de serviço."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    cred = service_account.Credentials.from_service_account_info(json.loads(credencial_json), scopes=[ESCOPO])
    return build("androidpublisher", "v3", credentials=cred, cache_discovery=False)


def _arquivo(aab: str):
    from googleapiclient.http import MediaFileUpload

    return MediaFileUpload(aab, mimetype="application/octet-stream", resumable=True)


def recusa(erro: Exception) -> str | None:
    """O que a loja respondeu, numa linha, se o erro é uma recusa dela; None se é outro erro."""
    resposta = getattr(erro, "resp", None)
    if resposta is None:
        return None
    return f"{getattr(resposta, 'status', '?')}: {getattr(erro, 'reason', None) or erro}"


def descreve(faixas: list[dict]) -> list[str]:
    """Uma linha por faixa: o nome, o que ela é e as versões que tem."""
    linhas = []
    for f in faixas:
        nome = f.get("track", "?")
        versoes = [f"versão {'/'.join(r.get('versionCodes') or ['sem pacote'])} ({r.get('status', '?')})"
                   for r in f.get("releases") or []]
        linhas.append(f"{nome} ({NOMES.get(nome, 'faixa de teste própria')}): " + (", ".join(versoes) or "sem versão"))
    return linhas


def faixas_do_app(api, edicao: str | None = None) -> list[dict]:
    """As faixas do app na loja. Sem edição, abre uma só para ler e a descarta: nada muda."""
    propria = edicao is None
    if propria:
        edicao = api.edits().insert(packageName=PACOTE, body={}).execute()["id"]
    try:
        return api.edits().tracks().list(packageName=PACOTE, editId=edicao).execute().get("tracks") or []
    finally:
        if propria:
            api.edits().delete(packageName=PACOTE, editId=edicao).execute()


def faixa_em_uso(faixas: list[dict]) -> str | None:
    """A faixa mais alta em que o app já tem versão lançada; None se não tem em nenhuma.

    Rascunho e lançamento interrompido não contam: o envio não pode levar o app
    a um público maior do que o autor já escolheu no Play Console.
    """
    lancadas = [f.get("track", "") for f in faixas
                if any(r.get("versionCodes") and r.get("status") in ("completed", "inProgress")
                       for r in f.get("releases") or [])]
    if not lancadas:
        return None

    def altura(nome: str) -> tuple[int, bool]:
        return (ORDEM.index(nome) if nome in ORDEM else ORDEM.index("alpha"), nome in ORDEM)
    return max(lancadas, key=altura)


def orientacao(faixa: str, resposta: str) -> str:
    """O que fazer, pelo que a loja respondeu."""
    if "draft" in resposta.lower():
        return ("O app ainda não teve nenhuma versão lançada: a primeira é lançada pelo Play Console, "
                "e as seguintes passam a ir por aqui.")
    if faixa == "production":
        return ("A conta ainda não pode lançar em produção (conta pessoal nova precisa antes do teste fechado com 12 "
                "testadores por 14 dias) ou há uma versão em revisão. Sem a variável PLAY_FAIXA, o envio vai sozinho "
                "para a faixa mais alta em que o app já tem versão; para reenviar esta, dispare o workflow "
                "\"Envia à Google Play\" com a etiqueta do Release.")
    return "Confira no Play Console se a faixa existe e se a conta de serviço pode lançar nela."


def envia(api, aab: str, notas: str, faixa: str) -> int:
    edicao = api.edits().insert(packageName=PACOTE, body={}).execute()["id"]
    try:
        pacote = api.edits().bundles().upload(packageName=PACOTE, editId=edicao, media_body=_arquivo(aab)).execute()
    except Exception as e:
        resposta = recusa(e)
        if resposta is None:
            raise
        print(f"::error::A Google Play recusou o pacote ({resposta}). Se a versão já foi enviada antes, "
              "promova-a à faixa desejada pelo Play Console.")
        return 1
    versao = str(pacote["versionCode"])
    try:
        api.edits().tracks().update(packageName=PACOTE, editId=edicao, track=faixa, body={
            "track": faixa,
            "releases": [{"versionCodes": [versao], "status": "completed",
                          "releaseNotes": [{"language": "pt-BR", "text": notas_da_versao(notas)}]}],
        }).execute()
        api.edits().commit(packageName=PACOTE, editId=edicao).execute()
    except Exception as e:
        resposta = recusa(e)
        if resposta is None:
            raise
        print(f"::error::A Google Play recusou a versão {versao} na faixa {faixa} ({resposta}). "
              + orientacao(faixa, resposta) + " Nada mudou na loja.")
        try:
            for linha in descreve(faixas_do_app(api, edicao)):
                print("Faixa do app na loja:", linha)
        except Exception as e2:  # a lista é só ajuda: não esconde a recusa
            print(f"(não foi possível listar as faixas: {type(e2).__name__})")
        return 1
    print(f"Versão {versao} enviada à faixa {faixa} da Google Play.")
    return 0


def ficha_do_arquivo(caminho: str | Path) -> dict:
    """Nome, breve descrição e descrição completa de textos_da_loja.txt, com os nomes da API.

    Recusa o arquivo sem uma das três seções ou com texto acima do limite do Play.
    Com a seção VÍDEO, traz também o endereço do vídeo, que precisa ser do YouTube.
    """
    partes: dict[str, list[str]] = {}
    atual = None
    for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
        if linha.strip() in SECOES_DA_FICHA:
            atual = SECOES_DA_FICHA[linha.strip()][0]
            partes[atual] = []
        elif linha.strip() == SECAO_VIDEO:
            atual = "video"
            partes[atual] = []
        elif atual:
            partes[atual].append(linha)
    ficha = {campo: "\n".join(linhas).strip() for campo, linhas in partes.items()}
    if "video" in ficha and not VIDEO_DO_YOUTUBE.match(ficha["video"]):
        raise ValueError(f"textos da loja: o vídeo precisa ser um endereço do YouTube, e não {ficha['video']!r}")
    faltando = [secao for secao, (campo, _) in SECOES_DA_FICHA.items() if not ficha.get(campo)]
    if faltando:
        raise ValueError("textos da loja sem " + ", ".join(faltando))
    longos = [f"{secao} ({len(ficha[campo])} de {limite})" for secao, (campo, limite) in SECOES_DA_FICHA.items()
              if len(ficha[campo]) > limite]
    if longos:
        raise ValueError("textos da loja acima do limite do Play: " + ", ".join(longos))
    return ficha


def diferencas(na_loja: dict, no_arquivo: dict) -> list[str]:
    """O que muda de um para o outro, campo a campo, em linhas de diff."""
    linhas: list[str] = []
    for campo in ("title", "shortDescription", "fullDescription", "video"):
        if campo == "video" and "video" not in no_arquivo:
            continue  # sem a seção VÍDEO no arquivo, o vídeo da loja fica como está
        antes = (na_loja.get(campo) or "").splitlines()
        depois = (no_arquivo.get(campo) or "").splitlines()
        if antes != depois:
            linhas += difflib.unified_diff(antes, depois, f"loja/{campo}", f"textos_da_loja.txt/{campo}",
                                           n=0, lineterm="")
    return linhas


def ficha(api, arquivo: str | Path, aplica: bool = False) -> int:
    """Compara a ficha em português da loja com textos_da_loja.txt e, com aplica, a atualiza.

    Só mexe no nome, nas duas descrições e, quando o arquivo tem a seção VÍDEO, no
    vídeo; as imagens ficam como estão.
    Sem aplica, ou sem diferença, a edição aberta para ler é descartada.
    """
    nova = ficha_do_arquivo(arquivo)
    edicao = api.edits().insert(packageName=PACOTE, body={}).execute()["id"]
    confirmada = False
    try:
        fichas = api.edits().listings().list(packageName=PACOTE, editId=edicao).execute().get("listings") or []
        print("Idiomas da ficha na loja:", ", ".join(f.get("language", "?") for f in fichas) or "nenhum")
        na_loja = next((f for f in fichas if f.get("language") == IDIOMA_DA_FICHA), None)
        if na_loja is None:
            print(f"::error::A loja não tem ficha em {IDIOMA_DA_FICHA}: crie-a pelo Play Console.")
            return 1
        mudancas = diferencas(na_loja, nova)
        if not mudancas:
            print(f"A ficha da loja ({IDIOMA_DA_FICHA}) já está igual a textos_da_loja.txt.")
            return 0
        print("\n".join(mudancas))
        if not aplica:
            print("Só a conferência: nada mudou na loja.")
            return 0
        api.edits().listings().patch(packageName=PACOTE, editId=edicao, language=IDIOMA_DA_FICHA,
                                     body={**nova, "language": IDIOMA_DA_FICHA}).execute()
        api.edits().commit(packageName=PACOTE, editId=edicao).execute()
        confirmada = True
        print(f"Ficha da loja ({IDIOMA_DA_FICHA}) atualizada a partir de textos_da_loja.txt.")
        return 0
    except Exception as e:
        resposta = recusa(e)
        if resposta is None:
            raise
        print(f"::error::A Google Play recusou a ficha ({resposta}). Nada mudou na loja.")
        return 1
    finally:
        if not confirmada:
            try:
                api.edits().delete(packageName=PACOTE, editId=edicao).execute()
            except Exception:  # a edição sem confirmar expira sozinha
                pass


# ── vídeo e imagens da ficha ─────────────────────────────────────────────────

# Os tipos de imagem da ficha na API (edits.images), com o nome do Play Console.
TIPOS_DE_IMAGEM = {"phoneScreenshots": "capturas de celular", "sevenInchScreenshots": "capturas de tablet de 7 pol.",
                   "tenInchScreenshots": "capturas de tablet de 10 pol.", "featureGraphic": "imagem de destaque",
                   "icon": "ícone", "tvBanner": "banner de TV", "tvScreenshots": "capturas de TV",
                   "wearScreenshots": "capturas de relógio"}
# As imagens que o envio troca, pelo nome que CapturasDeTelaTest dá a elas: as
# capturas de celular na ordem do número (loja_1_*.png a loja_8_*.png) e a
# imagem de destaque. Os limites são os do Play: de 2 a 8 capturas, PNG de até
# 8 MB, lados de 320 a 3840 px e proporção de no máximo 2 para 1; a imagem de
# destaque tem 1024 x 500 px.
CAPTURAS_MIN, CAPTURAS_MAX = 2, 8
LADO_MIN, LADO_MAX, BYTES_MAX = 320, 3840, 8 * 1024 * 1024
DESTAQUE = (1024, 500)


def midia(api, idioma: str = IDIOMA_DA_FICHA) -> dict:
    """O vídeo e as imagens da ficha na loja. Só lê: a edição aberta para isso é descartada."""
    edicao = api.edits().insert(packageName=PACOTE, body={}).execute()["id"]
    try:
        fichas = api.edits().listings().list(packageName=PACOTE, editId=edicao).execute().get("listings") or []
        ficha = next((f for f in fichas if f.get("language") == idioma), {})
        imagens = {}
        for tipo in TIPOS_DE_IMAGEM:
            lista = api.edits().images().list(packageName=PACOTE, editId=edicao, language=idioma,
                                              imageType=tipo).execute().get("images") or []
            imagens[tipo] = [i.get("url", "") for i in lista]
        return {"video": ficha.get("video") or "", "imagens": imagens}
    finally:
        try:
            api.edits().delete(packageName=PACOTE, editId=edicao).execute()
        except Exception:  # a edição sem confirmar expira sozinha
            pass


def descreve_midia(m: dict) -> list[str]:
    """O vídeo e quantas imagens de cada tipo a ficha tem, com o endereço de cada uma."""
    linhas = [f"Vídeo da ficha: {m['video'] or 'nenhum'}"]
    for tipo, nome in TIPOS_DE_IMAGEM.items():
        urls = m["imagens"].get(tipo) or []
        if urls:
            linhas.append(f"{nome} ({tipo}): {len(urls)}")
            linhas += [f"  {u}" for u in urls]
    if not any(m["imagens"].values()):
        linhas.append("Nenhuma imagem na ficha.")
    return linhas


def dimensoes_png(caminho: str | Path) -> tuple[int, int]:
    """Largura e altura de um PNG, pelo cabeçalho; recusa o que não é PNG."""
    cabecalho = Path(caminho).read_bytes()[:24]
    if cabecalho[:8] != b"\x89PNG\r\n\x1a\n" or cabecalho[12:16] != b"IHDR":
        raise ValueError(f"{Path(caminho).name} não é PNG")
    return int.from_bytes(cabecalho[16:20], "big"), int.from_bytes(cabecalho[20:24], "big")


def png_com_transparencia(caminho: str | Path) -> bool:
    """Se o PNG tem canal de transparência (tipos de cor 4 e 6), que o Play recusa nas imagens da ficha."""
    return Path(caminho).read_bytes()[25] in (4, 6)


def imagens_da_pasta(pasta: str | Path) -> dict[str, list[Path]]:
    """As capturas de celular e a imagem de destaque da pasta, conferidas contra os limites do Play."""
    pasta = Path(pasta)
    capturas = sorted(pasta.glob("loja_[1-8]_*.png"))
    destaque = pasta / "loja_destaque.png"
    problemas = []
    if not CAPTURAS_MIN <= len(capturas) <= CAPTURAS_MAX:
        problemas.append(f"{len(capturas)} capturas de celular (o Play aceita de {CAPTURAS_MIN} a {CAPTURAS_MAX})")
    for c in capturas:
        largura, altura = dimensoes_png(c)
        if not (LADO_MIN <= min(largura, altura) and max(largura, altura) <= LADO_MAX):
            problemas.append(f"{c.name}: {largura} x {altura} px, fora de {LADO_MIN} a {LADO_MAX} px")
        elif max(largura, altura) > 2 * min(largura, altura):
            problemas.append(f"{c.name}: {largura} x {altura} px, mais comprida que 2 para 1")
        if c.stat().st_size > BYTES_MAX:
            problemas.append(f"{c.name}: maior que 8 MB")
    if not destaque.exists():
        problemas.append("falta loja_destaque.png")
    elif dimensoes_png(destaque) != DESTAQUE:
        problemas.append("loja_destaque.png: {} x {} px, e não 1024 x 500".format(*dimensoes_png(destaque)))
    # O Play só aceita JPEG ou PNG de 24 bits, sem canal de transparência.
    problemas += [f"{a.name}: PNG com transparência" for a in [*capturas, destaque]
                  if a.exists() and png_com_transparencia(a)]
    if problemas:
        raise ValueError("imagens da loja recusadas: " + "; ".join(problemas))
    return {"phoneScreenshots": capturas, "featureGraphic": [destaque]}


def baixa_imagens(m: dict, pasta: str | Path) -> list[Path]:
    """Baixa as imagens da ficha (os endereços públicos que midia() devolve) para a pasta.

    Cada uma vira <tipo>_<n>.<png|jpg|webp>, no tamanho original (o "=s0" no
    fim do endereço; sem ele, o servidor manda uma versão reduzida). Grava
    também video.txt com o endereço do vídeo. Serve para guardar o que a ficha
    tinha antes de uma troca.
    """
    import urllib.request

    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    salvas = []
    for tipo, urls in m["imagens"].items():
        for i, url in enumerate(urls, 1):
            dados = None
            for endereco in (url + "=s0", url):
                try:
                    with urllib.request.urlopen(endereco, timeout=60) as r:
                        dados = r.read()
                    break
                except Exception as e:  # o "=s0" recusado: tenta o endereço puro
                    print(f"{tipo} {i}: {type(e).__name__} em {endereco}")
            if dados is None:
                continue
            ext = (".png" if dados[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg" if dados[:2] == b"\xff\xd8"
                   else ".webp" if dados[8:12] == b"WEBP" else ".bin")
            alvo = pasta / f"{tipo}_{i}{ext}"
            alvo.write_bytes(dados)
            salvas.append(alvo)
    (pasta / "video.txt").write_text((m.get("video") or "nenhum") + "\n", encoding="utf-8")
    return salvas


def _sha256(caminho: Path) -> str:
    import hashlib
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _imagem(caminho: Path):
    from googleapiclient.http import MediaFileUpload

    return MediaFileUpload(str(caminho), mimetype="image/png")


def envia_imagens(api, pasta: str | Path, aplica: bool = False, idioma: str = IDIOMA_DA_FICHA) -> int:
    """Compara as capturas de celular e a imagem de destaque da ficha com as da pasta e, com aplica, troca.

    Um tipo cujas imagens já são as mesmas (pelo SHA-256 que a loja guarda de
    cada uma) fica como está; o vídeo, o ícone e os textos não mudam. Sem
    aplica, ou sem diferença, a edição aberta para ler é descartada.
    """
    novas = imagens_da_pasta(pasta)
    edicao = api.edits().insert(packageName=PACOTE, body={}).execute()["id"]
    confirmada = False
    try:
        trocar = []
        for tipo, arquivos in novas.items():
            na_loja = api.edits().images().list(packageName=PACOTE, editId=edicao, language=idioma,
                                                imageType=tipo).execute().get("images") or []
            if [i.get("sha256") for i in na_loja] == [_sha256(a) for a in arquivos]:
                print(f"{TIPOS_DE_IMAGEM[tipo]}: as mesmas da loja.")
                continue
            print(f"{TIPOS_DE_IMAGEM[tipo]}: {len(na_loja)} na loja, {len(arquivos)} novas "
                  f"({', '.join(a.name for a in arquivos)}).")
            trocar.append((tipo, arquivos))
        if not trocar:
            print(f"As imagens da ficha ({idioma}) já são as da pasta.")
            return 0
        if not aplica:
            print("Só a conferência: nada mudou na loja.")
            return 0
        for tipo, arquivos in trocar:
            api.edits().images().deleteall(packageName=PACOTE, editId=edicao, language=idioma,
                                           imageType=tipo).execute()
            for a in arquivos:
                api.edits().images().upload(packageName=PACOTE, editId=edicao, language=idioma, imageType=tipo,
                                            media_body=_imagem(a)).execute()
        api.edits().commit(packageName=PACOTE, editId=edicao).execute()
        confirmada = True
        print(f"Imagens da ficha ({idioma}) atualizadas: " + ", ".join(TIPOS_DE_IMAGEM[t] for t, _ in trocar) + ".")
        return 0
    except Exception as e:
        resposta = recusa(e)
        if resposta is None:
            raise
        print(f"::error::A Google Play recusou as imagens ({resposta}). Nada mudou na loja.")
        return 1
    finally:
        if not confirmada:
            try:
                api.edits().delete(packageName=PACOTE, editId=edicao).execute()
            except Exception:  # a edição sem confirmar expira sozinha
                pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("aab", nargs="?")
    ap.add_argument("notas", nargs="?", default="")
    ap.add_argument("--faixa", default=os.environ.get("PLAY_FAIXA") or None,
                    help="a faixa de envio; sem ela, a mais alta em que o app já tem versão")
    ap.add_argument("--faixas", action="store_true", help="só lista as faixas do app na loja")
    ap.add_argument("--ficha", metavar="TEXTOS", help="compara a ficha da loja com textos_da_loja.txt")
    ap.add_argument("--aplica", action="store_true", help="com --ficha ou --imagens: grava na loja")
    ap.add_argument("--midia", action="store_true", help="só mostra o vídeo e as imagens da ficha")
    ap.add_argument("--baixa-imagens", metavar="PASTA", help="baixa as imagens que a ficha tem hoje para a pasta")
    ap.add_argument("--imagens", metavar="PASTA",
                    help="compara as capturas de celular e a imagem de destaque da ficha com as da pasta")
    args = ap.parse_args(argv)
    if args.imagens:
        imagens_da_pasta(args.imagens)  # confere a pasta antes de qualquer acesso à loja
    credencial = os.environ.get("PLAY_SERVICE_ACCOUNT_JSON", "")
    if not credencial.strip():
        print("::notice::PLAY_SERVICE_ACCOUNT_JSON não configurado: o .aab fica no Release para o envio manual.")
        return 0
    api = cliente(credencial)
    if args.ficha:
        return ficha(api, args.ficha, args.aplica)
    if args.midia or args.baixa_imagens:
        m = midia(api)
        for linha in descreve_midia(m):
            print(linha)
        if args.baixa_imagens:
            salvas = baixa_imagens(m, args.baixa_imagens)
            print(f"{len(salvas)} imagens da ficha baixadas em {args.baixa_imagens}.")
        return 0
    if args.imagens:
        return envia_imagens(api, args.imagens, args.aplica)
    if args.faixas:
        for linha in descreve(faixas_do_app(api)) or ["(o app não tem faixas com versão)"]:
            print("Faixa do app na loja:", linha)
        return 0
    if not args.aab:
        ap.error("falta o arquivo .aab")
    faixa = args.faixa
    if not faixa:
        faixa = faixa_em_uso(faixas_do_app(api))
        if faixa is None:
            print("::error::O app ainda não tem versão lançada em nenhuma faixa da Google Play: a primeira é lançada "
                  "pelo Play Console, e as seguintes passam a ir por aqui.")
            return 1
        print(f"Faixa de envio: {faixa} ({NOMES.get(faixa, 'faixa de teste própria')}), "
              "a mais alta em que o app já tem versão.")
    return envia(api, args.aab, args.notas, faixa)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
