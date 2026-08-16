from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
MOD_PATH = RAIZ / "software" / "automacao_github" / "atualiza_pam.py"
SPEC = spec_from_file_location("atualiza_pam", MOD_PATH)
atualiza_pam = module_from_spec(SPEC)
SPEC.loader.exec_module(atualiza_pam)


def test_csv_painel_path_uses_pesquisa_dados():
    esperado = RAIZ / "pesquisa" / "dados" / "soja_para_mascarado_2001_2024.csv"
    assert atualiza_pam.CSV_PAINEL == esperado
    assert atualiza_pam.CSV_PAINEL.exists()


def test_data_atualizacao_path_uses_pesquisa_dados():
    esperado = RAIZ / "pesquisa" / "dados" / "ultima_atualizacao.txt"
    assert atualiza_pam.DATA_ATUALIZACAO == esperado
