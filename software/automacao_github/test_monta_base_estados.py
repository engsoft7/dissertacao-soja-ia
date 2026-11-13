"""A safra nova dos outros estados: o que a atualização mensal manda coletar."""
import importlib.util
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("requests")

spec = importlib.util.spec_from_file_location("monta", Path(__file__).with_name("monta_base_estados.py"))
monta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monta)


def test_so_as_safras_depois_da_ultima_coletada():
    assert monta.safras_novas([2023, 2024, 2025, 2026], [2001, 2024, 2025]) == [2026]
    assert monta.safras_novas([2024, 2025], [2001, 2025]) == []
    # Um ano antigo sem coleta (município fora da máscara) não é safra nova.
    assert monta.safras_novas([2001, 2002, 2025], [2002, 2025]) == []
    assert monta.safras_novas([2026, 2027], []) == [2026, 2027]


def test_faltam_le_o_que_esta_no_disco(tmp_path, monkeypatch):
    saida, coleta = tmp_path / "estados", tmp_path / "coleta"
    saida.mkdir()
    coleta.mkdir()
    pd.DataFrame({"cod_ibge7": [1, 1, 1], "ano": [2024, 2025, 2026], "rendimento_kg_ha": [3000, 3100, 3200]}
                 ).to_csv(saida / "pam_soja_MT.csv", index=False)
    pd.DataFrame({"municipio_gaul": ["A", "A"], "ano": [2024, 2025]}).to_csv(coleta / "amazonia_legal_MT.csv", index=False)
    monkeypatch.setattr(monta, "SAIDA", saida)
    monkeypatch.setattr(monta, "COLETA", coleta)
    assert monta.faltam(["MT", "MA"]) == [("MT", 2026)]       # sem a PAM de MA no disco, nada a pedir
    pd.DataFrame({"municipio_gaul": ["A"], "ano": [2026]}).to_csv(coleta / "amazonia_legal_MT_2026.csv", index=False)
    assert monta.faltam(["MT"]) == []
