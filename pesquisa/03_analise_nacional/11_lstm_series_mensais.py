# -*- coding: utf-8 -*-
"""
Rede recorrente (LSTM) sobre as séries mensais do recorte nacional.

A dissertação registra como limitação a não implementação de arquiteturas
recorrentes. Na base nacional (von Bloh et al., 2023), porém, 119 dos 121
preditores já são séries mensais: 17 variáveis medidas de setembro a março,
do plantio ao fim do enchimento de grãos. Os modelos da Tabela 3 recebem essas
119 colunas soltas, sem saber que SPI3_11 e SPI3_12 são o mesmo índice em meses
seguidos; a LSTM as lê em ordem, mês a mês.

Protocolo, idêntico ao de 04_avalia_ajustado.py (Tabela 3):
- mesma base, mesmo alvo (anomalia YIELD_TREND_CORRECTED) e mesma
  reconstrução (+ YIELD_TREND), erro medido na produtividade em kg/ha;
- validação leave-one-year-out em 2016-2020, com as mesmas subamostras de
  7.000 registros por safra (RandomState(1000 + safra));
- a mesma padronização das 121 colunas (StandardScaler ajustado no treino);
- busca de hiperparâmetros só na janela de desenvolvimento 2001-2015, com
  validação interna em 2014 e 2015 e subamostra de 4.000, como em
  03_busca_hiperparametros.py; as safras de teste não entram na escolha.

Entrada da LSTM: sequência de 7 meses (set, out, nov, dez, jan, fev, mar) com
17 variáveis por mês; as 2 colunas que não variam no mês (área de soja e ano
da safra) entram junto do último estado da rede, antes da camada de saída.

Redes neurais variam com a semente: cada configuração final é treinada com 5
sementes; relata-se a média e o desvio entre sementes e a média das 5
previsões (conjunto).

CRITÉRIO, FIXADO ANTES DE RODAR: a LSTM supera o SVR (melhor modelo da
Tabela 3, R² 0,425, RMSE 461 kg/ha) se o intervalo de 95% da diferença de RMSE
(LSTM − SVR), por reamostragem de municípios com as mesmas observações para os
dois modelos, ficar inteiro abaixo de zero.

Uso:
    python 11_lstm_series_mensais.py busca [n_configs]
    python 11_lstm_series_mensais.py avalia [--base-completa]
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
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, 'results')
MESES = [9, 10, 11, 12, 1, 2, 3]
VARIAVEIS = ['MEAN_SRAD', 'MEAN_TMIN', 'MEAN_TMAX', 'HOT_DAYS', 'ACC_RAINFALL', 'LOWRAIN_DAYS',
             'MEAN_NDVI', 'MEAN_EVI', 'MEAN_CVI', 'MEAN_GLI', 'SPI1', 'SPI3', 'STI1', 'EXC', 'DEF',
             'ETP', 'ONI']
FORA = ['YIELD', 'YIELD_TREND', 'YIELD_TREND_CORRECTED', 'CODE', 'COUNTY', 'STATE', 'CLIMATE_ZONE']
SEED, SUB, SUB_BUSCA, DEV_ATE = 42, 7000, 4000, 2015
VAL_INTERNAS = [2014, 2015]
SAFRAS_TESTE = [2016, 2017, 2018, 2019, 2020]
SEMENTES = [42, 43, 44, 45, 46]
ESPACO = {'oculto': [32, 64, 128], 'camadas': [1, 2], 'dropout': [0.0, 0.2, 0.4],
          'lr': [1e-3, 3e-3], 'decaimento': [0.0, 1e-4, 1e-3]}
PADRAO = {'oculto': 64, 'camadas': 1, 'dropout': 0.2, 'lr': 1e-3, 'decaimento': 1e-4}

torch.set_num_threads(min(4, os.cpu_count() or 4))


# ── dados ────────────────────────────────────────────────────────────────────

def carrega():
    df = pd.read_csv(os.path.join(AQUI, 'data', 'data_cast.csv'))
    feat = [c for c in df.columns if c not in FORA and df[c].dtype != 'object']
    seq = [f'{v}_{m}' for m in MESES for v in VARIAVEIS]
    est = [c for c in feat if c not in seq]
    assert len(seq) + len(est) == len(feat) == 121, (len(seq), est)
    # Mesmo preenchimento das colunas que a Tabela 3 usa; a ordem das colunas
    # muda (meses em sequência), não os valores.
    X = df[feat].fillna(df[feat].median())
    return {
        'X': X[seq + est].values.astype(np.float32), 'n_seq': len(seq), 'est': est,
        'Y': df['YIELD'].values.astype(float), 'TREND': df['YIELD_TREND'].values.astype(float),
        'ANOM': df['YIELD_TREND_CORRECTED'].values.astype(float),
        'anos': df['HARVESTED'].values, 'mun': df['CODE'].values,
        'X_tabela3': df[feat].fillna(df[feat].median()).values,
    }


def em_sequencia(Xp, n_seq):
    """Colunas padronizadas → (n, 7 meses, 17 variáveis) e (n, estáticas)."""
    n = Xp.shape[0]
    return (Xp[:, :n_seq].reshape(n, len(MESES), len(VARIAVEIS)), Xp[:, n_seq:])


# ── modelo ───────────────────────────────────────────────────────────────────

class LSTMSafra(nn.Module):
    def __init__(self, n_var, n_est, oculto, camadas, dropout):
        super().__init__()
        self.lstm = nn.LSTM(n_var, oculto, num_layers=camadas, batch_first=True,
                            dropout=dropout if camadas > 1 else 0.0)
        self.saida = nn.Sequential(nn.Linear(oculto + n_est, 64), nn.ReLU(), nn.Dropout(dropout),
                                   nn.Linear(64, 1))

    def forward(self, xs, xe):
        _, (h, _) = self.lstm(xs)
        return self.saida(torch.cat([h[-1], xe], dim=1)).squeeze(-1)


def ajusta(cfg, xs, xe, alvo, semente, epocas=300, paciencia=20, lote=256):
    """Treina com parada antecipada em 10% do treino, como o MLP da Tabela 3."""
    rng = np.random.RandomState(semente)
    torch.manual_seed(semente)
    n = len(alvo)
    ordem = rng.permutation(n)
    nval = max(1, int(0.1 * n))
    iv, it = ordem[:nval], ordem[nval:]
    mu, dp = alvo[it].mean(), alvo[it].std() + 1e-9
    a = torch.tensor((alvo - mu) / dp, dtype=torch.float32)
    xs, xe = torch.tensor(xs), torch.tensor(xe)
    modelo = LSTMSafra(xs.shape[2], xe.shape[1], cfg['oculto'], cfg['camadas'], cfg['dropout'])
    otim = torch.optim.Adam(modelo.parameters(), lr=cfg['lr'], weight_decay=cfg['decaimento'])
    melhor, estado, sem_melhora = float('inf'), None, 0
    for _ in range(epocas):
        modelo.train()
        perm = it[rng.permutation(len(it))]
        for i in range(0, len(perm), lote):
            b = perm[i:i + lote]
            perda = nn.functional.mse_loss(modelo(xs[b], xe[b]), a[b])
            otim.zero_grad()
            perda.backward()
            otim.step()
        modelo.eval()
        with torch.no_grad():
            pv = nn.functional.mse_loss(modelo(xs[iv], xe[iv]), a[iv]).item()
        if pv < melhor - 1e-5:
            melhor, sem_melhora = pv, 0
            estado = {k: v.clone() for k, v in modelo.state_dict().items()}
        else:
            sem_melhora += 1
            if sem_melhora >= paciencia:
                break
    modelo.load_state_dict(estado)
    modelo.eval()

    def prediz(xs_n, xe_n):
        with torch.no_grad():
            return modelo(torch.tensor(xs_n), torch.tensor(xe_n)).numpy() * dp + mu
    return prediz


def prepara(d, idx, te):
    esc = StandardScaler().fit(d['X'][idx])
    xs_tr, xe_tr = em_sequencia(esc.transform(d['X'][idx]).astype(np.float32), d['n_seq'])
    xs_te, xe_te = em_sequencia(esc.transform(d['X'][te]).astype(np.float32), d['n_seq'])
    return xs_tr, xe_tr, xs_te, xe_te


# ── busca (só 2001-2015) ─────────────────────────────────────────────────────

def busca(n_cfg):
    d = carrega()
    rng = np.random.default_rng(SEED)
    cands, vistas = [PADRAO], {tuple(sorted(PADRAO.items()))}
    while len(cands) < n_cfg + 1:
        cfg = {k: v[rng.integers(len(v))] for k, v in ESPACO.items()}
        ch = tuple(sorted(cfg.items()))
        if ch not in vistas:
            vistas.add(ch)
            cands.append(cfg)
    linhas = []
    for i, cfg in enumerate(cands):
        t0, erros = time.time(), []
        for val in VAL_INTERNAS:
            idx = np.where((d['anos'] <= DEV_ATE) & (d['anos'] != val))[0]
            idx = np.random.RandomState(1000 + val).choice(idx, SUB_BUSCA, replace=False)
            te = d['anos'] == val
            xs_tr, xe_tr, xs_te, xe_te = prepara(d, idx, te)
            pred = ajusta(cfg, xs_tr, xe_tr, d['ANOM'][idx], SEED)(xs_te, xe_te) + d['TREND'][te]
            erros.append(np.sqrt(mean_squared_error(d['Y'][te], pred)))
        linhas.append({'config': cfg, 'rmse_val': round(float(np.mean(erros)), 1)})
        print(f'  [{i:2d}] RMSE_val={np.mean(erros):6.1f} ({time.time() - t0:4.0f}s) {cfg}', flush=True)
    linhas.sort(key=lambda r: r['rmse_val'])
    os.makedirs(SAIDA, exist_ok=True)
    json.dump({'melhor': linhas[0], 'todas': linhas}, open(os.path.join(SAIDA, 'busca_lstm.json'), 'w'),
              indent=1, ensure_ascii=False)
    print('melhor:', linhas[0])


# ── avaliação (2016-2020) ────────────────────────────────────────────────────

def metricas(obs, prev):
    return {'RMSE_pool': round(float(np.sqrt(mean_squared_error(obs, prev))), 1),
            'MAE_pool': round(float(mean_absolute_error(obs, prev)), 1),
            'R2_pool': round(float(r2_score(obs, prev)), 3)}


def compara(obs, a, b, mun, reps=2000):
    """IC 95% de RMSE(a) − RMSE(b) e R²(a) − R²(b), reamostrando municípios."""
    rng = np.random.default_rng(SEED)
    unicos = np.unique(mun)
    por_mun = {m: np.where(mun == m)[0] for m in unicos}
    drmse, dr2 = [], []
    for _ in range(reps):
        idx = np.concatenate([por_mun[m] for m in rng.choice(unicos, len(unicos), replace=True)])
        o = obs[idx]
        drmse.append(np.sqrt(np.mean((a[idx] - o) ** 2)) - np.sqrt(np.mean((b[idx] - o) ** 2)))
        dr2.append(r2_score(o, a[idx]) - r2_score(o, b[idx]))
    return {'dRMSE': round(float(np.sqrt(np.mean((a - obs) ** 2)) - np.sqrt(np.mean((b - obs) ** 2))), 1),
            'dRMSE_IC95': [round(float(np.percentile(drmse, q)), 1) for q in (2.5, 97.5)],
            'dR2': round(float(r2_score(obs, a) - r2_score(obs, b)), 3),
            'dR2_IC95': [round(float(np.percentile(dr2, q)), 3) for q in (2.5, 97.5)]}


def tabela3():
    """Os modelos de 04_avalia_ajustado.py, importados para rodar lado a lado."""
    spec = importlib.util.spec_from_file_location('aval', os.path.join(AQUI, '04_avalia_ajustado.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.AJUSTADOS, m.PRECISA_ESCALA, m.SUB_SVR


def avalia(base_completa):
    d = carrega()
    cfg_busca = json.load(open(os.path.join(SAIDA, 'busca_lstm.json')))['melhor']['config']
    print('configuração escolhida em 2001-2015:', cfg_busca)
    anos = d['anos']
    if base_completa:
        sub = {ty: np.where(anos != ty)[0] for ty in SAFRAS_TESTE}
    else:
        sub = {ty: np.random.RandomState(1000 + ty).choice(np.where(anos != ty)[0], SUB, replace=False)
               for ty in SAFRAS_TESTE}
    obs = np.concatenate([d['Y'][anos == ty] for ty in SAFRAS_TESTE])
    mun = np.concatenate([d['mun'][anos == ty] for ty in SAFRAS_TESTE])
    ano_obs = np.concatenate([anos[anos == ty] for ty in SAFRAS_TESTE])
    prev = {}

    # Modelos da Tabela 3, mesmo código e mesmas subamostras.
    ajustados, precisa_escala, sub_svr = tabela3()
    X3 = d['X_tabela3']
    for nome, base in ajustados.items():
        t0, p = time.time(), []
        for ty in SAFRAS_TESTE:
            idx, te = sub[ty], anos == ty
            Xtr, Xte, atr = X3[idx], X3[te], d['ANOM'][idx]
            if nome in precisa_escala:
                esc = StandardScaler().fit(Xtr)
                Xtr, Xte = esc.transform(Xtr), esc.transform(Xte)
                if nome == 'SVR' and not base_completa:
                    Xtr, atr = Xtr[:sub_svr], atr[:sub_svr]
            p.append(clone(base).fit(Xtr, atr).predict(Xte) + d['TREND'][te])
        prev[nome] = np.concatenate(p)
        print(f'{nome:14s} {metricas(obs, prev[nome])} ({time.time() - t0:.0f}s)', flush=True)

    # LSTM, 5 sementes.
    por_semente = []
    for s in SEMENTES:
        t0, p = time.time(), []
        for ty in SAFRAS_TESTE:
            idx, te = sub[ty], anos == ty
            xs_tr, xe_tr, xs_te, xe_te = prepara(d, idx, te)
            p.append(ajusta(cfg_busca, xs_tr, xe_tr, d['ANOM'][idx], s)(xs_te, xe_te) + d['TREND'][te])
        por_semente.append(np.concatenate(p))
        print(f'LSTM semente {s} {metricas(obs, por_semente[-1])} ({time.time() - t0:.0f}s)', flush=True)
    prev['LSTM (conjunto de 5 sementes)'] = np.mean(por_semente, axis=0)
    ms = [metricas(obs, p) for p in por_semente]

    resultado = {
        'protocolo': 'base completa' if base_completa else 'Tabela 3 (subamostra de 7.000; SVR 5.000)',
        'config_lstm': cfg_busca,
        'modelos': {k: metricas(obs, v) for k, v in prev.items()},
        'lstm_por_semente': {'RMSE': [m['RMSE_pool'] for m in ms], 'R2': [m['R2_pool'] for m in ms],
                             'RMSE_media': round(float(np.mean([m['RMSE_pool'] for m in ms])), 1),
                             'RMSE_dp': round(float(np.std([m['RMSE_pool'] for m in ms])), 1),
                             'R2_media': round(float(np.mean([m['R2_pool'] for m in ms])), 3),
                             'R2_dp': round(float(np.std([m['R2_pool'] for m in ms])), 3)},
        'por_safra_R2': {k: {int(ty): round(float(r2_score(obs[ano_obs == ty], v[ano_obs == ty])), 3)
                             for ty in SAFRAS_TESTE} for k, v in prev.items()},
        'lstm_menos_svr': compara(obs, prev['LSTM (conjunto de 5 sementes)'], prev['SVR'], mun),
        'lstm_semente_42_menos_svr': compara(obs, por_semente[0], prev['SVR'], mun),
    }
    ic = resultado['lstm_menos_svr']['dRMSE_IC95']
    resultado['criterio'] = ('LSTM supera o SVR' if ic[1] < 0 else
                             'SVR supera a LSTM' if ic[0] > 0 else 'sem diferença significativa')
    nome = 'lstm_base_completa.json' if base_completa else 'lstm_tabela3.json'
    json.dump(resultado, open(os.path.join(SAIDA, nome), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: resultado[k] for k in ('modelos', 'lstm_por_semente', 'lstm_menos_svr', 'criterio')},
                     indent=1, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'busca':
        busca(int(sys.argv[2]) if len(sys.argv) > 2 else 15)
    elif len(sys.argv) > 1 and sys.argv[1] == 'avalia':
        avalia('--base-completa' in sys.argv)
    else:
        print(__doc__)
