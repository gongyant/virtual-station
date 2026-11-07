"""Four scientific figure classes from actual frozen public observations and models."""
from p6d_common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
sys.stdout.reconfigure(encoding='utf-8');skill=Path(r'C:\Users\Administrator\.codex\skills\nature-figure');sys.path.insert(0,str(skill/'scripts'));from audit_panel_alignment import require_matplotlib_panel_alignment
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],'font.size':8,'axes.titlesize':8,'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False,'pdf.fonttype':42,'svg.fonttype':'none','axes.linewidth':.6,'savefig.facecolor':'white'})
blue='#4575A5';orange='#C56D32';green='#548269';gray='#8A8A8A';black='#252525';rows=cr(R/'P6D_MONTHLY_PAIRED_ERRORS.csv');decomp=cr(R/'P6D_PREDICTION_DECOMPOSITION.csv');season=cr(R/'P6D_SEASONAL_AND_DRIFT.csv');figmanifest=[]
def save(fig,name,sources,panels):
 fig.canvas.draw();require_matplotlib_panel_alignment(fig,json_out=R/'figure_qa'/f'{name}.alignment.json',overlay_svg=R/'figure_qa'/f'{name}.alignment.svg',tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
 fig.savefig(R/'figures'/f'{name}.pdf')
 fig.savefig(R/'figures'/f'{name}.svg')
 fig.savefig(R/'figures'/f'{name}.png',dpi=300)
 figmanifest.append({'name':name,'panels':panels,'sources':{str(Path(p).relative_to(R)):sha(p) for p in sources},'script_sha256':sha(__file__),'files':{f'figures/{name}.{e}':sha(R/'figures'/f'{name}.{e}') for e in ['pdf','svg','png']},'no_synthetic_data':True,'figure_role':'posthoc descriptive; no causal attribution, no independent confirmatory inference'});plt.close(fig)
def dateaxis(ax):
 ax.set_xticks([0,12,24,35],['2018-01','2019-01','2020-01','2020-12']);ax.set_xlim(-.5,35.5);labels=ax.get_xticklabels();labels[0].set_ha('left');labels[-1].set_ha('right')
# 1. The user-specified eight failure cases; full 24 station data remain in the tables.
focus=[171,185,255,343,383,455,533,545];ss=[r for r in rows if int(r['gauge_id']) in focus];p=R/'figure_source_data/F1_MONTHLY_FOCUS.csv';cw(p,ss);fig,axs=plt.subplots(4,2,figsize=(7.2,8.6));fig.subplots_adjust(left=.10,right=.98,bottom=.07,top=.91,hspace=.55,wspace=.30)
for i,(g,ax) in enumerate(zip(focus,axs.flat)):
 rr=sorted([r for r in ss if int(r['gauge_id'])==g],key=lambda r:r['date']);dd=sorted([d for d in decomp if int(d['gauge_id'])==g and d['model_id']=='P2-L1'],key=lambda d:d['date']);x=np.arange(len(rr));ax.plot(x,[float(r['Qobs']) for r in rr],color=black,lw=1.2);ax.plot(x,[float(r['Qsim_C0PT']) for r in rr],color=blue,lw=.9);ax.plot(x,[float(r['Qsim_L1']) for r in rr],color=orange,lw=1.05);ax.plot(x,[float(d['seasonal_baseline']) for d in dd],color=gray,lw=.8,ls='--');ax.set_title(f'{chr(97+i)}  ID{g}',loc='left',fontweight='bold');dateaxis(ax)
 if i%2==0:ax.set_ylabel('Discharge (m³/s)')
fig.legend([Line2D([],[],color=c,lw=1.2,ls=ls) for c,ls in [(black,'-'),(blue,'-'),(orange,'-'),(gray,'--')]],['Observed Q','C0+PT','P2-L1','Frozen seasonal template'],loc='upper center',ncol=2,bbox_to_anchor=(.53,.995),fontsize=8);fig.supxlabel('Provider calendar month · fixed models, observed meteorology',y=.015,fontsize=8);save(fig,'F1_MONTHLY_PREDICTIONS',[p,R/'P6D_PREDICTION_DECOMPOSITION.csv'],[f'ID{g}: 36 actual paired months' for g in focus])
# 2. Monthly location of gains and cumulative annual net gains, with exact signs.
ss=[r for r in rows if int(r['gauge_id']) in [455,171]];p=R/'figure_source_data/F2_MONTHLY_GAIN.csv';cw(p,ss);fig,axs=plt.subplots(2,2,figsize=(7.2,5.4));fig.subplots_adjust(left=.12,right=.98,bottom=.13,top=.92,hspace=.48,wspace=.32)
for j,g in enumerate([455,171]):
 rr=sorted([r for r in ss if int(r['gauge_id'])==g],key=lambda r:r['date']);vals=np.array([float(r['delta_annual_MSE_contribution']) for r in rr]);x=np.arange(36);axs[0,j].bar(x,vals,color=[blue if v>=0 else orange for v in vals],width=.8);axs[0,j].axhline(0,color=black,lw=.5);axs[0,j].set_title(f'{chr(97+j)}  ID{g}: monthly MSE improvement',loc='left',fontweight='bold')
 for y in range(3):axs[1,j].plot(np.arange(12*y,12*(y+1)),np.cumsum(vals[y*12:(y+1)*12]),color=black,lw=1.2)
 axs[1,j].axhline(0,color=gray,lw=.5);axs[1,j].set_title(f'{chr(99+j)}  ID{g}: cumulative gain, reset each year',loc='left',fontweight='bold')
 for ax in axs[:,j]:dateaxis(ax)
axs[0,0].set_ylabel('Monthly contribution ((m³/s)²)');axs[1,0].set_ylabel('Annual MSE reduction ((m³/s)²)');fig.supxlabel('Positive = L1 improves; negative = L1 worsens · no month excluded',y=.025,fontsize=8);save(fig,'F2_ERROR_CONTRIBUTION',[p],['ID455 monthly gain','ID171 monthly gain','ID455 annual accumulated gain','ID171 annual accumulated gain'])
# 3. Relative skill does not guarantee an acceptable absolute winter NSE.
ids=jl(R/'P6D_DIAGNOSTIC_PROTOCOL.json')['gauge_ids'];ss=[r for r in season if r['period'] in ['2018_2019','2020'] and r['model_id']=='P2-L1' and r['subset'] in ['DJF','MAY_JUNE']];p=R/'figure_source_data/F3_SEASONAL_PAIRED.csv';cw(p,ss);fig,axs=plt.subplots(1,3,figsize=(7.2,6.4),sharey=True);fig.subplots_adjust(left=.09,right=.98,bottom=.14,top=.88,wspace=.28)
for j,(subset,field,title) in enumerate([('DJF','MSE_skill_L1_vs_C0PT','a  Winter relative skill'),('MAY_JUNE','MSE_skill_L1_vs_C0PT','b  May–June relative skill'),('DJF','NSE','c  Winter absolute L1 NSE')]):
 ax=axs[j]
 for i,g in enumerate(ids):
  vv=[float(next(r for r in ss if int(r['gauge_id'])==g and r['period']==per and r['subset']==subset)[field]) for per in ['2018_2019','2020']];vv=np.array(vv)*(100 if j<2 else 1);ax.plot(vv,[i,i],color='#BEBEBE',lw=.7);ax.scatter(vv[0],i,color=blue,s=15,marker='o');ax.scatter(vv[1],i,color=orange,s=19,marker='s')
 ax.axvline(0,color=black,lw=.6);ax.set_title(title,loc='left',fontweight='bold');ax.set_xscale('symlog',linthresh=10 if j<2 else 1);ax.xaxis.set_major_formatter(FuncFormatter(lambda v,pos:f'{v:g}'));ax.set_xlabel('MSE skill (%) · symlog' if j<2 else 'NSE · symlog');ax.set_yticks(range(len(ids)),[str(g) for g in ids]);ax.set_ylim(len(ids)-.3,-.7)
axs[0].set_ylabel('Gauge ID');fig.legend([Line2D([],[],marker='o',ls='',color=blue),Line2D([],[],marker='s',ls='',color=orange)],['2018–2019','2020'],loc='upper center',ncol=2,bbox_to_anchor=(.53,.98),fontsize=8);fig.supxlabel('DJF = Jan, Feb, Dec of each calendar year; stations are network dependent',y=.025,fontsize=7);save(fig,'F3_SEASONAL_SKILL_AND_FAILURE',[p],['24 stations DJF paired relative skills','24 stations MayJune paired skills','same stations winter absolute NSE'])
# 4. Algebraic contribution allocation, not causal attribution or SHAP.
ss=[d for d in decomp if int(d['gauge_id']) in [455,171]];p=R/'figure_source_data/F4_FROZEN_FEATURE_CONTRIBUTIONS.csv';cw(p,ss);fig,axs=plt.subplots(2,2,figsize=(7.2,5.8));fig.subplots_adjust(left=.10,right=.98,bottom=.12,top=.85,hspace=.53,wspace=.32)
for j,g in enumerate([455,171]):
 rr=sorted([d for d in ss if int(d['gauge_id'])==g and d['model_id']=='P2-L1'],key=lambda d:d['date']);xx=np.arange(36)
 for k,col in [('P',blue),('T',orange),('L1',green)]:axs[0,j].plot(xx,[float(r[k+'_contribution']) for r in rr],color=col,lw=1)
 axs[0,j].set_title(f'{chr(97+j)}  ID{g}: L1 model weather terms',loc='left',fontweight='bold')
 pp=sorted([r for r in rows if int(r['gauge_id'])==g],key=lambda r:r['date'])
 for k,col in [('currentP_term',blue),('currentT_term',orange),('lag_term',green)]:axs[1,j].plot(xx,[float(r['delta_prediction_'+k]) for r in pp],color=col,lw=.9)
 axs[1,j].plot(xx,[float(r['prediction_change_L1_minus_C0']) for r in pp],color=black,lw=1.3,ls='--');axs[1,j].set_title(f'{chr(99+j)}  ID{g}: L1 minus C0+PT terms',loc='left',fontweight='bold')
 for ax in axs[:,j]:ax.axhline(0,color=gray,lw=.5);dateaxis(ax)
axs[0,0].set_ylabel('Saved beta × anomaly (m³/s)');axs[1,0].set_ylabel('Prediction difference (m³/s)');fig.legend([Line2D([],[],color=col,lw=1,ls=ls) for col,ls in [(blue,'-'),(orange,'-'),(green,'-'),(black,'--')]],['Current P term','Current T term','Previous-month P term','Total prediction difference'],loc='upper center',ncol=2,bbox_to_anchor=(.53,.995),fontsize=8);fig.supxlabel('Fixed standardized transforms; algebraic allocation is not a causal mechanism',y=.025,fontsize=7);save(fig,'F4_FEATURE_CONTRIBUTIONS',[p,R/'P6D_MONTHLY_PAIRED_ERRORS.csv'],['ID455 fixed feature terms','ID171 fixed feature terms','ID455 all prediction-difference terms','ID171 all prediction-difference terms'])
jw(R/'P6D_FIGURE_PROVENANCE.json',figmanifest);event('FIGURES_RENDERED',figure_classes=len(figmanifest),synthetic_data=False,fit_calls=0);print('FIGURE_CLASSES',len(figmanifest),'ALIGNMENT_PASSED')
