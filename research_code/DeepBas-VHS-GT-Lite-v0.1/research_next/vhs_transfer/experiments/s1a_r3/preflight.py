"""Bounded local forcing admission, synthetic tests, role isolation and execution freeze."""
from common import *
import xarray as xr
def main():
    if (H/(P+'execution_manifest.json')).exists():raise RuntimeError('Already frozen; no overwrite')
    hist=load(R2/'integrity_before.json')['hashes']
    for k,v in load(R2/'delivery_manifest.json').items():hist[k]=v['sha256']
    p=R2/'delivery_manifest.json';hist[p.relative_to(ROOT).as_posix()]=sha(p)
    sources=['scripts/download_era5_land.py','scripts/prepare_era5_land_daily.py','scripts/area_weight_era5_land.py','scripts/area_weight_incremental_era5.py','scripts/finalize_era5_after_download.ps1','data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc','data/processed/era5_land/incremental_grid_weights.csv','data/processed/era5_land/incremental_basin.geojson','data/processed/era5_land/era5land_daily_gridded_1978_1983.nc','data/processed/nodes.csv','outputs/era5_land_validation/validation_report.json','scripts/audit_bd1m_e4b0_incremental_forcing.py','outputs/vhs_bd1m/experiments/e4b0_incremental_forcing_report.md']
    registry=load(ROOT/'research_next/vhs_transfer/data_audit/source_manifest.json');checks=[]
    for p in sources:
        actual=sha(ROOT/p)
        if p in registry and actual!=registry[p]['sha256']:raise RuntimeError('Source differs from S0 inventory: '+p)
        if p in hist and actual!=hist[p]:raise RuntimeError('Historical source mismatch: '+p)
        hist[p]=actual;checks.append(dict(path=p,sha256=actual,verified_against_S0=p in registry))
    for p,v in hist.items():
        if sha(ROOT/p)!=v:raise RuntimeError('Historical mismatch: '+p)
    dump('integrity_before.json',dict(files=len(hist),hashes=hist))
    protocol=dict(phase='VHS-NEXT-S1A-R3',identity=IDENTITY,authorization='current user attachment 3ee1ffa7-6806-4d23-a513-c33f8c4d3df4',regime='nominally past-only daily index',features=['P7','T7','W1','W7','W30'],met_definition='P7=mean P(t-7..t-1); T7=mean T(t-7..t-1)',old_feature_difference='P_inc_7d is sum; P7 is exactly sum/7 over same fixed window; no old feature reused or changed',spatial_scope='existing incremental BYBLK-to-DSK basin only',train_dates={str(y):['1978-01-31',f'{y-1}-12-31',n] for y,n in zip((1981,1982,1983),(1066,1431,1796))},development_dates={str(y):[f'{y}-01-01',f'{y}-12-31',365] for y in (1981,1982,1983)},models={'M0':'R1 frozen monthly climatology','M1':'R1 frozen monthly + W1/W7/W30; no refit','M2':'C_target(month)+beta2 dot Z(P7,T7)','M3':'C_target(month)+beta3 dot Z(P7,T7,W1,W7,W30)'},target_baseline='reuse R1 target monthly means; residual y_train-C_target',meteorological_transform='training anchor-month means, then train anomaly std(ddof=0); dev only applies',q_transform='reuse exact R1 monthly means and std; never reestimate model transform',solver='OLS np.linalg.pinv rcond=1e-12; no intercept/ridge/search',minimum_scale=1e-12,rank_stop='smin <= 1e-12*smax; require full rank2/5',diagnostic_warning='condition>30 or VIF>10; descriptive only, no model change',nonnegative='max(raw,0), report clipping and untruncated RMSE',comparisons=[['M3','M2'],['M1','M0'],['M2','M0'],['M3','M1']],primary='M3_vs_M2',no_confirmatory_2percent_rule=True,exante_strata='training U(t-1) Q20/Q90, real aligned fixed date masks',orthogonal_blocks='nonoverlap30days anchored Jan1, yearend5days; restricted support intersects original blocks',year_swap=dict(support='Jan31-Dec31 335 target days',donors=list(range(1978,1984)),month_day_mapping=True,leap_rule='actual donor calendar; no target Feb29; donor Feb29 naturally enters trailing window',replace='only upstream W1/W7/W30; target P7/T7 unchanged, frozen M3 parameters',future_donor='noncausal historical negative control only'),uncertainty=dict(type='paired within-year circular block bootstrap plus noncircular sensitivity',replicates=10000,seed=20261011,block_days=[30,60],scopes=['1981','1982','1983','MACRO_EQUAL_YEAR'],conditional_only=True,parameter_uncertainty_covered=False,p_values=False),fit_calls_authorized=6,stop_on_material_anomaly=True,new_blind_test=False)
    dump(P+'frozen_protocol.json',protocol)
    # Deterministic causal window and train-transform tests with artificial values only.
    d=days('2001-01-01','2001-02-15');a={str(x):float(i) for i,x in enumerate(d)};anchors=d[7:];v=windows(a,anchors,(7,))[:,0];check(v,np.arange(len(anchors))+3)
    a2=a.copy();a2[str(d[20])]=10000.;before=windows(a, d[20:21],(7,));after=windows(a2,d[20:21],(7,));check(before,after)
    const=np.ones((5,2));assert np.linalg.matrix_rank(const)<2
    b=np.array(['1980'+str(x)[4:] for x in days('1981-02-28','1981-03-01')],dtype='datetime64[D]');assert str(b[1])=='1980-03-01' and str(b[1]-np.timedelta64(1,'D'))=='1980-02-29'
    synthetic=['exact_past7_mean','same_day_perturbation_excluded','rank_deficiency_detected','leap_month_day_alignment']
    with xr.open_dataset(FORCING) as ds:
        expected=days('1978-01-01','1983-12-31');assert np.array_equal(ds.time.values.astype('datetime64[D]'),expected) and len(expected)==2191
        assert np.array_equal(ds.time.values,expected.astype('datetime64[ns]'))
        assert ds.sizes['basin']==1 and str(ds.basin.values[0])=='00705600_to_00705700'
        assert ds.precipitation_mm.attrs['units']=='mm day-1' and ds.temperature_c.attrs['units']=='degC'
        assert ds.attrs['daily_boundary']=='UTC+00:00'
        vals={n:ds[n].values.reshape(-1) for n in ('precipitation_mm','temperature_c')}
        for x in vals.values():assert np.isfinite(x).all()
        assert np.min(vals['precipitation_mm'])>=0
        metadata=dict(attrs=dict(ds.attrs),variables={k:dict(attrs=dict(ds[k].attrs),min=float(v.min()),max=float(v.max()),n=len(v)) for k,v in vals.items()},incremental_area_km2=float(ds.incremental_area_km2.values[0]))
    weights=read(ROOT/'data/processed/era5_land/incremental_grid_weights.csv');check(sum(float(r['weight']) for r in weights),1.)
    area=sum(float(r['overlap_km2']) for r in weights);check(area,metadata['incremental_area_km2'])
    # Check saved spatial weights against the existing daily grid, P/T only; no reprocessing/download.
    with xr.open_dataset(ROOT/'data/processed/era5_land/era5land_daily_gridded_1978_1983.nc') as grid:
        spatial={}
        for name in vals:
            rec=np.zeros(2191)
            for r in weights:
                lat=float(r['latitude']);lon=float(r['longitude']);a=grid[name].sel(latitude=lat,longitude=lon,method='nearest',tolerance=1e-8).values.astype(float);rec+=float(r['weight'])*a
            err=float(max(abs(rec-vals[name])));assert np.allclose(rec,vals[name],rtol=1e-6,atol=1e-5);spatial[name]=err
    up,p,t=feature_sources();assert sorted(up)==sorted(p)==sorted(t)
    pars={(r['fold'],r['comparison']):r for r in load(R1/'fitted_parameters.json')};design=[]
    for yr in (1981,1982,1983):
        tr=days('1978-01-31',f'{yr-1}-12-31');dv=days(f'{yr}-01-01',f'{yr}-12-31');met,md,q,qd,cl,scale=transform(up,p,t,tr,dv,pars[yr,'past_only'])
        for model,x,k in [('M2',met,2),('M3',np.column_stack([met,q]),5)]:
            s=require_rank(x,k);design.append(dict(fold=yr,model=model,train_n=len(tr),dev_n=len(dv),singular_values=s.tolist(),condition=float(s[0]/s[-1])))
        common=dv[30:];assert len(common)==335
        for donor in range(1978,1984):windows(up,np.array([str(donor)+str(x)[4:] for x in common],dtype='datetime64[D]'),(1,7,30))
    # No Q labels enter the forcing pipeline: the inspected generators read climate, geometry, station IDs only.
    for pth in ('scripts/prepare_era5_land_daily.py','scripts/area_weight_incremental_era5.py','scripts/download_era5_land.py'):
        code=(ROOT/pth).read_text(encoding='utf-8');assert 'Q_target_dsk' not in code and 'timeseries.csv' not in code
    gate=dict(R3_DATA_GATE='PASS',project_numerical_scope_only=True,formal_independent_meteorology_certified=False,forcing_metadata=metadata,spatial_weight_rows=len(weights),weight_sum=sum(float(r['weight']) for r in weights),spatial_reproduction_max_abs=spatial,source_checks=checks,synthetic_tests=synthetic,design_checks=design,dates_complete=True,strict_t_minus1=True,target_Q_in_forcing_generation='NO_PATH_FOUND_IN_INSPECTED_GENERATORS; no target-based filtering in deterministic P/T extraction',development_labels_opened=False,limitations=['ERA5 reanalysis is retrospective, not operational','UTC forcing date is documented internally; station Q hydrological day remains unverified','Historical investigators selected this study basin and new feature hypothesis after Q exposure; not independent feature selection','No original hourly-download rerun; reuse historical85-file validation and current source hashes'])
    dump('data_gate.json',gate)
    lineage=f'''# VHS-NEXT-S1A-R3｜气象强迫来源与准入

身份：{IDENTITY}。R3_DATA_GATE=PASS，仅限项目数值级探索，不是独立气象过程认证。

实际读取NetCDF：{FORCING.relative_to(ROOT).as_posix()}，SHA256={sha(FORCING)}。实际2191个连续UTC午夜日期，1978-01-01至1983-12-31；precipitation_mm为日总降水mm day-1，temperature_c为24小时平均2m温度degC，均无非有限值。未凭文件名推断。

生成链：download_era5_land.py请求reanalysis-era5-land的tp与逐小时t2m；prepare_era5_land_daily.py将00UTC累计值移至前一日，tp×1000(m→mm)，t2m按UTC日取24小时均值后−273.15(K→°C)；area_weight_incremental_era5.py使用HydroBASINS拓扑及站点ID定义DSK上游集水区减BYBLK上游集水区，按EPSG:6933交叠面积加权。面积={area:.6f}km²，175权重和为1。新独立重算已有日网格P/T与加权NetCDF的最大差为{spatial}，符合float32保存精度；没有重新生成或写入气象文件。

指定生成器没有DSK观测Q输入或按Q调参/筛选路径；station nodes仅使用站号、HYBAS_ID和面积。上下游流域定义与S0/E4B0记录一致。原finalizer之后还有历史模型训练步骤，本轮仅阅读源码、不执行finalizer。旧D5有全时期目标参与特征选择污染，但不从D5选择结果/派生表读取特征；本轮P7/T7由当前用户固定，不宣称从未受历史Q观察启发。

差异明示：旧P_inc_7d=sum(P[t−7..t−1])；本轮P7=mean同七日，即旧数值/7；T7同旧7日均温。只从日P/T新建本轮固定平均特征，未改变窗口或旧表。各折1978-01-31起训练1066/1431/1796日，开发各365日。P/T与上游日键逐日一致，全部t−7..t−1窗口可用，无填补、删日或替代变量。

来源代码/数据与S0 source_manifest内已有SHA逐一核对，详见data_gate.json。历史原始85文件验证记录PASS仅作继承证据，没有重扫逐小时文件或全项目。强迫UTC日界为项目内部可核对约定；Q日界和实际供数时刻未正式认证，t−1仅为名义日期过去。ERA5再分析可能利用后验观测，不能视作实时可获取强迫。强迫独立于项目目标Q生成的结论限所查本地生成链，不等于已穷尽供应商全部同化来源。

合成窗口/同日扰动/秩/闰年检查通过。开发评分标签尚未由R3执行器打开；随后固定全部代码、配置、输入、环境和日期再拟合。数据、代码及历史哈希漂移/缺日/秩不足均立即停止，不自动修复。
'''
    (REPORTS/(P+'forcing_lineage.md')).write_text(lineage,encoding='utf-8')
    dump('environment.json',dict(python=sys.version,executable=sys.executable,numpy=np.__version__,xarray=xr.__version__,platform=platform.platform(),gpu_used=False))
    files=list(H.glob('*.py'))+[H/(P+'frozen_protocol.json'),H/'environment.json',H/'data_gate.json']
    frozen={p.relative_to(ROOT).as_posix():sha(p) for p in files};frozen.update(hist)
    dump(P+'execution_manifest.json',dict(phase='R3',identity=IDENTITY,frozen_at=datetime.now(timezone.utc).isoformat(),frozen_hashes=frozen,data_gate='PASS',development_labels_opened=False,authorized_fits=6))
    event('PREFLIGHT_AND_EXECUTION_FROZEN',gate='PASS',development_labels_opened=False,hashes=len(frozen));print(dict(gate='PASS',protected=len(hist),designs=design))
if __name__=='__main__':main()
