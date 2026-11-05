# -*- coding: utf-8 -*-
"""
Rede recorrente (LSTM) sobre séries de 16 dias no estudo de caso do Pará.

A conclusão da dissertação registra que o Pará ficou sem séries intra-safra e
que a LSTM só pôde ser avaliada no recorte nacional (11_lstm_series_mensais.py
de 03_analise_nacional). As séries existem desde a coleta de
08_previsao_futura/coleta/coleta_fases_gee.py: 17 composições do MODIS
MOD13Q1 (EVI e NDVI sob a máscara de soja do MapBiomas), de meados de outubro
ao fim de junho, e o clima diário de CHIRPS e ERA5-Land, na média do
município. Aqui elas viram uma sequência de 17 passos por município-safra,
cada passo com EVI, NDVI e o clima dos 16 dias que a composição cobre
(chuva somada; temperaturas média, mínima e máxima; radiação;
evapotranspiração potencial; umidade do solo nas duas camadas).

Protocolo, o da Tabela 6 (03_busca_hiperparametros.py), importado de lá:
- mesma base (415 registros; 414 com as 17 composições), mesmo alvo;
- leave-one-year-out nas safras com pelo menos 4 municípios;
- a rede aprende a correção sobre o modelo de referência (média do município
  + tendência), como os demais modelos da tabela;
- busca aninhada: a configuração de cada safra externa é escolhida em 4
  safras internas do próprio treino, sem olhar a safra de teste;
- 5 sementes por configuração final, com a média das 5 previsões.

O modelo de referência e o SVR da Tabela 6 são refeitos nos mesmos 414
registros, para a comparação não misturar amostras.

CRITÉRIO, FIXADO ANTES DE RODAR: a LSTM acrescenta algo se o intervalo de 95%
do ganho de habilidade sobre a referência, 1 − MSE(LSTM)/MSE(referência), por
reamostragem de safras inteiras, ficar inteiro acima de zero.

Uso:  python 09_lstm_series_para.py          (~20 min em CPU)
Saída: lstm_series_para.json
"""
import importlib.util
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, '..', '..'))
PREV = os.path.join(REPO, 'pesquisa', '08_previsao_futura')
sys.path.insert(0, PREV)
from comum import ganho_sobre_referencia  # noqa: E402

spec = importlib.util.spec_from_file_location('busca', os.path.join(AQUI, '03_busca_hiperparametros.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.DADOS = os.path.join(REPO, 'pesquisa', 'dados')

PASSOS = 17
CLIMA = ['precip_mm', 'tmean', 'tmin', 'tmax', 'srad', 'etp', 'sw1', 'sw2']
VAR = ['evi', 'ndvi'] + CLIMA
CONFIGS = [{'oculto': h, 'dropout': d, 'lr': lr} for h in (16, 32) for d in (0.2, 0.4) for lr in (1e-3, 3e-3)]
SEMENTES, EPOCAS, N_INTERNAS = 5, 300, 4
torch.set_num_threads(2)


def sequencias(base):
    """Tensor [registros, 17, 10] na ordem de `base`, e a máscara de quem tem as 17 composições."""
    dados = os.path.join(PREV, 'dados')
    v = pd.read_csv(os.path.join(dados, 'gee_vegetacao_16d.csv'), parse_dates=['data'])
    c = pd.read_csv(os.path.join(dados, 'gee_clima_diario.csv.gz'), parse_dates=['data'])
    c['tmean'], c['tmin'], c['tmax'] = c.tmean_k - 273.15, c.tmin_k - 273.15, c.tmax_k - 273.15
    c['srad'], c['etp'] = c.srad_j / 1e6, -c.etp_m * 1000   # MJ/m² e mm (o ERA5 dá evaporação negativa)
    for d in (v, c):
        d['safra'] = np.where(d.data.dt.month >= 8, d.data.dt.year + 1, d.data.dt.year)
    v = v.sort_values(['cod_ibge7', 'safra', 'data'])
    v['passo'] = v.groupby(['cod_ibge7', 'safra']).cumcount()
    v = v[v.passo < PASSOS]
    # clima de cada passo: os 16 dias a partir da data da composição
    janelas = v[['cod_ibge7', 'safra', 'passo', 'data']]
    cl = c.merge(janelas.rename(columns={'data': 'inicio'}), on=['cod_ibge7', 'safra'])
    cl = cl[(cl.data >= cl.inicio) & (cl.data < cl.inicio + pd.Timedelta(days=16))]
    agg = {k: 'mean' for k in CLIMA}
    agg['precip_mm'], agg['etp'] = 'sum', 'sum'
    cl = cl.groupby(['cod_ibge7', 'safra', 'passo']).agg(agg).reset_index()
    t = v.merge(cl, on=['cod_ibge7', 'safra', 'passo'], how='left')
    t['evi'], t['ndvi'] = t.evi / 1e4, t.ndvi / 1e4
    X = np.full((len(base), PASSOS, len(VAR)), np.nan)
    pos = {(int(cod), int(a)): i for i, (cod, a) in enumerate(zip(base.cod_ibge7, base.ano))}
    for r in t.itertuples():
        i = pos.get((int(r.cod_ibge7), int(r.safra)))
        if i is not None:
            X[i, r.passo] = [getattr(r, k) for k in VAR]
    completo = ~np.isnan(X).any(axis=(1, 2))
    return X, completo


class Rede(nn.Module):
    def __init__(self, n_var, oculto, dropout):
        super().__init__()
        self.lstm = nn.LSTM(n_var, oculto, batch_first=True)
        self.saida = nn.Sequential(nn.Dropout(dropout), nn.Linear(oculto, 1))

    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.saida(h[-1]).squeeze(-1)


def treina_preve(cfg, Xtr, rtr, Xte, semente):
    """Ajusta a correção sobre a referência (resíduo padronizado) e prevê o resíduo do teste."""
    mu, sd = Xtr.reshape(-1, Xtr.shape[-1]).mean(0), Xtr.reshape(-1, Xtr.shape[-1]).std(0) + 1e-6
    ym, ys = rtr.mean(), rtr.std() + 1e-6
    torch.manual_seed(semente)
    rede = Rede(Xtr.shape[-1], cfg['oculto'], cfg['dropout'])
    opt = torch.optim.Adam(rede.parameters(), lr=cfg['lr'], weight_decay=1e-4)
    xt = torch.tensor((Xtr - mu) / sd, dtype=torch.float32)
    yt = torch.tensor((rtr - ym) / ys, dtype=torch.float32)
    rede.train()
    for _ in range(EPOCAS):
        opt.zero_grad()
        perda = nn.functional.mse_loss(rede(xt), yt)
        perda.backward()
        opt.step()
    rede.eval()
    with torch.no_grad():
        p = rede(torch.tensor((Xte - mu) / sd, dtype=torch.float32)).numpy()
    return p * ys + ym


def previsao(cfg, X, y, anos, mun, tr, te, sementes):
    b_tr = m.referencia(y, anos, mun, tr, tr)
    b_te = m.referencia(y, anos, mun, tr, te)
    r = np.mean([treina_preve(cfg, X[tr], y[tr] - b_tr, X[te], s) for s in sementes], axis=0)
    return b_te + r


def main():
    t0 = time.time()
    base = m.carrega()
    X, completo = sequencias(base)
    df = base[completo].reset_index(drop=True)
    X = X[completo]
    y, anos, mun, Xtab, safras = m._matrizes(df)
    print(f'{len(df)} registros com as {PASSOS} composições; {len(safras)} safras de teste', flush=True)

    obs, ref, lstm, svr, escolhas = [], [], [], [], []
    svr_cfg = {'C': 100.0, 'epsilon': 0.1, 'gamma': 0.05}    # configuração modal da Tabela 6
    for ty in safras:
        te, tr = anos == ty, anos != ty
        internas = [a for a in sorted(set(anos[tr])) if (anos[tr] == a).sum() >= m.MIN_MUN][-N_INTERNAS:]
        erros = []
        for cfg in CONFIGS:
            e = []
            for ti in internas:
                tr_i, te_i = tr & (anos != ti), anos == ti
                p = previsao(cfg, X, y, anos, mun, tr_i, te_i, [0])
                e.append(np.mean((y[te_i] - p) ** 2))
            erros.append(np.mean(e))
        cfg = CONFIGS[int(np.argmin(erros))]
        escolhas.append(cfg)
        obs.append(y[te])
        ref.append(m.referencia(y, anos, mun, tr, te))
        lstm.append(previsao(cfg, X, y, anos, mun, tr, te, range(SEMENTES)))
        svr.append(m.preve('SVR', svr_cfg, Xtab, y, anos, mun, tr, te))
        print(f'  {ty}: {cfg}  ({time.time() - t0:.0f} s)', flush=True)

    aa = np.concatenate([anos[anos == t] for t in safras])
    obs, ref, lstm, svr = map(np.concatenate, (obs, ref, lstm, svr))
    saida = {
        'nota': ('Gerado por 09_lstm_series_para.py: LSTM sobre 17 composições de 16 dias (EVI, NDVI e clima), '
                 'correção sobre a referência, leave-one-year-out com busca aninhada, 5 sementes. '
                 f'Versões: torch {torch.__version__}.'),
        'registros': int(len(df)), 'safras': [int(s) for s in safras],
        'referencia': m.metricas(obs, ref, y.mean()),
        'svr_tabela6_mesmos_registros': {**m.metricas(obs, svr, y.mean()), **ganho_sobre_referencia(obs, svr, ref, aa)},
        'lstm': {**m.metricas(obs, lstm, y.mean()), **ganho_sobre_referencia(obs, lstm, ref, aa)},
        'lstm_sobre_svr': ganho_sobre_referencia(obs, lstm, svr, aa),
        'configs': CONFIGS,
        'escolhas': [CONFIGS.index(c) for c in escolhas],
        'segundos': round(time.time() - t0),
    }
    saida['criterio_atendido'] = bool(saida['lstm']['IC95'][0] > 0)
    with open(os.path.join(AQUI, 'lstm_series_para.json'), 'w', encoding='utf-8') as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: saida[k] for k in ('referencia', 'svr_tabela6_mesmos_registros', 'lstm',
                                            'lstm_sobre_svr', 'criterio_atendido')}, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
