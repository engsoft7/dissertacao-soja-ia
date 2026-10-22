from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
SPEC = spec_from_file_location("atualiza_enso", RAIZ / "software" / "automacao_github" / "atualiza_enso.py")
atualiza_enso = module_from_spec(SPEC)
SPEC.loader.exec_module(atualiza_enso)

TRIM = atualiza_enso.TRIMESTRES


def oni(valores):
    """Texto no formato da NOAA a partir de {ano: [12 anomalias, DJF a NDJ]}."""
    linhas = ["SEAS  YR   TOTAL   ANOM"]
    for ano, anoms in valores.items():
        linhas += [f"{t} {ano} 27.00 {a}" for t, a in zip(TRIM, anoms)]
    return "\n".join(linhas)


def test_el_nino_que_comeca_no_meio_do_ano_marca_a_safra_seguinte():
    # La Niña fraca no verão de 2022/23 (3 trimestres, não é episódio) e
    # El Niño a partir de maio de 2023 que dura até o verão de 2023/24.
    d = atualiza_enso.processar_oni(oni({
        2023: [-0.4, -0.3, -0.1, 0.2, 0.5, 0.8, 1.1, 1.3, 1.6, 1.8, 1.9, 2.0],
        2024: [1.8, 1.5, 1.1, 0.7, 0.4, 0.2, 0.0, -0.1, -0.2, -0.3, -0.4, -0.5],
    }))
    assert 2023 not in d["el_ninos"]
    assert 2024 in d["el_ninos"]


def test_menos_de_cinco_trimestres_nao_e_episodio():
    d = atualiza_enso.processar_oni(oni({
        2001: [-0.6, -0.6, -0.5, -0.5, -0.3, -0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        2002: [0.0] * 12,
    }))
    assert d["la_ninas"] == [] and d["el_ninos"] == []


def test_sequencia_no_fim_dos_dados_fica_provisoria():
    d = atualiza_enso.processar_oni(oni({
        2025: [0.0] * 10 + [0.6, 0.7],
        2026: [0.8, 0.7] + [0.0] * 10,
    }))
    assert 2026 not in d["el_ninos"]          # 4 trimestres e terminou: não é episódio
    d = atualiza_enso.processar_oni(oni({2025: [0.0] * 10 + [0.6, 0.7]}) + "\nDJF 2026 27.0 0.8")
    assert d["el_ninos"] == [2026]
    assert d["historico_detalhado"]["2026"]["provisoria"] is True


def test_arquivo_versionado_segue_a_regra():
    import json
    d = json.loads((RAIZ / "pesquisa" / "dados" / "eventos_enso.json").read_text(encoding="utf-8"))
    for ano, det in d["historico_detalhado"].items():
        fase = det["classificacao"]
        assert (int(ano) in d["el_ninos"]) == (fase == "El Niño")
        assert (int(ano) in d["la_ninas"]) == (fase == "La Niña")
        if fase != "Neutro":
            assert abs(det["oni_djf"]) >= atualiza_enso.LIMIAR
