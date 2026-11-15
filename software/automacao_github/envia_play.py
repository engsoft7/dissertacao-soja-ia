# -*- coding: utf-8 -*-
"""Envia o pacote (.aab) de um Release à Google Play, pela API oficial.

Chamado por publica-apk.yml depois de assinar o pacote, quando o segredo
PLAY_SERVICE_ACCOUNT_JSON está configurado. Sem ele, não faz nada: o Release
continua com o .aab anexado, para o envio manual pelo Play Console.

O que o autor configura uma vez:
  1. No Google Cloud, uma conta de serviço com uma chave em JSON.
  2. No Play Console (Usuários e permissões), essa conta convidada com permissão
     para lançar versões do AgroInteligência.
  3. No GitHub (Settings > Secrets and variables > Actions), o segredo
     PLAY_SERVICE_ACCOUNT_JSON com o conteúdo do JSON e, se quiser outra faixa
     que não a de produção, a variável PLAY_FAIXA (internal, alpha, beta).

A API segue o roteiro do Play Console: abre uma edição, envia o pacote, põe a
versão na faixa com as notas da versão e confirma a edição. Uma falha em
qualquer passo deixa a edição sem confirmar, e nada muda na loja.

Uso:  python envia_play.py ARQUIVO.aab "Notas da versão" [--faixa production]
"""
import argparse
import json
import os
import sys

PACOTE = "com.agrointeligencia.app"
ESCOPO = "https://www.googleapis.com/auth/androidpublisher"
# O Play aceita até 500 caracteres de notas por idioma.
LIMITE_NOTAS = 500


def notas_da_versao(texto: str) -> str:
    """As notas no limite do Play, cortadas numa palavra inteira."""
    texto = " ".join(texto.split())
    if len(texto) <= LIMITE_NOTAS:
        return texto
    corte = texto[: LIMITE_NOTAS - 1].rsplit(" ", 1)[0]
    return corte.rstrip(",;:") + "…"


def envia(aab: str, notas: str, faixa: str, credencial_json: str) -> int:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    cred = service_account.Credentials.from_service_account_info(json.loads(credencial_json), scopes=[ESCOPO])
    api = build("androidpublisher", "v3", credentials=cred, cache_discovery=False)
    edicao = api.edits().insert(packageName=PACOTE, body={}).execute()["id"]
    pacote = api.edits().bundles().upload(
        packageName=PACOTE, editId=edicao,
        media_body=MediaFileUpload(aab, mimetype="application/octet-stream", resumable=True)).execute()
    versao = str(pacote["versionCode"])
    api.edits().tracks().update(packageName=PACOTE, editId=edicao, track=faixa, body={
        "track": faixa,
        "releases": [{"versionCodes": [versao], "status": "completed",
                      "releaseNotes": [{"language": "pt-BR", "text": notas_da_versao(notas)}]}],
    }).execute()
    api.edits().commit(packageName=PACOTE, editId=edicao).execute()
    print(f"Versão {versao} enviada à faixa {faixa} da Google Play.")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("aab")
    ap.add_argument("notas")
    ap.add_argument("--faixa", default=os.environ.get("PLAY_FAIXA") or "production")
    args = ap.parse_args(argv)
    credencial = os.environ.get("PLAY_SERVICE_ACCOUNT_JSON", "")
    if not credencial.strip():
        print("::notice::PLAY_SERVICE_ACCOUNT_JSON não configurado: o .aab fica no Release para o envio manual.")
        return 0
    return envia(args.aab, args.notas, args.faixa, credencial)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
