# -*- coding: utf-8 -*-
"""Leitura dos arquivos de preços da CONAB (coleta_precos_conab.py).

As linhas reproduzem o formato conferido em 16/11/2026 no Actions: campos com
espaços à direita, decimal com vírgula, valor vazio, o nível de comercialização
cortado em 20 caracteres no arquivo semanal e linhas em Latin-1 no meio de
linhas em UTF-8. Um preço lido errado iria para a tela do produtor como preço
da CONAB.
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import coleta_precos_conab as cpc  # noqa: E402

CAB_SEMANAL = ("produto;classificao_produto;id_produto;nom_municipio;cod_ibge;uf;regiao;ano;mes;"
               "data_inicial_final_semana;semana;dsc_nivel_comercializacao;valor_produto_kg")
CAB_MENSAL = "produto;classificao_produto;id_produto;uf;regiao;ano;mes;dsc_nivel_comercializacao;valor_produto_kg"


def _semanal(produto, classif, municipio, ibge, uf, semana, nivel, valor, cod="4744", ano="2026", mes="11",
             enc="utf-8"):
    campos = [f"{produto:<25}", f"{classif:<20}", cod, f"{municipio:<50}", f"{ibge:<30}", f"{uf:<10}",
              f"{'NORTE':<25}", ano, mes, f"{semana:<26}", "1", nivel[:20], valor]
    return ";".join(campos).encode(enc)


def _mensal(produto, classif, uf, ano, mes, nivel, valor, enc="utf-8"):
    campos = [f"{produto:<25}", f"{classif:<20}", "4744", f"{uf:<10}", f"{'NORTE':<15}", ano, mes,
              f"{nivel:<60}", valor]
    return ";".join(campos).encode(enc)


RECEBIDO = "PREÇO RECEBIDO P/ PRODUTOR"
PAGO = "PREÇO PAGO PELO PRODUTOR"


def linhas_semanais():
    return [
        CAB_SEMANAL.encode(),
        # Soja em grão, preço recebido, em Latin-1 (como as linhas reais da soja).
        _semanal("SOJA", "EM GRÃOS", "PARAGOMINAS-PA", "1505502", "PA", "02-11-2026 - 06-11-2026", RECEBIDO,
                 "2,08", enc="latin-1"),
        _semanal("SOJA", "EM GRÃOS", "PARAGOMINAS-PA", "1505502", "PA", "26-10-2026 - 30-10-2026", RECEBIDO,
                 "2,1", mes="10", enc="latin-1"),
        # A mesma, em UTF-8.
        _semanal("SOJA", "EM GRÃOS", "PRIMAVERA DO LESTE-MT", "5107040", "MT", "02-11-2026 - 06-11-2026",
                 RECEBIDO, "1,95"),
        # Sem valor naquela semana.
        _semanal("SOJA", "EM GRÃOS", "BALSAS-MA", "2101400", "MA", "02-11-2026 - 06-11-2026", RECEBIDO, ""),
        # Fora do produto: outro estado, outro produto, outro nível.
        _semanal("SOJA", "EM GRÃOS", "CASCAVEL-PR", "4104808", "PR", "02-11-2026 - 06-11-2026", RECEBIDO, "2,2"),
        _semanal("OLEO DE SOJA", "REFINADO", "BELÉM-PA", "1501402", "PA", "02-11-2026 - 06-11-2026", "VAREJO",
                 "9,59", cod="11871"),
        _semanal("SEMENTE DE SOJA", "INTACTA RR2 PRO", "SORRISO-MT", "5107925", "MT", "02-11-2026 - 06-11-2026",
                 PAGO, "12,0", cod="11764"),
        _semanal("INOCULANTE PARA SOJA", "NÃO INFORMADO", "CAMPO NOVO DO PARECIS-MT", "5102637", "MT",
                 "02-11-2026 - 06-11-2026", PAGO, "4,26", cod="10192", enc="latin-1"),
        b"",
    ]


def linhas_mensais():
    return [
        CAB_MENSAL.encode(),
        _mensal("SOJA", "EM GRÃOS", "PA", "2026", "10", RECEBIDO, "2,09", enc="latin-1"),
        _mensal("SOJA", "EM GRÃOS", "PA", "2026", "9", RECEBIDO, "2,0", enc="latin-1"),
        _mensal("SOJA", "EM GRÃOS", "TO", "2026", "10", RECEBIDO, "1,92"),
        _mensal("OLEO DE SOJA", "REFINADO", "MA", "2026", "10", "VAREJO", "10,18"),
    ]


def test_texto_le_utf8_e_latin1_no_mesmo_arquivo():
    assert cpc.texto("NÃO INFORMADO".encode("utf-8")) == "NÃO INFORMADO"
    # Em Latin-1, o "Ã" é o byte \xc3, que no UTF-8 abre uma sequência: o teste
    # por \xc3 do diagnóstico antigo lia isso como "N�O".
    assert cpc.texto("NÃO INFORMADO".encode("latin-1")) == "NÃO INFORMADO"


def test_normaliza_tira_acento_e_espacos():
    assert cpc.normaliza("  EM GRÃOS   ") == "EM GRAOS"
    assert cpc.normaliza("PREÇO RECEBIDO P/ PR") == "PRECO RECEBIDO P/ PR"


def test_numero_com_virgula_vazio_e_ilegivel():
    assert cpc.numero("2,08") == 2.08
    assert cpc.numero(" 10,0 ") == 10.0
    assert cpc.numero("1.234,5") == 1234.5
    assert cpc.numero("2.08") == 2.08
    assert cpc.numero("") is None
    assert cpc.numero("n/d") is None


def test_semana():
    assert cpc.semana("17-11-2025 - 21-11-2025  ") == (date(2025, 11, 17), date(2025, 11, 21))
    assert cpc.semana("29-12-2025 - 02-01-2026") == (date(2025, 12, 29), date(2026, 1, 2))
    with pytest.raises(ValueError):
        cpc.semana("semana 3")
    with pytest.raises(ValueError):
        cpc.semana("21-11-2025 - 17-11-2025")


def test_nome_municipio():
    assert cpc.nome_municipio("PRIMAVERA DO LESTE-MT       ", "MT") == "Primavera do Leste"
    assert cpc.nome_municipio("SÃO LUÍS-MA", "MA") == "São Luís"
    assert cpc.nome_municipio("ALTA FLORESTA D'OESTE-RO", "RO") == "Alta Floresta D'Oeste"
    assert cpc.nome_municipio("CAMPO NOVO DO PARECIS-MT", "MT") == "Campo Novo do Parecis"
    # Um "E" no começo é nome, não conjunção.
    assert cpc.nome_municipio("ELDORADO DOS CARAJÁS-PA", "PA") == "Eldorado dos Carajás"


def test_semanal_fica_so_com_soja_em_grao_recebida_nos_estados_do_produto():
    semanal, descartes = cpc.semanal_por_municipio(linhas_semanais())
    assert [(l["uf"], l["municipio"], l["inicio"], l["preco_saca"]) for l in semanal] == [
        ("MT", "Primavera do Leste", "2026-11-02", 117.0),
        ("PA", "Paragominas", "2026-10-26", 126.0),
        ("PA", "Paragominas", "2026-11-02", 124.8),
    ]
    assert semanal[-1] == {"uf": "PA", "cod_ibge": "1505502", "municipio": "Paragominas", "inicio": "2026-11-02",
                           "fim": "2026-11-06", "preco_kg": 2.08, "preco_saca": 124.8}
    assert descartes == {"sem valor": 1}


def test_mensal_por_uf():
    mensal, descartes = cpc.mensal_por_uf(linhas_mensais())
    assert [(l["uf"], l["ano"], l["mes"], l["preco_saca"]) for l in mensal] == [
        ("PA", 2026, 9, 120.0), ("PA", 2026, 10, 125.4), ("TO", 2026, 10, 115.2)]
    assert not descartes


def test_cabecalho_diferente_interrompe_a_coleta():
    linhas = linhas_semanais()
    linhas[0] = CAB_SEMANAL.replace(";semana;", ";").encode()
    with pytest.raises(cpc.FormatoNovo, match="cabeçalho"):
        cpc.semanal_por_municipio(linhas)
    with pytest.raises(cpc.FormatoNovo, match="vazio"):
        cpc.mensal_por_uf([b"", b"  "])


def test_preco_fora_da_faixa_e_linha_quebrada_ficam_de_fora():
    linhas = [CAB_SEMANAL.encode(),
              # 0,2 R$/kg = R$ 12/saca: erro de unidade.
              _semanal("SOJA", "EM GRÃOS", "PARAGOMINAS-PA", "1505502", "PA", "02-11-2026 - 06-11-2026",
                       RECEBIDO, "0,2"),
              b"SOJA;EM GRAOS;4744;PARAGOMINAS-PA;1505502;PA",
              _semanal("SOJA", "EM GRÃOS", "PARAGOMINAS-PA", "1505502", "PA", "semana 1", RECEBIDO, "2,0")]
    semanal, descartes = cpc.semanal_por_municipio(linhas)
    assert semanal == []
    assert descartes == {"fora da faixa de R$ 40 a R$ 400 por saca": 1, "linha com outro número de campos": 1,
                         "semana ilegível": 1}


def test_junta_guarda_o_historico_e_aceita_a_revisao():
    antigas = [{"uf": "PA", "cod_ibge": "1505502", "municipio": "Paragominas", "inicio": "2026-01-05",
                "fim": "2026-01-09", "preco_kg": "2.2", "preco_saca": "132"},
               {"uf": "PA", "cod_ibge": "1505502", "municipio": "Paragominas", "inicio": "2026-11-02",
                "fim": "2026-11-06", "preco_kg": "2.1", "preco_saca": "126"}]
    novas, _ = cpc.semanal_por_municipio(linhas_semanais())
    juntas = cpc._ordena_semanal(cpc.junta(antigas, novas, ("uf", "cod_ibge", "inicio")))
    pa = [(l["inicio"], l["preco_saca"]) for l in juntas if l["uf"] == "PA"]
    # A semana de janeiro saiu do arquivo da CONAB e fica; a de novembro foi revisada e troca.
    assert pa == [("2026-01-05", "132"), ("2026-10-26", "126"), ("2026-11-02", "124.8")]


def test_main_grava_os_csvs_e_so_muda_quando_ha_novidade(tmp_path, monkeypatch, capsys):
    fontes = {cpc.URL_SEMANAL: linhas_semanais, cpc.URL_MENSAL: linhas_mensais}
    monkeypatch.setattr(cpc, "baixa", lambda url: iter(fontes[url]()))
    resumo = tmp_path / "resumo.md"
    assert cpc.main(["--saida", str(tmp_path), "--resumo", str(resumo)]) == 0
    saida = capsys.readouterr().out
    assert "Arquivos alterados: precos_soja_semanal_municipio.csv, precos_soja_mensal_uf.csv" in saida
    assert (tmp_path / cpc.ARQ_SEMANAL).read_text(encoding="utf-8").splitlines() == [
        "uf,cod_ibge,municipio,inicio,fim,preco_kg,preco_saca",
        "MT,5107040,Primavera do Leste,2026-11-02,2026-11-06,1.95,117",
        "PA,1505502,Paragominas,2026-10-26,2026-10-30,2.1,126",
        "PA,1505502,Paragominas,2026-11-02,2026-11-06,2.08,124.8",
    ]
    assert (tmp_path / cpc.ARQ_MENSAL).read_text(encoding="utf-8").splitlines() == [
        "uf,ano,mes,preco_kg,preco_saca", "PA,2026,9,2,120", "PA,2026,10,2.09,125.4", "TO,2026,10,1.92,115.2"]
    texto = resumo.read_text(encoding="utf-8")
    assert "| PA | Paragominas | 2 | 26/10/2026 | 02/11/2026 a 06/11/2026 | R$ 124,80 |" in texto
    assert "| TO | 1 | 10/2026 | 10/2026 | R$ 115,20 |" in texto
    # Balsas (MA) veio sem valor: o Maranhão fica sem preço, como Rondônia.
    assert "Sem preço de soja em grão nos arquivos: MA, RO." in texto
    assert "1 sem valor" in texto

    # Segunda coleta igual: nada muda.
    assert cpc.main(["--saida", str(tmp_path)]) == 0
    assert "Arquivos alterados: nenhum" in capsys.readouterr().out


def test_diagnostico_nao_grava(tmp_path, monkeypatch):
    fontes = {cpc.URL_SEMANAL: linhas_semanais, cpc.URL_MENSAL: linhas_mensais}
    monkeypatch.setattr(cpc, "baixa", lambda url: iter(fontes[url]()))
    assert cpc.main(["--diagnostico", "--saida", str(tmp_path)]) == 0
    assert list(tmp_path.iterdir()) == []


def test_sem_nenhuma_soja_a_coleta_falha(monkeypatch):
    monkeypatch.setattr(cpc, "baixa", lambda url: iter([
        (CAB_SEMANAL if url == cpc.URL_SEMANAL else CAB_MENSAL).encode()]))
    with pytest.raises(cpc.FormatoNovo, match="nenhuma linha"):
        cpc.main(["--diagnostico"])


def test_csvs_gravados_no_repositorio_tem_o_formato_esperado():
    """Os CSVs que a coleta automática grava na main: cabeçalho, estados, datas e faixa de preço."""
    pasta = Path(__file__).resolve().parents[2] / "pesquisa" / "dados" / "conab"
    semanal = cpc.le_csv(pasta / cpc.ARQ_SEMANAL)
    mensal = cpc.le_csv(pasta / cpc.ARQ_MENSAL)
    if not semanal and not mensal:
        pytest.skip("a coleta automática ainda não gravou os preços da CONAB")
    for l in semanal:
        assert tuple(l) == cpc.CAMPOS_SEMANAL
        assert l["uf"] in cpc.ESTADOS and len(l["cod_ibge"]) == 7
        assert date.fromisoformat(l["inicio"]) <= date.fromisoformat(l["fim"])
        assert cpc.PRECO_MIN <= float(l["preco_saca"]) <= cpc.PRECO_MAX
    for l in mensal:
        assert tuple(l) == cpc.CAMPOS_MENSAL
        assert l["uf"] in cpc.ESTADOS and 1 <= int(l["mes"]) <= 12
        assert cpc.PRECO_MIN <= float(l["preco_saca"]) <= cpc.PRECO_MAX
