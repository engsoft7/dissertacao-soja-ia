# -*- coding: utf-8 -*-
"""
O app de release num Android (emulador do teste-premium.yml), comandado por adb.

Complementa o PercursoNoAparelhoTest, que roda o build de depuração com as
verificações de acessibilidade: aqui é o mesmo código que vai para a loja, com
R8, e o que se mede é o que o produtor sente.

    python teste_aparelho.py <apk> <pasta de saída>

1. Partida a frio (am start -W), na primeira abertura e com o município guardado.
2. Percurso: escolhe Pau D'Arco na lista e passa por todas as abas.
3. Memória (PSS) e fluidez da rolagem (dumpsys gfxinfo: quadros lentos e
   percentis do tempo de quadro).
4. Fonte em 200%, modo escuro, tela pequena, tablet e tela deitada: capturas.
5. Sem internet: o app abre de novo com os dados guardados?
6. Alvos de toque menores que 48 dp e botões sem rótulo, pela árvore de
   acessibilidade de cada tela (uiautomator).
7. Monkey: milhares de toques aleatórios, contando falhas e ANRs.

Grava resultados.json, resumo.md e capturas/*.png na pasta de saída.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PACOTE = "com.agrointeligencia.app"
ATIVIDADE = f"{PACOTE}/.MainActivity"
APK = Path(sys.argv[1])
SAIDA = Path(sys.argv[2])
CAPTURAS = SAIDA / "capturas"
CAPTURAS.mkdir(parents=True, exist_ok=True)

res: dict = {"verificacoes": [], "acessibilidade": {}, "medidas": {}}


def adb(*args: str, timeout: int = 120, check: bool = False) -> str:
    p = subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def sh(cmd: str, timeout: int = 120) -> str:
    return adb("shell", cmd, timeout=timeout)


def verifica(nome: str, ok: bool, detalhe: str = "") -> bool:
    res["verificacoes"].append({"item": nome, "ok": bool(ok), "detalhe": detalhe})
    print(("ok    " if ok else "FALHA ") + nome + (f" ({detalhe})" if detalhe else ""), flush=True)
    return ok


# ── árvore de acessibilidade ────────────────────────────────────────────────
def arvore() -> list[dict]:
    for _ in range(3):
        sh("rm -f /sdcard/ui.xml; uiautomator dump /sdcard/ui.xml >/dev/null 2>&1")
        conteudo = sh("cat /sdcard/ui.xml")
        if conteudo.strip().startswith("<?xml"):
            break
        time.sleep(1)
    else:
        return []
    nos = []

    def visita(e, pai_texto=False):
        b = re.findall(r"\d+", e.get("bounds", "[0,0][0,0]"))
        x1, y1, x2, y2 = map(int, b) if len(b) == 4 else (0, 0, 0, 0)
        filhos = list(e)
        texto_filhos = any((f.get("text") or f.get("content-desc")) for f in e.iter() if f is not e)
        nos.append({
            "texto": e.get("text") or "", "desc": e.get("content-desc") or "",
            "classe": e.get("class") or "", "pacote": e.get("package") or "",
            "clicavel": e.get("clickable") == "true", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "texto_dentro": texto_filhos,
        })
        for f in filhos:
            visita(f)

    try:
        raiz = ET.fromstring(re.sub(r"^\s*<\?xml[^>]*\?>", "", conteudo.strip()))
    except ET.ParseError:
        return []
    visita(raiz)
    return nos


def acha(texto: str, nos: list[dict] | None = None, parcial: bool = True, mais_baixo: bool = False) -> dict | None:
    nos = nos if nos is not None else arvore()
    if parcial:
        cand = [n for n in nos if texto in n["texto"] or texto in n["desc"]]
    else:
        cand = [n for n in nos if n["texto"] == texto or n["desc"] == texto]
    if not cand:
        return None
    return max(cand, key=lambda n: n["y1"]) if mais_baixo else cand[0]


def espera(texto: str, s: int = 60, **kw) -> dict | None:
    fim = time.time() + s
    while time.time() < fim:
        n = acha(texto, **kw)
        if n:
            return n
        time.sleep(1.5)
    return None


def toca_no(n: dict) -> None:
    sh(f"input tap {(n['x1'] + n['x2']) // 2} {(n['y1'] + n['y2']) // 2}")
    time.sleep(1.2)


def toca(texto: str, s: int = 30, **kw) -> bool:
    n = espera(texto, s, **kw)
    if n:
        toca_no(n)
    return n is not None


def aba(nome: str) -> bool:
    # O rótulo da aba é o texto mais baixo da tela com esse nome.
    return toca(nome, 15, parcial=False, mais_baixo=True)


def captura(nome: str) -> None:
    with open(CAPTURAS / f"{nome}.png", "wb") as f:
        subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=f, timeout=60)


def tela(nome: str) -> None:
    """Captura e confere alvos de toque e rótulos da tela atual."""
    time.sleep(1)
    captura(nome)
    nos = [n for n in arvore() if n["pacote"] == PACOTE]
    dp = res["medidas"]["densidade_dpi"] / 160
    pequenos, sem_rotulo = [], []
    for n in nos:
        if not n["clicavel"]:
            continue
        w, h = (n["x2"] - n["x1"]) / dp, (n["y2"] - n["y1"]) / dp
        nome_no = n["texto"] or n["desc"] or n["classe"].split(".")[-1]
        # Um alvo cortado pela borda da tela não é pequeno de verdade.
        cortado = n["y1"] <= 0 or n["y2"] >= res["medidas"]["altura_px"] - 2
        if (w < 47.5 or h < 47.5) and not cortado and w > 0 and h > 0:
            pequenos.append(f"{nome_no} ({w:.0f}×{h:.0f} dp)")
        if not (n["texto"] or n["desc"] or n["texto_dentro"]):
            sem_rotulo.append(f"{n['classe'].split('.')[-1]} em ({n['x1']},{n['y1']})")
    res["acessibilidade"][nome] = {"alvos_pequenos": sorted(set(pequenos)), "sem_rotulo": sorted(set(sem_rotulo))}


def rola(vezes: int, para_cima: bool = False) -> None:
    w, h = res["medidas"]["largura_px"], res["medidas"]["altura_px"]
    a, b = (int(h * 0.75), int(h * 0.30))
    for _ in range(vezes):
        y1, y2 = (b, a) if para_cima else (a, b)
        sh(f"input swipe {w // 2} {y1} {w // 2} {y2} 250")
        time.sleep(0.6)


def abre_frio() -> int | None:
    sh(f"am force-stop {PACOTE}")
    time.sleep(1)
    saida = sh(f"am start -W -n {ATIVIDADE}")
    m = re.search(r"TotalTime:\s*(\d+)", saida)
    return int(m.group(1)) if m else None


def mediana(v: list[int]) -> float | None:
    v = sorted(x for x in v if x is not None)
    return None if not v else (v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2)


def memoria_kb() -> int | None:
    t = sh(f"dumpsys meminfo {PACOTE}")
    m = re.search(r"TOTAL PSS:\s*(\d+)", t) or re.search(r"^\s*TOTAL\s+(\d+)", t, re.M)
    return int(m.group(1)) if m else None


def fluidez() -> dict:
    t = sh(f"dumpsys gfxinfo {PACOTE}")
    def num(rx):
        m = re.search(rx, t)
        return float(m.group(1)) if m else None
    return {"quadros": num(r"Total frames rendered:\s*(\d+)"),
            "lentos_pct": num(r"Janky frames:\s*\d+\s*\(([\d.]+)%\)"),
            "p50_ms": num(r"50th percentile:\s*(\d+)ms"), "p90_ms": num(r"90th percentile:\s*(\d+)ms"),
            "p99_ms": num(r"99th percentile:\s*(\d+)ms")}


def rede(ligada: bool) -> None:
    v = "enable" if ligada else "disable"
    sh(f"svc wifi {v}; svc data {v}")
    time.sleep(4)


def main() -> int:
    m = res["medidas"]
    m["api_level"] = int(sh("getprop ro.build.version.sdk").strip() or 0)
    m["aparelho"] = sh("getprop ro.product.model").strip()
    tam = re.search(r"(\d+)x(\d+)", sh("wm size"))
    m["largura_px"], m["altura_px"] = (int(tam.group(1)), int(tam.group(2))) if tam else (1080, 2400)
    dens = re.findall(r"(\d+)", sh("wm density"))
    m["densidade_dpi"] = int(dens[-1]) if dens else 420
    m["apk_mb"] = round(APK.stat().st_size / 2**20, 1)
    print(f"Android API {m['api_level']}, {m['largura_px']}x{m['altura_px']} {m['densidade_dpi']} dpi", flush=True)

    adb("uninstall", PACOTE)
    adb("install", "-r", str(APK), timeout=300, check=True)
    sh("settings put system font_scale 1.0")
    rede(True)

    # 1. Partida a frio na primeira abertura (sem município guardado).
    m["partida_fria_primeira_ms"] = abre_frio()
    tempos = [abre_frio() for _ in range(4)]
    m["partida_fria_sem_municipio_ms"] = mediana(tempos)
    verifica("abre na tela de boas-vindas", espera("Qual é o seu município?", 150) is not None)
    tela("r01_boas_vindas")

    # 2. Percurso pelas abas, com a API em produção.
    toca("Escolher na lista")
    espera("Buscar pelo nome", 150)
    tela("r02_lista")
    campo = acha("Buscar pelo nome")
    if campo:
        toca_no(campo)
        sh("input text Pau")
        time.sleep(1.5)
    t0 = time.time()
    verifica("acha Pau D'Arco na busca", toca("Pau D'Arco", 30, mais_baixo=True))
    resumo = espera("(safra ", 150)
    m["dados_do_municipio_s"] = round(time.time() - t0, 1)
    verifica("Resumo carrega a safra em curso", resumo is not None, resumo["texto"] if resumo else "")
    verifica("Resumo mostra a última safra do IBGE, 2025", espera("Safra 2025, IBGE", 10) is not None)
    tela("r03_resumo")
    m["memoria_resumo_kb"] = memoria_kb()

    sh(f"dumpsys gfxinfo {PACOTE} reset")
    for i in range(1, 5):
        rola(1)
        tela(f"r04_resumo_{i}")
    rola(6)
    rola(10, para_cima=True)
    m["rolagem_resumo"] = fluidez()

    for i, (nome, espera_por) in enumerate([("Mapa", None), ("Histórico", "kg/ha"), ("Mercado", "Chicago"),
                                            ("Sobre", None)], start=5):
        ok = aba(nome)
        if espera_por:
            espera(espera_por, 60)
        else:
            time.sleep(6)
        verifica(f"abre a aba {nome}", ok)
        tela(f"r{i:02d}_{nome.lower().replace('ó', 'o')}")
        if nome == "Histórico":
            sh(f"dumpsys gfxinfo {PACOTE} reset")
            rola(8)
            rola(8, para_cima=True)
            m["rolagem_historico"] = fluidez()
    m["memoria_depois_das_abas_kb"] = memoria_kb()

    aba("Resumo")
    if toca("Estimativa no campo", 15):
        tela("r09_estimativa_no_campo")
        aba("Resumo")
    if toca("Tempo em", 15):
        espera("Pulverizar", 60)
        tela("r10_tempo")
        aba("Resumo")

    # Com o município guardado, a partida a frio inclui ler o que ficou no celular.
    m["partida_fria_com_municipio_ms"] = mediana([abre_frio() for _ in range(5)])

    # 3. Fonte em 200%.
    sh("settings put system font_scale 2.0")
    abre_frio()
    verifica("fonte 200%: Resumo abre", espera("(safra ", 60) is not None)
    tela("r11_fonte_200")
    rola(2)
    tela("r12_fonte_200_rolado")
    aba("Mercado")
    espera("Chicago", 40)
    tela("r13_fonte_200_mercado")
    sh("settings put system font_scale 1.0")

    # 4. Modo escuro (Android 10+).
    if m["api_level"] >= 29:
        sh("cmd uimode night yes")
        abre_frio()
        espera("(safra ", 60)
        tela("r14_escuro_resumo")
        aba("Histórico")
        espera("kg/ha", 30)
        tela("r15_escuro_historico")
        sh("cmd uimode night no")

    # 5. Tela pequena e tablet.
    for nome, tamanho, dens in [("pequena", "720x1280", 320), ("tablet", "1600x2560", 320)]:
        sh(f"wm size {tamanho}; wm density {dens}")
        time.sleep(2)
        abre_frio()
        verifica(f"tela {nome}: Resumo abre", espera("(safra ", 60) is not None)
        w0, h0, d0 = m["largura_px"], m["altura_px"], m["densidade_dpi"]
        m["largura_px"], m["altura_px"] = map(int, tamanho.split("x"))
        m["densidade_dpi"] = dens
        tela(f"r16_tela_{nome}")
        m["largura_px"], m["altura_px"], m["densidade_dpi"] = w0, h0, d0
        sh("wm size reset; wm density reset")
        time.sleep(2)

    # 6. Tela deitada.
    sh("settings put system accelerometer_rotation 0; settings put system user_rotation 1")
    time.sleep(2)
    abre_frio()
    verifica("tela deitada: Resumo abre", espera("(safra ", 60) is not None)
    captura("r17_deitada")
    sh("settings put system user_rotation 0")
    time.sleep(2)

    # 7. Sem internet.
    rede(False)
    abre_frio()
    verifica("sem internet: Resumo abre com os dados guardados", espera("(safra ", 40) is not None)
    verifica("sem internet: o app avisa", espera("Sem conexão", 10) is not None)
    tela("r18_sem_internet")
    aba("Mapa")
    verifica("sem internet: o Mapa explica", espera("indisponível sem conexão", 15) is not None)
    aba("Mercado")
    time.sleep(4)
    tela("r19_sem_internet_mercado")
    aba("Resumo")
    verifica("sem internet: a Estimativa no campo abre", toca("Estimativa no campo", 15)
             and espera("Conte plantas", 10) is not None)
    rede(True)

    # 8. Monkey.
    adb("logcat", "-c")
    abre_frio()
    espera("(safra ", 60)
    saida = sh(f"monkey -p {PACOTE} --pct-syskeys 0 --pct-appswitch 0 --pct-anyevent 0 "
               "-s 2026 --throttle 120 -v 3000", timeout=900)
    falhas = len(re.findall(r"// CRASH", saida))
    anrs = len(re.findall(r"// NOT RESPONDING|ANR in", saida))
    eventos = re.search(r"Events injected:\s*(\d+)", saida)
    crash_log = adb("logcat", "-d", "-b", "crash")
    m["monkey"] = {"eventos": int(eventos.group(1)) if eventos else None, "falhas": falhas, "anrs": anrs}
    (SAIDA / "monkey.txt").write_text(saida[-20000:] + "\n--- logcat crash ---\n" + crash_log[-20000:])
    verifica("monkey: sem falhas nem ANR", falhas == 0 and anrs == 0 and PACOTE not in crash_log,
             f"{m['monkey']['eventos']} eventos, {falhas} falhas, {anrs} ANR")
    rede(True)
    sh("settings put system font_scale 1.0")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except Exception as e:  # o relatório sai mesmo se um passo quebrar
        verifica("roteiro completo", False, f"{type(e).__name__}: {e}")
        codigo = 1
    finally:
        (SAIDA / "resultados.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        m = res["medidas"]
        linhas = [f"# App de release no Android {m.get('api_level')} ({m.get('aparelho')})", "",
                  "| Verificação | Resultado | Detalhe |", "|---|---|---|"]
        linhas += [f"| {v['item']} | {'ok' if v['ok'] else '**falha**'} | {v['detalhe']} |" for v in res["verificacoes"]]
        linhas += ["", "## Medidas", "", "```", json.dumps(m, ensure_ascii=False, indent=1), "```", "",
                   "## Acessibilidade pela árvore do uiautomator", ""]
        for tela_, a in res["acessibilidade"].items():
            if a["alvos_pequenos"] or a["sem_rotulo"]:
                linhas.append(f"- **{tela_}**: alvos < 48 dp: {', '.join(a['alvos_pequenos']) or 'nenhum'}; "
                              f"sem rótulo: {', '.join(a['sem_rotulo']) or 'nenhum'}")
        (SAIDA / "resumo.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    sys.exit(codigo)
