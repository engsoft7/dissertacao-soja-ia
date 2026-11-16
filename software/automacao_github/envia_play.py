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

Uso:  python envia_play.py ARQUIVO.aab "Notas da versão" [--faixa alpha]
      python envia_play.py --faixas      só lista as faixas do app; não envia nada
"""
import argparse
import json
import os
import sys

PACOTE = "com.agrointeligencia.app"
ESCOPO = "https://www.googleapis.com/auth/androidpublisher"
# O Play aceita até 500 caracteres de notas por idioma.
LIMITE_NOTAS = 500
NOMES = {"production": "produção", "beta": "teste aberto", "alpha": "teste fechado", "internal": "teste interno"}
# Da faixa mais restrita à mais aberta. Uma faixa de nome próprio é um teste fechado.
ORDEM = ["internal", "alpha", "beta", "production"]


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


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("aab", nargs="?")
    ap.add_argument("notas", nargs="?", default="")
    ap.add_argument("--faixa", default=os.environ.get("PLAY_FAIXA") or None,
                    help="a faixa de envio; sem ela, a mais alta em que o app já tem versão")
    ap.add_argument("--faixas", action="store_true", help="só lista as faixas do app na loja")
    args = ap.parse_args(argv)
    credencial = os.environ.get("PLAY_SERVICE_ACCOUNT_JSON", "")
    if not credencial.strip():
        print("::notice::PLAY_SERVICE_ACCOUNT_JSON não configurado: o .aab fica no Release para o envio manual.")
        return 0
    api = cliente(credencial)
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
