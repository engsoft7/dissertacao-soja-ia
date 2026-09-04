"""Testes de robustez do painel.

Escritos depois de um NameError que derrubou o app publicado em 30/08/2026: o
bloco `except` do simulador financeiro usava CUSTO_REFERENCIA_HA, um nome que só
passa a existir se o `import` dentro do `try` tiver dado certo. Quando o import
falhou, o tratamento de erro quebrou junto e a tela inteira caiu.

Rode com:  python -m pytest software -q
"""
import ast
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "software" / "dashboard_web" / "app.py"
FINANCAS = RAIZ / "software" / "api_backend" / "financas.py"
REQUISITOS = RAIZ / "software" / "dashboard_web" / "requirements.txt"


def _nomes_ligados(corpo):
    """Nomes que só existem se o corpo do try rodar até o fim."""
    ligados = set()
    for no in corpo:
        for x in ast.walk(no):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                ligados.add(x.id)
            elif isinstance(x, (ast.Import, ast.ImportFrom)):
                for a in x.names:
                    ligados.add((a.asname or a.name).split(".")[0])
            elif isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                ligados.add(x.name)
    return ligados


def _nomes_lidos(corpo):
    lidos = set()
    for no in corpo:
        for x in ast.walk(no):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load):
                lidos.add(x.id)
    return lidos


def test_tratamento_de_erro_nao_depende_do_try():
    """Nenhum `except` pode ler um nome que só o `try` cria."""
    problemas = []
    for arquivo in sorted((RAIZ / "software").rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Try):
                continue
            ligados = _nomes_ligados(no.body)
            for tratador in no.handlers:
                risco = sorted(ligados & _nomes_lidos(tratador.body))
                if risco:
                    rel = arquivo.relative_to(RAIZ)
                    problemas.append(f"{rel}:{tratador.lineno} usa {risco}")
    assert not problemas, "except depende de nome criado no try: " + "; ".join(problemas)


def test_tratamento_de_erro_nao_depende_do_try():
    """Nenhum `except` pode ler um nome que só o `try` cria."""
    problemas = []
    for arquivo in sorted((RAIZ / "software").rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Try):
                continue
            ligados = _nomes_ligados(no.body)
            for tratador in no.handlers:
                risco = sorted(ligados & _nomes_lidos(tratador.body))
                if risco:
                    rel = arquivo.relative_to(RAIZ)
                    problemas.append(f"{rel}:{tratador.lineno} usa {risco}")
    assert not problemas, "except depende de nome criado no try: " + "; ".join(problemas)


def _constante(arquivo: Path, nome: str) -> float:
    """Lê uma constante numérica de módulo sem importar o arquivo."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
    for no in arvore.body:
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id == nome:
                    return float(ast.literal_eval(no.value))
    raise AssertionError(f"{nome} não encontrado em {arquivo.name}")


def test_levantamento_e_reservas_conferem_com_os_csv():
    """O produto inteiro tem que descrever um único levantamento da CONAB.

    Preço, custo, praça, data e a frase que situa o preço na série saem de
    pesquisa/dados/conab/levantamento_atual.json, gerado dos CSVs da extração.
    financas.py e app.py guardam uma cópia literal do mesmo levantamento, para
    subirem com números corretos se o arquivo não chegar ao deploy — e é aí que
    mora o risco: uma cópia defasada faz painel e API afirmarem preços
    diferentes sem ninguém perceber. Este teste roda a mesma conferência do CI.
    """
    sys.path.insert(0, str(RAIZ / "software" / "automacao_github"))
    import gera_levantamento_conab as gerador

    assert gerador.main(["--conferir"]) == 0, (
        "levantamento_atual.json ou as reservas de emergência estão defasados "
        "em relação aos CSVs da CONAB. Rode "
        "`python software/automacao_github/gera_levantamento_conab.py`.")


def test_preco_e_custo_saem_do_mesmo_levantamento():
    """A regra que a versão anterior quebrou ao exibir Chicago como porteira.

    O gerador tem que recusar um preço de um levantamento com o custo de outro,
    inclusive no caso real em que a CONAB publica custo sem divulgar preço — o
    0,00 da planilha não é cotação.
    """
    import csv

    sys.path.insert(0, str(RAIZ / "software" / "automacao_github"))
    import gera_levantamento_conab as gerador

    serie = gerador.ler_serie()
    com_preco = [l for l in serie if l["preco_recebido_saca"] > 0]
    adotado = com_preco[-1]

    lev = json.loads(gerador.SAIDA.read_text(encoding="utf-8"))
    assert lev["levantamento"] == adotado["levantamento"]
    assert lev["preco_recebido_saca"] == round(adotado["preco_recebido_saca"], 2)
    assert lev["custo_variavel_saca"] == round(adotado["custo_variavel_saca"], 2)
    assert lev["custo_fixo_saca"] == round(adotado["custo_fixo_saca"], 2)

    # E o custo por saca do levantamento adotado tem que ser o mesmo da
    # planilha por município, senão os dois CSVs vieram de extrações
    # diferentes.
    with (RAIZ / "pesquisa" / "dados" / "conab" /
          "custo_variavel_e_produtividade_por_municipio.csv").open(encoding="utf-8") as fh:
        por_municipio = {l["Municipio.Municipio"].strip('"').upper():
                         float(l["Custo Variavel Unid Comercializacao(R$)"])
                         for l in csv.DictReader(fh, delimiter=";")}
    assert por_municipio[lev["praca_csv"]] == lev["custo_variavel_saca"]


def test_reserva_vale_quando_o_levantamento_some():
    """A rede de segurança precisa funcionar, não só existir.

    Se o JSON não chegar ao deploy, API e painel têm que subir com os números
    do levantamento em vigor, e não quebrar nem servir zero — foi um NameError
    no caminho de erro que tirou o painel do ar em 30/08/2026.
    """
    sys.path.insert(0, str(RAIZ / "software" / "api_backend"))
    import financas

    original = financas.LEVANTAMENTO_JSON
    try:
        financas.LEVANTAMENTO_JSON = Path("/caminho/que/nao/existe.json")
        reserva = financas._carregar_levantamento()
    finally:
        financas.LEVANTAMENTO_JSON = original

    lev = json.loads((RAIZ / "pesquisa" / "dados" / "conab" /
                      "levantamento_atual.json").read_text(encoding="utf-8"))
    assert reserva["preco_recebido_saca"] == lev["preco_recebido_saca"]
    assert reserva["custo_operacional_ha"] == lev["custo_operacional_ha"]
    assert reserva["textos"]["descricao"] == lev["textos"]["descricao"]


def test_requisitos_declaram_o_que_financas_importa():
    """O painel importa financas.py; o que financas.py usa precisa estar no
    requirements.txt do painel, e não só como dependência transitiva."""
    declarados = {
        linha.split("=")[0].split(">")[0].split("<")[0].split("[")[0].strip().lower()
        for linha in REQUISITOS.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    }
    arvore = ast.parse(FINANCAS.read_text(encoding="utf-8"), filename=str(FINANCAS))
    faltando = []
    for no in arvore.body:
        if isinstance(no, ast.Import):
            modulos = [a.name.split(".")[0] for a in no.names]
        elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
            modulos = [no.module.split(".")[0]]
        else:
            continue
        for m in modulos:
            if m not in sys.stdlib_module_names and m.lower() not in declarados:
                faltando.append(m)
    assert not faltando, f"ausentes em dashboard_web/requirements.txt: {faltando}"
