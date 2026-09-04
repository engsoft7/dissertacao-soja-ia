# -*- coding: utf-8 -*-
"""
Cotações físicas diárias da soja, por praça.

Por que existe: o preço padrão do produto vem do levantamento da CONAB, que é
bimestral. Preço de soja muda todo dia, então nenhum valor de levantamento
chega atualizado ao usuário. O painel já lia uma cotação diária, mas só de
Paranaguá — porto no Paraná, longe do que o produtor paraense enfrenta.

Este módulo generaliza aquela leitura para uma LISTA de praças, com as do
corredor do Pará na frente. A técnica de extração é a mesma que já roda em
produção: varrer as células da linha da praça e aceitar o primeiro número que
se pareça com preço em reais dentro de uma faixa plausível. Não se confia em
posição de coluna, porque a tabela da fonte muda de formato de tempos em
tempos, e uma coluna de variação ("-2,15") ou um total em milhares não pode
entrar no lugar da cotação.

O que este módulo NÃO faz: transformar cotação de porto em preço de porteira.
Barcarena e Miritituba são terminais; entre eles e a fazenda ainda há frete e
base. A praça de cada valor é sempre devolvida junto, para a interface poder
dizer de onde o número veio em vez de apresentá-lo como "o preço".
"""
from __future__ import annotations

import re
import urllib.request

# Faixa plausível para uma saca de 60 kg em reais. Serve para descartar
# variação percentual, volume e qualquer outro número da mesma linha.
PRECO_SACA_MIN, PRECO_SACA_MAX = 60.0, 400.0

FONTE_NOTICIAS_AGRICOLAS = "https://www.noticiasagricolas.com.br/cotacoes/soja/"

# Praças procuradas, em ordem de preferência. As do Pará vêm primeiro por
# serem as mais próximas da realidade de quem usa o produto; as demais entram
# como comparação e como rede de segurança quando nenhuma do Norte aparecer.
#
# A lista é intencionalmente maior do que se espera encontrar: o coletor
# relata TODAS as praças que localizou, e é assim que se descobre o que a
# fonte realmente publica, sem precisar adivinhar daqui.
PRACAS = (
    ("Barcarena", "PA", "porto"),
    ("Miritituba", "PA", "terminal"),
    ("Itaituba", "PA", "terminal"),
    ("Santarém", "PA", "porto"),
    ("Paragominas", "PA", "interior"),
    ("Redenção", "PA", "interior"),
    ("Marabá", "PA", "interior"),
    ("Balsas", "MA", "interior"),
    ("Porto Franco", "MA", "interior"),
    ("Uruçuí", "PI", "interior"),
    ("Barreiras", "BA", "interior"),
    ("Sorriso", "MT", "interior"),
    ("Rondonópolis", "MT", "interior"),
    ("Paranaguá", "PR", "porto"),
    ("Rio Grande", "RS", "porto"),
)


def _valor_na_linha(html: str, inicio: int) -> float | None:
    """Primeiro número plausível de preço na linha de tabela que começa aqui."""
    linha = html[inicio:inicio + 800].split("</tr>")[0]
    for celula in re.findall(r"<td[^>]*>(.*?)</td>", linha, re.DOTALL):
        texto = re.sub(r"<[^>]+>", " ", celula)
        for numero in re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto):
            valor = float(numero.replace(".", "").replace(",", "."))
            if PRECO_SACA_MIN <= valor <= PRECO_SACA_MAX:
                return valor
    return None


def extrair_precos(html: str) -> list[dict]:
    """Cotações encontradas na página, na ordem de preferência de PRACAS.

    Devolve lista de {praca, uf, tipo, valor}. Praça que aparece na página sem
    número plausível na linha fica de fora: melhor não ter cotação do que ter
    uma coluna errada.
    """
    achados = []
    for nome, uf, tipo in PRACAS:
        for ocorrencia in re.finditer(re.escape(nome), html, re.IGNORECASE):
            valor = _valor_na_linha(html, ocorrencia.end())
            if valor is not None:
                achados.append({"praca": nome, "uf": uf, "tipo": tipo,
                                "valor": valor})
                break
    return achados


def buscar_precos(url: str = FONTE_NOTICIAS_AGRICOLAS) -> list[dict]:
    """Busca e extrai. Lista vazia quando a fonte não responde ou não bate.

    Nunca devolve valor de reserva: exibir um número inventado como se fosse
    cotação do dia é pior que não exibir cotação nenhuma.
    """
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        bruto = urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        print(f"[precos] fonte indisponivel: {type(e).__name__}: {e}", flush=True)
        return []
    for codec in ("utf-8", "latin-1"):
        try:
            return extrair_precos(bruto.decode(codec))
        except UnicodeDecodeError:
            continue
    return []


def preferida(precos: list[dict]) -> dict | None:
    """A cotação mais próxima da realidade do usuário do produto.

    PRACAS já está em ordem de preferência e extrair_precos a preserva, então
    é a primeira da lista. Fica como função para o critério ter um nome e um
    lugar só, em vez de um [0] espalhado por quem chama.
    """
    return precos[0] if precos else None


def descricao(preco: dict) -> str:
    """'Barcarena (PA), porto' — para a interface dizer de onde veio o número."""
    return f"{preco['praca']} ({preco['uf']}), {preco['tipo']}"


if __name__ == "__main__":  # diagnóstico manual e no GitHub Actions
    encontrados = buscar_precos()
    if not encontrados:
        print("::warning::nenhuma cotação reconhecida na fonte.")
        raise SystemExit(1)
    print(f"{len(encontrados)} praça(s) encontradas, na ordem de preferência:")
    for p in encontrados:
        print(f"  {descricao(p):<34} R$ {p['valor']:.2f}/sc")
    escolhida = preferida(encontrados)
    print(f"\nadotada: {descricao(escolhida)} — R$ {escolhida['valor']:.2f}/sc")
