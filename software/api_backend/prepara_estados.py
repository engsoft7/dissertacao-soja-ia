# -*- coding: utf-8 -*-
"""Deixa os estados prontos para a API subir na hora.

Treina o modelo de cada estado (estados.py), calcula o histórico de cada
município e grava tudo em software/api_backend/cache/<UF>.joblib, que
api.carrega_estado lê na subida. Roda na build do Render (render.yaml) e, à mão:

    cd software/api_backend && python prepara_estados.py [UF ...]

Sem argumento, todos os estados com base no disco. O cache não é versionado:
cada build faz o seu, da base daquele commit.
"""
import sys
import time

import api
import estados


def main(argv: list[str]) -> int:
    ufs = [a.upper() for a in argv] or [e.uf for e in estados.disponiveis()]
    for uf in ufs:
        e = estados.ESTADOS[uf]
        inicio = time.time()
        ce = api.prepara_estado(e)
        print(f"{e.nome}: {len(ce.df)} registros, {len(ce.historicos)} municípios, "
              f"{time.time() - inicio:.0f} s, em {api._arquivo_do_cache(e)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
