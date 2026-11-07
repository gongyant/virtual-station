"""Reports from completed R2 diagnostics; never fits or modifies historical artifacts."""
from analyze import *

def f(v,n=2): return 'NA' if v in ('',None) else f'{float(v):.{n}f}'
def rows(name): return read(HERE/(PREFIX+name+'.csv'))
def pick(data,**kwargs): return [r for r in data if all(str(r[k])==str(v) for k,v in kwargs.items())]
def report(name,text): (REPORTS/(PREFIX+name+'.md')).write_text(text,encoding='utf-8')

def main():
    protected()
    annual=rows('annual_metrics');flow=rows('flow_strata');ex=rows('exante_strata');inf=rows('influence');ranks=rows('year_swap_ranks');sw=rows('year_swap_metrics');ss=rows('year_swap_strata');mon=rows('monthly_strata');dis=rows('displacement_reanalysis');daily=rows('delta_sse')
    phase=[];composition=[];signatures=[]
    for yr in YEARS:
        for model in ('past_only','f2'):
            a=pick(daily,fold=yr,model=model)
            for kind in ('outcome','exante'):
                for m in range(1,13):
                    for half in ('day01_15','day16_end'):
                        v=[r for r in a if int(r['month'])==m and r[kind]=='LOW' and ((int(r['date'][-2:])<=15)==(half=='day01_15'))]
                        y,b,p=[np.array([float(r[k]) for r in v]) for k in ('observed','baseline','augmented')]
                        phase.append(dict(identity=IDENTITY,fold=yr,model=model,grouping=kind,month=m,within_month_phase=half,small_cell=len(v)<10)|pair(y,b,p))
        a=pick(daily,fold=yr,model='past_only');ol={r['date'] for r in a if r['outcome']=='LOW'};el={r['date'] for r in a if r['exante']=='LOW'}
        composition.append(dict(fold=yr,outcome_low_n=len(ol),exante_low_n=len(el),intersection_n=len(ol&el),union_n=len(ol|el),jaccard=len(ol&el)/len(ol|el)))
        for comp in ('past_only','f2'):
            ar=next(r for r in annual if r['fold']==str(yr) and r['model']==comp)
            low=next(r for r in flow if r['fold']==str(yr) and r['model']==comp and r['stratum']=='LOW')
            xl=next(r for r in ex if r['fold']==str(yr) and r['model']==comp and r['stratum']=='LOW')
            sr=pick(ranks,fold=yr,model=comp)
            signatures.append(dict(fold=yr,model=comp,annual_gain=float(ar['relative_RMSE_gain']),outcome_low_gain=float(low['relative_RMSE_gain']),exante_low_gain=float(xl['relative_RMSE_gain']),swap_overall_rank=int(next(r for r in sr if r['grouping']=='overall')['rank']),swap_within_rank=int(next(r for r in sr if r['stratum']=='within')['rank']),swap_exante_low_rank=int(next(r for r in sr if r['grouping']=='exante' and r['stratum']=='LOW')['rank'])))
    write('low_flow_month_phase',phase);write('low_flow_group_overlap',composition);dump('interpretation_signatures.json',signatures)
    s=['# VHS-NEXT-S1A-R2｜冻结预测误差结构与年份交换反证','',f'身份：**{IDENTITY}**。全部结果为历史已暴露数据上的回顾性事后诊断，不是独立测试、确认性检验或因果证据。单位沿用项目 Q 数值单位，SSE 为 Q²；单位、日界与供数时刻未认证。','',
       'R1 主结论保持：1981/1982/1983 相对 RMSE 增益 −10.487%/−0.091%/+8.079%，三年等权宏平均 −0.833%，预定主实践标准未通过。R2 没有重新拟合、搜索或重新 bootstrap。','',
       '## 1. 1981 全年恶化由哪些日期与区间主导？','']
    for r in pick(flow,fold=1981,model='past_only'):
        s.append(f"- Outcome {r['stratum']}：n={r['n']}，DeltaSSE={f(r['DeltaSSE'])}，RMSE {f(r['RMSE0'])}→{f(r['RMSE1'])}。")
    s += ['', '全年 DeltaSSE=−163407.47。MID 贡献 −137498.89，HIGH 仅2日贡献 −27236.32；训练 Q90 的 HIGH 与日常语言的所有洪水事件并不等同。不能把恶化全部归给极少数 HIGH 日。绝对贡献最大的前5日恰为 5月27–31日，共 −59500.51；前20日净贡献 −119440.45，覆盖总 |DeltaSSE| 的41.23%。', '']
    for r in pick(inf,fold=1981,model='past_only',record='top_day')[:10]:
        s.append(f"- {r['date']}：outcome={r['outcome']}，ex-ante={r['exante']}，DeltaSSE={f(r['DeltaSSE'])}。")
    s += ['', '完整前20日、正负总贡献、前5/10/20集中度和全部块删除诊断保存在 influence.csv。N_eff 是贡献集中度，不是独立样本数。','']
    for yr in YEARS:
        r=pick(inf,fold=yr,model='past_only',record='top_summary')[0];fl=pick(inf,fold=yr,model='past_only',record='leave_one_block_out');changed=[x for x in fl if x['sign_changed']=='True']
        s.append(f"- {yr}：正贡献 {f(r['positive_total'])}，负贡献 {f(r['negative_total'])}，N_eff={f(r['N_eff_contribution_days'])}；删除固定30日块导致年度符号改变 {len(changed)}/{len(fl)}。")
        for x in changed:s.append(f"  删除 {x['start']}–{x['end']} 后剩余 DeltaSSE={f(x['remaining_DeltaSSE'])}；仅为影响诊断，不更新正式结果。")
    s += ['', '## 2. 低流改善是绝对下降还是分母效应？','']
    for yr in YEARS:
        for model in ('past_only','f2'):
            r=pick(flow,fold=yr,model=model,stratum='LOW')[0]
            s.append(f"- {yr} {model} outcome LOW n={r['n']}：RMSE {f(r['RMSE0'],4)}→{f(r['RMSE1'],4)}，绝对变化 {float(r['RMSE1'])-float(r['RMSE0']):+.4f}；DeltaSSE={f(r['DeltaSSE'])}；MSE差={f(r['MSE_difference'],4)}，偏差平方贡献={f(r['bias_MSE_contribution'],4)}，组内方差贡献={f(r['variance_MSE_contribution'],4)}。")
    s += ['', 'Monthly 低流误差确实绝对下降，不只是百分比分母造成：三年 RMSE 减少约1.39/1.27/1.87。1981 F2-only 低流 RMSE 已为2.7683，远低于 Monthly-only 的6.7383；F2+upstream 为3.5258，虽绝对上低于 Monthly+upstream 的5.3477，却相对其自身对照恶化27.36%。必须区分基线之间的绝对水平与各自上游增量。1981 Monthly LOW 均值偏差反而由2.0180升至2.6961，改善来自组内误差方差减少；F2 LOW 的偏差平方和方差均恶化。1982/1983 的低流改善较多来自偏差项，不能统一解释为传播。','',
       '## 3. 事前分层是否支持同样的低流改善？','']
    for yr in YEARS:
        for model in ('past_only','f2'):
            r=pick(ex,fold=yr,model=model,stratum='LOW')[0]
            s.append(f"- {yr} {model} 已知上游 LOW：n={r['n']}，RMSE {f(r['RMSE0'],4)}→{f(r['RMSE1'],4)}，增益 {100*float(r['relative_RMSE_gain']):+.2f}%，DeltaSSE={f(r['DeltaSSE'])}。")
    s += ['', '两种基线下三年事前上游 LOW 均改善。因此不能将总体低状态改善判定为只有 outcome 条件选择才出现；OUTCOME_CONDITIONING_SENSITIVE 的整体现象触发条件不成立。但1981 outcome LOW 在F2下恶化、ex-ante LOW却改善，说明具体标签和基线确实影响结论。事前 LOW 是已知上游状态，绝非下游真实低流量分类。','']
    for r in composition:s.append(f"- {r['fold']}：两种 LOW 交集 {r['intersection_n']} 日，outcome/ex-ante分别 {r['outcome_low_n']}/{r['exante_low_n']} 日，Jaccard={r['jaccard']:.3f}。")
    s += ['', '## 4. 四格基线与月份、月内相位','', '四格冻结预测在每种分层内使用相同日期。A/B为Monthly-only/+upstream，C/D为F2-only/+upstream；详见 four_cell_baselines.csv（绝对 RMSE/MAE/Bias/SSE 和两组配对 DeltaSSE）。1981 outcome LOW 的增量方向随季节表示翻转，支持“增益依赖季节表示”，但F2仍未修复年度稳定性，也不能证明Monthly季节不足是唯一原因。','', '以下为 outcome LOW 各月 n、Monthly/F2 DeltaSSE（全部空格及小样本格保留在 monthly_strata.csv；n<10只作不稳定描述）。']
    for yr in YEARS:
        cells=[]
        for m in range(1,13):
            a=pick(mon,fold=yr,model='past_only',grouping='outcome',stratum='LOW',month=m)[0];c=pick(mon,fold=yr,model='f2',grouping='outcome',stratum='LOW',month=m)[0]
            cells.append(f"{m:02d}月 n={a['n']}, Δ={f(a['DeltaSSE'])}/{f(c['DeltaSSE'])}")
        s.append(f"- {yr}："+'；'.join(cells)+'。')
    s += ['', '固定月内01–15/16–月底的 LOW 组成、偏差、方差及绝对误差另见 low_flow_month_phase.csv。未按结果寻找分割点、调整季节谐波或改变评价样本。月份与低流状态重叠，不是两条独立证据。','']
    # Show every nonempty 1981 outcome LOW phase cell, enabling the phase explanation to be reviewed.
    for r in phase:
        if r['fold']==1981 and r['grouping']=='outcome' and r['n']:
            s.append(f"- 1981 {r['model']} {r['month']:02d}月 {r['within_month_phase']}：n={r['n']}，RMSE {f(r['RMSE0'],3)}→{f(r['RMSE1'],3)}，Bias {f(r['Bias0'],3)}→{f(r['Bias1'],3)}，DeltaSSE={f(r['DeltaSSE'])}。")
    s += ['', '1981的具体相位线索：2–3月Monthly-only在LOW样本中多为约−4的低估，上游修正可补偿；F2-only在这些样本已接近观测或轻微高估，同方向上游修正转为过估。11月LOW全部位于下半月，Monthly偏差14.956→12.541，而F2偏差1.227→−1.170，其DeltaSSE仅4.51，远小于Monthly的677.94。12月两个半月的增量方向又不同。样本与季节相位重叠可以解释敏感性现象，不能识别季节不足的因果比例。', '', '## 5. 块均值与块内误差哪部分决定全年结果？','']
    for r in annual:s.append(f"- {r['fold']} {r['model']}：between Δ={f(r['DeltaSSE_between'])}，within Δ={f(r['DeltaSSE_within'])}，合计 {f(r['DeltaSSE'])}。")
    s += ['', '1981两部分都恶化，块均值损失较大；1982 Monthly的块内改善被块均值恶化抵消；1983 Monthly几乎全部改善来自块均值，F2的块内部分甚至恶化。此正交数学分解不把 between 等同基流，也不把 within 等同真实快速河道传播。','', '## 6. 年份交换中真实对齐的位置','', '仅335日 Jan31–Dec31，同一目标季节基线、beta、训练月份均值、尺度和真实日期分层。每年每种基线完整报告五个donor及self。如下相对RMSE增益只在本335日支持比较；排序按 augmented RMSE，1最好；并列按固定数值容差，不构造p值。','']
    for yr in YEARS:
        for model in ('past_only','f2'):
            r=pick(ranks,fold=yr,model=model,grouping='overall')[0]
            s.append(f"- {yr} {model}：真实名次 {r['rank']}/6，{r['donors_better']}/5 donor超过真实，ties={r['donor_ties']}；donor增益 min/median/max={100*float(r['donor_gain_min']):+.3f}%/{100*float(r['donor_gain_median']):+.3f}%/{100*float(r['donor_gain_max']):+.3f}%。")
            for x in pick(sw,fold=yr,model=model):s.append(f"  donor {x['donor']}{' self' if x['real_aligned']=='True' else ''}：RMSE {f(x['RMSE0'],4)}→{f(x['RMSE1'],4)}，gain={100*float(x['relative_RMSE_gain']):+.3f}%，ΔSSE={f(x['DeltaSSE'])}，between/within Δ={f(x['DeltaSSE_between'])}/{f(x['DeltaSSE_within'])}。")
            for kind,state in [('orthogonal','between'),('orthogonal','within'),('outcome','LOW'),('exante','LOW')]:
                z=pick(ranks,fold=yr,model=model,grouping=kind,stratum=state)[0];s.append(f"  {kind}/{state} 真实名次={z['rank']}/6；donor胜出={z['donors_better']}/5。")
    s += ['', '1983真实对齐在两种基线的整体、between、within及事前LOW中均排第一，提供单年年份对应信息的描述性线索；1981/1982不复现。尤其1983相对自身基线的年度改善主要来自between，而真实对齐相对donor的within比较也占优：这两种参照不同，不能混为“块内绝对误差改善很大”。不能据此确认跨年稳定事件同步能力。','', '## 7. 交换年份是否保留类似低流改善？','']
    for yr in YEARS:
        for model in ('past_only','f2'):
            for kind in ('outcome','exante'):
                r=pick(ss,fold=yr,model=model,grouping=kind,stratum='LOW');don=[x for x in r if x['real_aligned']=='False'];real=next(x for x in r if x['real_aligned']=='True');good=sum(float(x['DeltaSSE'])>0 for x in don)
                s.append(f"- {yr} {model} {kind} LOW：真实gain={100*float(real['relative_RMSE_gain']):+.2f}%；{good}/5 donor仍改善；所有donor gain="+', '.join(f"{x['donor']}:{100*float(x['relative_RMSE_gain']):+.2f}%" for x in don)+'。')
    s += ['', '部分donor仍保留低流收益，说明“低流改善”本身不能识别目标年份的独特同步。1983真实优于全部donor仍只是一年条件性线索。','', '## 8. 原+30/+60远错位增益来自哪些状态和日期？','', '这里只用冻结275日 Jan1–Oct2支持，不与365/335日直接排名。每个k的系数来自R1其原冻结对照，未重新fit，也未把+60选作主lag。']
    for yr in YEARS:
        for k in (30,60):
            ar=pick(dis,fold=yr,k=k,record='overall')[0]
            s.append(f"- {yr} k=+{k}：Δ={f(ar['DeltaSSE'])}，between/within={f(ar['DeltaSSE_between'])}/{f(ar['DeltaSSE_within'])}。")
            for kind in ('outcome','exante'):
                a=pick(dis,fold=yr,k=k,grouping=kind);s.append('  '+kind+' '+', '.join(f"{x['stratum']} n={x['n']} Δ={f(x['DeltaSSE'])}" for x in a)+'。')
            a=pick(inf,fold=yr,model=f'placebo_k_{k:+d}',record='top_day')[:5]
            s.append('  绝对贡献前5日：'+'；'.join(f"{x['date']} {x['outcome']}/{x['exante']} Δ={f(x['DeltaSSE'])}" for x in a)+'。')
    s += ['', '远错位收益多数来自MID和块均值部分，1981 k+30事前HIGH也有较大贡献；LOW的贡献绝对量小。不同年k+30/+60的within正负不一致，不能解释为最优物理时滞。','',
       '## 9. 四种竞争解释的描述性证据','',
       '- H1：分层确实改变样本和1981 F2低流结论，但事前LOW在两种基线下三年均改善，整体“仅outcome条件才有收益”不成立。不能据此定量分离选择效应。',
       '- H2：季节表示敏感和收益主要落在块均值部分，与上游补偿残余季节或慢变状态相容；没有识别其唯一来源。',
       '- H3：1981贡献集中且5月末事件影响大；然而严格HIGH仅贡献部分损失，大量损失仍为MID，不能说少数HIGH解释所有年度失败。',
       '- H4：1983对全部donor的优势在F2、事前LOW和within比较中保留；1981/1982年度对齐优势缺失，故不支持跨年稳定的年份特异信息。',
       '', '## 10. 仍无法识别的物理机制','',
       '共同气象驱动、年份湿润状态、季节相位与缓慢河道响应未被分离；不能确认真实传播时滞、传播因果效应、地下水/雪融机制、多站点泛化、strict zero-shot或独立盲测成功。五个donor不是独立随机样本。未来donor仅为历史非因果negative control。',
       '', '## 11. 冻结完整性与验证','',
       '226个定向保护文件（继承150个历史保护项，合并R1交付/参数/预测/视图/执行冻结清单去重）均哈希不变。48组R1指标复核，365日六组真实重建全部通过；36组年份交换共12060行，39组原错位完整保留。参数/预测/scaler/beta未改，fit=0。分层互斥覆盖、SSE加总、ddof=0偏差方差恒等式和块正交守恒均通过。详细验证及可复现代码见validation_report与JSON；没有重跑大型历史审计。',
       '', '## 12. 下一阶段唯一建议假设','',
       '**上游异常对目标的增量主要体现为年份特异的慢变预测状态；日内块残差信息的优势不能跨年份稳定复现。** 这是由当前结果生成的待检验假设。将来须在新独立年份、预先固定的季节基线及事前分层下区分它与稳定事件同步信息；本轮不执行该实验。',
       '', 'R2完成后停止，等待用户下一次批准。全部正负结果、空格及小样本格保留在CSV中。']
    report('results','\n'.join(s)+'\n')
    report('interpretation_limits','\n'.join(['# VHS-NEXT-S1A-R2｜解释边界','',IDENTITY,'',
        'Outcome分层标签：OUTCOME_CONDITIONED_POST_HOC。Ex-ante分层只表示真实已知上游t−1状态，所有donor/placebo均沿用同一真实日期分组，不对替代上游重新分层。阈值来自各折原训练日期，未使用开发期估计。整体OUTCOME_CONDITIONING_SENSITIVE触发条件未满足；具体1981F2结果仍高度依赖分层。','',
        '全年365、year-swap335和displacement275日是不同支持。原365日主结论及宏平均不能由子支持改善替换。原13个k全部保留，未选择lag。所有计算均固定参数，无模型拟合、scaler重估或新谐波。','',
        '年份交换按month-day匹配。1980 donor的Mar1对应真实1980-03-01，窗口自然包含Feb29；非闰target无Feb29，不补齐。1978最早anchor Jan31，30日历史从Jan1开始，不虚构1977。未来donor不是合法实时输入。交换保留donor实际窗口的季节内变化及自相关，不保留目标的边际分布/年际湿润状态，不完全控制共同驱动。五donor固定且非独立，无显著性p值。','',
        '30日非重叠块从Jan1起，年末5日另块；335/275日仅用原日历块与支持的交集（部分块如实计n）。between与within为正交误差表示，不等同基流/快流机制。比donor的within更好与比自己的基线within更好是不同问题。','',
        '正DeltaSSE表示改善；误差方向prediction−observation。有符号贡献可能超过100%或为负；当abs年度净差≤max(1e−10,1%总绝对日贡献)时抑制年度占比。绝对贡献比例及原始值始终保留。空单元n=0，指标NA；n<10标为小样本，不改阈值。N_eff是贡献集中度，不是独立重复。','',
        '低流偏差减少可能有预测价值，方差减少不自动具有物理含义。月份/流量状态/月内相位是重叠的同一组资料，没有独立复现含义。前5/10/20日和固定块删除只能诊断影响，不能删除不利日期改写正式评价。','',
        '哈希验证限于继承的定向保护清单，不声称全磁盘或对抗性OS访问审计。所有本轮写入由代码限定为R2目录及三个R2报告和status；没有向原始数据目录写入的代码路径。单位、日界、供数时刻继续未认证，不转换物理流量单位。','',
        '1983的正线索不能抵消1981/1982失败，不确认传播因果、lag、地下水/雪融、多站点、zero-shot或独立测试。R2结束即停止。'])+'\n')
    print('Results and limits written; low-flow phase cells',len(phase))

if __name__=='__main__': main()
