# -*- coding: utf-8 -*-
"""Fotografa as três telas do painel num navegador de verdade.

Par das capturas do aplicativo (CapturasDeTelaTest): sobe o painel com a base
do produto, abre cada página da navegação principal e grava em PNG a área de
conteúdo, sem a barra lateral. Roda no workflow capturas.yml, que tem internet
plena; daqui o mapa sai em branco, porque o Leaflet vem de CDN (ver
confere_mapa_no_navegador.py).

Uso:  python capturas_do_painel.py [--porta 8598] [--pasta capturas]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

from confere_mapa_no_navegador import sobe_painel

# Rótulo do item na navegação principal → nome do arquivo.
PAGINAS = {
    "Inteligência Territorial": "painel_territorial",
    "Análise Histórica": "painel_historico",
    "Viabilidade Financeira": "painel_viabilidade",
}


async def espera_parar(pg) -> None:
    """Espera o Streamlit terminar de rodar o roteiro e o desenho assentar."""
    for _ in range(90):
        if await pg.locator('[data-testid="stStatusWidget"]').count() == 0:
            break
        await pg.wait_for_timeout(1000)
    await pg.wait_for_timeout(6000)


async def fotografa(porta: int, pasta: Path) -> int:
    from playwright.async_api import async_playwright

    pasta.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        pronto = os.environ.get("CHROMIUM_EXECUTAVEL")
        nav = await (p.chromium.launch(executable_path=pronto) if pronto
                     else p.chromium.launch())
        # Altura folgada: o conteúdo do Streamlit rola dentro de um contêiner
        # próprio, e a foto de página inteira não o alcança.
        pg = await nav.new_page(viewport={"width": 1440, "height": 3600})
        await pg.goto(f"http://127.0.0.1:{porta}", wait_until="load")
        await pg.wait_for_timeout(15000)
        await espera_parar(pg)

        falhas = 0
        for rotulo, nome in PAGINAS.items():
            opcao = pg.get_by_text(rotulo, exact=False).first
            if not await opcao.count():
                print(f"{nome}: item '{rotulo}' não encontrado na navegação")
                falhas += 1
                continue
            await opcao.click()
            await espera_parar(pg)
            if await pg.locator('[data-testid="stException"]').count():
                print(f"{nome}: a página mostrou exceção")
                falhas += 1
            conteudo = pg.locator('[data-testid="stMainBlockContainer"]').first
            await conteudo.screenshot(path=str(pasta / f"{nome}.png"))
            print(f"{nome}: gravada")
        await nav.close()
    return 1 if falhas else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=8598)
    ap.add_argument("--pasta", default="capturas")
    args = ap.parse_args()

    proc = sobe_painel(args.porta)
    try:
        return asyncio.run(fotografa(args.porta, Path(args.pasta).resolve()))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
