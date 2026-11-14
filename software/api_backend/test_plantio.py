# -*- coding: utf-8 -*-
"""Janela de plantio (plantio.py): a região certa do calendário para cada
município, as datas dos decêndios do ZARC e a junção das janelas. Um erro aqui
diria ao produtor que ele pode plantar num dia em que a portaria proíbe."""
import csv
import json
from pathlib import Path

import pytest

import plantio


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    plantio.carrega.cache_clear()
    (tmp_path / "calendario_soja_2026_2027.json").write_text(json.dumps({
        "safra": "2026/2027", "fonte": "Portaria SDA/MAPA nº 1.579, de 9 de abril de 2026", "url": "https://dou",
        "estados": {
            "PA": [
                {"regiao": "I", "vazio": ["2026-06-15", "2026-09-15"], "semeadura": ["2026-09-16", "2027-01-14"],
                 "municipios": [1505551], "excecoes": {},
                 "distritos": [{"municipio": 1500602, "texto": "além dos distritos de Cachoeira da Serra e "
                                "Castelo de Sonhos, pertencentes ao município de Altamira"}]},
                {"regiao": "II", "vazio": ["2026-08-01", "2026-10-31"], "semeadura": ["2026-11-01", "2027-02-28"],
                 "municipios": [1505502], "excecoes": {}, "distritos": []},
                {"regiao": "III", "vazio": ["2026-08-15", "2026-11-15"], "semeadura": ["2026-11-16", "2027-03-14"],
                 "municipios": [1500602, 1501402],
                 "excecoes": {"1500602": "exceto os distritos de Cachoeira Grande e Castelo de Sonhos"},
                 "distritos": []},
            ],
            "MT": [{"regiao": None, "vazio": ["2026-06-08", "2026-09-06"], "semeadura": ["2026-09-07", "2027-01-07"],
                    "municipios": None, "excecoes": {}, "distritos": []}],
        }}), encoding="utf-8")
    with open(tmp_path / "zarc_soja_2026_2027.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["uf", "geocodigo", "municipio", "ciclo", "solo", "riscos"])
        w.writerow(["PA", 1505502, "Paragominas", 21, 13, "0" * 30 + "222233"])
        w.writerow(["MT", 5107925, "Sorriso", 21, 13, "0" * 27 + "222222000"])
    (tmp_path / "fontes_plantio.json").write_text(json.dumps({
        "safra": "2026/2027", "lido_em": "2026-11-14",
        "zarc": {"fonte": "Tábua de risco do ZARC", "url": "https://dados", "portarias": {"PA": "Port.203_de_03-07-2026",
                 "MT": "Port.202_de_03-07-2026"}, "ciclos": {"21": "Grupo II"}, "solos": {"13": "AD3"}}}),
        encoding="utf-8")
    yield tmp_path
    plantio.carrega.cache_clear()


def test_municipio_pega_a_regiao_da_lista(pasta):
    d = plantio.para_municipio("PA", 1505502, pasta)
    assert d["calendario"]["regiao"] == "II" and d["calendario"]["semeadura"] == ["2026-11-01", "2027-02-28"]
    assert d["zarc"]["portaria"] == "Portaria nº 203, de 03/07/2026"
    assert d["zarc"]["riscos"]["21-13"].endswith("222233")


def test_distritos_que_seguem_outra_regiao_so_aparecem_para_o_municipio_deles(pasta):
    """Altamira fica na Região III, mas dois distritos seguem a Região I."""
    d = plantio.para_municipio("PA", 1500602, pasta)
    assert d["calendario"]["regiao"] == "III"
    assert d["calendario"]["observacao"] == (
        "Os distritos de Cachoeira da Serra e Castelo de Sonhos seguem a Região I: vazio sanitário de "
        "15/06/2026 a 15/09/2026 e semeadura de 16/09/2026 a 14/01/2027.")
    assert plantio.para_municipio("PA", 1505551, pasta)["calendario"]["observacao"] is None
    assert plantio.para_municipio("PA", 1501402, pasta)["calendario"]["observacao"] is None
    assert plantio.para_municipio("PA", 1505502, pasta)["calendario"]["observacao"] is None


def test_estado_sem_regioes_vale_para_todos(pasta):
    d = plantio.para_municipio("MT", 5107925, pasta)
    assert d["calendario"]["regiao"] is None and d["calendario"]["vazio"] == ["2026-06-08", "2026-09-06"]


def test_municipio_fora_das_listas_e_sem_zarc(pasta):
    """Sem região na lista, o app não inventa uma; sem linha no ZARC, a soja
    não está zoneada ali nesta safra."""
    d = plantio.para_municipio("PA", 1500107, pasta)
    assert d["calendario"] is None and d["zarc"] is None


def test_sem_arquivos_devolve_none(tmp_path):
    plantio.carrega.cache_clear()
    assert plantio.para_municipio("PA", 1505502, tmp_path) is None


def test_decendios_e_virada_do_ano():
    assert plantio.decendio(28, 2026)[0].isoformat() == "2026-10-01"
    assert plantio.decendio(36, 2026)[1].isoformat() == "2026-12-31"
    assert plantio.decendio(1, 2026)[0].isoformat() == "2027-01-01"
    assert plantio.decendio(6, 2026)[1].isoformat() == "2027-02-28"  # 2027 não é bissexto
    assert plantio.decendio(6, 2027)[1].isoformat() == "2028-02-29"


def test_janelas_juntam_decendios_seguidos_e_atravessam_o_ano():
    riscos = ["0"] * 36
    for i in (34, 35, 36, 1, 2):  # dezembro inteiro e começo de janeiro a 20%
        riscos[i - 1] = "2"
    riscos[3 - 1] = "3"
    j = plantio.janelas("".join(riscos), 2026)
    assert j == [{"inicio": "2026-12-01", "fim": "2027-01-20", "risco": 20},
                 {"inicio": "2027-01-21", "fim": "2027-01-31", "risco": 30}]


# ── os arquivos reais da coleta (pesquisa/dados/plantio/), quando já existem ──

@pytest.fixture
def real():
    plantio.carrega.cache_clear()
    if plantio.carrega() is None:
        pytest.skip("sem os arquivos de pesquisa/dados/plantio/ (coleta_plantio.py)")
    yield plantio.carrega()
    plantio.carrega.cache_clear()


def test_cada_municipio_do_para_e_do_maranhao_tem_uma_regiao_so(real):
    """A portaria divide os dois estados em regiões pelas listas das notas; com
    os "demais municípios", cada município cai em exatamente uma."""
    totais = {"PA": 144, "MA": 217}
    for uf, total in totais.items():
        regioes = real["calendario"]["estados"][uf]
        listas = [set(r["municipios"]) for r in regioes]
        assert sum(len(x) for x in listas) == len(set().union(*listas)) == total, uf


def test_datas_da_portaria_nos_municipios_reais(real):
    def cal(uf, cod):
        return plantio.para_municipio(uf, cod)["calendario"]
    assert cal("MT", 5107925)["semeadura"] == ["2026-09-07", "2027-01-07"]            # Sorriso
    assert cal("PA", 1505502)["regiao"] == "II"                                        # Paragominas
    assert cal("PA", 1505502)["semeadura"] == ["2026-11-01", "2027-02-28"]
    assert cal("PA", 1505551)["regiao"] == "I"                                         # Pau D'Arco
    assert cal("MA", 2101400)["regiao"] == "I"                                         # Balsas
    assert cal("MA", 2105708)["regiao"] == "II"                    # Lago da Pedra ("Lagoa da Pedra" no anexo)
    altamira = cal("PA", 1500602)
    assert altamira["regiao"] == "III" and "Castelo de Sonhos" in altamira["observacao"]
    assert "Região I:" in altamira["observacao"]


def test_zarc_real_tem_36_decendios_e_os_tres_grupos(real):
    d = plantio.para_municipio("MT", 5107925)["zarc"]
    assert {c["nome"] for c in d["ciclos"]} == {"Grupo I", "Grupo II", "Grupo III"}
    assert d["riscos"] and all(len(r) == 36 and set(r) <= set("0234") for r in d["riscos"].values())
    assert any(set(r) != {"0"} for r in d["riscos"].values())
