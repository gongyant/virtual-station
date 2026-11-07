"""Post-score Python figures only. No fitting, model selection or score changes."""
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import HERE,ROOT,read_csv,dump,sha

SKILL=__import__('pathlib').Path.home()/'.codex/skills/nature-figure'
sys.path.insert(0,str(SKILL/'scripts'))
from audit_panel_alignment import require_matplotlib_panel_alignment

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],
    'font.size':7,'axes.titlesize':8,'axes.labelsize':7,'xtick.labelsize':6,'ytick.labelsize':6,
    'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,
    'axes.linewidth':0.7,'legend.frameon':False})

def export(fig,name):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=HERE/f'{name}.alignment.json',
        overlay_svg=HERE/f'{name}.alignment.svg',strict=True,require_panel_labels=True)
    fig.savefig(HERE/f'{name}.pdf',facecolor='white')
    fig.savefig(HERE/f'{name}.svg',facecolor='white')
    fig.savefig(HERE/f'{name}.png',dpi=600,facecolor='white')
    plt.close(fig)

def main():
    rows=read_csv(HERE/'s1a_r1_placebo_metrics.csv')
    # Figure contract: fixed displacement response stratified by exposed year;
    # no optimized lag or mechanistic peak claim. Raw per-year points, no aggregation CI.
    dump(HERE/'figure_contract.json',{'archetype':'quantitative grid','backend':'Python/matplotlib',
        'placebo_question':'Does fixed temporal displacement consistently weaken aligned predictive gain?',
        'placebo_panels':'a/b/c stratify response across 1981/1982/1983; each year can overturn consistency',
        'source_data':'s1a_r1_placebo_metrics.csv','source_sha256':sha(HERE/'s1a_r1_placebo_metrics.csv'),
        'support':'275 days Jan1-Oct2; 13 fixed shifts; no random replicate interpretation',
        'uncertainty':'point estimates in placebo figure; paired conditional CIs in bootstrap CSV',
        'export':'183mm width; editable PDF/SVG; 600dpi PNG; 5pt glyph floor',
        'journal_submission_claim':False})
    fig,axs=plt.subplots(3,1,figsize=(7.2047244094,6.4960629921),sharex=True,sharey=True)
    fig.subplots_adjust(left=.13,right=.97,bottom=.10,top=.94,hspace=.39)
    for i,year in enumerate((1981,1982,1983)):
        ax=axs[i]; rr=sorted([r for r in rows if int(r['fold'])==year],key=lambda r:int(r['k']))
        k=np.array([int(r['k']) for r in rr]); g=np.array([100*float(r['relative_RMSE_gain']) for r in rr])
        ax.plot(k,g,color='#566477',linewidth=1.0,zorder=1)
        ax.scatter(k[k<0],g[k<0],s=16,facecolors='white',edgecolors='#566477',linewidths=.9,zorder=2)
        ax.scatter(k[k>=0],g[k>=0],s=16,color='#276A8C',zorder=2)
        ax.axhline(0,color='#9A9A9A',lw=.65,ls='--',zorder=0)
        ax.set_xlim(-96,96); ax.set_ylim(-14,10); ax.set_yticks([-10,0,10])
        ax.set_ylabel('RMSE gain (%)')
        ax.set_title(str(year)+' | Common 275-day support',loc='left',pad=5)
        ax.text(-.10,1.06,chr(97+i),transform=ax.transAxes,fontweight='bold',fontsize=8,va='bottom')
    axs[-1].set_xticks([-90,-60,-30,0,30,60,90])
    axs[-1].set_xlabel('Prespecified displacement k (days); negative k uses future upstream')
    export(fig,'s1a_r1_placebo_gain')
    # Orthogonal evidence: annual and equal-year macro gains with conditional CIs;
    # regimes/baselines are separated, not ranked against each other.
    boot=read_csv(HERE/'s1a_r1_bootstrap_summary.csv')
    fig,axs=plt.subplots(1,3,figsize=(7.2047244094,3.4645669291),sharey=True)
    fig.subplots_adjust(left=.11,right=.98,bottom=.19,top=.77,wspace=.21)
    titles=[('past_only','Past-only primary'),('same_day','Same-day secondary'),('f2','F2 sensitivity')]
    for i,(comp,title) in enumerate(titles):
        ax=axs[i]
        for block,offset,color,marker in ((30,-.08,'#276A8C','o'),(60,.08,'#8A667F','s')):
            rr=[next(r for r in boot if r['comparison']==comp and r['circular']=='True' and int(r['block_days'])==block and r['scope']==scope)
                for scope in ('1981','1982','1983','MACRO_EQUAL_YEAR')]
            point=np.array([100*float(r['gain_point']) for r in rr]); lo=np.array([100*float(r['gain_lower']) for r in rr]); hi=np.array([100*float(r['gain_upper']) for r in rr])
            # Plot intervals directly: percentile CI need not contain the original point.
            x=np.arange(4)+offset
            ax.vlines(x,lo,hi,color=color,lw=1)
            ax.scatter(x,point,color=color,s=12,marker=marker,label=f'{block}-day blocks')
        ax.axhline(0,color='#9A9A9A',lw=.65,ls='--')
        ax.set_xticks(range(4),['1981','1982','1983','Macro'])
        ax.set_title(title,pad=7)
        ax.text(-.10,1.05,chr(97+i),transform=ax.transAxes,fontweight='bold',fontsize=8,va='bottom')
    axs[0].set_ylabel('RMSE gain (%)')
    handles,labels=axs[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.55,.98),ncol=2,fontsize=7)
    export(fig,'s1a_r1_conditional_gain')
    # Residual diagnostics were requested in original S0.1; no new model contrast.
    daily=read_csv(HERE/'scored_daily_view.csv')
    fig,axs=plt.subplots(3,1,figsize=(7.2047244094,6.4960629921),sharex=True,sharey=True)
    fig.subplots_adjust(left=.13,right=.97,bottom=.10,top=.91,hspace=.39)
    for i,year in enumerate((1981,1982,1983)):
        rr=[r for r in daily if int(r['fold'])==year and r['comparison']=='past_only']
        x=np.arange(1,len(rr)+1)
        axs[i].plot(x,[float(r['observed_anomaly']) for r in rr],color='#8E8E8E',lw=.7,label='Observed anomaly')
        axs[i].plot(x,[float(r['predicted_anomaly']) for r in rr],color='#276A8C',lw=.9,label='Predicted anomaly')
        axs[i].axhline(0,color='#AAAAAA',lw=.6,ls='--')
        axs[i].set_title(str(year)+' | Past-only, full year',loc='left',pad=5)
        axs[i].set_ylabel('Project Q anomaly')
        axs[i].text(-.10,1.06,chr(97+i),transform=axs[i].transAxes,fontweight='bold',fontsize=8,va='bottom')
    axs[-1].set_xlabel('Development day index')
    fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.99),ncol=2,fontsize=7)
    export(fig,'s1a_r1_residuals')
    dump(HERE/'plot_environment.json',{'python':sys.version,'numpy':np.__version__,'matplotlib':matplotlib.__version__,
        'plot_code_sha256':sha(__file__),'backend':'Python only','input_files_unchanged':True})
    print('Three scientific figures exported with alignment manifests.')

if __name__=='__main__': main()
