import sys,json,csv,hashlib,re,calendar,math,collections,time
from pathlib import Path
from datetime import datetime
from pyproj import Transformer,Geod
sys.stdout.reconfigure(encoding='utf-8');L=Path(r'E:\VHS_Public_Baseline_Lab');R=L/'vhs_p6b_external_validation';P4=L/'p4_final_reconstruction'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def jw(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def cw(p,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with Path(p).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def readcsv(p,sep=','):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig',newline=''),delimiter=sep))
def prev(d):y,m=map(int,d.split('-'));return f'{y if m>1 else y-1}-{m-1 if m>1 else 12:02d}'
def ehyd(p,values=False):
 txt=p.read_text(encoding='latin1');assert 'Werte:' in txt;head,body=txt.split('Werte:',1);assert ',Abfluss,I,Mit,T,' in head and '[m³/s]' in head,'NOT_DAILY_MEASURED_DISCHARGE'
 rows={};duplicate=set()
 for line in body.splitlines():
  if ';' not in line:continue
  dt,tok=line.split(';',1)
  try:d=datetime.strptime(dt.strip(),'%d.%m.%Y %H:%M:%S')
  except ValueError:continue
  key=d.strftime('%Y-%m-%d');token=tok.strip();present=bool(re.fullmatch(r'-?\d+(?:,\d+)?',token))
  if key in rows:duplicate.add(key)
  rows[key]={'present':present,'midnight':d.hour==d.minute==d.second==0}
  if values:rows[key]['Q']=float(token.replace(',','.')) if present else None
 return head,rows,duplicate
if __name__=='__main__' and sys.argv[1]=='freeze':
 assert not (R/'P6B_FROZEN_PROTOCOL.json').exists();models=[]
 for s in jl(R/'evidence/STATIONS_27.json'):
  for mid in ['C0_PT','P2-L1']:
   path=P4/'models/V2'/f'ID_{s["gauge_id"]}'/mid;models.append({'gauge_id':s['gauge_id'],'path':str(path),'model_hash':sha(path/'SHA256SUMS.txt'),'files':{x.name:sha(x) for x in path.iterdir() if x.is_file()}})
 protocol={'experiment':'PUBLIC_DATA_P6B_EXTERNAL_TEMPORAL_VALIDATION','task':'RECONSTRUCTION_WITH_OBSERVED_MET','frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'models':['C0+PT','P2-L1'],'frozen_models':models,'station_cohort':[s['gauge_id'] for s in jl(R/'evidence/STATIONS_27.json')],'primary_period':['2018-01','2019-12'],'2020':'ONLY_AFTER_FULL_2015_2019_DRIVER_PARITY_PASS','exclude_previously_scored_samples':['818:2018-01..2019-12'],'eligibility':{'identity':'exact official ID; river/name supporting; full-upstream area difference <=5%; closest documented BMN meridian CRS position <=500m; post2017 relocation notes require manual exclusion','Q':'official measured daily mean discharge m3/s; exactly all unique calendar days, no missing/gap tokens, midnight provider date; no filling; negative/nonfinite triggers scoring abort; official footnotes retained','met':'original frozen LamaH full-upstream ERA5L daily file hash; all real calendar days finite nonnegative P / finite T; full preceding calendar month P; no missing-as-zero','minimum_months_for_station_summary':12,'no_score_selection':True},'quality_tiers':{'DESCRIPTIVE_ARCHIVE':'provider daily Q archive, no per-day QC field; includes flagged reconstructed/ice-affected months; provider civil day timezone not independently certified UTC','STRICT_SENSITIVITY':'same archive excluding every month mentioned in target-year OWF-Q quality footnotes, including ice/reconstructed/missing; unresolvable dated note excludes whole applicable year; still not daily-QC-certified','CERTIFIED_STRICT':'requires explicit checked daily QC plus time/identity certification; none assumed'},'source_licence':'eHYD BMLUK official noncommercial reproduction with attribution unless specific restriction; source downloads kept local, no Qobs bulk export; CAMELS-CH distinct licence as prior source record','score':{'metrics':['NSE','KGE','KGE_r','KGE_alpha','KGE_beta','RMSE','MAE','PBIAS','MSE_skill'],'intervals':[80,90],'interval_score':'width+2/a*(lower-y)+ outside_lower +2/a*(y-upper) outside_upper','raw_primary_nonnegative_secondary':True,'subsets':['ALL','year','DJF','MAM','JJA','SON','MAY_JUNE'],'summary':'station equal weight and median by macro river group; two years not independent basins; no significance claim; no cross-basin pooling raw m3/s squared errors','undefined':'null plus reason, never zero'},'fit_calls_allowed':0,'prediction_before_label_scoring':True,'teacher_Q_read':False,'no_web_changes':True,'P6A_scores_previously_known':True,'P6B_new_test_scores_seen':False}
 jw(R/'P6B_FROZEN_PROTOCOL.json',protocol);print('PROTOCOL_FROZEN',sha(R/'P6B_FROZEN_PROTOCOL.json'))
elif __name__=='__main__' and sys.argv[1]=='admit':
 assert not (R/'P6B_ADMISSION_FROZEN.json').exists();protocol=jl(R/'P6B_FROZEN_PROTOCOL.json');ss=jl(R/'evidence/STATIONS_27.json');snap=jl(P4/'source/SNAPSHOT.json');rows=[];support=[];met={};pins={};sources={};notes=[];identities={};geo=Geod(ellps='WGS84')
 monthnames={'jän':1,'jan':1,'feb':2,'mrz':3,'mär':3,'apr':4,'mai':5,'jun':6,'jul':7,'aug':8,'sep':9,'okt':10,'nov':11,'dez':12}
 for s in ss:
  g=s['gauge_id'];code=s['official_gauge_id'];base={'gauge_id':g,'country':s['country'],'region':s['original_attributes']['region'],'official_id':code,'LamaH_name':s['name'],'river':s['river'],'original_area_km2':s['area_km2']};flagged=set();qrows={};dupes=set();identity=False;reason=''
  if s['country']=='AUT':
   qp=R/'external'/f'EHYD_{code}_file5.txt';mp=R/'external'/f'EHYD_{code}_file1.txt';base['Q_source']='eHYD official HZB daily Abfluss archive';base['source_url']=f'https://ehyd.gv.at/services/MessstellenExtraData/owf?id={code}&file=5'
   try:
    head,qrows,dupes=ehyd(qp);meta=mp.read_text(encoding='latin1');pins[str(qp)]=sha(qp);pins[str(mp)]=sha(mp);sources[str(g)]=str(qp)
    assert re.search(r'HZB-Nummer:\s*;'+code+r'\b',head)
    newarea=float(re.search(r'Einzugsgebiet \[km²\]:\s*;([\d,]+)',head).group(1).replace(',','.'));coordblock=head.split('Bundesmeldenetz(BMN)-Koordinaten:')[1].split('Exportzeitreihe:')[0];coords=re.findall(r'(\d\d\.\d\d\.\d{4})\s*;([\d,]+)\s*-\s*([\d,]+)',coordblock);assert coords
    valid=[c for c in coords if datetime.strptime(c[0],'%d.%m.%Y')<=datetime(2018,1,1)];assert valid;last=valid[-1];e,n=[float(x.replace(',','.')) for x in last[1:]];distances=[]
    for crs in [31257,31258,31259]:
     lon,lat=Transformer.from_crs(crs,4326,always_xy=True).transform(e,n);_,_,d=geo.inv(*s['coordinates_wgs84'],lon,lat);distances.append((d,crs,lon,lat))
    d,crs,lon,lat=min(distances);ar=abs(newarea/s['area_km2']-1);postmove=[]
    for line in meta.splitlines():
     if 'OWF-' not in line:continue
     match=re.match(r'\s*(\d\d\.\d\d\.(\d{4}))\s*(\d\d\.\d\d\.(\d{4}))?;(.+)',line)
     if not match:continue
     start=int(match[2]);end=int(match[4]) if match[4] else 9999;note=match[5]
     if start<=2020 and end>=2018:
      notes.append({'gauge_id':g,'from':match[1],'to':match[3],'note':note})
      if 'verlegt' in note.lower() and start>=2018:postmove.append(note)
      if not note.startswith('OWF-Q/') or 'Neuberechnung des Flusskilometers' in note:continue
      found={m for k,m in monthnames.items() if re.search(r'(?<![a-zäöü])'+k+r'(?![a-zäöü])',note.lower())};months=found or set(range(1,13))
      for y in range(max(2018,start),min(2020,end)+1):flagged.update(f'{y}-{m:02d}' for m in months)
    identity=d<=500 and ar<=.05 and not postmove;base.update(new_name=re.search(r'Messstelle:\s*;([^\n]+)',head)[1].strip(),new_area_km2=newarea,area_relative_difference=ar,coordinate_difference_m=d,BMN_CRS=crs,new_lon=lon,new_lat=lat,coordinate_valid_from=last[0],identity_status='MATCHED_EXACT_CODE_AREA_COORDINATES' if identity else 'BLOCKED_IDENTITY_AREA_POSITION_OR_RELOCATION',post2017_relocation_notes='|'.join(postmove),source_period='..'.join([min(qrows),max(qrows)]))
    if not identity:reason='IDENTITY_AREA_POSITION_OR_RELOCATION_GATE'
   except Exception as ex:reason='SOURCE_OR_IDENTITY_CHECK_FAILED:'+str(ex);base['identity_status']='BLOCKED';base['error']=str(ex)
  elif g==818:
   base.update(Q_source='CAMELS-CH v0.9 observation_based',source_url='https://zenodo.org/records/15025258',identity_status='P6A_EXACT_OFFICIAL_ID_AREA_PRIMARY_COORDINATE_MATCH',source_period='1981..2020',quality='PROVIDER_NO_DAILY_QC_FLAGS');reason='2018_2019_ALREADY_SCORED_P6A;2020_DRIVER_PARITY_PENDING'
   cam=Path(L/'vhs_r2u1_p6a/external/CAMELS_CAMELS_CH_obs_based_2304.csv');pins[str(cam)]=sha(cam)
   for rr in readcsv(cam):
    token=rr['discharge_vol(m3/s)'].strip();qrows[rr['date']]={'present':token.lower() not in {'','nan','na','-999','-999.0','null'},'midnight':True}
   identity=True
  else:
   base.update(Q_source='GKD Bayern checked daily Q NOT_OBTAINED',source_url=f'https://www.gkd.bayern.de/',identity_status='P6A_EXACT_GOVERNMENT_ID_COORDINATE_AREA_MATCH',quality='BLOCKED_OFFICIAL_CHECKED_DAILY_NOT_OBTAINED');reason='GKD_DAILY_CHECKED_Q_NOT_OBTAINED;ESTREAMS_SPARSE_MONTHS_NOT_ACCEPTED';identity=True
  src=Path(snap['source_paths'][str(g)]['MET']);assert sha(src)==snap['source_files'][str(src)];pins[str(src)]=sha(src);daily=collections.defaultdict(list)
  for rr in readcsv(src,';'):
   dt=f'{int(rr["YYYY"]):04d}-{int(rr["MM"]):02d}'
   if '2017-12'<=dt<='2020-12':daily[dt].append(rr)
  mm={}
  for dt,rr in daily.items():
   y,m=map(int,dt.split('-'));n=calendar.monthrange(y,m)[1];ps=[float(r['prec']) for r in rr];ts=[float(r['2m_temp_mean']) for r in rr];ok=len(rr)==n and {int(r['DD']) for r in rr}==set(range(1,n+1)) and all(math.isfinite(v) and v>=0 for v in ps) and all(math.isfinite(v) and v!=-999 for v in ts)
   if ok:mm[dt]={'date':dt,'gauge_id':g,'P':sum(ps),'T':sum(ts)/n}
  met[str(g)]=list(mm.values());counts={}
  for y in [2018,2019,2020]:
   counts[y]=0
   for m in range(1,13):
    dt=f'{y}-{m:02d}';days=[f'{dt}-{d:02d}' for d in range(1,calendar.monthrange(y,m)[1]+1)];qok=all(d in qrows and qrows[d]['present'] and qrows[d]['midnight'] and d not in dupes for d in days);metok=dt in mm and prev(dt) in mm;eligible=bool(s['country']=='AUT' and identity and qok and metok);strict=eligible and dt not in flagged;counts[y]+=qok
    support.append({'gauge_id':g,'date':dt,'official_identity_match':identity,'expected_days':len(days),'Q_complete_calendar_days':qok,'P_T_same_processing':metok,'previous_precipitation_date':prev(dt),'target_Q_footnote':dt in flagged,'descriptive_eligible':eligible,'strict_sensitivity_eligible':strict,'certified_strict':False,'P6A_already_scored':g==818 and y in [2018,2019],'reason':'ADMITTED_PROVIDER_ARCHIVE_QUALIFIED' if eligible else reason or ('2020_DRIVER_PARITY_PENDING' if y==2020 else 'INCOMPLETE_Q_OR_MET')})
  base.update(Q_complete_months_2018=counts[2018],Q_complete_months_2019=counts[2019],Q_complete_months_2020=counts[2020],P_T_same_processing_2018_2019=all(f'{y}-{m:02d}' in mm for y in [2018,2019] for m in range(1,13)),P_T_2020=False,descriptive_months=sum(r['descriptive_eligible'] for r in support if r['gauge_id']==g),strict_sensitivity_months=sum(r['strict_sensitivity_eligible'] for r in support if r['gauge_id']==g),quality_tier='OFFICIAL_ARCHIVE_NO_PER_DAY_QC_WITH_FOOTNOTES' if s['country']=='AUT' else base.get('quality'),reason=reason,day_boundary='PROVIDER_CALENDAR_DAY; UTC_OFFSET_NOT_IN_EXPORT_HEADER',source_download_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()));rows.append(base);identities[str(g)]=identity
 cw(R/'P6B_STATION_CROSSWALK.csv',rows);cw(R/'P6B_MONTHLY_ADMISSION.csv',support);cw(R/'P6B_SOURCE_Q_FOOTNOTES.csv',notes);jw(R/'driver/MET_ONLY_2018_2019.json',met)
 ids=[f'{r["gauge_id"]}:{r["date"]}' for r in support if r['descriptive_eligible']];strictids=[f'{r["gauge_id"]}:{r["date"]}' for r in support if r['strict_sensitivity_eligible']];assert len(ids)==len(set(ids))
 admission={'protocol_hash':sha(R/'P6B_FROZEN_PROTOCOL.json'),'crosswalk_hash':sha(R/'P6B_STATION_CROSSWALK.csv'),'monthly_support_hash':sha(R/'P6B_MONTHLY_ADMISSION.csv'),'met_file_hash':sha(R/'driver/MET_ONLY_2018_2019.json'),'sources':sources,'source_hashes':pins,'descriptive_ids':ids,'strict_sensitivity_ids':strictids,'certified_strict_ids':[],'Q_numeric_values_sent_to_prediction':False,'quality_limit':'Provider archive includes reconstructed and ice-affected source notes; strict sensitivity excludes noted months but has no day-level checked QC certification; provider day boundary not UTC certified','scores_seen':False}
 jw(R/'P6B_ADMISSION_FROZEN.json',admission);print('ADMISSION',len({i.split(':')[0] for i in ids}),len(ids),'strict_sensitivity',len(strictids));print('STATIONS',[(r['gauge_id'],r['descriptive_months'],r['coordinate_difference_m'] if 'coordinate_difference_m' in r else None,r['reason']) for r in rows])
