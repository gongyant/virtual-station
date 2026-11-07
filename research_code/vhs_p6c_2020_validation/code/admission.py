"""Admission reads record/Q tokens for validation; writes NO Q observations."""
from p6c_common import *
from datetime import timedelta
sys.stdout.reconfigure(encoding='utf-8');stage=sys.argv[1];rows=[];notes=readcsv(B/'P6B_SOURCE_Q_FOOTNOTES.csv');source_rows=readcsv(R/'P6C_STATION_CROSSWALK_INITIAL.csv');pins={};sources={};monthnames={'jän':1,'jan':1,'feb':2,'mrz':3,'mär':3,'apr':4,'mai':5,'jun':6,'jul':7,'aug':8,'sep':9,'okt':10,'nov':11,'dez':12};met={};parity={}
if stage=='final':
 assert not (R/'P6C_ADMISSION_FROZEN.json').exists();parity={str(s['gauge_id']):s for s in jl(R/'driver/ALL24_PARITY_RESULT.json')};newmet=jl(R/'driver/ALL24_MONTHLY_MET_2015_2020.json');snap=jl(P4/'source/SNAPSHOT.json')
for s in source_rows:
 g=int(s['gauge_id']);path=Path(s['Q_source']);head,dd,dups=ehyd(path,values=True);pins[str(path)]=sha(path);pins[s['metadata_source']]=sha(s['metadata_source']);sources[str(g)]=str(path)
 assert re.search(r'HZB-Nummer:\s*;'+s['official_id']+r'\b',head);flagged=set();why={}
 for n in notes:
  if int(n['gauge_id'])!=g or not n['note'].startswith('OWF-Q/') or 'Neuberechnung des Flusskilometers' in n['note']:continue
  start=datetime.strptime(n['from'],'%d.%m.%Y');end=datetime.strptime(n['to'],'%d.%m.%Y') if n['to'] else datetime.max
  if start.year>2020 or end.year<2020:continue
  months={v for k,v in monthnames.items() if re.search(r'(?<![a-zäöü])'+k+r'(?![a-zäöü])',n['note'].lower())} or set(range(1,13))
  for m in months:flagged.add(m);why.setdefault(m,[]).append(n['note'])
 if stage=='final':
  src=Path(snap['source_paths'][str(g)]['MET']);assert sha(src)==snap['source_files'][str(src)];pins[str(src)]=sha(src);rr=[r for r in readcsv(src,';') if r['YYYY']=='2019' and int(r['MM'])==12];assert len(rr)==31 and len({r['DD'] for r in rr})==31
  pp=[float(r['prec']) for r in rr];tt=[float(r['2m_temp_mean']) for r in rr];assert all(math.isfinite(v) and v>=0 for v in pp) and all(math.isfinite(v) and v!=-999 for v in tt)
  met[str(g)]=[{'gauge_id':g,'date':'2019-12','P':sum(pp),'T':sum(tt)/31},*[{k:r[k] for k in ['gauge_id','date','P','T']} for r in newmet if r['gauge_id']==g and r['date'].startswith('2020-')]];assert len(met[str(g)])==13
 for m in range(1,13):
  dt=f'2020-{m:02d}';days=[f'{dt}-{d:02d}' for d in range(1,calendar.monthrange(2020,m)[1]+1)];complete=all(d in dd and dd[d]['present'] and dd[d]['midnight'] and d not in dups and math.isfinite(dd[d]['Q']) and dd[d]['Q']>=0 for d in days);driver=bool(parity.get(str(g),{}).get('driver_admitted',False));eligible=complete and driver
  rows.append({'gauge_id':g,'official_id':s['official_id'],'region':s['region'],'date':dt,'identity_status':'P6B_EXACT_ID_AREA_COORDINATE_MATCH_REUSED','coordinate_difference_m':s['coordinate_difference_m'],'Q_expected_days':len(days),'Q_present_valid_tokens':sum(d in dd and dd[d]['present'] for d in days),'Q_duplicate_days':sum(d in dups for d in days),'Q_calendar_complete':complete,'Q_unit':'m3/s','Q_daily_QC_certified':False,'Q_provider_UTC_day_certified':False,'Q_interval_header':'interval value until next timestamp or gap; midnight dates','prior_2020_Q_parser_exposure':True,'P_T_same_processing_parity':driver,'lag_date':'2019-12' if m==1 else f'2020-{m-1:02d}','Q_source_hash':sha(path),'source_Q_footnote':m in flagged,'source_notes':'|'.join(why.get(m,[])),'descriptive_eligible':eligible,'strict_sensitivity_eligible':eligible and m not in flagged,'reason':'ADMITTED_DESCRIPTIVE_NOT_DAILY_QC_CERTIFIED' if eligible else 'DRIVER_PENDING' if complete else 'INCOMPLETE_DUPLICATE_OR_NONNUMERIC_Q'})
cw(R/('P6C_STATION_ADMISSION.csv' if stage=='final' else 'P6C_Q_COVERAGE_INITIAL.csv'),rows)
if stage=='final':
 ww=jl(R/'driver/ALL_BASIN_GRID_WEIGHTS_FROZEN.json')
 for r in rows:
  s=next(s for s in source_rows if int(s['gauge_id'])==r['gauge_id']);r.update(basin_A_area_km2=ww[str(r['gauge_id'])]['basin_area_m2']/1e6,n_intersecting_grid_cells=len(ww[str(r['gauge_id'])]['weights']),weights_file_hash=sha(R/'driver/ALL_BASIN_GRID_WEIGHTS_FROZEN.json'),Q_source_path=s['Q_source'],metadata_source_path=s['metadata_source'])
 cw(R/'P6C_STATION_ADMISSION.csv',rows)
if stage=='final':
 jw(R/'driver/MET_ONLY_2019_12_2020.json',met);models=[]
 for mm in jl(B/'P6B_FROZEN_PROTOCOL.json')['frozen_models']:
  if str(mm['gauge_id']) not in sources:continue
  for n,h in mm['files'].items():assert sha(Path(mm['path'])/n)==h
  models.append(mm)
 ids=[f'{r["gauge_id"]}:{r["date"]}' for r in rows if r['descriptive_eligible']];strict=[f'{r["gauge_id"]}:{r["date"]}' for r in rows if r['strict_sensitivity_eligible']]
 jw(R/'P6C_ADMISSION_FROZEN.json',{'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'protocol_hash':sha(R/'P6C_FROZEN_PROTOCOL.json'),'admission_hash':sha(R/'P6C_STATION_ADMISSION.csv'),'met_hash':sha(R/'driver/MET_ONLY_2019_12_2020.json'),'weights_hash':sha(R/'driver/ALL_BASIN_GRID_WEIGHTS_FROZEN.json'),'parity_hash':sha(R/'driver/ALL24_PARITY_RESULT.json'),'source_hashes':pins,'sources':sources,'descriptive_ids':ids,'strict_sensitivity_ids':strict,'models':models,'scores_2020_read':False,'prior_Q_archive_exposure':True,'QC_limit':'no perday checked QC or certified UTC day; conservative footnote exclusion not certification'})
 event('ADMISSION_FROZEN',stations=len({s.split(':')[0] for s in ids}),months=len(ids),strict_months=len(strict),protocol_hash=sha(R/'P6C_FROZEN_PROTOCOL.json'),admission_hash=sha(R/'P6C_ADMISSION_FROZEN.json'))
print(stage,'Q_COMPLETE',sum(r['Q_calendar_complete'] for r in rows),'DRIVER_ADMITTED',sum(r['descriptive_eligible'] for r in rows),'STRICT',sum(r['strict_sensitivity_eligible'] for r in rows))

