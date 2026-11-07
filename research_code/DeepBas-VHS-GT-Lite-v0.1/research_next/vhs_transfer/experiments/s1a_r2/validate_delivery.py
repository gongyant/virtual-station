"""Independent CSV arithmetic/coverage checks and bounded integrity validation."""
from pathlib import Path
import csv,json,hashlib,ast
import numpy as np

H=Path(__file__).resolve().parent;ROOT=H.parents[3];R1=H.parent/'s1a_r1';REPORTS=ROOT/'research_next/vhs_transfer/reports';P='vhs_next_s1a_r2_'
def read(name):
    with (H/(P+name+'.csv')).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,v):(H/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def near(a,b):assert np.allclose(a,b,rtol=1e-12,atol=1e-10),(a,b)
def subset(rows,**kw):return [r for r in rows if all(str(r[k])==str(v) for k,v in kw.items())]
def write(name,rows):
    with (H/(P+name+'.csv')).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    protected=json.loads((H/'integrity_before.json').read_text(encoding='utf-8'))['hashes']
    for p,v in protected.items():assert sha(ROOT/p)==v,p
    daily=read('delta_sse');annual=read('annual_metrics');swap=read('year_swap_predictions');swmet=read('year_swap_metrics');swstrata=read('year_swap_strata');strata=read('flow_strata')+read('exante_strata');disp=read('displacement_reanalysis');blockrows=read('orthogonal_blocks')+read('year_swap_orthogonal_blocks')
    threshold={int(r['fold']):r for r in read('thresholds')}
    with (R1/'views/feature_view.csv').open(encoding='utf-8') as f:up={r['date']:float(r['Q_input_byblk']) for r in csv.DictReader(f)}
    with (R1/'scored_daily_view.csv').open(encoding='utf-8') as f:old=list(csv.DictReader(f))
    parameters={(r['fold'],r['comparison']):r for r in json.loads((R1/'fitted_parameters.json').read_text())}
    total_checks=0;max_cross_ratio=0.;allmonth=[]
    for yr in (1981,1982,1983):
        for model in ('past_only','f2'):
            a=subset(daily,fold=yr,model=model);assert len(a)==365 and len({r['date'] for r in a})==365
            source=subset(old,fold=yr,comparison=model);assert [r['date'] for r in a]==[r['date'] for r in source]
            y,b,p=[np.array([float(r[k]) for r in a]) for k in ('observed','baseline','augmented')]
            for k,x in [('observed',y),('baseline',b),('augmented',p)]:near(x,[float(r[k]) for r in source])
            delta=(b-y)**2-(p-y)**2;near(delta,[float(r['DeltaSSE']) for r in a])
            am=subset(annual,fold=yr,model=model)[0];near(delta.sum(),float(am['DeltaSSE']))
            for kind in ('outcome','exante'):
                for state in ('LOW','MID','HIGH'):
                    ix=np.array([r[kind]==state for r in a]);st=subset(strata,fold=yr,model=model,grouping=kind,stratum=state)[0]
                    assert ix.sum()==int(st['n']);near(delta[ix].sum(),float(st['DeltaSSE']))
                    q=threshold[yr];vals=y if kind=='outcome' else np.array([up[str(np.datetime64(r['date'])-np.timedelta64(1,'D'))] for r in a]);lo=float(q['target_Q20' if kind=='outcome' else 'upstream_tminus1_Q20']);hi=float(q['target_Q90' if kind=='outcome' else 'upstream_tminus1_Q90']);expected=(vals<=lo) if state=='LOW' else ((vals>=hi) if state=='HIGH' else ((vals>lo)&(vals<hi)))
                    assert np.array_equal(ix,expected)
                    e0=(b-y)[ix];e1=(p-y)[ix];near(np.mean(e0**2)-np.mean(e1**2),float(st['bias_MSE_contribution'])+float(st['variance_MSE_contribution']))
                    total_checks+=1
            for m in range(1,13):
                ix=np.array([int(r['month'])==m for r in a]);allmonth.append(dict(fold=yr,model=model,support='MAIN_365',month=m,n=int(ix.sum()),SSE0=float(np.sum((b-y)[ix]**2)),SSE1=float(np.sum((p-y)[ix]**2)),DeltaSSE=float(delta[ix].sum())))
            for donor in range(1978,1984):
                a2=subset(swap,fold=yr,model=model,donor=donor);assert len(a2)==335
                targetdates=[r['date'] for r in a2];assert targetdates==[r['date'] for r in a[30:]]
                for r,o in zip(a2,a[30:]):
                    assert r['donor_anchor']==str(donor)+r['date'][4:]
                    assert r['outcome']==o['outcome'] and r['exante']==o['exante']
                    near(float(r['baseline']),float(o['baseline']));near(float(r['observed']),float(o['observed']))
                sy,sb,sp=[np.array([float(r[k]) for r in a2]) for k in ('observed','baseline','augmented')]
                # Independent scalar frozen-parameter reconstruction of EVERY donor output.
                pm=parameters[yr,model];beta=np.array(pm['beta']);scale=np.array(pm['upstream_scale']);climate=np.array(pm['upstream_monthly_climate'])
                expected=[]
                for r in a2:
                    anchor=np.datetime64(r['donor_anchor']);m=int(r['donor_anchor'][5:7])-1
                    w=np.array([np.mean([up[str(anchor-np.timedelta64(i,'D'))] for i in range(1,n+1)]) for n in (1,7,30)])
                    expected.append(max(0.,float(r['baseline'])+float(((w-climate[m])/scale)@beta)))
                near(sp,expected)
                if donor==yr:near(sp,p[30:])
                met=subset(swmet,fold=yr,model=model,donor=donor)[0];near(np.sum((sb-sy)**2-(sp-sy)**2),float(met['DeltaSSE']));near(np.sqrt(np.mean((sp-sy)**2)),float(met['RMSE1']))
                for kind in ('outcome','exante'):
                    group=subset(swstrata,fold=yr,model=model,donor=donor,grouping=kind);assert sum(int(r['n']) for r in group)==335
                    near(sum(float(r['DeltaSSE']) if r['DeltaSSE'] else 0. for r in group),float(met['DeltaSSE']))
                for m in range(1,13):
                    ix=np.array([int(r['date'][5:7])==m for r in a2]);allmonth.append(dict(fold=yr,model=model,support='YEAR_SWAP_335',donor=donor,month=m,n=int(ix.sum()),SSE0=float(np.sum((sb-sy)[ix]**2)),SSE1=float(np.sum((sp-sy)[ix]**2)),DeltaSSE=float(np.sum(((sb-sy)**2-(sp-sy)**2)[ix]))))
                total_checks+=1
    for r in blockrows:
        for j in (0,1):
            sse=float(r[f'SSE_between{j}'])+float(r[f'SSE_within{j}']);cross=abs(float(r[f'cross_term{j}']));assert cross<=1e-10+1e-12*sse
            max_cross_ratio=max(max_cross_ratio,cross/max(sse,1.))
        near(float(r['DeltaSSE_between'])+float(r['DeltaSSE_within']),float(r['SSE_between0'])+float(r['SSE_within0'])-float(r['SSE_between1'])-float(r['SSE_within1']))
    kset={-90,-60,-30,-14,-7,-3,0,3,7,14,30,60,90}
    for yr in (1981,1982,1983):
        ar=subset(disp,fold=yr,record='overall');assert {int(r['k']) for r in ar}==kset
        for r in ar:
            assert int(r['n'])==275
            a=subset(old,fold=yr,comparison=r['model']);assert len(a)==275 and a[0]['date']==f'{yr}-01-01' and a[-1]['date']==f'{yr}-10-02'
            e0=np.array([float(x['baseline'])-float(x['observed']) for x in a]);e1=np.array([float(x['augmented'])-float(x['observed']) for x in a]);near(e0@e0-e1@e1,float(r['DeltaSSE']))
            for kind in ('outcome','exante'):
                ss=subset(disp,fold=yr,model=r['model'],grouping=kind);assert sum(int(x['n']) for x in ss)==275;near(sum(float(x['DeltaSSE']) if x['DeltaSSE'] else 0 for x in ss),float(r['DeltaSSE']))
    for name in ('monthly_strata','year_swap_monthly_strata','low_flow_month_phase'):
        for r in read(name):
            if int(r['n'])==0:assert all(r[k]=='' for k in ('RMSE0','RMSE1','SSE0','SSE1','DeltaSSE'))
            assert (r['small_cell']=='True')==(int(r['n'])<10)
    # Supplemental monthly sums: union columns keep all month and donor cells, including Jan support of one day.
    keys=list(dict.fromkeys(k for r in allmonth for k in r))
    with (H/(P+'monthly_metrics.csv')).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(allmonth)
    audit=[]
    for file in H.glob('*.py'):
        tree=ast.parse(file.read_text(encoding='utf-8'));calls=[n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else '' for n in ast.walk(tree) if isinstance(n,ast.Call)]
        assert not {'fit','fit_model','ols','lstsq','pinv','minimize','polyfit','curve_fit'}.intersection(calls),file
        audit.append(dict(file=file.name,sha256=sha(file),forbidden_estimator_calls=0))
    qa=json.loads((H/'figure_qa_summary.json').read_text());assert len(qa)==11 and all(r['returncode']==0 for r in qa)
    for p,v in protected.items():assert sha(ROOT/p)==v,p
    summary=dict(status='PASS',identity='POST_HOC_EXPLORATORY_DIAGNOSTIC',protected_files=len(protected),changed_files=[],independent_stratum_and_swap_checks=total_checks,orthogonal_block_rows=len(blockrows),max_cross_term_over_SSE=max_cross_ratio,fit_calls=0,year_swap_prediction_rows=len(swap),year_swap_arms=len(swmet),displacement_arms=39,bootstrap_recomputed=False,qa=qa,code_audit=audit,empty_cells_preserved=True,write_scope='R2 directory and named R2 reports/status only; code review, not adversarial OS tracing',initial_numerical_issue='Absolute 1e-10 zero check encountered -1.1213e-10 roundoff on a placebo block. Replaced by scale-aware 1e-10 + 1e-12*SSE cross-term tolerance; exact decomposition unchanged.')
    dump('delivery_validation.json',summary)
    txt=f'''# VHS-NEXT-S1A-R2｜交付验证

身份：POST_HOC_EXPLORATORY_DIAGNOSTIC。数值/执行完整性 PASS 不代表科研主假设通过。

226个继承定向保护文件开始/结束SHA256一致。已封存预测、48套参数及训练月份均值、标准差、beta字节未变；E4/E5/论文/S0/S0.1/R0/R1清单内文件未变。没有重新进行大规模历史扫描。

48组R1指标独立按已评分日视图复核；历史bootstrap256行只读，不重抽样。六组365日原真实预测在生成任何swap之前由冻结参数重建，并满足rtol=1e−12、atol=1e−12；最大误差见pre_swap_validation.json。36组×335日共12060行交换预测再由独立逐日标量实现复核。每个目标年两种基线都保留1978–1983六条参照（五donor+self），同日期同目标基线同冻结beta/scaler同真实分组，无择优删除。

训练DSK Q20/Q90与上游t−1 Q20/Q90分别定义两套互斥完整分层。独立复核主365日每个日期标签与36组swap固定mask；各层SSE与年度加总、偏差平方+ddof=0误差方差恒等式通过。原39组placebo支持始终275日Jan1–Oct2，完整13个k，无跨支持排名。year-swap Jan31–Dec31固定335日；1978历史最早Jan1；1980按month-day映射，Mar1为实际Mar1，窗口自然含Feb29。

非重叠30日块从Jan1开始，年末5日独立块。335/275日对原日历块取交集并记录n。{len(blockrows)}行块分解SSE守恒且cross-term满足1e−10+1e−12*SSE，最大abs(cross)/max(SSE,1)={max_cross_ratio:.3g}。最初固定绝对1e−10的零检验在一条placebo块遇到−1.1213e−10浮点舍入，已明确改用SSE尺度容差；未改变分解、日期或模型。

5项CPU合成测试通过：偏差方差恒等式、阈值边界覆盖、跨块正交、闰年month-day/真实窗口、335日计数。全部R2 Python源AST未出现模型fit/OLS/pinv/lstsq/优化调用；没有导入历史拟合执行器。阈值为允许的训练分位数诊断统计，不更新模型scaler。写入仅R2及三个R2报告和status，无原始数据目录写入代码路径；该证明基于代码与限定哈希，不是对抗性OS沙箱。

五张图各有PDF/SVG/600dpi PNG，标注Retrospective post-hoc diagnostic.，同类面板共享y轴范围。渲染轴对齐、源码、5pt下限、最终PDF碰撞全部通过；逐年面板与整图人工检查见visual_qa.json。PDF库只读复用R1隔离目录，使用Python -B，没有安装依赖或修改历史缓存。

空单元n=0保留NA，n<10标小样本；不以空格为零误差。年度占比守卫、绝对贡献、固定top5/10/20、全部块删除及所有donor结果均保留。没有p值、独立确认、物理机制或lag识别升级。

复现顺序（当前封存目录不覆盖重跑）：在新的授权输出目录使用相同源码和冻结输入，analyze.py → build_reports.py → plot_results.py → figure_qa.py → validate_delivery.py。analyze.py已完成保护会拒绝自动重跑；后处理不修改历史或模型。代码/输入哈希、原始中间CSV及delivery_manifest.json均可追溯。

R1主失败结论不变。本轮没有新lag/OLS/ridge/Fourier/GNN/Muskingum/气象训练/GPU/S1B/S1C/E5I1。完成R2后停止等待批准。
'''
    (REPORTS/(P+'validation_report.md')).write_text(txt,encoding='utf-8')
    (REPORTS/(P+'status.txt')).write_text('VHS-NEXT-S1A-R2 COMPLETE\nIDENTITY=POST_HOC_EXPLORATORY_DIAGNOSTIC\nVALIDATION=PASS\nHISTORICAL_HASH_CHANGES=0\nMODEL_FIT_CALLS=0\nR1_MAIN_PRACTICAL_CRITERION=FAIL_UNCHANGED\nSTOPPED_AFTER_R2=TRUE\nAWAITING_NEXT_USER_AUTHORIZATION=TRUE\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('code_audit','qa')},ensure_ascii=False))

if __name__=='__main__':main()
