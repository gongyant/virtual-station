from common import *
import geopandas as gpd,pandas as pd,numpy as np,shutil,subprocess,ast
def md(name,s):
 p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')
def table(df,cols):
 return '| '+' | '.join(cols)+' |\n| '+' | '.join(['---']*len(cols))+' |\n'+'\n'.join('| '+' | '.join(f'{r[c]:,.3f}' if isinstance(r[c],(float,np.floating)) else str(r[c]) for c in cols)+' |' for _,r in df.iterrows())
def main():
 assert not (ROOT/'SHA256SUMS.txt').exists();event('final_reports','STARTED');p=read(ROOT/'P8_FROZEN_PROTOCOL.json');qa=read(ROOT/'P8_SPATIAL_QA.json');assert qa['failed']==0 and p.get('protocol_version')=='P8_GEOGRAPHIC_CORRECTION_V2';assert sha(ROOT/'P8_FROZEN_PROTOCOL.json')==read(ROOT/'evidence/PROTOCOL_FREEZE.json')['sha256']
 a=read(ROOT/'evidence/BASIN_AREA_QA.json');g=read(ROOT/'evidence/GAUGE_AND_CANDIDATE_STATUS.json');eight=pd.read_csv(ROOT/'P8_EIGHT_BASIN_SUMMARY.csv');six=pd.read_csv(ROOT/'P8_SIX_BASIN_SUMMARY.csv');den=pd.read_csv(ROOT/'P8_REAL_GAUGE_DENSITY.csv');national=eight[eight.scope=='NATIONAL'].iloc[0];sixsum=six[six.scope=='SIX_SUBSET_TOTAL'].iloc[0]
 # Reconcile namespaces by observed names, never by coincident numeric IDs.
 pairs=sorted({(r['properties']['bassein_id'],r['properties']['bassein']) for r in read(ROOT/'source/qazsu_hydroposts_response.json')['features']});qm={}
 for i,name in pairs:
  s=name.lower();n='Ertis' if 'иртыш' in s else 'Yesil' if 'есил' in s else 'Tobyl-Torgai' if 'тобол' in s else 'Balkhash-Alakol' if 'балхаш' in s else 'Nura-Sarysu' if 'нура' in s else 'Shu-Talas' if 'шу-талас' in s else 'Zhaiyk-Caspian' if 'урало-касп' in s else 'Aral-Syr Darya' if 'арало-сыр' in s else None;assert n;qm[n]={'QazSu_system_basin_id':i,'QazSu_basin_name':name}
 rows=list(csv.DictReader((ROOT/'BASIN_SCOPE_CROSSWALK.csv').open(encoding='utf-8-sig')))
 for r in rows:
  if 'official_eight_basin_id' in r:r['research_source_basin_id']=r.pop('official_eight_basin_id')
  r.update(qm[r['name']]);r['national_standard_official_basin_code']=None;r['ID_status']='Zenodo paper IDs and QazSu official system IDs are different namespaces; universal national standard code not verified'
 csvout(ROOT/'BASIN_SCOPE_CROSSWALK.csv',rows);put(ROOT/'P8_SIX_SCOPE_CONFIG.json',{'scope_id':'PLATFORM_SIX_REPORTED_2025_10_03','basin_names':p['six_scope'],'source':p['six_scope_source'],'supervisor_definition_confirmed':False})
 # The alternative eight-basin union geometry did not change in the country correction.
 cached=ROOT/'runs/P8_INITIAL_ADMIN_BOUNDARY_V1/BOUNDARY_LENGTH_SENSITIVITY_FULL.json'
 if cached.exists():
  alt=read(cached);alt['primary_country_clip_length_km']=a['national_length_km'];alt['difference_km']=alt['source_eight_basin_union_length_km']-a['national_length_km'];alt.update(reused_source_union_geometry=True,original_alternative_cache_sha256=sha(cached),primary_boundary_protocol=p['protocol_version']);put(ROOT/'evidence/BOUNDARY_LENGTH_SENSITIVITY_FULL.json',alt)
 # Run the configuration interface and compare against frozen default, not a new geographic selection.
 dest=ROOT/'evidence/SIX_SCOPE_REPRODUCED.csv';cmd=[sys.executable,'-B',str(ROOT/'code/derive_six_scope.py'),'--config',str(ROOT/'P8_SIX_SCOPE_CONFIG.json'),'--output',str(dest)];r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0,r.stderr
 v=pd.read_csv(dest);check=abs(float(v[(v.order_system=='ORD_CLAS')&(v.order_group=='ALL')].river_length_km.iloc[0])-float(sixsum.all_orders_km))<1e-7;assert check;put(ROOT/'evidence/SIX_SCOPE_INTERFACE_CHECK.json',{'command':cmd,'passed':1,'failed':0,'stdout':r.stdout})
 gates={'RIVER_NETWORK_NATIONWIDE_COMPLETE':{'status':'PASS_AT_HYDRORIVERS_V1_SPECIFICATION','passed':True,'reason':'official global8477883 unique source, country uses both KAZ and KAB sovereign units; thresholded product, not all natural ditches/canals'},'BASIN_BOUNDARIES_ADMITTED':{'status':'CONDITIONAL_RESEARCH_BOUNDARIES_WITH_RESIDUAL','passed':False,'reason':f'8valid CC-BY polygons admitted for research intersection; country coverage {a["country_covered_fraction"]:.6%}; {a["unassigned_length_km"]:.3f}km river remains unassigned; not legal surveying'},'ORDER_LENGTHS_REPRODUCIBLE':{'status':'PASS_FOR_DECLARED_GEOGRAPHIC_SCOPE','passed':True,'reason':f'{qa["passed"]} independent checks, {qa["independent_sample_n"]} Vincenty samples; residual included'},'REAL_GAUGES_MATCHED':{'status':'PARTIAL_GEOMETRIC_QAZSU_CATALOG_ONLY','passed':False,'reason':f'334coordinates,279 river/stream labels,{g["geometric_500m_provisional_matches"]}provisional matches; no394identity reconciliation or river-name/relocation certification'},'KAZ_Q_AVAILABLE':{'status':'CURRENT_PUBLIC_SNAPSHOT_ONLY_NOT_PUB_SERIES','passed':False,'reason':'315 current q_mean values, units/QC/license not verified, no continuous historical Q archive acquired'},'READY_FOR_P9':{'status':'CONDITIONAL_GEOMETRY_WORK_ONLY_NOT_FULL_GAUGE_DENSITY','passed':False,'reason':'confirm supervisors six-scope; resolve border residual and official394catalog/type/river identity/rights before formal virtual-gauge admission'},'READY_FOR_P10':{'status':'BLOCKED_FOR_KAZ_PUB_TRAINING','passed':False,'reason':'need licensed continuous Q with units/QC/date definition, catchment-driven homogeneous P/T/static attributes, target isolation and unexposed evaluation protocol'}}
 put(ROOT/'P8_FINAL_STATUS.json',{'completed_utc':now(),'protocol_version':p['protocol_version'],'fit_calls':0,'Q_scoring_calls':0,'teacher_Q_reads':0,'old_websites_changed':False,'gates':gates,'QA_passed':qa['passed'],'QA_failed':qa['failed'],'history_files_checked':qa['history_checked'],'source_reaches':8477883,'national_reaches':read(ROOT/'evidence/GLOBAL_RIVER_SOURCE_CHECK.json')['national_source_reaches'],'national_length_km':a['national_length_km'],'unassigned_length_km':a['unassigned_length_km'],'six_subset_length_km':float(sixsum.all_orders_km),'gauge_catalog':g,'Kazakhstan_NSE':None,'Kazakhstan_KGE':None,'candidate_admitted':0})
 csvout(ROOT/'P8_NATIONAL_AREA_DENSITY.csv',[{'scope':s,'official_count':n,'official_area_km2':2724900,'density_per_km2':n/2724900,'density_per10000km2':10000*n/2724900,'geometry_area_not_used':True,'virtual_admitted':0} for s,n in [('ALL_TYPES',442),('RIVER_POSTS',394)]] )
 md('P8_BASIN_DEFINITIONS_AND_SIX_SCOPE.md',f'''# 八流域与六子集定义

完整8组为Aral-Syr Darya、Balkhash-Alakol、Ertis、Yesil、Zhaiyk-Caspian、Nura-Sarysu、Tobyl-Torgai、Shu-Talas。边界是Yapiyev等发布的研究数据v2，DOI10.5281/zenodo.17077776，CC BY4.0，8个EPSG4326有效多边形，不冒充政府法定测绘。

本轮六子集：{'、'.join(p['six_scope'])}。来源为2025-10-03 Kazinform报道当时数字平台已覆盖的六流域，不能推定为导师正式六水系定义；Aral-Syr Darya与Nura-Sarysu独立保留。历史新闻不表示2026年现状仍只覆盖六区。

研究数据源id与QazSu系统basin_id不是同一命名空间，例如Ertis为研究id3、QazSu id7。`BASIN_SCOPE_CROSSWALK.csv`按名称核验两套编号，并将尚未核实的全国统一官方代码留空。

`ORD_CLAS`沿用全球原值：1为每个连接河网的源至汇主干，2汇入1，3汇入2；包括许多内流小网络的主干，不是国家行政河流等级，也不是按河宽排序。`ORD_STRA`1为源头小溪、同级汇合才升一级；`ORD_FLOW`原值保留但不参加导师三级分类。境外上游等级不因裁剪而重新计算。

河链总长定义为各唯一HYRIV_ID裁剪几何的各片段测地长度之和，不把每条支流到出口的公共路径重复累加。等级4+和未分类独立列出。

六水系后续可配置：编辑新的JSON并调用`code/derive_six_scope.py --config <新JSON> --output <P8内新CSV>`，必须6个不同且已存在的名称，拒绝覆盖；不修改任何八流域片段与原统计。当前配置实测与六子集主表一致。
''')
 subset=den[(den.scope=='EIGHT_BASIN')&(den.ORD_CLAS_group=='ALL')][['basin_name','matched_QazSu_geometric_subset_count','river_length_km','matched_subset_density_per_1000km']]
 primary=den[(den.scope=='NATIONAL')&(den.ORD_CLAS_group=='ALL')].iloc[0];old=pd.read_csv(ROOT/'runs/P8_INITIAL_ADMIN_BOUNDARY_V1/P8_EIGHT_BASIN_SUMMARY.csv');oldnat=float(old[old.scope=='NATIONAL'].all_orders_km.iloc[0])
 md('P8_SUPERVISOR_REPORT_ZH.md',f'''# P8：全国河网等级、六/八流域河链长度与站点密度

## 可直接向导师报告的结论

本轮已实际取得全球HydroRIVERS v1.0与Zenodo八管理流域研究边界v2，并获取QazSu公开334站坐标。全国主权范围国界内实际{read(ROOT/'evidence/GLOBAL_RIVER_SOURCE_CHECK.json')['national_source_reaches']:,}个来源河段，总河链长度**{a['national_length_km']:,.3f}km**；经典一级**{national.class1_km:,.3f}**、二级**{national.class2_km:,.3f}**、三级**{national.class3_km:,.3f}km**。这不是行政分级或所有天然沟道统计。

八流域已归属总长**{a['assigned_eight_length_km']:,.3f}km**；另**{a['unassigned_length_km']:,.3f}km**因研究分区与国界差异单列。六流域子集总长**{sixsum.all_orders_km:,.3f}km**，其中一级**{sixsum.class1_km:,.3f}**、二级**{sixsum.class2_km:,.3f}**、三级**{sixsum.class3_km:,.3f}km**。六子集是2025平台报道口径，导师定义仍待确认。

## 八流域完整长度表（km）

{table(eight,['scope','basin_name','class1_km','class2_km','class3_km','class4plus_km','all_orders_km'])}

## 匹配站点与可计算密度

QazSu334记录全部带有效坐标和唯一站码，无重复坐标。按名称分类：河流/溪流279、湖泊/水库40、海洋12、渠道/渠道提及3。保守500m吸附、国界、类型、编号与10m等级/流域歧义规则最终保留**{g['geometric_500m_provisional_matches']}个临时几何匹配**，不是已经完成394官方河流站核对。源属性x/y与GeoJSON坐标顺序不一，优先使用声明EPSG4326的GeoJSON longitude-latitude，原属性完整保留，不盲用x作经度。

{table(subset,['basin_name','matched_QazSu_geometric_subset_count','river_length_km','matched_subset_density_per_1000km'])}

全国已取得目录子集为**{primary.matched_subset_density_per_1000km:.6f}站/千km**；经典1/2/3分级子集人数和密度在P8_REAL_GAUGE_DENSITY.csv。每级表均有分母、人数及状态。没有匹配完整官方394站，故完整分流域分级实站密度均为N/A；394口径未知未匹配人数留空，不能简单394减334，因为334还含非河流站，是否属于同一现行目录未证实。作为未分级粗比例，394÷全国总长×1000={394000/a['national_length_km']:.6f}站/千km，另标“未分配官方计数比”，不能当作已匹配密度。

准入虚拟站V仍为0，故已匹配子集加虚拟站密度与之前相同；不把1230几何点加入分子。全国面积密度另表：442/2724900={442/2724900:.12f}个/km²，394/2724900={394/2724900:.12f}个/km²，不能和站/河长km混用。

## 边界、覆盖和序级限制

官方下载global源8,477,883个唯一HYRIV_ID；主统计覆盖欧亚/西伯利亚/亚洲三种来源前缀，已经解决KAZ-N1仅AS瓦片缺口。官方提取门槛为上游面积≥10km²或长期自然流量模型估计≥0.1m³/s，15角秒，不包含所有小沟/人工渠；源DIS_AV_CMS只是WaterGAP长期估计，不当Q观测或VHS预测。ENDORHEIC内流标志单独统计；没有季节性认证字段，不能据模型Q零值判断干涸或删除。

初版直接使用Natural Earth ADMIN=Kazakhstan，图面复核发现拜科努尔被单列。已保存初版所有统计和图到runs/P8_INITIAL_ADMIN_BOUNDARY_V1，先冻结地理修正版V2，再按相同源SOVEREIGNT=Kazakhstan合并KAZ+KAB计算。本轮最终全国长度比初版{oldnat:,.3f}km增加{a['national_length_km']-oldnat:,.3f}km，原N1未改。这是国家范围解释修正，不依据模型分数或密度调规则。

八研究多边形几何全部有效，源面积合计{a['source_area_attribute_sum_km2']:,.3f}km²；相同LAEA计算并集{a['basin_union_area_km2']:,.3f}km²，与官方面积2,724,900及概化国界不同；国界内覆盖率{a['country_covered_fraction']:.6%}，缺口{a['country_uncovered_area_km2']:,.3f}km²，区划超出国界部分{a['basin_outside_country_area_km2']:,.3f}km²。没有把缺口强行填给最近流域。共享边界/重叠河线按较小研究id分配一次，并记录冲突；河段跨流域切分{a['source_reaches_crossing_multiple_basins']}个，全部134k级片段有唯一来源ID。

## 1230点重新核查

原清单只读导入，{g['candidate_basin_assigned_once']}点有唯一八流域归属，{g['candidate_available_gauge_conflicts5km']}点距已取得河流站坐标不足5km。逐点保留完整河网一致性、国界、序级、重复、未匹配原因；其余官方394站空间冲突仍未知。精确点位上游集水区及同质气象输入均未完成，因此1230点仍仅GEOMETRY_SCREENED，正式准入0。未放宽N1规则。

## Q准入与下一阶段

官方现页442点/394河流站已重新保存；QazSu334混合目录中315条含当前q_mean，通用q字段全部null，另有稀疏prev值；有零值但不自动删或证明有效。未核实单位、连续历史年月、流量QC编码及再发布/训练许可，不能当成315条训练序列。历史数据库标准及官方英文链接均45秒读取超时；HR页面可取但未证明有历史Q导出。没有绕过权限、猜测受限API或读取教师Q。哈萨克斯坦PUB的NSE/KGE仍未知，没有把欧洲精度写过来。

P9最小缺口：确认导师六水系定义；用有权边界资料解决未归属片段；补齐394河流站现行身份、类型、迁站及河名/河段核对与坐标使用许可。P10另需连续合法Q及单位/QC/日界、同口径全上游P/T和静态特征，冻结真正未暴露的空间/时间验证。不能只凭GIS通过开始全国PUB建模。

## 实际核验与失败记录

空间数值检查**{qa['passed']}通过/{qa['failed']}失败**。独立Vincenty算法复核{qa['independent_sample_n']}片段，最大差{qa['max_independent_length_error_km']:.12g}km；分段与全国总长差{a['partition_length_difference_km']:.12g}km。{qa['history_checked']}个历史文件SHA256一致。fit_calls=0、Q评分调用0，旧模型和网站不改。

第一次GPKG写入源LENGTH_KM与重算length_km大小写冲突而失败，已保留失败文件，源字段明确改名SOURCE_REACH_LENGTH_KM后重跑。一次延迟的进度控制请求发生在原计算已经完成之后，重复匹配调用被防覆盖门禁拒绝；RUN_ATTEMPTS末尾已追加更正，未删除错误记录。全部负面准入状态保留。图面数值来源真实，图形QA不代表水文业务认证；详见图形QA日志。
''')
 md('P8_FULL_REPRODUCTION.md',rf'''# P8复核、命令与文件映射

解释器：`{sys.executable}`；交付根：`{ROOT}`。不安装新依赖，不读教师Q，不改任何网站。环境、磁盘和初始历史检查见evidence/DISCOVERY.json。

本轮实际入口：acquire.py→freeze.py→river_statistics.py→gauges_candidates.py→verify.py→figures.py；独立source_discovery.py与source_audit.py读取正常公开页面/公开WFS及官方Q入口；sourceID/boundary检查在scope_and_boundary.py；图面发现国家要素遗漏后，boundary_v2.py保留初版、修正同源主权边界并冻结V2，再按原GIS和匹配规则重算。所有入口调用格式为`& '{sys.executable}' -B '{(ROOT/'code').as_posix()}/<入口>.py'`，RUN_ATTEMPTS.jsonl记录真实阶段和失败、更正，不捏造下载或评分。

主源：Zenodo17077776/ver.2.zip，官方MD5及ZIP CRC验证；HydroRIVERS官方全球ZIP全部成员CRC/路径配额检查。source/ACCESS_LOG和FETCH_*含实际HTTP、时间、字节及SHA256。主权国界来源为旧N1合法NaturalEarth全球快照的KAZ+KAB；原N1不改。P8国家边界与协议SHA在evidence/COUNTRY_BOUNDARY_AMENDMENT.json和PROTOCOL_FREEZE.json。

GPkg层：national_reaches（唯一来源ID的国内几何及原属性）、basin_fragments（切分片段ID、来源HYRIV_ID、序级、流域、测地长度）、basins_source、country_boundary。SOURCE_REACH_LENGTH_KM保留原整段长度，length_km为裁剪后重算值，后者是唯一统计分母。不要用原长度按国家比例猜测裁剪长度。生产脚本不能覆盖已有主GPkg/跨表；正式封存后勿直接重跑会写QA的verify.py，应先复制输出到新工作根。

封存后只读检验：

```powershell
& '{sys.executable}' -B '{(ROOT/'code/verify_delivery.py').as_posix()}'
```

该入口只比较当前SHA256和2741历史清单，无网络/拟合/评分。字节清单包含原始下载、解包数据、GeoPackage、所有代码、图和报告，操作日志runtime除外。完整GPKG不含任何新Q观测列。

配置其他六水系：新JSON需有basin_names（6个不同且存在的英文名称）。

```powershell
& '{sys.executable}' -B '{(ROOT/'code/derive_six_scope.py').as_posix()}' --config '<新配置JSON>' --output '{(ROOT/'P8_CUSTOM_SIX.csv').as_posix()}'
```

输出必须在P8且不存在；八流域数据不变。默认配置已真实调用并和原六子集表相等。

核验独立性：verify.py不导入生产长度函数，单独持久化几何重算并独立逐段Vincenty反算{qa["independent_sample_n"]}个样本；包含全球唯一ID、三大来源区、分级和全网长度守恒、密度算式、虚拟准入0、未对齐官方密度N/A及历史hash。图的显示简化150m不用于长度计算；原始几何在GPKG。

文件：P8_RIVER_LENGTH_BY_BASIN_ORDER.csv和P8_CLASSICAL_VS_STRAHLER.csv均为明确标order_system的长表，后者保留全等级平行对照；P8_EIGHT_BASIN_SUMMARY/SIX_BASIN_SUMMARY为宽表；P8_OFFICIAL_GAUGE_CROSSWALK含334原始身份和匹配状态；P8_REAL_GAUGE_DENSITY将临时子集与完整官方N/A字段分开；KAZ_P8_Q_SOURCE_AUDIT.csv是P8_Q_SOURCE_AUDIT.csv的相同内容别名；图在figures，有脚本和source契约；P8_FINAL_STATUS逐项门槛不全设PASS。
''')
 event('final_reports','FINISHED',national_length_km=a['national_length_km'],geometric_subset_gauges=g['geometric_500m_provisional_matches']);print('REPORTS READY',flush=True)
if __name__=='__main__':main()
