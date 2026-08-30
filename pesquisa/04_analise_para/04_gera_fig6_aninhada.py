# -*- coding: utf-8 -*-
"""Figura 6 - resultado da busca aninhada de hiperparametros no Para.

Painel (a): RMSE de cada modelo ajustado dobra a dobra, contra o baseline.
            Barras acima da linha vermelha erram MAIS que a media historica do
            municipio somada a tendencia tecnologica.
Painel (b): estabilidade da escolha. Para cada modelo, a fracao das dobras
            externas em que a configuracao mais escolhida foi selecionada.
            Escolha instavel de dobra para dobra indica que a validacao interna
            nao encontra um otimo consistente -- o que se espera quando as
            variaveis ambientais nao carregam sinal sobre o alvo.

Entrada: resultados_busca_aninhada.json (de 03_busca_hiperparametros.py)
Saida:   results/fig6_busca_aninhada.png
Uso:     python 04_gera_fig6_aninhada.py
"""
import json, os
from collections import Counter
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 10,
                     'axes.grid': True, 'grid.alpha': 0.3})
os.makedirs('results', exist_ok=True)
B1 = '#1F4E79'; B2 = '#2E75B6'; RED = '#B00020'

r = json.load(open('resultados_busca_aninhada.json'))
base = r['baseline']['RMSE']
MODELS = list(r['modelos'].keys())
rmse = [r['modelos'][m]['RMSE'] for m in MODELS]

fig, ax = plt.subplots(1, 2, figsize=(9.8, 3.9))
x = np.arange(len(MODELS))

# (a) RMSE contra o baseline. Dentro da tolerancia de empate o modelo nao
# "vence" nem "perde" do baseline: empata, e a cor precisa dizer isso.
TOL = r.get('tolerancia_empate_kg_ha', 2.0)
CINZA = '#8C8C8C'
def cor_de(v):
    if abs(base - v) <= TOL: return CINZA      # empate tecnico
    return B1 if v < base else B2
cor = [cor_de(v) for v in rmse]
ax[0].bar(x, rmse, color=cor, width=0.6)
ax[0].axhline(base, ls='--', color=RED, lw=1.4,
              label=f'Baseline ({base:.0f} kg/ha)')
ax[0].axhspan(base - TOL, base + TOL, color=CINZA, alpha=0.25, lw=0,
              label=f'Empate técnico (±{TOL:.0f} kg/ha)')
ax[0].set_xticks(x); ax[0].set_xticklabels(MODELS, rotation=15, fontsize=8.5)
ax[0].set_ylabel('RMSE (kg/ha)')
ax[0].set_title(f'(a) Busca aninhada — {r["protocolo"]["dobras_externas"]} dobras\n'
                f'({r["protocolo"]["n"]} registros, '
                f'{r["protocolo"]["configuracoes_por_modelo_por_dobra"]} '
                f'configurações por dobra)', fontsize=9.5)
ax[0].legend(fontsize=7.5)
lo, hi = min(rmse + [base]), max(rmse + [base])
ax[0].set_ylim(lo - (hi - lo) * 0.5, hi + (hi - lo) * 0.28)
for i, v in enumerate(rmse):
    ax[0].text(i, v + (hi - lo) * 0.04, f'{v:.0f}', ha='center', fontsize=8.5)

# (b) estabilidade da configuracao escolhida
frac = []
for m in MODELS:
    esc = [json.dumps(e['params'], sort_keys=True, default=str)
           for e in r['modelos'][m]['escolhas_por_dobra']]
    frac.append(Counter(esc).most_common(1)[0][1] / len(esc) * 100 if esc else 0)
ax[1].bar(x, frac, color=B2, width=0.6)
ax[1].set_xticks(x); ax[1].set_xticklabels(MODELS, rotation=15, fontsize=8.5)
ax[1].set_ylabel('% das dobras com a mesma configuração')
ax[1].set_title('(b) Estabilidade da configuração escolhida\n'
                '(baixo = a validação interna não converge)', fontsize=9.5)
ax[1].set_ylim(0, 100)
for i, v in enumerate(frac):
    ax[1].text(i, v + 2, f'{v:.0f}%', ha='center', fontsize=8.5)

plt.tight_layout()
plt.savefig('results/fig6_busca_aninhada.png', dpi=200,
            bbox_inches='tight', facecolor='white')
plt.close()

print('OK: results/fig6_busca_aninhada.png')
print(f'  baseline: {base:.1f} kg/ha')
for m, v, f in zip(MODELS, rmse, frac):
    situacao = ('empata' if abs(base - v) <= TOL
                else 'supera' if v < base else 'perde para')
    print(f'  {m:14s} RMSE={v:6.1f}  ({v-base:+.1f}: {situacao} o baseline)  '
          f'config mais escolhida em {f:.0f}% das dobras')
print('  algum supera o baseline:',
      'SIM' if r['algum_supera_baseline'] else 'NAO')
