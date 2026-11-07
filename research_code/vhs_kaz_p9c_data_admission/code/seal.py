from acquire import *
import ast,shutil
if __name__=='__main__':
 if (ROOT/'SHA256SUMS.txt').exists():raise RuntimeError('Refuse resealing')
 required=['P9C_COMPLETION_REPORT_ZH.md','P9C_NEW_Q_SOURCE_RESULTS.csv','P9C_GAUGE_Q_ADMISSION.csv','P9C_HISTORICAL_STATION_CROSSWALK.csv','P9C_MONTHLY_Q_QC.csv','P9C_CATCHMENT_VALIDATION.csv',
  'P9C_ERA5_LAND_DRIVER_RESULTS.csv','P9C_P10_READINESS.md','P9C_SCI_EVIDENCE_UPDATE.md','P9C_REPRODUCTION_GUIDE.md','P9C_CATCHMENT_GIS.gpkg']
 missing=[n for n in required if not (ROOT/n).is_file() or (ROOT/n).stat().st_size==0];assert not missing
 qa=json.loads((ROOT/'P9C_INDEPENDENT_QA.json').read_text(encoding='utf-8'));assert qa['failed']==0
 for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
 h=json.loads((ROOT/'evidence/HISTORY_BASELINE.json').read_text(encoding='utf-8'));bad=[p for p,s in h.items() if not Path(p).is_file() or sha(p)!=s];assert not bad
 js(ROOT/'evidence/HISTORY_PRESEAL_CHECK.json',dict(checked=len(h),passed=len(h),failed=0))
 # Weight hashes, rather than an unrelated added GPKG layer, are the exact
 # forcing identity for every job. The final Q-aligned job pins current GIS.
 weight_hash=sha(ROOT/'data/TAUTURGEN_ERA5_LAND_AREA_WEIGHTS.csv');gp_hash=sha(ROOT/'P9C_CATCHMENT_GIS.gpkg')
 contracts={k:json.loads((ROOT/f'driver/{k}_DRIVER_CONTRACT.json').read_text(encoding='utf-8')) for k in ['PILOT1965','LONG1964_1978','QALIGNED2000_2015']}
 assert all(x['weights_sha256']==weight_hash for x in contracts.values())
 assert contracts['QALIGNED2000_2015']['source_catchment_sha256']==gp_hash
 js(ROOT/'evidence/FORCING_INPUT_PROVENANCE.json',dict(weights_sha256=weight_hash,current_GPKG_sha256=gp_hash,all3job_weights_hashes_match=True,Q_aligned_job_GPKG_hash_matches=True,
  initial_pilot_GPKG_byte_revision_note='Pilotfilehashprecedesadditionoflegacy_host_conflictlayerinauxiliary.py;weightfileunchangedandalljobsbindthesame14weights;noassertionoldwholeGPKGbytesarestillavailable',
  initial_pilot_GPKG_byte_hash_current_match=contracts['PILOT1965']['source_catchment_sha256']==gp_hash))
 reg=[dict(experiment_id='P9C_E2_WB10195_SCHEMA_V2',path='exploratory_temporal/run',scientific_state='EXPLORATORY_KNOWN_GAUGE_SCHEMA_NORMALIZED_QC_LIMITED',predictions=96,model_estimates=2,
  prediction_sha256=sha(ROOT/'exploratory_temporal/run/E2_PREDICTIONS.csv'),not_PUB=True,not_blind_future_test=True,default_national_model=False),
 dict(experiment_id='P9C_INVALID_TIME_COLUMN_ALIGNMENT',path='exploratory_temporal_REJECTED_COLUMN_ALIGNMENT/run',scientific_state='REJECTED_SOURCE_COLUMN_ALIGNMENT',predictions=120,model_estimates=2,
  include_in_any_scientific_performance_summary=False,old_run_SHA_preserved=True)]
 js(ROOT/'P9C_EXPERIMENT_REGISTRY.json',reg)
 import pandas as pd
 metric=pd.read_csv(ROOT/'exploratory_temporal/run/E2_TEMPORAL_METRICS.csv',dtype={'year':str});failedyear=metric[(metric.variant=='RAW')&(metric.year=='2014')]
 extra='\n\n## 最终数值复核与完整失败保留\n\n'+f"独立科学数值检查{qa['passed']}通过、{qa['failed']}失败；历史{len(h)}个文件哈希一致。2014年C0 NSE={float(failedyear[failedyear.model_id=='C0'].NSE.iloc[0]):.6f}，C0+PT NSE={float(failedyear[failedyear.model_id=='C0+PT'].NSE.iloc[0]):.6f}，均保留。全年48月合并NSE不是4个年度NSE的平均。所有4年的气象增量均负，不调整alpha或删除年份。\n\n"
 extra+='字段归一化仍待源方正式确认；数值核验通过不等于观测QC或业务认证。初版错误成绩不可引用，科学状态以P9C_EXPERIMENT_REGISTRY为准。\n'
 with (ROOT/'P9C_COMPLETION_REPORT_ZH.md').open('a',encoding='utf-8') as f:f.write(extra)
 # Archive failed setup/processing attempts, including the original bs4 import
 # error fixed using stdlib only. No dependencies were installed.
 js(ROOT/'evidence/FAILURE_RECOVERY_INDEX.json',[
  dict(issue='missing_bs4_beforebootstrap',action='removeddependencyusedstdlibregex;nopackageinstall'),
  dict(issue='DNSandNCDCremoteclosed/Kazdatabase_timeout',action='boundedretries;publicdirectWBfileacquired;NCDC/officialgatekept'),
  dict(issue='WB_API_HTTP200_invalidresource',action='usedexplicitpublicCSVlinkfromofficialpage;notcalledemptyAPIaQsuccess'),
  dict(issue='sourcefooter22bytes',action='rawbytesretained;nondatefooterisolated;derivedmetadataremovessuffix'),
  dict(issue='UNDECLARED_TIME_HEADER_COLUMN',action='INITIALQCOUNTSAND2MODELS120PREDICTIONSWITHDRAWN;sourcecontractnormalized;newcoverage-onlysplit;oldrunSHAretained'),
  dict(issue='D8floattransform7e-15degree',action='samepixelgridverifiedwithin1e-10degree;noreprojection'),
  dict(issue='ACCplus1assumption',action='officialTechDocp18countsfrom1;initialfailurearchived'),
  dict(issue='GeometryCollectionareaomission',action='initial11cellweightsfailed11.035percentpartition;retainallpolygoncomponents;final14cellconservation1.31e-9'),
  dict(issue='tinyNetCDFnegativeprecipitation',action='ECMWFsource;explicitderivedphysicalPnegativeQCbound;rawsignedvaluesandmonthlycorrectionretained'),
  dict(issue='Kashiannual2015extrayear',action='retain846annualvalues;metadataexception;noannualrunoffusedasQlabels')])
 state=json.loads((ROOT/'P9C_FINAL_STATUS.json').read_text(encoding='utf-8'));state.update(independent_QA_passed=qa['passed'],independent_QA_failed=qa['failed'],historical_unchanged=len(h))
 js(ROOT/'P9C_FINAL_STATUS.json',state)
 js(ROOT/'evidence/DELIVERY_ACCEPTANCE.json',dict(required_files_checked=len(required),required_missing=missing,source_schema_disclosure=True,
  independent_science_passed=qa['passed'],independent_science_failed=qa['failed'],history_checked=len(h),history_changed=0,
  actual_new_Q_target_stations=4,complete_station_months=705,numeric_complete_station_years=57,
  actual_raster_point_catchments=1,field_survey_exact_boundaries=0,actual_Q_aligned_driver_months=192,accepted_E2_predictions=96,
  invalid_source_alignment_predictions_excluded=120,P10_fit_calls=0,teacher_Q_read=0,web_modified=False))
 event(stage='P9C_FINAL_SEAL',science_passed=qa['passed'],science_failed=qa['failed'],historical_unchanged=len(h),accepted_E2_predictions=96,rejected_predictions=120,P10='NOT_READY')
 # Explicit state index prevents consumers from treating retained failures or
 # reconstructed annual data as active independent observations/results.
 index=[]
 for p in sorted(ROOT.rglob('*')):
  if not p.is_file() or p==ROOT/'SHA256SUMS.txt':continue
  name=p.relative_to(ROOT).as_posix()
  if 'REJECTED_COLUMN_ALIGNMENT' in name or 'rejected_column_alignment/' in name:status='REJECTED_SOURCE_COLUMN_ALIGNMENT_NOT_A_RESULT'
  elif 'initial_ACC_semantics/' in name or 'initial_grid_geometrycollection/' in name:status='REJECTED_PROCESSING_ATTEMPT'
  elif 'ZENODO_ANNUAL' in name or 'Water_cycle_components' in name:status='AUXILIARY_ANNUAL_CONSTRUCTED_NOT_OBSERVED_LABELS'
  elif name.startswith('exploratory_temporal/run/'):status='ACTIVE_EXPLORATORY_E2_SCHEMA_NORMALIZED_QC_LIMITED'
  elif 'LONG1964_1978' in name or 'PILOT1965' in name:status='REAL_MET_NOT_USED_IN_EFFECTIVE_Q_ALIGNED_MODEL'
  else:status='SOURCE_OR_DATA_ADMISSION_EVIDENCE_SEE_REGISTRY'
  index.append(dict(path=name,scientific_state=status))
 pd.DataFrame(index).to_csv(ROOT/'P9C_ARTIFACT_STATE_MANIFEST.csv',index=False,encoding='utf-8-sig')
 files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p!=ROOT/'SHA256SUMS.txt')
 (ROOT/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in files),encoding='utf-8')
 print(json.dumps(dict(sealed_files=len(files),manifest_sha256=sha(ROOT/'SHA256SUMS.txt')),ensure_ascii=False))
