"""Testes de robustez do painel.

Escritos depois de um NameError que derrubou o app publicado em 30/08/2026: o
bloco `except` do simulador financeiro usava CUSTO_REFERENCIA_HA, um nome que só
passa a existir se o `import` dentro do `try` tiver dado certo. Quando o import
falhou, o tratamento de erro quebrou junto e a tela inteira caiu.

Rode com:  python -m pytest software -q
"""
import ast
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


def _constante(arquivo: Path, nome: str) -> float:
    """Lê uma constante numérica de módulo sem importar o arquivo."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
    for no in arvore.body:
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id == nome:
                    return float(ast.literal_eval(no.value))
    raise AssertionError(f"{nome} não encontrado em {arquivo.name}")


def test_custo_de_emergencia_igual_ao_oficial():
    """A cópia literal no painel tem que bater com a fonte da verdade."""
    assert _constante(APP, "CUSTO_OPERACIONAL_PADRAO_HA") == \
        _constante(FINANCAS, "CUSTO_OPERACIONAL_HA")


def test_preco_de_emergencia_igual_ao_oficial():
    """Mesma regra do custo, para o preço de referência da CONAB."""
    assert _constante(APP, "PRECO_RECEBIDO_CONAB_PADRAO_SACA") == \
        _constante(FINANCAS, "PRECO_RECEBIDO_CONAB_SACA")


def test_custo_total_de_emergencia_igual_ao_oficial():
    """Mesma regra do custo operacional, para o custo total."""
    assert _constante(APP, "CUSTO_TOTAL_PADRAO_HA") == \
        _constante(FINANCAS, "CUSTO_TOTAL_HA")


def test_serie_conab_confere_com_o_csv():
    """O painel e o aplicativo afirmam ao usuário que os R$ 105,09 são o menor
    dos 13 levantamentos da praça. A afirmação tem que sair da série extraída da
    CONAB, não da memória de quem escreveu a legenda."""
    import csv
    import statistics

    serie = RAIZ / "pesquisa" / "dados" / "conab" / "serie_pedro_afonso_to.csv"
    with serie.open(encoding="utf-8") as fh:
        precos = [float(linha["Preco Mercado"])
                  for linha in csv.DictReader(fh, delimiter=";")]
    # Levantamentos sem preço divulgado saem como 0,00 na planilha da CONAB;
    # não são cotação e não entram na conta (eram JAN e MAR de 2024).
    precos = [p for p in precos if p > 0]

    assert len(precos) == int(_constante(FINANCAS, "PRECO_SERIE_LEVANTAMENTOS"))
    assert min(precos) == _constante(FINANCAS, "PRECO_SERIE_MENOR_SACA")
    assert max(precos) == _constante(FINANCAS, "PRECO_SERIE_MAIOR_SACA")
    assert round(statistics.median(precos), 2) == \
        _constante(FINANCAS, "PRECO_SERIE_MEDIANA_SACA")
    # O preço padrão do produto é justamente o menor da série. Se um
    # levantamento novo mudar isso, a legenda passa a mentir e o teste avisa.
    assert _constante(FINANCAS, "PRECO_RECEBIDO_CONAB_SACA") == min(precos)


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
