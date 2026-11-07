"""Post-seal R3 report assembly. Does not import the model worker."""
from common import *
def r(name):return read(H/(P+name+'.csv'))
def sel(rows,**kw):return [x for x in rows if all(str(x[k])==str(v) for k,v in kw.items())]
def f(v,n=3):return 'NA' if v in ('',None) else f'{float(v):.{n}f}'
def gain(x):return f"{100*float(x['relative_RMSE_gain']):+.3f}%"
def main():
    verify_inputs();assert load(H/'scoring_complete.json')['status']=='PASS'
    fm=r('fold_metrics');cg=r('conditional_gain');st=r('exante_strata');sw=r('year_swap_metrics');ss=r('year_swap_strata');rk=r('year_swap_ranks');ma=r('macro_metrics');bs=r('bootstrap_summary');diag=read(H/'feature_diagnostics.csv')
    s=['# VHS-NEXT-S1A-R3｜气象条件化上游增量预测信息','',f'身份：**{IDENTITY}**。数据准入PASS仅限项目数值级回顾性探索，所有年份早已暴露，不是独立测试、严格zero-shot或河道输移因果识别。Q单位/日界仍未正式认证；年水量只报数值日和误差，不换算m³。','',
       'R1主实践规则未通过。R2的1981 MID主损失、事前LOW改善、年度对齐优势不跨年、1983主要块均值收益及远错位慢变贡献保持原事实；共同气象、季节相位与水文状态原先尚未区分。本轮不改写历史结论或已有论文。','',
       '## 固定执行与公平支持','',
       '气象仅使用既有BYBLK→DSK增量流域日P/T。P7、T7均为t−7..t−1均值；旧P_inc_7d为总和，两者相差常数7，窗口相同，旧表未修改。训练1066/1431/1796日统一从1978-01-31开始，开发各365日。Monthly目标均值和三列上游异常尺度原样复用R1。M0/M1预测逐日复用，未重拟合；只拟合M2(P7,T7)及M3(P7,T7,W1,W7,W30)共6次OLS，无截距/调参/ridge/lag搜索。所有预测含18条交换参照先保存哈希，再由独立评分进程打开开发标签。','',
       '## 1. P7/T7是否提供季节外预测信息？','']
    for x in sel(cg,comparison='M2_vs_M0'):s.append(f"- {x['fold']}：M2相对M0 gain={gain(x)}，RMSE {f(x['RMSE0'])}→{f(x['RMSE1'])}，DeltaSSE={f(x['DeltaSSE'])}。")
    m=sel(ma,comparison='M2_vs_M0')[0];s.append(f"三年等权宏平均gain={gain(m)}，改善年数={m['improved_years']}/3，最差年份={m['worst_year']}。只说明指定P/T窗口在固定Monthly之外的有限线性预测表现，不证明已控制所有气象。")
    s+=['','## 2. M3相对M2三年分别改善多少？','']
    for x in sel(cg,comparison='M3_vs_M2'):s.append(f"- {x['fold']}：gain={gain(x)}，RMSE {f(x['RMSE0'],5)}→{f(x['RMSE1'],5)}，DeltaNSE={f(x['DeltaNSE'],5)}，DeltaSSE={f(x['DeltaSSE'])}，Bias {f(x['Bias0'])}→{f(x['Bias1'])}，PBIAS {f(x['PBIAS0'])}%→{f(x['PBIAS1'])}%。")
    m=sel(ma,comparison='M3_vs_M2')[0];s.append(f"主条件比较宏平均gain={gain(m)}，改善{m['improved_years']}/3，最差年份={m['worst_year']}。2%不作为本轮确认性阈值。")
    s+=['','固定参数条件bootstrap：每年内配对抽样，10000次，seed20261011，30/60日circular及noncircular全部保留；不覆盖训练参数或历史选择不确定性，三年不是独立流域样本，无总体p值。']
    for x in sel(bs,comparison='M3_vs_M2',scope='MACRO_EQUAL_YEAR'):s.append(f"- circular={x['circular']}，block={x['block_days']}：gain95%CI [{100*float(x['gain_lower']):+.3f}%, {100*float(x['gain_upper']):+.3f}%]。")
    s+=['','## 3. 气象信息是否改变1981失败的性质？','']
    for comp in ('M1_vs_M0','M2_vs_M0','M3_vs_M2','M3_vs_M1'):
        x=sel(cg,fold=1981,comparison=comp)[0];s.append(f"- 1981 {comp}：gain={gain(x)}，DeltaSSE={f(x['DeltaSSE'])}，between/within Δ={f(x['DeltaSSE_between'])}/{f(x['DeltaSSE_within'])}。")
    x=sel(cg,fold=1981,comparison='M3_vs_M2')[0];s.append('在当前条件模型下1981上游增量'+('仍为负；原1981失败没有被此气象条件化消除。' if float(x['relative_RMSE_gain'])<=0 else '转为正，但只是不同固定对照中的条件开发结果，不能改写R1失败结论。'))
    s+=['','## 4. 1983上游增益是否仍存在？','']
    x=sel(cg,fold=1983,comparison='M3_vs_M2')[0];s.append(f"1983 M3_vs_M2 gain={gain(x)}，DeltaSSE={f(x['DeltaSSE'])}；"+('条件上游增量仍保留。' if float(x['DeltaSSE'])>0 else '在这一指定条件模型中没有保留正的年度上游增量。'))
    s+=['','## 5. 低上游状态增益是否仍存在？','', '使用每折训练上游U(t−1)的Q20/Q90；真实开发日期分组对所有M0–M3及交换donor固定。不是下游真实低流标签。']
    for yr in (1981,1982,1983):
        for comp in ('M3_vs_M2','M1_vs_M0','M2_vs_M0','M3_vs_M1'):
            rr=sel(st,fold=yr,comparison=comp);s.append(f"- {yr} {comp}："+'；'.join(f"{x['stratum']} n={x['n']}, RMSE {f(x['RMSE0'])}→{f(x['RMSE1'])}, gain={gain(x)}, ΔSSE={f(x['DeltaSSE'])}" for x in rr)+'。')
    s+=['','## 6. 改善来自块均值还是块内变化？','', '固定30日块从Jan1开始，最后5日另块；between与within正交加总，不等同基流与快速传播。']
    for comp in ('M3_vs_M2','M2_vs_M0','M3_vs_M1'):
        for x in sel(cg,comparison=comp):s.append(f"- {x['fold']} {comp}：between Δ={f(x['DeltaSSE_between'])}，within Δ={f(x['DeltaSSE_within'])}，合计={f(x['DeltaSSE'])}。")
    s+=['','## 7. 气象固定后的年份交换是否保留类似增益？','', '仅335日Jan31–Dec31；同目标实际P7/T7、同M3参数及训练尺度，只换W1/W7/W30。month-day对齐，1980真实窗口可自然含Feb29，1978不借1977。五donor全部列出，未来donor仅历史非因果negative control。不能与365日主结果直接排名；donor不是独立随机样本。']
    for yr in (1981,1982,1983):
        ranks=sel(rk,fold=yr,scope='overall')[0];s.append(f"- {yr}：真实全年名次={ranks['rank']}/6，{ranks['donors_better']}/5 donor优于真实，ties={ranks['ties']}；donor相对固定M2 gain min/median/max={100*float(ranks['donor_gain_min']):+.3f}%/{100*float(ranks['donor_gain_median']):+.3f}%/{100*float(ranks['donor_gain_max']):+.3f}%。")
        for x in sel(sw,fold=yr):s.append(f"  donor={x['donor']}{' real' if x['real_aligned']=='True' else ''}：M2/M3 RMSE={f(x['RMSE0'])}/{f(x['RMSE1'])}，gain={gain(x)}，ΔSSE={f(x['DeltaSSE'])}，between/within Δ={f(x['DeltaSSE_between'])}/{f(x['DeltaSSE_within'])}。")
        for scope in ('between','within','LOW','MID','HIGH'):
            x=sel(rk,fold=yr,scope=scope)[0];s.append(f"  {scope} 真实名次={x['rank']}/6，donor优于真实={x['donors_better']}/5。")
        for state in ('LOW','MID','HIGH'):
            rr=sel(ss,fold=yr,stratum=state);s.append('  '+state+' 全部gain：'+'；'.join(f"{x['donor']}:{gain(x)}" for x in rr)+'。')
    s+=['','## 8. 共线性或估计不稳定？','', '满秩为执行门槛，不保证物理可辨识。训练标准化beta、相关矩阵、SVD和VIF全部保存；VIF由训练相关矩阵逆对角得到，不新增辅助目标模型拟合。condition>30/VIF>10只警示，不改模型。']
    for x in diag:s.append(f"- {x['fold']} {x['model']}：condition={f(x['condition'])}，VIF={x['VIF']}，beta按{x['features']}顺序={x['beta']}，warning={x['warning']}。")
    s+=['','## 9. 能否部分排除共同气象解释？','', '本比较最多针对“已指定增量流域P7/T7在当前线性季节模型中足以吸收上游增量”的狭义解释。M3_vs_M2的正增益只表明这些有限P/T特征之外仍有预测信息；负增益只表明当前有限年份/特征/线性设定未检测到额外效用。任何单年正负或donor排序均不能排除未测气象、非线性气象响应、共同湿润状态或季节相位。不是完整共同气象驱动反证。','',
       '## 10. 哪些水文机制仍无法区分？','', '增量流域P/T不能充分代表完整上游降水/温度、降雪累积、雪融、地下水储量、土壤状态、调度及再分析误差。没有独立传播时滞/流量日界证据；真实河道传播、共同驱动与慢变代理未被因果分离。禁止河道因果、独立气象验证、多站点泛化或strict zero-shot主张。','',
       '## 11. 历史冻结文件完整性','', '历史保护清单及R1/R2交付/预测/参数在执行前后SHA保持一致（实际数量及独立检查见validation_report）。M0/M1原预测直接复用，旧E4 R1/R2/Fourier6、论文、S0/S0.1/S1A-R0/R1/R2未改。6次真实OLS全部在本轮授权范围内且先于开发标签打开；没有额外真实fit、超参搜索或GPU。','',
       '## 12. 下一轮是否需要新的独立数据？','', '是。当前气象条件假设也来自已暴露1978–1983数据；继续叠加诊断不能恢复独立性。下一步优先获取并核实新的未参与设计年份或站点、同步气象覆盖和流量元数据，在解封标签前固定单一假设、模型与评价边界。本轮不下载、补数据、训练新模型或自行解封。','',
       '## 完整指标与次要比较','']
    for x in fm:s.append(f"- {x['fold']} {x['model']}：RMSE={f(x['RMSE'])}, MAE={f(x['MAE'])}, NSE={f(x['NSE'],5)}, Bias={f(x['Bias'])}, PBIAS={f(x['PBIAS'])}%, 日和数值误差={f(x['numeric_annual_sum_error'])}, clip={x['clip_n']}/365, rawRMSE={f(x['raw_RMSE'])}。")
    for x in ma:s.append(f"- 等权年度宏平均 {x['comparison']}：gain={gain(x)}，DeltaNSE={f(x['DeltaNSE'],5)}，年度DeltaSSE均值={f(x['DeltaSSE'])}，worst={x['worst_year']}，改善{x['improved_years']}/3。")
    s+=['', '所有逐月、状态、块、donor、条件bootstrap正负结果均保留于CSV，无2%确认性判定，无p值，未因表现修改特征。最终状态：','', '`R3_DATA_GATE=PASS`','', '`R3_CONDITIONAL_ANALYSIS_COMPLETE=true`','', '`NEW_BLIND_TEST_PERFORMED=false`','', '`STRICT_ZERO_SHOT_CLAIM=false`','', '`HISTORICAL_FILES_CHANGED=false`','', 'R3完成后停止，等待下一次批准。']
    (REPORTS/(P+'results.md')).write_text('\n'.join(s)+'\n',encoding='utf-8')
    limits=['# VHS-NEXT-S1A-R3｜局限与解释边界','',IDENTITY,'',
      '本地ERA5生成链未发现目标DSK Q参与P/T构造、筛选或标准化；这仅排除所检查实现的直接目标路径，不证明ERA5供应商同化体系与任何地面水文观测完全独立。流域选择及本轮科学假设受历史Q暴露影响，后验设计身份保留。旧D5选择污染不被继承为训练输入，但不能据此将新设计称为独立。',
      '强迫UTC日界、00UTC累计后移一天、mm/°C转换由项目代码和实际元数据支持；站点Q单位/日界/发布时间未认证，故nominally past-only不等于实时可部署。再分析利用后验资料，不认证operational forecasting。',
      'P7/T7仅固定增量流域七日均值，不是全流域或完整共同气象驱动集。未包括融雪、雪储量、调度和非线性/交互机制。不能以两列气象控制排除所有共同原因。',
      'M2/M3固定Monthly残差OLS、无截距，气象按训练anchor month去季节化并训练std缩放；M1沿用旧三参数，上游新M3系数联合重估而非简单沿用M1系数。系数竞争与相关性影响解释，不能把某系数等同过程效应。',
      '365日主支持、335日swap支持分别比较；每个target的真实P/T、baseline、M3参数和mask在所有donor间相同。month-day映射保留donor真实窗口；不同donor边际分布/湿润状态不相同，五donor非独立随机重复，future donor非因果诊断。',
      '30日正交块为固定误差分解，between不等同基流、within不等同快速输移。真实优于donor与真实优于M2是不同参照，不能混用。状态LOW由训练上游t−1阈值定义，非下游目标低流标签。',
      '三个相邻开发年、重叠训练窗、单上下游案例，均早已暴露。10000次年内配对30/60日circular/noncircular区间只条件于已估计参数和所见年份，不覆盖训练估计、后验方法选择或新站点不确定性；不用原2%阈值作本轮确认性标准，不报告总体p值。',
      '数据/来源/执行/数值PASS不同于科研增量稳定性PASS。哈希仅覆盖定向继承及本轮输入清单，不声称全磁盘审计。角色隔离由独立worker及白名单实现，不是对抗性OS沙箱。所有异常停止，不自动删日/补数据/换变量/搜索。',
      '既有科学结果与论文冻结；没有新盲测、strict zero-shot、河道因果识别、独立气象认证或跨流域泛化。需要新的独立数据而非无限重分析旧年。', '',
      '`R3_DATA_GATE=PASS`\n\n`R3_CONDITIONAL_ANALYSIS_COMPLETE=true`\n\n`NEW_BLIND_TEST_PERFORMED=false`\n\n`STRICT_ZERO_SHOT_CLAIM=false`\n\n`HISTORICAL_FILES_CHANGED=false`']
    (REPORTS/(P+'limitations.md')).write_text('\n\n'.join(limits)+'\n',encoding='utf-8')
    print('R3 twelve-question results and limitations written')
if __name__=='__main__':main()
