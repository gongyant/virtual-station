"""Independent score/verification process. First verifies prediction seal, then opens exposed Q."""
from engine import metric
from common import *
import collections,sys
checks=[]
def ck(name,value):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
def main():
 if (ROOT/'SHA256SUMS.txt').exists():raise FileExistsError('FROZEN_P7A_NO_SCORE_REWRITE')
 status=readj(ROOT/'P7A_FINAL_STATUS.json');protocol=readj(ROOT/'P7A_FROZEN_PROTOCOL.json');cache=readj(ROOT/'cache/TRAINING_ONLY_2017.json')
 cv=rows(ROOT/'P7A_CV_PREDICTIONS.csv');pars=readj(ROOT/'evidence/OUTER_PARAMETERS.json');folds=readj(ROOT/'evidence/FOLDS_DETAIL.json');byfold={f['fold_id']:f for f in folds}
 lookup={(int(g),r['sample_id']):r for g,rs in cache.items() for r in rs}
 ck('CV_prediction_seal',sha(ROOT/'P7A_CV_PREDICTIONS.csv')==readj(ROOT/'evidence/CV_PREDICTIONS_SEALED.json')['sha256'])
 ck('no_duplicate_CV_identity',len(cv)==len({(r['fold_id'],r['sample_id'],r['model_id']) for r in cv}))
 pr={(r['fold_id'],r['record']['model_id']):r for r in pars};maxerr=0
 for r in cv:
  g=int(r['gauge_id']);d=lookup[(g,r['sample_id'])];pa=pr[(r['fold_id'],r['model_id'])]['record'];mi=d['month']-1
  ck('CV_identity_'+r['sample_id']+'_'+r['model_id'],byfold[r['fold_id']]['cutoff']<d['year']<=byfold[r['fold_id']]['cutoff']+2 and d['year']<=2017)
  if r['model_id']=='C0':pred=pa['climate'][mi]
  else:
   raw=np.array([d[f'MEM_{pa["rho"]}'] if k=='MEM' else d[k] for k in pa['fields']]);mu=np.array(pa['transform']['monthly_mean'])[mi];sd=np.array(pa['transform']['monthly_sample_std'])[mi];constant=np.array(pa['transform']['monthly_constant'])[mi]
   z=np.where(constant,0,(raw-mu)/np.where(constant,1,sd));pred=pa['parameters']['monthly_climatology'][mi]+z@np.array(pa['parameters']['beta_standardized'])
  err=abs(float(r['qsim_raw'])-pred);maxerr=max(maxerr,err);ck('CV_parameter_reconstruction_'+r['sample_id']+'_'+r['model_id'],err<=1e-10*max(1,abs(pred)))
  ck('parameter_hash_'+r['sample_id']+'_'+r['model_id'],r['parameter_hash']==digest(pa))
 for t in readj(ROOT/'evidence/INNER_CV_LOG.json'):
  tr=t['candidates'];best=min(tr,key=lambda r:(r['mean'],r['alpha'],r['rho'] or 0));cut=best['mean']+best['SE'];valid=[r for r in tr if r['mean']<=cut+1e-12*max(1,abs(cut))];sel=sorted(valid,key=lambda r:(-r['alpha'],r['rho'] or 0))[0]
  ck('oneSE_'+t['fold_id']+t['model_id'],sel==t['selection'])
 # All training-period aggregate/secondary figures are recomputed from serialized predictions.
 aggregate=[];secondary=[]
 for g in GAUGES:
  for model in MODELS:
   rr=[r for r in cv if int(r['gauge_id'])==g and r['model_id']==model];y=np.array([lookup[(g,r['sample_id'])]['Q'] for r in rr]);p=np.array([float(r['qsim_raw']) for r in rr])
   record=next(r for r in rows(ROOT/'P7A_STATION_MODEL_METRICS.csv') if int(r['gauge_id'])==g and r['model_id']==model)
   for k,v in metric(y,p).items():
    if k in ['MSE','NSE','KGE','MAE','RMSE','PBIAS']:ck('serialized_metric_'+str(g)+model+k,abs(v-float(record[k]))<1e-10*max(1,abs(v)))
   se=(p-y)**2;idx=np.argsort(se)[::-1];secondary.append({'gauge_id':g,'model_id':model,'kind':'NONNEGATIVE_SECONDARY',**metric(y,np.maximum(p,0)),'raw_top1_SSE_fraction':float(se[idx[:1]].sum()/se.sum()),'raw_top3_SSE_fraction':float(se[idx[:3]].sum()/se.sum()),'raw_worst_month':rr[idx[0]]['date']})
 csvout(ROOT/'P7A_NONNEGATIVE_AND_LOSS_DIAGNOSTICS.csv',secondary)
 # Verify prediction file and model hashes before independent Q scorer reads any exposed labels.
 seal=readj(ROOT/'evidence/HISTORICAL_PREDICTION_SEAL.json');ck('historical_seal_before_label_open',sha(ROOT/'P7A_HISTORICAL_PREDICTIONS_WITHOUT_QOBS.csv')==seal['sha256'])
 ck('prediction_role_no_Q_read',seal['external_Q_read'] is False and not any('MONTHLY_PAIRED_ERRORS' in p for p in seal['opened_public_files']))
 hp=rows(ROOT/'P7A_HISTORICAL_PREDICTIONS_WITHOUT_QOBS.csv');ck('historical_no_duplicate',len(hp)==len({(r['gauge_id'],r['date'],r['model_id']) for r in hp}))
 observed=rows(LAB/'vhs_p6d_failure_diagnostics/P6D_MONTHLY_PAIRED_ERRORS.csv');obs={(int(r['gauge_id']),r['date']):r for r in observed}
 ck('actual_exposed_Q_support',len(obs)==864)
 for reg in readj(ROOT/'P7A_MODEL_REGISTRY.json')['research_models']:ck('final_model_pin_'+str(reg['gauge_id'])+reg['model_id'],sha(reg['model_path'])==reg['sha256'])
 metrics=[];seasons=[]
 for g in GAUGES:
  for period,lo,hi in [('2018','2018-01','2018-12'),('2019','2019-01','2019-12'),('2020','2020-01','2020-12'),('2018_2019','2018-01','2019-12'),('2018_2020','2018-01','2020-12')]:
   for subset,months in [('ALL',list(range(1,13))),('DJF',[1,2,12]),('MAY_JUNE',[5,6])]:
    for model in ['C0+PT','P2-L1','P7-MEM']:
     rr=sorted([r for r in hp if int(r['gauge_id'])==g and r['model_id']==model and lo<=r['date']<=hi and int(r['month']) in months],key=lambda r:r['date'])
     y=np.array([float(obs[(g,r['date'])]['Qobs']) for r in rr]);p=np.array([float(r['qsim_raw']) for r in rr]);base={(r['date']):float(r['qsim_raw']) for r in hp if int(r['gauge_id'])==g and r['model_id']=='P2-L1'}
     b=np.array([base[r['date']] for r in rr]);oldb=np.array([float(obs[(g,r['date'])]['Qsim_L1']) for r in rr]);den=float(np.mean((b-y)**2));old_den=float(np.mean((oldb-y)**2))
     for kind,pp in [('RAW_PRIMARY',p),('NONNEGATIVE_SECONDARY',np.maximum(p,0))]:
      item={'gauge_id':g,'period':period,'subset':subset,'model_id':model,'analysis':kind,**metric(y,pp),'MSE_skill_vs_matched_P2L1':1-float(np.mean((pp-y)**2))/den,'MSE_skill_vs_original_frozen_P4_L1':1-float(np.mean((pp-y)**2))/old_den,'comparison_class':'POSTHOC_EXPOSED_PERIOD_NOT_BLIND','training_support':'common 24-month weather warmup; differs from original P4 initial dates','negative_raw_predictions':int(sum(p<0))}
      (metrics if subset=='ALL' else seasons).append(item)
 csvout(ROOT/'P7A_HISTORICAL_EXPOSED_COMPARISON.csv',metrics);csvout(ROOT/'P7A_HISTORICAL_EXPOSED_SEASONAL.csv',seasons)
 yearly=[]
 for model in ['P7-SL','P7-MEM']:
  for year in sorted({int(r['year']) for r in cv}):
   vals=[float(r['skill_vs_P2L1']) for r in rows(ROOT/'P7A_YEARLY_METRICS.csv') if r['model_id']==model and int(r['year'])==year]
   yearly.append({'year':year,'model_id':model,'station_equal_skill':float(np.mean(vals)),'station_n':len(vals)})
 csvout(ROOT/'P7A_YEAR_STATION_EQUAL.csv',yearly)
 summaries={}
 for model in ['P7-SL','P7-MEM']:
  r=[x['station_equal_skill'] for x in yearly if x['model_id']==model];a=np.array(r);rng=np.random.default_rng(20261102);boot=a[rng.integers(0,len(a),size=(999,len(a)))].mean(1)
  summaries[model]={'year_equal_station_skill':float(a.mean()),'leave_one_year_out_min':float(min((a.sum()-a)/(len(a)-1))),'year_block_bootstrap95':np.quantile(boot,[.025,.975]).tolist(),'caveat':'developmental only, dependent years/basins; not a confirmatory p value'}
 put(ROOT/'P7A_DEVELOPMENT_UNCERTAINTY.json',summaries)
 exsummary={}
 for subset in ['ALL','DJF','MAY_JUNE']:
  rr=[r for r in (metrics if subset=='ALL' else seasons) if r['model_id']=='P7-MEM' and r['period']=='2018_2020' and r['analysis']=='RAW_PRIMARY' and r['subset']==subset]
  vals=np.array([r['MSE_skill_vs_matched_P2L1'] for r in rr]);exsummary[subset]={'mean_skill':float(vals.mean()),'median_skill':float(np.median(vals)),'positive_stations':int(sum(vals>0)),'negative_NSE_stations':sum(r['NSE']<0 for r in rr),'negative_skill_stations':[r['gauge_id'] for r in rr if r['MSE_skill_vs_matched_P2L1']<0]}
 final=readj(ROOT/'evidence/FINAL_MODELS_SEALED.json')
 status.update(final_research_models=72,final_training_calls=final['fit_calls'],final_model_fits=final['final_fits'],total_real_fitting_calls=status['all_fits']+final['fit_calls'],historical_exposed_scoring='COMPLETED_POSTHOC_NOT_BLIND',historical_prediction_records=len(hp),historical_paired_station_months=864,historical_summary_vs_matched_L1=exsummary,future_holdout='FUTURE_HOLDOUT_NOT_AVAILABLE',code_sha256={p.name:sha(p) for p in (ROOT/'code').glob('*.py')})
 put(ROOT/'P7A_FINAL_STATUS.json',status)
 put(ROOT/'evidence/INDEPENDENT_NUMERICAL_VERIFICATION.json',{'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'max_CV_prediction_reconstruction_error':maxerr,'fit_calls':0,'checks':checks,'prediction_seal_verified_before_external_Q_load':True})
 (ROOT/'evidence/FUTURE_HOLDOUT_STATUS.md').write_text('''# 真正独立确认集状态\nFUTURE_HOLDOUT_NOT_AVAILABLE。\n2018–2020已评分并参与P6D诊断，不能再当P7盲测。原eHYD整档解析曾接触至2023/2024年初的数值；虽未分析那些年份评分，也不能声称其从未暴露。本轮未读取2021年以后的Q。2024年以后的站点身份、日QC、时间边界及同口径驱动尚未形成可用且由独立保管人锁定的标签集。\nP7B应先由独立保管人核实未暴露的新数据与许可；锁定站点/时期/QC和评分协议，仅向预测角色提供气象，封存预测后再开放Q。未取得此条件前不宣称最终独立检验。\n''',encoding='utf-8')
 report=f'''# P7A公开水文模型升级：真实执行结果\n\n本轮为PUBLIC_DATA_EXPLORATORY_P7A，任务为观测目标月气象驱动的历史月流量重建。不是未来业务预报、因果机制识别或业务认证。\n\n## 数据与冻结规则\n24站原公开LamaH观测，源Q全部止于2017；完全复现原P4训练标签哈希。先过滤日期再转换Q，训练角色拒绝P6与教师工作区。24个月连续气象初始化后共{sum(map(len,cache.values()))}个训练候选站月。五模型共同支持，120折中118折合格，2折按覆盖规则提前拒绝，原因见REJECTED_COVERAGE_FOLDS.json，未用得分删站。外层截止1996/2001/2006/2011/2015，各验证随后两年；内层三个向前块，所有月气候态/标准化只拟合内层训练。\n\n## 训练期结果与晋升\n每模型24站、118次外层拟合；总590外层、10620内层、14160条验证预测（2832唯一站月）。P7-SL站点等权技能−0.3428%，14/24站改善，冬季+2.3017%，未达到均值、改善比例及块稳定性门槛，停止晋升，未在2018–2020运行该候选。P7-MEM站点等权技能+3.5563%，中位+2.9434%，22/24站改善，冬季+0.7242%；5块中4块为正，但2016–2017块−2.3559%，风险保留。满足的是本轮预设研究候选门槛，不能解释为客观普适阈值。\n\n模型比较完整保留C0、C0+PT、L1、SL、MEM负结果、冬季与5–6月、逐年误差和损失集中度。SL相对L1新增1个系数；MEM相对当月P/T新增1个记忆系数及离散rho选择，相对L1连续系数数相同。去项消融复用同折同样本基线，无重复训练。\n\n## 最终实验模型与已暴露时期对照\n仅MEM晋升；在共同合法<=2017训练样本重拟合MEM、C0+PT及L1共72个研究模型，另{final['inner_fits']}次内层拟合。总真实拟合调用{status['total_real_fitting_calls']}；无旧模型被覆盖。新模型使用统一暖启动支持，与原P4起始月份略不同，所以公平主对照是本轮同支持L1，原P4-L1比较作为另一列保留。独立预测进程不导入fit、拒绝同期Q文件，先封存2592条预测，再由本评分进程关联P6D原864个站月。\n\nMEM相对同支持新L1，2018–2020合并站点等权技能{exsummary['ALL']['mean_skill']:+.2%}、中位{exsummary['ALL']['median_skill']:+.2%}，{exsummary['ALL']['positive_stations']}/24站改善；负技能站{exsummary['ALL']['negative_skill_stations']}。冬季等权技能{exsummary['DJF']['mean_skill']:+.2%}，5–6月{exsummary['MAY_JUNE']['mean_skill']:+.2%}。MEM合并绝对负NSE仍有{exsummary['ALL']['negative_NSE_stations']}站，不能把相对改善等同于绝对可靠。各年、每站、raw/nonnegative完整指标在HISTORICAL_EXPOSED_COMPARISON.csv；未重校准经验区间，不提供P7的新覆盖承诺。\n\n这些是已暴露时期的后验描述性对照，P6D已用于模型设计，绝非新的独立盲测。没有基于此结果改变公式、alpha网格、rho、冷季月份或晋升门槛。旧P4-V2和默认P2-L1保持不变。\n\n## 检查、失败与限制\n独立数值复核{len(checks)}项通过，重构最大误差{maxerr:.3g} m³/s，失败0。第一次数值训练完成后因新输出哈希读取白名单遗漏中断；恢复仅汇总原预测。最终模型首个ID2 C0+PT完成后遇同类自输出读取问题；已复用该保存模型及选择轨迹，未重复拟合。保留失败说明与attempt记录；首次恢复模型的原运行耗时不可恢复，未伪造。软件通过不等于水文认证。\n\n跨流域不混合原始m³/s平方误差；站点等权，三大水系分别描述，24站不视为完全独立。历史质量、日界/UTC和驱动处理限制延续。发展性年度bootstrap/jackknife不构成确认性统计推断。没有进入训练的2018–2020 Q，也没有读教师Q。\n\n## 下一步\n建议进入有限范围P7B独立验证准备，仅保留MEM为待检候选并强制L1/C0+PT基线；不再晋升SL，不在已暴露时期继续调参。真正未接触标签集当前FUTURE_HOLDOUT_NOT_AVAILABLE。先独立保管新Q与同质驱动，再锁定预测和评分，不立即开展所谓最终盲测或生产替换。\n'''
 (ROOT/'P7A_RESEARCH_REPORT_ZH.md').write_text(report,encoding='utf-8')
 (ROOT/'P7A_REPRODUCTION_GUIDE.md').write_text('''# 复现\n使用现有Python环境，所有命令加-B，输出必须另指定干净副本而不是覆盖本次证据。\n1. code/prepare.py：只读历史保护及原公开<=2017Q缓存，冻结协议；已存在协议时拒绝覆盖。\n2. code/engine.py：训练期时序嵌套CV。首次运行生成数值预测后封存读取失败；实际用--resume-summary-only恢复汇总，未重训。\n3. code/final_train.py：检查晋升，只训练MEM及同支持基线，已保存完整模型优先复用，日志说明恢复。\n4. code/historical_predict.py：独立无Q角色，加载最终参数，不fit，封存历史预测。\n5. code/score_verify_report.py：先核对预测封存，再读取P6D公开Q独立评分/重构，无fit。\n6. code/finalize_delivery.py：历史哈希和交付封存。\n\n命令前缀：E:\\CodexProject\\CodexProject\\DeepBas-VHS-GT-Lite-v0.1\\.venv\\Scripts\\python.exe -B\n所有源路径、模型哈希、协议/数据快照、气象单位、初始化、共同支持集及准确切分见协议、cache和evidence。未来Q不属于训练缓存；训练审计禁止读取P6。网站只有封存证据展示，不能触发这些训练命令。\n''',encoding='utf-8')
 put(WEB/'research/P7A_SUMMARY.json',status)
 print(json.dumps({'independent_checks':len(checks),'historical_summary':exsummary,'final_fit_calls':final['fit_calls']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
