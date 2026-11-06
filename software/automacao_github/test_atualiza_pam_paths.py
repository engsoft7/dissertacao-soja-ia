from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
MOD_PATH = RAIZ / "software" / "automacao_github" / "atualiza_pam.py"
SPEC = spec_from_file_location("atualiza_pam", MOD_PATH)
atualiza_pam = module_from_spec(SPEC)
SPEC.loader.exec_module(atualiza_pam)


def test_csv_painel_path_uses_pesquisa_dados():
    esperado = RAIZ / "pesquisa" / "dados" / "soja_para_painel.csv"
    assert atualiza_pam.CSV_PAINEL == esperado
    assert atualiza_pam.CSV_PAINEL.exists()


def test_data_atualizacao_path_uses_pesquisa_dados():
    esperado = RAIZ / "pesquisa" / "dados" / "ultima_atualizacao.txt"
    assert atualiza_pam.DATA_ATUALIZACAO == esperado


def test_grava_pam_guarda_so_os_municipios_da_base_com_rendimento(tmp_path):
    import pandas as pd

    base = pd.DataFrame({"cod_ibge7": [1505551, 1505551], "ano": [2016, 2017]})
    sidra = pd.DataFrame({
        "cod_ibge7": [1505551, 1505551, 1505551, 1500107],
        "nome_ibge": ["Pau D'Arco - PA"] * 3 + ["Abaetetuba - PA"],
        "ano": [2017, 2025, 2019, 2025],
        "rendimento_kg_ha": [3000.0, 3700.0, 0.0, 2500.0],
    })
    arq = tmp_path / "pam.csv"
    assert atualiza_pam.grava_pam(arq, base, sidra) is True
    assert arq.read_text(encoding="utf-8") == (
        "cod_ibge7,ano,rendimento_kg_ha\n1505551,2017,3000\n1505551,2025,3700\n"
    )
    # Mesmo conteúdo: não regrava, e o PR mensal não sai com diff vazio.
    assert atualiza_pam.grava_pam(arq, base, sidra) is False
    # Revisão do IBGE troca o valor; safra ausente de uma resposta parcial fica.
    parcial = sidra[sidra["ano"] == 2025].assign(rendimento_kg_ha=3650.0)
    assert atualiza_pam.grava_pam(arq, base, parcial) is True
    assert arq.read_text(encoding="utf-8") == (
        "cod_ibge7,ano,rendimento_kg_ha\n1505551,2017,3000\n1505551,2025,3650\n"
    )


def test_pam_versionado_cobre_a_base_com_os_mesmos_valores():
    """As safras da base têm no arquivo oficial o mesmo rendimento."""
    import pandas as pd

    assert atualiza_pam.CSV_PAM == RAIZ / "pesquisa" / "dados" / "pam_soja_para.csv"
    pam = pd.read_csv(atualiza_pam.CSV_PAM)
    base = pd.read_csv(atualiza_pam.CSV_PAINEL)
    juntos = base.merge(pam, on=["cod_ibge7", "ano"], how="left", suffixes=("", "_pam"))
    assert juntos["rendimento_kg_ha_pam"].notna().all()
    assert ((juntos["rendimento_kg_ha"] - juntos["rendimento_kg_ha_pam"]).abs() < 0.5).all()
    assert set(pam["cod_ibge7"]) == set(base["cod_ibge7"])
