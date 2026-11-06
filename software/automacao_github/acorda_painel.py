# -*- coding: utf-8 -*-
"""
Abre o painel no Streamlit Community Cloud num navegador e o acorda se estiver
dormindo (mantem-painel-acordado.yml).

O Streamlit põe para dormir o app que fica horas sem visita, e quem chega
depois vê "This app has gone to sleep" e espera o app subir de novo. Só conta
como visita uma sessão de verdade, com o JavaScript do Streamlit rodando:
uma consulta HTTP simples não basta. Por isso um navegador sem tela abre a
página, toca no botão de acordar quando ele aparece e espera o painel
desenhar o título.

    python acorda_painel.py [url]

Sai com 1 se o painel não desenhar em 6 minutos.
"""
from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://soja-para.streamlit.app"
TITULO = "AgroInteligência"


def desenhado(pagina) -> bool:
    for quadro in pagina.frames:
        try:
            if quadro.get_by_text(TITULO).count():
                return True
        except Exception:  # quadro que sumiu durante a carga
            continue
    return False


def main() -> int:
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page()
        pagina.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        pagina.wait_for_timeout(8_000)
        botao = pagina.get_by_role("button", name=re.compile("get this app back up", re.I))
        if botao.count():
            print("O painel estava dormindo; acordando.", flush=True)
            botao.first.click()
        else:
            print("O painel já estava acordado.", flush=True)
        ok = False
        for _ in range(36):  # até 6 minutos para o app subir
            if desenhado(pagina):
                ok = True
                break
            pagina.wait_for_timeout(10_000)
        if ok:
            # Fica um pouco com a sessão aberta: é ela que conta como visita.
            pagina.wait_for_timeout(20_000)
        print("Painel desenhado." if ok else "O painel não desenhou em 6 minutos.", flush=True)
        navegador.close()
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
