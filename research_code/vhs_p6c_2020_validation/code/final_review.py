"""Post-score reporting refinement only. Never modifies sealed prediction/scoring runs."""
from p6c_common import *
import shutil
sys.stdout.reconfigure(encoding='utf-8');archive=R/'evidence/INITIAL_DELIVERY_REPORTS';assert not archive.exists();archive.mkdir()
for name in ['SHA256SUMS.txt','P6C_EXTERNAL_VALIDATION_REPORT_ZH.md','P6C_COMPLETION_REPORT_ZH.md','P6C_DRIVER_PARITY_REPORT.md','P6C_FINAL_STATUS.json']:shutil.copy2(R/name,archive/name)
groups=jl(L/'p2_antecedent_snow_features/P2_NEW_BASINS_FROZEN.json')['all_grouping'];cc=readcsv(R/'P6C_MODEL_COMPARISON.csv');macro=[]
for quality in ['DESCRIPTIVE_ARCHIVE','STRICT_SENSITIVITY']:
 for subset in ['ALL','DJF','MAY_JUNE']:
  for region in ['Rhine','Elbe','Danube']:
   rr=[c for c in cc if c['quality_tier']==quality and c['prediction']=='raw' and c['subset']==subset and groups[c['gauge_id']]['macro']==region and c['MSE_skill'] and (subset!='ALL' or c['station_summary_min12_supported']=='True')]
   skills=[float(c['MSE_skill']) for c in rr];macro.append({'macro_region':region,'quality_tier':quality,'subset':subset,'stations':len(rr),'positive_stations':sum(x>0 for x in skills),'station_mean_MSE_skill':float(np.mean(skills)) if skills else None,'station_median_MSE_skill':float(np.median(skills)) if skills else None,'station_ids':'|'.join(str(c['gauge_id']) for c in rr),'spatial_independence_assumed':False,'reason':None if rr else 'NO_ELIGIBLE_STATIONS'})
cw(R/'P6C_MACRO_REGION_SUMMARY.csv',macro)
pred=readcsv(R/'P6C_2020_PREDICTIONS.csv');boundary=readcsv(R/'P6C_DAY_SHIFT_SUMMARY.csv');negative=sum(float(r['q_hat_raw'])<0 for r in pred);sup={s:sum(r['support_class']==s for r in pred) for s in ['IN_SUPPORT','EXTRAPOLATION_CAUTION','HIGH_EXTRAPOLATION']};maxdelta=max(abs(float(r['NSE_difference_from_provider_calendar'])) for r in boundary if r['NSE_difference_from_provider_calendar'])
def pct(x):return 'N/A' if x is None else f'{100*x:.2f}%'
text='\n## 最终交付复核补充\n\n'
text+='原region字段是官方细分河区；宏观水系另按既有P2冻结分组汇总，不能把多个Danube细分区当作独立大水系。\n\n'
for m in macro:
 if m['quality_tier']=='DESCRIPTIVE_ARCHIVE' and m['subset']=='ALL':text+=f"- {m['macro_region']}：{m['positive_stations']}/{m['stations']}站正技能，等权均值{pct(m['station_mean_MSE_skill'])}。\n"
text+=f'''\n2020年原始负预测为{negative}条，因此本轮nonnegative次分析与raw数值一致。输入支持为IN_SUPPORT {sup['IN_SUPPORT']}条、EXTRAPOLATION_CAUTION {sup['EXTRAPOLATION_CAUTION']}条、HIGH_EXTRAPOLATION {sup['HIGH_EXTRAPOLATION']}条；保留全部预测及其状态，不因误差或外推风险删除。

冬季失败需要区分两个判据：L1相对C0+PT的总体DJF技能仍为负；ID533、545在2020冬季相对基线技能分别转为正，但L1冬季NSE仍分别为−9.0432和−7.4079，绝对重建仍失败。全年相对增益也不等于绝对可用，L1仍有8站全年负NSE，尤其ID255/343应进入P6D失败诊断。

预先固定±1日边界诊断中，最大年度NSE绝对变化为{maxdelta:.6f}。这提示日期归属限制不能忽略；未将任何偏移替换主结果。该诊断远大于实际未知时区偏移的可能小时数，不是UTC校正证据。

已保留官方MD5格式异常的首次失败：T09 API给出31位十六进制摘要（省略前导0），而官方HEAD ETag、实际32位MD5和ZIP CRC检查完全一致。使用128位数值等价的左补0正规化后通过；不是哈希容差放宽。Windows IWR慢下载的中断记录也保留。最终6908项复核0失败不意味着下载过程中从未出现失败。

2015–2019气象重叠一致性通过，不足以单独证明2020再分析输入的所有生产同质性或物理真实性；没有利用2020 Q选择气象处理或做偏差订正。来源、算法和此项限制均保留。
'''
with (R/'P6C_EXTERNAL_VALIDATION_REPORT_ZH.md').open('a',encoding='utf-8') as f:f.write(text)
with (R/'P6C_DRIVER_PARITY_REPORT.md').open('a',encoding='utf-8') as f:f.write('\n校验格式修复：T09官方API摘要省略前导0，实际MD5 09c0739731ff01e82042824f50c3f18c 与官方HEAD ETag相同；原失败、HEAD、ZIP和正规化记录均保留，未放宽哈希数值比较。2015–2019通过不等同2020所有生产机制同质性已认证。\n')
with (R/'P6C_COMPLETION_REPORT_ZH.md').open('a',encoding='utf-8') as f:f.write('\n最终复核补充：宏观水系结果见P6C_MACRO_REGION_SUMMARY.csv；原始负预测0，故raw/nonnegative一致。冬季绝对失败仍存在，不把相对技能改善当成绝对可靠。日界固定敏感性已计算但UTC仍未认证。首次交付报告/清单已归档，冻结预测和评分目录未改动。\n')
(R/'SOURCE_LICENSE_AND_DOWNLOADS.md').write_text('''# P6C来源与许可

LamaH-CE v1.0：Klingler, Schulz, Herrnegger (2021), DOI10.5281/zenodo.5153305 / 10.5194/essd-13-4529-2021，CC BY-SA4.0；合法独立快照、官方全上游流域、网格及原R处理代码从P6B只读复用，保留作者署名和直接移植代码适用的共享条件。

Copernicus Climate Change Service / ECMWF：ERA5-Land hourly time-series，DOI10.24381/ee82e357，CC-BY。官方目录https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries?tab=overview 。16个紧凑矩形的实际请求、job ID、下载URL、版本响应、MD5/SHA256和原始NetCDF成员均在driver中。来源生成/下载为2026-11-02，历史时段2015–2020加真实2021边界；不隐瞒这是现行版本回取。仅获取P/T，不下载欧洲全变量包。CDS本机凭据仅内存使用，不在项目/日志/交付包保存。

Hydrographie Österreichs / BMLUK / Hydrographische Landesdienste：24站日均Abfluss归档及站点说明复用P6B合法eHYD来源，未重复下载Q。官方入口https://ehyd.gv.at/ ，https://wasser.gv.at/hydjb/index.xhtml 。原来源/下载/非商业署名使用限制见P6B/SOURCE_LICENSE_AND_DOWNLOADS.md及归档eHYD版权说明；没有将eHYD误标为CC-BY或允许无限商业再分发。原始Q保留在已有本地源，不批量复制到P6C输出。

所有对应原文件路径与哈希见P6C_ADMISSION_FROZEN.json、P6C_STATION_ADMISSION.csv。P4模型的正式来源、代码和参数哈希保留；无教师锡尔河数据，无跨数据集混用。
''',encoding='utf-8')
status=jl(R/'P6C_FINAL_STATUS.json');status.update(macro_regions=macro,negative_raw_predictions=negative,input_support_counts=sup,fixed_day_shift_max_abs_annual_NSE_change=maxdelta,previous_delivery_manifest_hash=sha(archive/'SHA256SUMS.txt'));jw(R/'P6C_FINAL_STATUS.json',status)
verify(R/'runs/P6C_2020_PREDICTION');verify(R/'runs/P6C_2020_SCORING');event('FINAL_DELIVERY_REVIEW_COMPLETE',prediction_and_score_runs_unchanged=True,negative_raw_predictions=negative)
seal(R);print('FINAL_ROOT_SHA256',sha(R/'SHA256SUMS.txt'));print(json.dumps([m for m in macro if m['quality_tier']=='DESCRIPTIVE_ARCHIVE' and m['subset']=='ALL'],indent=2))
