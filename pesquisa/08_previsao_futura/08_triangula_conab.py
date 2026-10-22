# -*- coding: utf-8 -*-
"""
Triangula a variável-alvo: PAM (IBGE) contra a CONAB, por UF.

Item 4 de TRABALHOS_FUTUROS.md. A CONAB publica só por UF, então o teste
municipal previsto no protocolo (refazer as Tabelas 5 e 6 com outro alvo) não
é possível com ela. O que a escala estadual permite:

  1. Concordância: diferença média e correlação de produtividade entre as duas
     fontes, em nível e em variação de um ano para o outro, em todas as UFs
     com soja relevante, 2001-2025.
  2. Pará: as duas séries sem tendência têm a mesma variabilidade? A hipótese
     subsidiária da dissertação prevê que a PAM, por repetir valores no
     município, varie menos do que uma fonte independente.
  3. Pará: o sinal climático da safra (chuva, EVI máximo, ONI, gradiente do
     Atlântico) aparece mais na CONAB do que na PAM? Correlação de Spearman
     com a anomalia de produtividade de cada fonte, e diferença entre as duas
     com intervalo por reamostragem de safras (exploratório: 24 safras).
  4. Previsões da safra 2025 e 2026 no Pará: levantamentos da CONAB mês a
     mês, a PAM publicada e as projeções registradas nesta pasta.

Uso:  python 08_triangula_conab.py
Saída: triangula_conab.json
"""
import json
import os

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from comum import RAIZ, carrega_base_para, oni
from fases import atlantico

DADOS = os.path.join(RAIZ, 'dados')
ANOS = (2001, 2025)
MIN_AREA_MIL_HA = 100          # UFs com soja relevante na safra mais recente


def series():
    pam = pd.read_csv(os.path.join(DADOS, 'pam_uf.csv'))
    siglas = {11: 'RO', 12: 'AC', 13: 'AM', 14: 'RR', 15: 'PA', 16: 'AP', 17: 'TO', 21: 'MA', 22: 'PI',
              23: 'CE', 24: 'RN', 25: 'PB', 26: 'PE', 27: 'AL', 28: 'SE', 29: 'BA', 31: 'MG', 32: 'ES',
              33: 'RJ', 35: 'SP', 41: 'PR', 42: 'SC', 43: 'RS', 50: 'MS', 51: 'MT', 52: 'GO', 53: 'DF'}
    pam['uf'] = pam.uf_cod.map(siglas)
    con = pd.read_csv(os.path.join(DADOS, 'conab', 'conab_serie_historica_soja.csv'))
    con = con[~con.previsao]
    d = pam.merge(con, on=['uf', 'ano'], suffixes=('', '_conab'))
    d = d[(d.ano >= ANOS[0]) & (d.ano <= ANOS[1]) & (d.rendimento_kg_ha > 0) & (d.produtividade_kg_ha > 0)]
    return d.rename(columns={'rendimento_kg_ha': 'pam', 'produtividade_kg_ha': 'conab'})


def anomalia(s):
    """Resíduo da tendência linear, em % da tendência."""
    t = np.polyval(np.polyfit(s.index, s.values, 1), s.index)
    return pd.Series((s.values / t - 1) * 100, index=s.index)


def concordancia(d):
    ult = d[d.ano == d.ano.max()]
    ufs = sorted(ult[ult.area_colhida_ha / 1000 >= MIN_AREA_MIL_HA].uf)
    out = {}
    for uf in ufs:
        s = d[d.uf == uf].set_index('ano').sort_index()
        dp, dc = s.pam.diff().dropna(), s.conab.diff().dropna()
        out[uf] = {'safras': int(len(s)),
                   'dif_media_produtividade_%': round(float((s.conab / s.pam - 1).mean() * 100), 1),
                   'dif_media_producao_%': round(float((s.producao_mil_t * 1000 / s.producao_t - 1).mean() * 100), 1),
                   'r_nivel': round(float(np.corrcoef(s.pam, s.conab)[0, 1]), 3),
                   'r_variacao_anual': round(float(np.corrcoef(dp, dc)[0, 1]), 3),
                   'dp_anomalia_pam_%': round(float(anomalia(s.pam).std()), 1),
                   'dp_anomalia_conab_%': round(float(anomalia(s.conab).std()), 1)}
    return out


def sinal_climatico(d):
    s = d[d.uf == 'PA'].set_index('ano').sort_index()
    an = pd.DataFrame({'pam': anomalia(s.pam), 'conab': anomalia(s.conab)})
    base = carrega_base_para()
    peso = base.assign(p=base.soy_area_ha)
    clima = peso.groupby('ano').apply(
        lambda g: pd.Series({c: np.average(g[c], weights=g.p) for c in ('precip_total', 'EVI_max')}))
    djf, _ = oni()
    atl = atlantico().set_index('ano')
    x = clima.assign(oni_djf=pd.Series(djf), grad_atl=atl.grad_atl)
    j = an.join(x, how='inner').dropna()
    rng = np.random.default_rng(42)
    out = {'safras': int(len(j)), 'anos': [int(j.index.min()), int(j.index.max())], 'variaveis': {}}
    for v in ('precip_total', 'EVI_max', 'oni_djf', 'grad_atl'):
        rp, pp = spearmanr(j[v], j.pam)
        rc, pc = spearmanr(j[v], j.conab)
        boot = []
        for _ in range(2000):
            k = rng.integers(0, len(j), len(j))
            b = j.iloc[k]
            boot.append(abs(spearmanr(b[v], b.conab)[0]) - abs(spearmanr(b[v], b.pam)[0]))
        out['variaveis'][v] = {'rho_pam': round(float(rp), 3), 'p_pam': round(float(pp), 3),
                               'rho_conab': round(float(rc), 3), 'p_conab': round(float(pc), 3),
                               'dif_abs_rho_conab_menos_pam': round(float(abs(rc) - abs(rp)), 3),
                               'IC95': [round(float(q), 3) for q in np.nanpercentile(boot, [2.5, 97.5])]}
    rr, pr = spearmanr(j.pam, j.conab)
    out['rho_entre_fontes'] = {'rho': round(float(rr), 3), 'p': round(float(pr), 3)}
    return out


def safras_recentes(d):
    lev = pd.read_csv(os.path.join(DADOS, 'conab', 'conab_levantamentos_soja.csv'))
    lev = lev[lev.uf == 'PA'].sort_values(['ano', 'divulgado'])
    with open(os.path.join(RAIZ, 'previsao_producao_para.json'), encoding='utf-8') as f:
        reg = json.load(f)
    with open(os.path.join(RAIZ, 'confere_projecao_2025.json'), encoding='utf-8') as f:
        conf = json.load(f)
    nome = reg['melhor_no_retroteste']
    pa = d[d.uf == 'PA'].set_index('ano')
    out = {}
    for ano in (2025, 2026):
        l = lev[lev.ano == ano]
        out[str(ano)] = {
            'conab_levantamentos_mil_t': {r.divulgado: r.producao_mil_t for r in l.itertuples()},
            'pam_mil_t': round(float(pa.producao_t.get(ano, np.nan)) / 1000, 1) if ano in pa.index else None,
            'projecao_origem_2024_mil_t': {'central': reg['projecao'][nome][str(ano)]['central_t'] / 1000,
                                           'faixa80': [v / 1000 for v in reg['projecao'][nome][str(ano)]['faixa80_t']]},
        }
        if ano == 2026:
            p = conf['novo_registro_origem_2025']['projecao']['2026']
            out['2026']['projecao_origem_2025_mil_t'] = {'central': p['central_t'] / 1000,
                                                         'faixa80': [v / 1000 for v in p['faixa80_t']]}
    return out


def main():
    d = series()
    saida = {'fontes': {'pam': 'IBGE, SIDRA 5457 (dados/pam_uf.csv)',
                        'conab': 'CONAB, série histórica da soja (dados/conab/conab_serie_historica_soja.csv)'},
             'concordancia_por_uf': concordancia(d), 'para_sinal_climatico': sinal_climatico(d),
             'para_safras_recentes': safras_recentes(d)}
    with open(os.path.join(RAIZ, 'triangula_conab.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    pd.set_option('display.width', 200)
    print(pd.DataFrame(saida['concordancia_por_uf']).T.to_string())
    print(json.dumps({k: saida[k] for k in ('para_sinal_climatico', 'para_safras_recentes')}, indent=1,
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
