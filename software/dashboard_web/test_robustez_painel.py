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


def _funcoes_do_painel(nomes: tuple[str, ...], constantes: tuple[str, ...],
                      extras: dict) -> dict:
    """Extrai funções e constantes de app.py e as executa isoladas.

    O painel não pode ser importado num teste: o corpo do módulo é um script
    Streamlit que desenha a página inteira. As funções puras, porém, precisam
    ser exercitadas de verdade — não basta conferir que existem.

    As constantes vêm do PRÓPRIO app.py, e nunca são injetadas por `extras`.
    A primeira versão deste ajudante recebia os limiares de financas.py, e com
    isso o teste do espelho passava mesmo com os limiares do painel alterados —
    ou seja, não testava nada.
    """
    fonte = APP.read_text(encoding="utf-8")
    arvore = ast.parse(fonte, filename=str(APP))
    espaco = dict(extras)
    for nome in constantes:
        assert nome not in extras, (
            f"{nome} tem que vir de app.py, não ser injetada pelo teste")
    for no in arvore.body:
        if isinstance(no, ast.Assign) and any(
                isinstance(a, ast.Name) and a.id in constantes for a in no.targets):
            exec(compile(ast.Module([no], []), str(APP), "exec"), espaco)
        elif isinstance(no, ast.FunctionDef) and no.name in nomes:
            exec(compile(ast.Module([no], []), str(APP), "exec"), espaco)
    faltando = [n for n in nomes + constantes if n not in espaco]
    assert not faltando, f"não encontrei em app.py: {faltando}"
    return espaco


def test_produto_denuncia_levantamento_velho():
    """A pergunta é: aberto daqui a dois anos, o produto exibe o preço de 2026
    como se fosse o de hoje?

    Não pode. O levantamento é um arquivo estático e a automação depende de
    alguém manter o repositório; o usuário do aplicativo não vê issue nenhuma.
    A idade tem que ser calculada na leitura, nunca gravada, para o produto se
    denunciar sozinho sem rede e sem manutenção.
    """
    from datetime import date

    sys.path.insert(0, str(RAIZ / "software" / "api_backend"))
    import financas

    lev = json.loads((RAIZ / "pesquisa" / "dados" / "conab" /
                      "levantamento_atual.json").read_text(encoding="utf-8"))
    sigla, _, ano = lev["levantamento"].partition("-")
    mes = financas.MESES_SIGLA[sigla.upper()]
    publicado = date(int(ano), mes, 1)

    def somar_meses(base, n):
        total = base.month - 1 + n
        return date(base.year + total // 12, total % 12 + 1, 1)

    # Na cadência normal da CONAB (publica a cada dois meses), silêncio.
    assert financas.aviso_de_defasagem(somar_meses(publicado, 2)) is None
    assert financas.aviso_de_defasagem(somar_meses(publicado, 4)) is None
    # Passada a cadência, o produto avisa.
    aviso = financas.aviso_de_defasagem(somar_meses(publicado, 6))
    assert aviso and "provavelmente já há um mais recente" in aviso
    # Dois anos depois, o alerta muda de tom e manda editar o campo.
    dois_anos = financas.aviso_de_defasagem(somar_meses(publicado, 24))
    assert dois_anos and "referência histórica" in dois_anos
    assert "mais de 2 anos" in dois_anos


def test_painel_e_api_avisam_com_as_mesmas_palavras():
    """O painel espelha a função de financas.py porque não pode depender de
    importá-lo. Espelho que diverge é pior que espelho nenhum: as duas telas do
    mesmo produto passariam a descrever o preço de formas diferentes."""
    from datetime import date

    sys.path.insert(0, str(RAIZ / "software" / "api_backend"))
    import financas

    painel = _funcoes_do_painel(
        nomes=("meses_desde_o_levantamento", "aviso_de_defasagem"),
        constantes=("MESES_SIGLA_CONAB", "MESES_PARA_AVISAR_CONAB",
                    "MESES_PARA_ALERTAR_CONAB"),
        extras={"LEVANTAMENTO_CONAB": financas.LEVANTAMENTO, "date": date})

    for quando in (date(2026, 3, 1), date(2026, 7, 1), date(2026, 9, 4),
                   date(2027, 3, 1), date(2028, 9, 4), date(2031, 1, 1)):
        assert painel["meses_desde_o_levantamento"](quando) == \
            financas.meses_desde_o_levantamento(quando), quando
        assert painel["aviso_de_defasagem"](quando) == \
            financas.aviso_de_defasagem(quando), quando


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
            # Módulo vizinho no mesmo diretório não é dependência a declarar:
            # viaja junto com o próprio arquivo. É o caso de precos.py, que
            # financas.py importa.
            local = (FINANCAS.parent / f"{m}.py").exists()
            if (m not in sys.stdlib_module_names and not local
                    and m.lower() not in declarados):
                faltando.append(m)
    assert not faltando, f"ausentes em dashboard_web/requirements.txt: {faltando}"

def test_sinal_do_resultado_avisa_quando_depende_do_rateio():
    """A CONAB publica o custo por saca sem abrir por item, e acima da
    produtividade de referência os dois rateios possíveis discordam sobre lucro
    ou prejuízo. Pintar um deles de verde é dar por decidido o que o dado não
    decide — e quem decide com isso é o produtor, no talhão."""
    import json as _json

    lev = _json.loads((RAIZ / "pesquisa" / "dados" / "conab" /
                       "levantamento_atual.json").read_text(encoding="utf-8"))
    painel = _funcoes_do_painel(
        nomes=("resultado_por_hectare",),
        constantes=(),
        extras={"LEVANTAMENTO_CONAB": lev})
    calcular = painel["resultado_por_hectare"]
    preco = lev["preco_recebido_saca"]
    prod_ref = lev["produtividade_referencia_sc_ha"]

    # Na produtividade de referência os dois rateios coincidem, por construção:
    # é exatamente ali que o custo por saca vezes as sacas dá o custo por
    # hectare publicado.
    valor, outro, incerto = calcular(prod_ref, preco)
    assert outro is not None
    assert abs(valor - outro) < 0.01
    assert not incerto

    # Acima dela, com margem estreita, o sinal se inverte.
    valor, outro, incerto = calcular(52.0, preco)
    assert incerto, "a 52 sc/ha os dois rateios discordam e o teste tem que ver isso"
    assert valor > 0 > outro

    # Com custo informado pelo produtor não há rateio a discutir.
    valor, outro, incerto = calcular(52.0, preco, 4000.0)
    assert outro is None and not incerto
    assert abs(valor - (52.0 * preco - 4000.0)) < 0.01
