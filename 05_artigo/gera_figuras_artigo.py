# -*- coding: utf-8 -*-
import numpy as np, pandas as pd, json, os, warnings
warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
np.random.seed(42)
OUT='figs'; os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':9,'axes.grid':True,'grid.alpha':0.3})
B1='#1F4E79'; B2='#2E75B6'; RED='#B00020'; GRAY='#808080'

pa = pd.read_csv('../dados/soja_para_mascarado_2001_2024.csv').sort_values(['municipio','ano'])
nac = pd.read_csv('../03_analise_nacional/data/data_cast.csv',
                  usecols=['HARVESTED','STATE','COUNTY','YIELD']).sort_values(['STATE','COUNTY','HARVESTED'])

def taxa(df, gcols, ycol):
    r=t=0
    for _,d in df.groupby(gcols):
        v=d[ycol].values
        if len(v)<2: continue
        r+=int((np.diff(v)==0).sum()); t+=len(v)-1
    return r/t*100

# ---------- FIG 1: Pará vs estados (barras) ----------
estados={}
for st,d in nac.groupby('STATE'):
    estados[st.replace('_',' ').title()] = taxa(d,'COUNTY','YIELD')
estados['Pará (este estudo)'] = taxa(pa,'municipio','rendimento_kg_ha')
s = pd.Series(estados).sort_values()
cores=[RED if 'Pará' in i else B2 for i in s.index]
fig,ax=plt.subplots(figsize=(6.6,3.4))
ax.barh(s.index, s.values, color=cores)
ax.axvline(12.9, ls='--', color=GRAY, lw=1.2, label='Média dos estados consolidados (12,9%)')
ax.set_xlabel('Safras consecutivas com produtividade idêntica (%)')
for i,v in enumerate(s.values): ax.text(v+0.6,i,f'{v:.1f}%',va='center',fontsize=8)
ax.set_xlim(0,48); ax.legend(fontsize=7.5, loc='lower right')
plt.tight_layout(); plt.savefig(f'{OUT}/fig1_estados.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

# ---------- FIG 2: teste de permutação ----------
obs = taxa(pa,'municipio','rendimento_kg_ha')
perm=[]
for _ in range(2000):
    r=t=0
    for _,d in pa.groupby('municipio'):
        v=d.rendimento_kg_ha.values.copy()
        if len(v)<2: continue
        np.random.shuffle(v)
        r+=int((np.diff(v)==0).sum()); t+=len(v)-1
    perm.append(r/t*100)
perm=np.array(perm)
fig,ax=plt.subplots(figsize=(6.0,3.2))
ax.hist(perm,bins=30,color=B2,alpha=0.75,edgecolor='white',label='Distribuição sob H₀ (2.000 permutações)')
ax.axvline(obs,color=RED,lw=2,label=f'Observado: {obs:.1f}%')
ax.annotate(f'{(obs-perm.mean())/perm.std():.1f} desvios-padrão\n(p < 0,0005)',
            xy=(obs,ax.get_ylim()[1]*0.55), xytext=(obs-11,ax.get_ylim()[1]*0.75),
            arrowprops=dict(arrowstyle='->',color=RED,lw=1.1), fontsize=8, color=RED)
ax.set_xlabel('Safras consecutivas idênticas (%)'); ax.set_ylabel('Frequência')
ax.legend(fontsize=7.5)
plt.tight_layout(); plt.savefig(f'{OUT}/fig2_permutacao.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

# ---------- FIG 3: (a) sequências longas  (b) repetição x área ----------
runs=[]
for mun,d in pa.groupby('municipio'):
    v=d.rendimento_kg_ha.values; L=1
    for i in range(1,len(v)):
        if v[i]==v[i-1]: L+=1
        else:
            if L>1: runs.append(L)
            L=1
    if L>1: runs.append(L)
rl=pd.Series(runs).value_counts().sort_index()

pa['rep']=pa.groupby('municipio').rendimento_kg_ha.transform(lambda s: s.diff().eq(0))
q=pa.groupby(pd.qcut(pa.soy_area_ha,4,labels=['Q1\n(menor)','Q2','Q3','Q4\n(maior)'])).rep.mean()*100

fig,ax=plt.subplots(1,2,figsize=(7.6,3.0))
ax[0].bar(rl.index.astype(str), rl.values, color=B2)
ax[0].set_xlabel('Anos consecutivos com o mesmo valor'); ax[0].set_ylabel('Nº de sequências')
ax[0].set_title('(a) Sequências de valores idênticos', fontsize=9)
for i,v in enumerate(rl.values): ax[0].text(i,v+0.4,str(v),ha='center',fontsize=7.5)
ax[1].bar(range(4), q.values, color=[B2,B2,B2,B1])
ax[1].set_xticks(range(4)); ax[1].set_xticklabels(q.index, fontsize=8)
ax[1].set_xlabel('Quartil de área plantada de soja'); ax[1].set_ylabel('Repetição (%)')
ax[1].set_title('(b) Repetição decresce com a área', fontsize=9)
for i,v in enumerate(q.values): ax[1].text(i,v+0.9,f'{v:.1f}%',ha='center',fontsize=7.5)
ax[1].set_ylim(0,52)
plt.tight_layout(); plt.savefig(f'{OUT}/fig3_padroes.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

# ---------- FIG 4: séries exemplares ----------
fig,ax=plt.subplots(figsize=(6.6,3.2))
for mun,cor,ls in [('Floresta Do Araguaia',RED,'-'),('Uruara','#C55A11','-'),('Paragominas',B1,'-')]:
    d=pa[pa.municipio==mun].sort_values('ano')
    ax.plot(d.ano,d.rendimento_kg_ha,marker='o',ms=3.4,color=cor,ls=ls,lw=1.4,label=mun.replace('Do','do'))
ax.set_xlabel('Ano-safra'); ax.set_ylabel('Produtividade (kg/ha)')
ax.legend(fontsize=8); ax.set_title('Séries municipais da PAM/IBGE: platôs de valor constante', fontsize=9)
plt.tight_layout(); plt.savefig(f'{OUT}/fig4_series.png',dpi=200,bbox_inches='tight',facecolor='white'); plt.close()

stats={'obs':round(obs,1),'h0_mean':round(float(perm.mean()),1),'h0_sd':round(float(perm.std()),1),
 'z':round(float((obs-perm.mean())/perm.std()),1),'nac':12.9,
 'max_run':int(max(runs)),'n_runs':len(runs),
 'mult100_pa':round(float((pa.rendimento_kg_ha%100==0).mean()*100),1),
 'mult100_nac':53.4,'q':{k:round(float(v),1) for k,v in q.items()},
 'estados':{k:round(v,1) for k,v in estados.items()}}
json.dump(stats,open('stats.json','w'),indent=2,ensure_ascii=False)
print(json.dumps(stats,ensure_ascii=False,indent=1))
print('\nfiguras:', os.listdir(OUT))
