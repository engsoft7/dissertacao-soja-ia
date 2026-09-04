import json
from datetime import date
from pathlib import Path

import requests

REV_MUNICIPIOS = {
    "Goianesia Do Para": "GOIANESIA DO PARA",
    "Dom Eliseu": "DOM ELISEU",
    "Ulianopolis": "ULIANOPOLIS",
    "Paragominas": "PARAGOMINAS",
    "Rondon Do Para": "RONDON DO PARA",
    "Santana Do Araguaia": "SANTANA DO ARAGUAIA",
    "Conceicao Do Araguaia": "CONCEICAO DO ARAGUAIA",
    "Redencao": "REDENCAO",
}

# ── LEVANTAMENTO DA CONAB: PREÇO E CUSTO ─────────────────────────────────────
# Fonte: CONAB, Custos de Produção — Soja, município de Pedro Afonso (TO),
# ponto de coleta da CONAB no cerrado do Tocantins. O Pará não integra o
# MATOPIBA e não tem custo de soja levantado, por isso adota-se o cerrado
# vizinho, conforme registrado em software/dashboard_web/README.md e na
# subseção 4.9 da dissertação.
#
# Preço e custo NÃO são literais aqui. Saem de
# pesquisa/dados/conab/levantamento_atual.json, gerado dos CSVs da extração por
# software/automacao_github/gera_levantamento_conab.py e atualizado pelo
# workflow mensal. Antes eram oito literais espalhados por este arquivo, por
# app.py, por MainActivity.kt e por três READMEs, com a data do levantamento
# escrita por extenso em cada legenda — atualizar a CONAB exigia editar tudo e
# recompilar o APK, o que na prática significava não atualizar.
#
# A CONAB publica o custo POR SACA COMERCIALIZADA; a conversão para hectare usa
# a produtividade de referência do próprio levantamento (2.880 kg/ha, ou
# 48 sc/ha, em março de 2026) e é feita pelo gerador.
#
# Usa-se o custo OPERACIONAL, variável mais fixo, que é o que a CONAB define
# como tal e o que o campo "Custo Operacional" da interface representa. Para
# simular só o desembolso de custeio, trocar por CUSTO_VARIAVEL_HA.
#
# Valor único para todos os municípios: a tabela anterior trazia sete valores
# escalonados a partir do preço da terra (correlação de 0,985 com o VTN), o que
# não tem base agronômica — fertilizante e defensivo não custam mais onde o
# hectare é mais caro.
LEVANTAMENTO_JSON = (Path(__file__).resolve().parents[2] /
                     "pesquisa" / "dados" / "conab" / "levantamento_atual.json")

# Reserva de emergência, com o levantamento de março de 2026, para a API e o
# painel subirem com números corretos caso o arquivo não chegue ao deploy. Não
# é uma segunda fonte da verdade: test_robustez_painel.py confere que continua
# idêntica ao JSON, e quebra se alguém atualizar um sem o outro.
# reserva-conab-inicio (reescrita por gera_levantamento_conab.py)
LEVANTAMENTO_RESERVA = {
    "praca": "Pedro Afonso (TO)",
    "praca_csv": "PEDRO AFONSO-TO",
    "levantamento": "MAR-2026",
    "levantamento_extenso": "março de 2026",
    "fonte": "https://portaldeinformacoes.conab.gov.br/custos-de-producao.html",
    "gerado_por": "software/automacao_github/gera_levantamento_conab.py",
    "preco_recebido_saca": 105.09,
    "custo_variavel_saca": 85.03,
    "custo_fixo_saca": 24.91,
    "custo_operacional_saca": 109.94,
    "renda_fatores_saca": 9.12,
    "custo_total_saca": 119.06,
    "margem_liquida_saca": -4.85,
    "produtividade_referencia_kg_ha": 2880.0,
    "produtividade_referencia_sc_ha": 48.0,
    "custo_variavel_ha": 4081.44,
    "custo_operacional_ha": 5277.12,
    "custo_total_ha": 5714.88,
    "renda_fatores_ha": 437.76,
    "serie": {
        "levantamentos": 13,
        "periodo": "março de 2023 a março de 2026",
        "periodo_curto": "mar/2023 a mar/2026",
        "menor_saca": 105.09,
        "menor_levantamento": "MAR-2026",
        "menor_levantamento_extenso": "março de 2026",
        "maior_saca": 146.35,
        "maior_levantamento": "MAR-2023",
        "maior_levantamento_extenso": "março de 2023",
        "mediana_saca": 116.91,
        "media_saca": 118.89,
        "posicao_do_atual": 1,
        "levantamentos_negativos": [
            "MAI-2023",
            "MAR-2026"
        ]
    },
    "levantamentos_sem_preco": [],
    "textos": {
        "descricao": "CONAB, Pedro Afonso (TO), março de 2026",
        "nota_preco": "R$ 105,09/sc é o menor dos 13 levantamentos da praça (mar/2023 a mar/2026, mediana R$ 116,91). Cenário conservador, não previsão de preço.",
        "nota_custo": "Custo operacional de R$ 109,94/sc, convertido para R$ 5.277,12/ha pela produtividade de referência do próprio levantamento (2.880 kg/ha, 48 sc/ha)."
    }
}
# reserva-conab-fim

# Campos sem os quais o resto do módulo não tem o que calcular.
_OBRIGATORIOS = ("preco_recebido_saca", "custo_variavel_ha",
                 "custo_operacional_ha", "custo_total_ha",
                 "levantamento_extenso", "praca", "serie", "textos")
_OBRIGATORIOS_SERIE = ("levantamentos", "menor_saca", "maior_saca",
                       "mediana_saca", "posicao_do_atual", "periodo_curto")


def _carregar_levantamento() -> dict:
    """Lê o levantamento do disco e cai na reserva se faltar ou vier quebrado.

    Nunca levanta exceção: este módulo é importado na subida da API e do
    painel, e um JSON ilegível não pode derrubar os dois — foi um NameError no
    tratamento de erro do painel que tirou o app do ar em 30/08/2026.
    """
    try:
        dados = json.loads(LEVANTAMENTO_JSON.read_text(encoding="utf-8"))
        faltando = [c for c in _OBRIGATORIOS if c not in dados]
        faltando += [f"serie.{c}" for c in _OBRIGATORIOS_SERIE
                     if c not in dados.get("serie", {})]
        if faltando:
            raise KeyError(", ".join(faltando))
    except Exception as e:
        print(f"[financas] levantamento da CONAB indisponivel "
              f"({type(e).__name__}: {e}); usando a reserva de "
              f"{LEVANTAMENTO_RESERVA['levantamento_extenso']}", flush=True)
        return dict(LEVANTAMENTO_RESERVA)
    return dados


LEVANTAMENTO = _carregar_levantamento()

CUSTO_VARIAVEL_HA    = LEVANTAMENTO["custo_variavel_ha"]
CUSTO_OPERACIONAL_HA = LEVANTAMENTO["custo_operacional_ha"]
CUSTO_TOTAL_HA       = LEVANTAMENTO["custo_total_ha"]
CUSTO_REFERENCIA_HA  = CUSTO_OPERACIONAL_HA

# ── PREÇO RECEBIDO PELO PRODUTOR ─────────────────────────────────────────────
# Coluna "preço recebido" do mesmo levantamento. É preço de PORTEIRA, que é o
# que entra na conta da margem.
#
# Não se usa Paranaguá nem Chicago como referência: Paranaguá é preço de porto
# no Paraná e o CBOT é bolsa em dólar; ambos ficam acima do que o produtor
# recebe no Pará, onde ainda se descontam frete e base. Os dois continuam sendo
# consultados e exibidos como comparação, nunca como padrão da simulação.
#
# Usar o preço da mesma praça de onde vem o custo mantém a conta internamente
# consistente: receita e custo saem do mesmo levantamento. O gerador garante
# isso — se a CONAB publicar custo novo sem divulgar preço, ele fica no último
# levantamento com cotação em vez de misturar dois momentos.
PRECO_RECEBIDO_CONAB_SACA = LEVANTAMENTO["preco_recebido_saca"]
CUSTO_OPERACIONAL_CONAB_SACA = LEVANTAMENTO["custo_operacional_saca"]
PRODUTIVIDADE_REFERENCIA_SC = LEVANTAMENTO["produtividade_referencia_sc_ha"]


# ── IDADE DO LEVANTAMENTO ────────────────────────────────────────────────────
# A pergunta que este bloco responde: se alguém abrir este produto daqui a dois
# anos, ele vai exibir o preço de 2026 como se fosse o de hoje?
#
# Sem isto, sim. O levantamento é um arquivo estático; a automação depende de
# alguém manter o repositório, e o usuário do aplicativo não vê issue nenhuma.
# O número simplesmente envelhece calado, que é o pior comportamento possível
# para um valor que dirige quase toda a margem exibida.
#
# A idade é calculada A CADA LEITURA, e nunca gravada no JSON: um número
# congelado na geração já nasce errado no dia seguinte. Assim o produto se
# denuncia sozinho, sem rede, sem manutenção e sem depender de ninguém.
MESES_SIGLA = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
               "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}

# A CONAB publica custos de produção da soja a cada dois meses. Uma defasagem
# de até quatro meses é a cadência normal somada ao atraso de publicação, e não
# merece alarme. A partir daí, provavelmente já existe levantamento mais novo.
MESES_PARA_AVISAR = 5
MESES_PARA_ALERTAR = 12


def meses_desde_o_levantamento(hoje: date | None = None) -> int | None:
    """Meses entre o levantamento em uso e hoje. None se o rótulo não for lido."""
    rotulo = str(LEVANTAMENTO.get("levantamento", ""))
    sigla, _, ano = rotulo.partition("-")
    if sigla.upper() not in MESES_SIGLA or not ano.isdigit():
        return None
    hoje = hoje or date.today()
    return (hoje.year - int(ano)) * 12 + (hoje.month - MESES_SIGLA[sigla.upper()])


def aviso_de_defasagem(hoje: date | None = None) -> str | None:
    """Frase a exibir quando o levantamento está velho, ou None se está em dia.

    Servida pela API para o aplicativo poder exibi-la sem recompilar, e montada
    aqui para painel e aplicativo dizerem exatamente a mesma coisa.
    """
    meses = meses_desde_o_levantamento(hoje)
    if meses is None or meses < MESES_PARA_AVISAR:
        return None
    quando = LEVANTAMENTO.get("levantamento_extenso", "data desconhecida")
    if meses < MESES_PARA_ALERTAR:
        return (f"Este levantamento é de {quando}, há {meses} meses. A CONAB "
                f"publica a cada dois meses, então provavelmente já há um mais "
                f"recente — confira antes de decidir por este preço.")
    anos = meses // 12
    tempo = "mais de um ano" if anos == 1 else f"mais de {anos} anos"
    return (f"Este levantamento é de {quando}, há {meses} meses ({tempo}). "
            f"Trate o preço como referência histórica, não como cotação atual, "
            f"e edite o campo com o preço que você recebe hoje.")


def descricao_do_levantamento() -> str:
    """'CONAB, Pedro Afonso (TO), março de 2026'."""
    return LEVANTAMENTO["textos"]["descricao"]


def nota_sobre_o_preco() -> str:
    """Onde o preço padrão está na série histórica da praça.

    O preço adotado é oficial, mas em março de 2026 era o MENOR dos 13
    levantamentos desde março de 2023 — e a margem por hectare é quase toda
    dirigida por ele. Sem esta frase o usuário lê o padrão como "o preço da
    soja" quando ele pode ser o piso do triênio.

    A frase é escrita pelo gerador, junto com os números, e servida por esta
    função à interface: quando o levantamento muda, o texto muda junto, sem
    recompilar o aplicativo.
    """
    return LEVANTAMENTO["textos"]["nota_preco"]


def nota_sobre_o_custo() -> str:
    """Custo por saca, custo por hectare e a produtividade que os liga."""
    return LEVANTAMENTO["textos"]["nota_custo"]


# ── VALOR DA TERRA NUA ───────────────────────────────────────────────────────
# Fonte: Receita Federal, Tabela de Valores de Terra Nua do exercício 2026,
# publicada em 07/08/2026 e reenviada corrigida em 21/08/2026. O PDF nacional e
# a extração dos municípios paraenses estão em pesquisa/dados/receita_federal/.
#
# A tabela publica seis valores por município, por classe de aptidão agrícola.
# Usa-se "Lavoura — Aptidão Boa", que é a classe da soja. As demais (aptidão
# regular e restrita, pastagem, silvicultura, preservação) são menores e não
# descrevem área de lavoura tecnificada.
#
# A Receita Federal publica VTN para 13 dos 38 municípios da base. Para os
# demais não há valor oficial, e a interface informa isso em vez de estimar.
VTN_LAVOURA_APTIDAO_BOA = {
    "ALTAMIRA": 6552.64,
    "BREU BRANCO": 17500.00,
    "CUMARU DO NORTE": 6519.09,
    "FLORESTA DO ARAGUAIA": 6947.65,
    "MARABA": 8900.00,
    "NOVO PROGRESSO": 3693.95,
    "PARAGOMINAS": 4564.00,
    "REDENCAO": 8672.24,
    "RIO MARIA": 5076.41,
    "SANTANA DO ARAGUAIA": 7061.84,
    "SAO FELIX DO XINGU": 5930.09,
    "ULIANOPOLIS": 4006.79,
    "XINGUARA": 7438.01,
}

def get_custos_locais(municipio: str):
    """VTN vem como None quando a Receita Federal não publica o município,
    para a interface dizer isso em vez de exibir número estimado."""
    mun = REV_MUNICIPIOS.get(municipio, municipio).upper()
    return {"custo_ha": CUSTO_REFERENCIA_HA,
            "vtn_ha": VTN_LAVOURA_APTIDAO_BOA.get(mun)}

def get_financas(municipio: str):
    headers = {'User-Agent': 'Mozilla/5.0'}
    brl_price_bag = 120.0
    try:
        r_cbot = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/ZS=F',
                              headers=headers, timeout=8)
        price_cents = r_cbot.json()['chart']['result'][0]['meta']['regularMarketPrice']
        usd_price_bag = (price_cents / 100) * 2.20462
        
        r_usd = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/BRL=X',
                             headers=headers, timeout=8)
        usd_brl = float(r_usd.json()['chart']['result'][0]['meta']['regularMarketPrice'])
        brl_price_bag = round(usd_price_bag * usd_brl, 2)
    except Exception as e:
        print("Erro online financas:", e, flush=True)
        pass

    raw_municipio = REV_MUNICIPIOS.get(municipio, municipio)
    custos = get_custos_locais(raw_municipio)
    
    custo_ha = custos["custo_ha"]
    
    return {
        # referência da simulação: preço de porteira da CONAB
        "soja_preco_saca": PRECO_RECEBIDO_CONAB_SACA,
        # cotação de bolsa, só para comparação na interface
        "soja_preco_cbot_saca": brl_price_bag,
        "custo_ha": custo_ha,
        "vtn_ha": custos["vtn_ha"],
        "margem_ebitda_estimada": 0.0,
        "risco_direto": "MODERADO"
    }
