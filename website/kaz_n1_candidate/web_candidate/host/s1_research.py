"""Selected-station frozen evidence; no model execution and no bulk observation API."""
import json,csv,hashlib,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parent.parent
DS='LAMAH_CE_PUBLIC_V1'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
def csvrows(p):
 with open(p,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def typed(r):
 out={}
 for k,v in r.items():
  if v=='':out[k]=None
  elif v in ('True','False'):out[k]=v=='True'
  elif k=='period' or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',v):out[k]=v
  else:
   try:out[k]=float(v) if any(t in v.lower() for t in ['.','e']) else int(v)
   except (ValueError,TypeError):out[k]=v
 return out
class ResearchEvidence:
 def __init__(self):
  self.contract=jl(ROOT/'WEB_S1_DATA_CONTRACT.json');self.pins=self.contract['source_pins'];self.data={}
  for p,h in self.pins.items():
   if sha(p)!=h:raise ValueError('WEB_S1_FROZEN_SOURCE_MISMATCH')
   if p.endswith('.csv'):self.data[pathlib.Path(p).name]=[typed(r) for r in csvrows(p)]
  self.contract_pin=sha(ROOT/'WEB_S1_DATA_CONTRACT.json')
 def env(self,**v):return {'dataset_id':DS,'display_scope':'USER_REQUEST_LOCAL_CANDIDATE_RESEARCH_ONLY','production_display_permission':'NOT_GRANTED','dynamic_execution':'NOT_AUTHORIZED','business_certification':'NOT_CERTIFIED','reach_status':'REACH_PREDICTION_NOT_AVAILABLE',**v}
 def validation_status(self,g):
  return {'gauge_id':g,'status':'P6B_C_D_FROZEN_2018_2020_VALIDATION_AVAILABLE','paired_months':36,'model_release':'P4-V2','train_cutoff':'2017-12','business_certification':'NOT_CERTIFIED','source_scopes':self.contract['periods']} if g in self.contract['external_cohort'] else None
 def handle(self,path,q,bridge):
  try:
   if sha(ROOT/'WEB_S1_DATA_CONTRACT.json')!=self.contract_pin:return 409,self.env(status='SOURCE_DATA_MISMATCH')
   for p,h in self.pins.items():
    if sha(p)!=h:return 409,self.env(status='SOURCE_DATA_MISMATCH')
   if q.get('dataset')!=DS:return (403 if q.get('dataset')=='SYRDARYA' else 409),self.env(status='DATASET_NOT_AUTHORIZED')
   leaf=path.rsplit('/',1)[-1]
   if leaf in ['execute','predict','export','download']:return 403,self.env(status='OPERATION_NOT_AUTHORIZED')
   if any(k in q for k in ['format','export','download','Qobs','qobs','path','file']):return 403,self.env(status='BULK_EXPORT_NOT_AUTHORIZED')
   if q.get('local_qobs','0') not in ['0','1']:return 400,self.env(status='INVALID_LOCAL_RESEARCH_SELECTION')
   if leaf=='catalog':
    cat=bridge.catalog()
    return 200,self.env(stations=[{**s,'P6_external_station':int(s['gauge_id']) in self.contract['external_cohort'],'P6_station_months':36 if int(s['gauge_id']) in self.contract['external_cohort'] else 0} for s in cat['stations']],periods=self.contract['periods'],v1_scope=cat['releases']['TEMPORAL_HOLDOUT'],coverage={'original_stations':27,'matched_external_cohort':24,'paired_station_months':864,'frozen_predictions':1728},notice='P6C原288站月；严格敏感性132站月、仅4站完整年度；均不等于逐日QC或业务认证。')
   if leaf=='p7':
    p=ROOT/'research/P7A_SUMMARY.json'
    return 200,self.env(research=jl(p) if p.exists() else {'status':'NOT_IMPORTED'},default_model='P2-L1_UNCHANGED')
   period=q.get('period');scope=self.contract['periods'].get(period)
   if not scope or q.get('snapshot')!=scope['source_snapshot_id']:return 409,self.env(status='SOURCE_DATA_MISMATCH')
   uid=q.get('station','');allowed={s['station_uid'] for s in bridge.bundle['stations']}
   if uid not in allowed:return 400,self.env(status='STATION_DATASET_MISMATCH')
   if q.get('model','P2-L1') not in self.contract['models']:return 400,self.env(status='MODEL_NOT_RELEASED')
   g=int(uid.rsplit(':',1)[-1]);start=q.get('start',scope['start']);end=q.get('end',scope['end'])
   if not all(re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',v) for v in [start,end]) or start>end:return 400,self.env(status='INVALID_TIME_WINDOW')
   # Date window must belong to the selected snapshot. Missing results are never filled with zero.
   start=max(start,scope['start']);end=min(end,scope['end'])
   if leaf=='station':
    paired=[r for r in self.data['P6D_MONTHLY_PAIRED_ERRORS.csv'] if r['gauge_id']==g and start<=r['date']<=end]
    local=q.get('local_qobs')=='1'
    public_fields=['gauge_id','date','year','month','Qsim_C0PT','Qsim_L1','support_C0PT','support_L1','strict_sensitivity_eligible','prediction_source_hash']
    monthly=[{**{k:r.get(k) for k in public_fields if k in r},**({'Qobs':r['Qobs']} if local else {})} for r in paired]
    metrics=[r for r in self.data['P6D_STATION_YEAR_FAILURES.csv'] if r['gauge_id']==g and str(r['period'])==period and r['quality_tier']=='MAIN_DESCRIPTIVE']
    seasonal=[r for r in self.data['P6D_SEASONAL_AND_DRIFT.csv'] if r['gauge_id']==g and str(r['period'])==period]
    decomp=[r for r in self.data['P6D_PREDICTION_DECOMPOSITION.csv'] if r['gauge_id']==g and start<=r['date']<=end]
    intervals=[r for r in self.data['P6D_INTERVAL_AND_QC_DIAGNOSTICS.csv'] if r['gauge_id']==g and str(r['period'])==period and r['quality_tier']=='MAIN_DESCRIPTIVE' and r['subset']=='ALL']
    return 200,self.env(status='FROZEN_EVIDENCE_AVAILABLE' if paired else 'NOT_EVALUATED',reason=None if paired else 'NO_MATCHED_24_STATION_EXTERNAL_SUPPORT',station_uid=uid,scope=scope,records=monthly,metrics=metrics,metric_scope='FULL_FROZEN_PERIOD_NOT_RECOMPUTED_FOR_DATE_WINDOW',seasonal=seasonal,decomposition=decomp,intervals=intervals,Qobs_status='CONTROLLED_LOCAL_SELECTED_STATION_CHART_ONLY' if local else 'NOT_EXPORTED',monthly_record_count=len(monthly),source_hashes=self.pins,limitations=['NO_NEW_FIT_OR_SCORING_IN_WEBSITE','POSTHOC_DIAGNOSTICS_NOT_CAUSAL','NO_DAILY_QC_CERTIFICATION','PROVIDER_CALENDAR_DAY_UTC_NOT_CERTIFIED','NO_NEW_INTERVAL_CALIBRATION'])
   if leaf=='report':
    report=q.get('report','P6D');name={'P6B':'P6B_INDEPENDENT_VALIDATION_REPORT_ZH.md','P6C':'P6C_EXTERNAL_VALIDATION_REPORT_ZH.md','P6D':'P6D_RESEARCH_REPORT_ZH.md'}.get(report)
    p=next((pathlib.Path(p) for p in self.pins if pathlib.Path(p).name==name),None)
    if p is None:return 400,self.env(status='UNKNOWN_REPORT')
    return 200,self.env(report=report,content=p.read_text(encoding='utf-8-sig'),sha256=self.pins[str(p)],scope=scope)
   return 404,self.env(status='NOT_FOUND')
  except (KeyError,ValueError,TypeError) as e:return 400,self.env(status='INVALID_SELECTION',reason=str(e))
