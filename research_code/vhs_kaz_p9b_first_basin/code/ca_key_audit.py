from common import *
import pyogrio
g=pyogrio.read_dataframe(ROOT/'source/CA-discharge.gpkg',layer='gauges',IMMUTABLE='YES');t=pd.read_csv(ROOT/'data/CA_ALL_SERIES_METADATA.csv',dtype={'CODE':str});t['base_CODE']=t.CODE.str.replace(r'[dm]$','',regex=True)
inv=pd.read_csv(ROOT/'P9B_AVAILABLE_Q_INVENTORY.csv',dtype={'source_CODE':str});indices=inv.index[inv.source=='CA-discharge v1.0'];assert len(indices)==len(g)
for ix,r in zip(indices,g.itertuples()):
    assert inv.loc[ix,'source_CODE']==str(r.CODE)
    z=t[(t.base_CODE==str(r.CODE))&(t.res==r.res)] if pd.notna(r.res) else t.iloc[:0]
    inv.loc[ix,'has_actual_timeseries']=not z.empty;inv.loc[ix,'available_resolutions']='|'.join(z.res.astype(str));inv.loc[ix,'source_start']='|'.join(z.start.astype(str));inv.loc[ix,'source_end']='|'.join(z.end.astype(str));inv.loc[ix,'record_count']=int(z.rows.sum());inv.loc[ix,'timeseries_CODE']='|'.join(z.CODE.astype(str));inv.loc[ix,'CA_join_contract']='metadataCODE+resolution -> unique seriesCODE; suffixaliases retained'
csv(ROOT/'P9B_AVAILABLE_Q_INVENTORY.csv',inv)
q=read(ROOT/'evidence/CA_DATA_AUDIT.json');q['series_unique_base_locations']=int(t.base_CODE.nunique());q['metadata_has_ts_rows']=int(g.has_ts.fillna(0).sum());q['publication_claimed135_locations_vs_file134']='COUNT_DEFINITION_OR_SOURCE_DOCUMENT_DISCREPANCY_NOT_RESOLVED';q['CODE_resolution_aliases']={'16070d':'16070/day','16070m':'16070/decade','17050d':'17050/decade','17050m':'17050/month'};js(ROOT/'evidence/CA_DATA_AUDIT.json',q)
md('source/CA_SOURCE_QUALITY_AND_KEY_NOTES.md','''# CA-discharge源契约实查

下载24,576,000字节GPKG的官方MD5匹配e0ba6664aaec3e0b27138abdfd4ba263，Zenodo v1.0明示CC-BY4.0。实际297gauges/295唯一站点、136个time-series CODE/134个规范化地点，244632行。网页称135个时序地点与本文件实际计数仍有差异，原因未确认，不把说明数当实际抽取数。

gauges.CODE对16070、17050各重复两行，分辨率不同；时序CODE用16070d(day)/16070m(decade)、17050d(decade)/17050m(month)。必须以原站CODE+res解析到时序CODE，不能简单rawCODE直接连接或无条件删除后缀。全部本国6站及唯一16390时序不受这个别名问题影响。

16390有492条1980-2020月记录，单位m³/s已由数据论文Discharge time series章节核实，均有限非负且年月唯一。但源qual_duplicates=0及qual_wb=0要求复查，不等于本轮发现每条观测都是假的；qual_consistency=0表示统计持久性，qual_order=0不适用，qual_regime为分类，不是所有0都失败或所有1都业务认证。源曾对孤立单点缺口插补而未给逐条原始/插补标记，不把492条全部称作未经处理的原始逐日观测。

六个KAZ点都在Arys，首流域0点/0时序。其492个月不用于替换巴尔喀什—阿拉湖目标样本。原始文件使用SQLite immutable=1/GDAL IMMUTABLE=YES，只读并保留原MD5；不修改WAL头或源表。两个冰川变薄字段按发布者警告排除，不用于特征。
''')
event('CA_key_contract_audited',time_series_CODEs=len(t),normalized_locations=int(t.base_CODE.nunique()),target_basin_Q_from_CA=0)
