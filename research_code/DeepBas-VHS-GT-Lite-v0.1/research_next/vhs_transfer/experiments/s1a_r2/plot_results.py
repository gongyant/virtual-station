"""Python scientific figures from frozen R2 diagnostics; point estimates only."""
from analyze import HERE, dump, sha, read, PREFIX
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path.home()/'.codex/skills/nature-figure/scripts'))
from audit_panel_alignment import require_matplotlib_panel_alignment

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':7,'axes.titlesize':8,'axes.labelsize':7,'xtick.labelsize':6,'ytick.labelsize':6,'legend.fontsize':7,'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.7,'legend.frameon':False})
C0='#286E91';C1='#BB6337';C2='#52774B'
def data(name): return read(HERE/(PREFIX+name+'.csv'))
def select(rows,**kw): return [r for r in rows if all(str(r[k])==str(v) for k,v in kw.items())]
def figure():
    fig,axs=plt.subplots(1,3,figsize=(7.2047244094,2.95))
    fig.subplots_adjust(left=.09,right=.98,bottom=.24,top=.77,wspace=.46)
    for i,ax in enumerate(axs):
        ax.set_title(str(1981+i),loc='left',pad=6)
        ax.text(-.16,1.12,chr(97+i),transform=ax.transAxes,fontweight='bold',fontsize=8,va='bottom')
    fig.suptitle('Retrospective post-hoc diagnostic.',x=.5,y=.97,fontsize=8)
    return fig,axs
def export(fig,name):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=HERE/f'{name}.alignment.json',overlay_svg=HERE/f'{name}.alignment.svg',strict=True,require_panel_labels=True)
    fig.savefig(HERE/f'{name}.pdf',facecolor='white')
    fig.savefig(HERE/f'{name}.svg',facecolor='white')
    fig.savefig(HERE/f'{name}.png',dpi=600,facecolor='white')
    plt.close(fig)
def legend(fig,handles,labels):fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.54,.91),ncol=len(labels),handlelength=1.4,columnspacing=1.4)

def main():
    sources=('flow_strata','exante_strata','delta_sse','annual_metrics','year_swap_metrics','four_cell_baselines')
    dump('figure_contract.json',dict(identity='POST_HOC_EXPLORATORY_DIAGNOSTIC',backend='Python/matplotlib',width_mm=183,exports='editable PDF/SVG and 600dpi PNG; 5pt glyph floor',uncertainty='descriptive point estimates, no independent donor inference',panels='each of three years may overturn consistency; no omitted year or donor',questions=['R2-1: which fixed strata contribute absolute SSE changes?','R2-2: are contributions concentrated in few days?','R2-3: do between or within block errors dominate?','R2-4: is real alignment better than all five year swaps?','R2-5: do absolute LOW errors depend on seasonal baseline and grouping?'],claims='No physical transport identification; conditional and seasonal sensitivities retained.',source_hashes={s:sha(HERE/(PREFIX+s+'.csv')) for s in sources},supports='R2-1/2/3/5 365 days; R2-4 335 days; no cross-support ranking'))
    flow=data('flow_strata');ex=data('exante_strata');fig,axs=figure()
    for yr,ax in zip((1981,1982,1983),axs):
        for j,(rr,color,label) in enumerate(((flow,C0,'Outcome-defined'),(ex,C1,'Ex-ante upstream'))):
            a=select(rr,fold=yr,model='past_only');h=ax.bar(np.arange(3)+(j-.5)*.34,[float(x['DeltaSSE'])/1000 for x in a],width=.32,color=color,label=label)
        a=select(flow,fold=yr,model='past_only');e=select(ex,fold=yr,model='past_only')
        ax.axhline(0,color='#888888',lw=.6);ax.set_xticks(range(3),[f"{r['stratum']}\n{r['n']}/{z['n']}" for r,z in zip(a,e)]);ax.set_ylabel('Delta SSE (1000 Q²)');ax.set_ylim(-150,120)
    legend(fig,*axs[0].get_legend_handles_labels());fig.text(.54,.055,'365 days | tick counts: outcome/ex-ante n | positive = improvement',ha='center',fontsize=7)
    export(fig,'s1a_r2_1_strata')
    daily=data('delta_sse');fig,axs=figure()
    for yr,ax in zip((1981,1982,1983),axs):
        a=select(daily,fold=yr,model='past_only');v=np.sort(np.abs([float(r['DeltaSSE']) for r in a]))[::-1];x=np.arange(1,366)
        ax.plot(x,100*np.cumsum(v)/v.sum(),color=C0,lw=1.2)
        ax.scatter([5,10,20],100*np.cumsum(v)[np.array([4,9,19])]/v.sum(),s=12,color=C1,zorder=3)
        ax.set_xlim(0,365);ax.set_ylim(0,103);ax.set_xticks([0,100,200,365]);ax.set_yticks([0,50,100]);ax.set_xlabel('Days ranked by |Delta SSE|');ax.set_ylabel('Cumulative absolute share (%)')
    fig.text(.54,.86,'Orange points: fixed top 5, 10 and 20 days',ha='center',fontsize=7)
    fig.text(.54,.055,'Monthly frozen pair | 365 days | ranks are influence diagnostics',ha='center',fontsize=7)
    export(fig,'s1a_r2_2_concentration')
    annual=data('annual_metrics');fig,axs=figure()
    for yr,ax in zip((1981,1982,1983),axs):
        for j,(model,color,label) in enumerate((('past_only',C0,'Monthly pair'),('f2',C1,'F2 pair'))):
            r=select(annual,fold=yr,model=model)[0];ax.bar(np.arange(2)+(j-.5)*.32,[float(r['DeltaSSE_between'])/1000,float(r['DeltaSSE_within'])/1000],width=.30,color=color,label=label)
        ax.axhline(0,color='#888888',lw=.6);ax.set_xticks([0,1],['Between','Within']);ax.set_ylabel('Delta SSE (1000 Q²)');ax.set_ylim(-110,110)
    legend(fig,*axs[0].get_legend_handles_labels());fig.text(.54,.055,'Jan1-anchored 30-day blocks | 365 days | positive = improvement',ha='center',fontsize=7)
    export(fig,'s1a_r2_3_orthogonal')
    swaps=data('year_swap_metrics');fig,axs=figure()
    for yr,ax in zip((1981,1982,1983),axs):
        for j,(model,color,label,marker) in enumerate((('past_only',C0,'Monthly pair','o'),('f2',C1,'F2 pair','s'))):
            a=select(swaps,fold=yr,model=model);x=np.array([int(r['donor']) for r in a]);v=np.array([100*float(r['relative_RMSE_gain']) for r in a]);off=(j-.5)*.16
            other=x!=yr;ax.scatter(x[other]+off,v[other],s=20,facecolors='white',edgecolors=color,marker=marker,label=label,zorder=3)
            ax.scatter(x[~other]+off,v[~other],s=23,color=color,marker=marker,zorder=4)
        ax.axhline(0,color='#888888',lw=.6);ax.set_xticks(range(1978,1984),['78','79','80','81','82','83']);ax.set_xlabel('Upstream donor year (19xx)');ax.set_ylabel('Relative RMSE gain (%)');ax.set_ylim(-34,10)
    legend(fig,*axs[0].get_legend_handles_labels());fig.text(.54,.055,'335 days | filled = real aligned | all five controls retained',ha='center',fontsize=7)
    export(fig,'s1a_r2_4_year_swap')
    four=data('four_cell_baselines');fig,axs=figure()
    for yr,ax in zip((1981,1982,1983),axs):
        for j,(kind,color,label) in enumerate((('outcome',C0,'Outcome LOW'),('exante',C1,'Ex-ante LOW'))):
            a=select(four,fold=yr,grouping=kind,stratum='LOW');v=[float(next(r for r in a if r['cell']==c)['RMSE']) for c in 'ABCD'];ax.bar(np.arange(4)+(j-.5)*.34,v,width=.32,color=color,label=label)
        ns=[select(four,fold=yr,grouping=k,stratum='LOW')[0]['n'] for k in ('outcome','exante')]
        ax.set_title(f'{yr} | n={ns[0]}/{ns[1]}',loc='left',pad=6)
        ax.set_xticks(range(4),['A','B','C','D']);ax.set_ylabel('LOW RMSE (Q units)');ax.set_ylim(0,10.5)
    legend(fig,*axs[0].get_legend_handles_labels());fig.text(.54,.055,'365 days | A: Monthly  B: +upstream  C: F2  D: +upstream',ha='center',fontsize=7)
    export(fig,'s1a_r2_5_four_cell')
    print('Five figures exported')

if __name__=='__main__':main()
