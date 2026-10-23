"""Grava as respostas reais da API para as capturas de tela do aplicativo.

As capturas (CapturasDeTelaTest) desenhavam as telas com uma série inventada,
boa para conferir o leiaute mas imprópria para mostrar o produto a alguém: o
histórico de Paragominas que aparecia não era o de Paragominas. Este script
sobe a API no próprio processo, sem servidor nem rede para o Render, pede as
mesmas rotas que o aplicativo pede e grava cada resposta em JSON na pasta que
o teste lê. A rota de mercado consulta o Yahoo Finance; quando ele não
responde, o arquivo não é gravado e o teste volta aos dados de exemplo só
naquela tela.

Uso: python software/automacao_github/dados_das_capturas.py [município]
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "software" / "aplicativo_mobile" / "app" / "build" / "dados_capturas"

sys.path.insert(0, str(RAIZ / "software" / "api_backend"))


def main(municipio: str = "Paragominas") -> None:
    from fastapi.testclient import TestClient
    import api

    DESTINO.mkdir(parents=True, exist_ok=True)
    with TestClient(api.app) as cliente:
        rotas = {
            "previsao": f"/api/previsao/{municipio}",
            "financas": f"/api/financas/{municipio}",
            "mercado": "/api/mercado?periodo=1mo",
        }
        for nome, rota in rotas.items():
            resposta = cliente.get(rota)
            dados = resposta.json() if resposta.status_code == 200 else None
            if nome == "mercado" and dados and not dados.get("cotacao"):
                dados = None
            if dados is None:
                print(f"{nome}: sem dados ({resposta.status_code}), a captura usa o exemplo")
                (DESTINO / f"{nome}.json").unlink(missing_ok=True)
                continue
            (DESTINO / f"{nome}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            print(f"{nome}: gravado")


if __name__ == "__main__":
    main(*sys.argv[1:2])
