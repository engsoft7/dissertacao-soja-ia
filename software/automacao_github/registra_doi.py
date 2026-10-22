# -*- coding: utf-8 -*-
"""
Registra no REGISTRO_INPI.md o DOI que o Zenodo atribui a um Release.

A publicação de um Release dispara o depósito no Zenodo, que leva alguns
minutos para atribuir o DOI de versão. Até aqui alguém copiava o DOI do site do
Zenodo, conferia à mão o resumo criptográfico sobre a etiqueta e editava o
registro. Este script faz as três coisas:

  1. pergunta à API pública do Zenodo, de minuto em minuto, pelas versões do
     DOI de conceito, até aparecer a que tem o nome da etiqueta;
  2. recalcula o resumo criptográfico sobre uma cópia limpa da etiqueta, com o
     mesmo critério do comando da seção 9.1 do registro, e compara com a linha
     da tabela;
  3. só se conferir, troca o "a preencher" pelo DOI e registra a conferência.

O workflow registra-doi.yml abre um PR com a alteração; o merge fica com o
autor, porque o registro é documento formal. Se o resumo não conferir, nada é
alterado e o workflow abre uma issue.

Uso:  python registra_doi.py v2.4.7 [--esperar-min 40]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
from datetime import date
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[2]
REGISTRO = RAIZ / "REGISTRO_INPI.md"
CONCEITO = "21285918"          # DOI de conceito 10.5281/zenodo.21285918
BUSCA = "https://zenodo.org/api/records"
EXTENSOES = (".py", ".kt", ".kts")
FORA = ("/.git/", "/build/", "__pycache__", "/.gradle/")


# ── resumo criptográfico ─────────────────────────────────────────────────────

def resumo(diretorio: Path) -> tuple[int, int, str]:
    """(arquivos, linhas, SHA-256 do conjunto), como o comando da seção 9.1:

        LC_ALL=C find . ( -name '*.py' -o -name '*.kt' -o -name '*.kts' ) \\
          -not -path './.git/*' -not -path '*/build/*' \\
          -not -path '*__pycache__*' -not -path '*/.gradle/*' \\
          | LC_ALL=C sort | xargs sha256sum | sha256sum
    """
    caminhos = []
    for raiz, _, nomes in os.walk(diretorio):
        for nome in nomes:
            if not nome.endswith(EXTENSOES):
                continue
            rel = "./" + os.path.relpath(os.path.join(raiz, nome), diretorio).replace(os.sep, "/")
            if any(f in rel for f in FORA) or rel.startswith("./.git/"):
                continue
            caminhos.append(rel)
    caminhos.sort(key=lambda p: p.encode())           # LC_ALL=C: ordem de bytes
    saida, linhas = [], 0
    for rel in caminhos:
        dados = (diretorio / rel[2:]).read_bytes()
        linhas += dados.count(b"\n")
        saida.append(f"{hashlib.sha256(dados).hexdigest()}  {rel}\n")
    return len(caminhos), linhas, hashlib.sha256("".join(saida).encode()).hexdigest()


def resumo_da_etiqueta(etiqueta: str) -> tuple[int, int, str, str]:
    """Resumo sobre uma cópia limpa da etiqueta, e o commit para onde ela aponta."""
    commit = subprocess.run(["git", "rev-parse", "--short=7", f"{etiqueta}^{{commit}}"], cwd=RAIZ,
                            check=True, capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "copia"
        subprocess.run(["git", "worktree", "add", "--detach", str(copia), etiqueta], cwd=RAIZ,
                       check=True, capture_output=True)
        try:
            return (*resumo(copia), commit)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(copia)], cwd=RAIZ,
                           capture_output=True)


def resumo_registrado(texto: str, etiqueta: str) -> tuple[int, int, str] | None:
    """(arquivos, linhas, hash) da linha da etiqueta na tabela da seção 9.1."""
    m = re.search(r"^\| Tag `" + re.escape(etiqueta) + r"` [^|]*\| (\d+) \| ([\d.]+) \| `([0-9a-f]{64})` \|$",
                  texto, re.M)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2).replace(".", "")), m.group(3)


# ── Zenodo ───────────────────────────────────────────────────────────────────

def doi_da_versao(etiqueta: str, sessao=requests) -> str | None:
    """DOI da versão do conceito cujo nome é a etiqueta, ou None se ainda não há."""
    r = sessao.get(BUSCA, params={"q": f"conceptrecid:{CONCEITO}", "all_versions": "true",
                                  "sort": "newest", "size": 25}, timeout=30)
    r.raise_for_status()
    for reg in r.json().get("hits", {}).get("hits", []):
        versao = (reg.get("metadata") or {}).get("version", "")
        if versao.strip() == etiqueta:
            doi = reg.get("doi") or ((reg.get("pids") or {}).get("doi") or {}).get("identifier")
            if doi:
                return doi
    return None


def espera_doi(etiqueta: str, minutos: int) -> str | None:
    limite = time.time() + minutos * 60
    while True:
        try:
            doi = doi_da_versao(etiqueta)
            if doi:
                return doi
            print(f"Zenodo ainda sem a versão {etiqueta}", flush=True)
        except requests.RequestException as e:
            print(f"Zenodo indisponível ({type(e).__name__}); nova tentativa", flush=True)
        if time.time() > limite:
            return None
        time.sleep(60)


# ── edição do registro ──────────────────────────────────────────────────────

def _reflui(paragrafo: str) -> str:
    return textwrap.fill(" ".join(paragrafo.split()), width=80,
                         break_long_words=False, break_on_hyphens=False)


def registra(texto: str, etiqueta: str, doi: str, commit: str, publicado: str) -> str:
    """Troca o "a preencher" pelo DOI e registra a conferência na etiqueta.

    Levanta ValueError se o registro não tiver os trechos que a preparação de
    versão escreve: melhor parar do que editar o lugar errado.
    """
    ref_antes = f"- **DOI da versão mais recente (`{etiqueta}`):** a preencher após a publicação do Release"
    if texto.count(ref_antes) != 1:
        raise ValueError(f"referência 'a preencher' da {etiqueta} não encontrada")
    texto = texto.replace(ref_antes, f"- **DOI da versão mais recente (`{etiqueta}`):** {doi}")

    blocos = texto.split("\n\n")
    alvo = [i for i, b in enumerate(blocos) if b.startswith(f"O resumo criptográfico da `{etiqueta}`")]
    if len(alvo) != 1:
        raise ValueError(f"parágrafo do resumo criptográfico da {etiqueta} não encontrado")
    par = " ".join(blocos[alvo[0]].split())
    padrao = (r"de modo que o valor deve se manter na etiqueta; (?:como nas anteriores, )?"
              r"convém conferi-lo sobre uma cópia limpa dela depois de etiquetar\.")
    if not re.search(padrao, par):
        raise ValueError(f"parágrafo da {etiqueta} não tem a frase de conferência pendente")
    par = re.sub(padrao, (f"de modo que o valor se mantém na etiqueta. Conferido depois de etiquetar, "
                          f"sobre uma cópia limpa da `{etiqueta}` (commit `{commit}`), pelo workflow "
                          f"`registra-doi.yml`: o valor confere."), par)
    par += (f" O DOI de versão desta etiqueta é {doi}, atribuído pelo Zenodo no depósito disparado "
            f"pela publicação do Release em {publicado}.")
    blocos[alvo[0]] = _reflui(par)
    return "\n\n".join(blocos)


def _saida(**campos):
    caminho = os.environ.get("GITHUB_OUTPUT")
    if caminho:
        with open(caminho, "a", encoding="utf-8") as f:
            for k, v in campos.items():
                f.write(f"{k}={v}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("etiqueta")
    ap.add_argument("--esperar-min", type=int, default=40)
    ap.add_argument("--publicado", default=date.today().strftime("%d/%m/%Y"))
    args = ap.parse_args(argv)
    texto = REGISTRO.read_text(encoding="utf-8")

    registrado = resumo_registrado(texto, args.etiqueta)
    if registrado is None:
        print(f"::error::A tabela da seção 9.1 não tem linha para {args.etiqueta}.")
        _saida(confere="false", motivo="sem linha na tabela")
        return 1
    arquivos, linhas, sha, commit = resumo_da_etiqueta(args.etiqueta)
    print(f"Etiqueta {args.etiqueta} ({commit}): {arquivos} arquivos, {linhas} linhas, {sha}")
    print(f"Registrado:                 {registrado[0]} arquivos, {registrado[1]} linhas, {registrado[2]}")
    if (arquivos, linhas, sha) != registrado:
        print("::error::O resumo criptográfico da etiqueta não confere com o registrado.")
        _saida(confere="false", motivo=f"calculado {arquivos}/{linhas}/{sha}, registrado "
                                       f"{registrado[0]}/{registrado[1]}/{registrado[2]}")
        return 1

    doi = espera_doi(args.etiqueta, args.esperar_min)
    if not doi:
        print(f"::error::O Zenodo não publicou a versão {args.etiqueta} em {args.esperar_min} min.")
        _saida(confere="true", doi="", motivo="DOI não encontrado no prazo")
        return 1
    print(f"DOI da {args.etiqueta}: {doi}")
    REGISTRO.write_text(registra(texto, args.etiqueta, doi, commit, args.publicado), encoding="utf-8")
    _saida(confere="true", doi=doi, commit=commit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
