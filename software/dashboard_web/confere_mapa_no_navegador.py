# -*- coding: utf-8 -*-
"""Abre o painel num navegador de verdade e confere se o mapa desenha.

Existe porque o ambiente de desenvolvimento não alcança cdn.jsdelivr.net —
negado por política de rede — e é de lá que o folium carrega o Leaflet em tempo
de execução. Daqui, portanto, o mapa nunca desenha, e não há como distinguir
"bloqueio da rede" de "o mapa quebrou". No runner do GitHub Actions, que tem
internet plena, a distinção é possível: se o mapa não desenhar lá, o defeito é
do painel.

A frase que o painel exibe — "o mapa não usa camada de terceiros em tempo de
execução" — continua verdadeira: ela fala dos ladrilhos, e as geometrias vêm de
arquivos versionados em pesquisa/dados/. Mas a biblioteca que os desenha vem de
CDN, e é isso que este roteiro verifica.

Uso:  python confere_mapa_no_navegador.py [--porta 8599] [--foto mapa.png]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent

# Onde o Leaflet põe o que desenha. São vários porque o renderizador varia: as
# camadas vetoriais podem sair como <path> no painel de sobreposição ou como um
# <canvas> só, e os círculos dos municípios podem vir como marcador. Contar um
# seletor só já me fez chamar de defeito o que era seletor errado.
SELETORES = (".leaflet-interactive",
             ".leaflet-overlay-pane path",
             ".leaflet-overlay-pane canvas",
             ".leaflet-marker-icon")


def sobe_painel(porta: int) -> subprocess.Popen:
    """Sobe o Streamlit e espera ele responder."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", str(porta), "--server.headless", "true",
         "--server.address", "127.0.0.1",
         "--browser.gatherUsageStats", "false"],
        cwd=AQUI, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(90):
        if proc.poll() is not None:
            print(proc.stdout.read() if proc.stdout else "")
            raise SystemExit("o painel morreu antes de responder")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{porta}/", timeout=2) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    raise SystemExit("o painel não respondeu em 90 s")


async def confere(porta: int, foto: Path) -> int:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # No CI o navegador vem de `playwright install`. Em máquinas que já
        # trazem um Chromium pronto, CHROMIUM_EXECUTAVEL aponta para ele e
        # poupa o download.
        pronto = os.environ.get("CHROMIUM_EXECUTAVEL")
        nav = await (p.chromium.launch(executable_path=pronto) if pronto
                     else p.chromium.launch())
        pg = await nav.new_page(viewport={"width": 1440, "height": 1200})
        bloqueados: list[str] = []
        pg.on("requestfailed",
              lambda r: bloqueados.append(f"{r.failure} {r.url[:90]}"))

        await pg.goto(f"http://127.0.0.1:{porta}", wait_until="load")
        # A primeira carga treina o modelo; o mapa só vem depois disso.
        await pg.wait_for_timeout(15000)
        for _ in range(40):
            if await pg.locator('[data-testid="stStatusWidget"]').count() == 0:
                break
            await pg.wait_for_timeout(1000)
        await pg.wait_for_timeout(5000)

        problemas = []
        excecoes = await pg.locator('[data-testid="stException"]').count()
        if excecoes:
            problemas.append(f"{excecoes} bloco(s) de exceção na página")

        quadro = next((f for f in pg.frames if "folium" in f.url), None)
        if quadro is None:
            problemas.append("o componente do mapa não foi montado")
        else:
            mapas = await quadro.locator(".leaflet-container").count()
            # Espera o desenho parar de crescer: o contorno do estado aparece
            # antes da malha municipal, e conferir cedo demais aprova um mapa
            # pela metade.
            medida, estavel = {}, 0
            for _ in range(25):
                agora = {sel: await quadro.locator(sel).count() for sel in SELETORES}
                estavel = estavel + 1 if agora == medida else 0
                medida = agora
                if estavel >= 3 and sum(medida.values()):
                    break
                await pg.wait_for_timeout(1000)
            print(f"leaflet-container: {mapas}")
            for sel, n in medida.items():
                print(f"  {sel:32} {n}")
            desenhado = sum(medida.values())
            if not mapas:
                problemas.append("o Leaflet não montou dentro do componente")
            elif not desenhado:
                problemas.append("o Leaflet montou, mas não desenhou geometria")

        await pg.screenshot(path=str(foto), full_page=True)
        print(f"foto: {foto}")
        if bloqueados:
            print(f"recursos que falharam ({len(bloqueados)}):")
            for b in bloqueados[:8]:
                print("  ", b)
        await nav.close()

    if problemas:
        print("\nREPROVADO:")
        for p_ in problemas:
            print("  -", p_)
        return 1
    print("\nOK: o mapa desenhou.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=8599)
    ap.add_argument("--foto", default="mapa_no_navegador.png")
    args = ap.parse_args()

    import asyncio
    proc = sobe_painel(args.porta)
    try:
        return asyncio.run(confere(args.porta, Path(args.foto).resolve()))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
