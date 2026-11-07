"""Reconstruct frozen predictions and paired public observations, never fit."""
from p6d_common import *
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8');checks=[];fit_events=[];opened=[]
def ck(name,ok,detail=None):checks.append({'name':name,'pass':bool(ok),'detail':detail});assert ok,(name,detail)
def profile(frame,ev,arg):
 if ev=='call' and frame.f_code.co_name in {'fit','partial_fit','fit_transform','_fit','lstsq'}:fit_events.append(frame.f_code.co_name);raise RuntimeError('P6D_FITTING_FORBIDDEN')
def audit(ev,args):
 if ev=='open' and isinstance(args[0],(str,bytes)):
  p=str(args[0]);opened.append(p)
  if any(s in p.lower() for s in ['vhs_workbuddy','sealed_runoff','quarantine','syrdarya']):raise RuntimeError('TEACHER_OR_RESTRICTED_PATH_FORBIDDEN')
sys.setprofile(profile);sys.addaudithook(audit);sys.path.insert(0,str(P4/'code'));from inference import load_model
protocol=jl(R/'P6D_DIAGNOSTIC_PROTOCOL.json');ids=protocol['gauge_ids'];ab=jl(B/'P6B_ADMISSION_FROZEN.json');ac=jl(C/'P6C_ADMISSION_FROZEN.json');snap=jl(P4/'source/SNAPSHOT.json');predpaths=[B/'runs/P6B_EHYD_2018_2019/P6B_PREDICTIONS_WITHOUT_QOBS.csv',C/'runs/P6C_2020_PREDICTION/P6C_2020_PREDICTIONS.csv'];pred={};predsource={}
for p in predpaths:
 for r in cr(p):
  if int(r['gauge_id']) not in ids:continue
  key=(int(r['gauge_id']),r['date'],r['model_id']);ck('UNIQUE_'+str(key),key not in pred);pred[key]=r;predsource[key]=str(p)
ck('PREDICTION_COUNT',len(pred)==1728,len(pred));met=defaultdict(dict)
for p in [B/'driver/MET_ONLY_2018_2019.json',C/'driver/MET_ONLY_2019_12_2020.json']:
 for g,rr in jl(p).items():
  if int(g) not in ids:continue
  for r in rr:
   r={k:r[k] for k in ['gauge_id','date','P','T']}
   if r['date'] in met[int(g)]:ck('SHARED_MET_'+g+':'+r['date'],all(near(r[k],met[int(g)][r['date']][k]) for k in ['P','T']))
   met[int(g)][r['date']]=r
# Dedicated public eHYD label parsing; target values never enter model met inputs.
q={};qhash={};headers=[]
for g in ids:
 path=Path(ac['sources'][str(g)]);ck('PUBLIC_Q_SOURCE_'+str(g),str(path).startswith(str(B/'external')) and sha(path)==ac['source_hashes'][str(path)]);qhash[g]=sha(path);text=path.read_text(encoding='latin1');head,body=text.split('Werte:',1);ck('DAILY_M3S_'+str(g),',Abfluss,I,Mit,T,' in head and '[m³/s]' in head);days={};duplicate=set()
 for line in body.splitlines():
  if ';' not in line:continue
  dt,tok=line.split(';',1)
  try:date=datetime.strptime(dt.strip(),'%d.%m.%Y %H:%M:%S')
  except ValueError:continue
  if not 2018<=date.year<=2020:continue
  key=date.strftime('%Y-%m-%d')
  if key in days:duplicate.add(key)
  ck('MIDNIGHT_'+str(g)+key,date.hour==date.minute==date.second==0)
  v=float(tok.strip().replace(',','.'));ck('FINITE_Q_'+str(g)+key,math.isfinite(v) and v>=0);days[key]=v
 ck('DAILY_1096_'+str(g),len(days)==1096 and not duplicate)
 for y in [2018,2019,2020]:
  for mo in range(1,13):
   dt=f'{y}-{mo:02d}';nd=calendar.monthrange(y,mo)[1];q[g,dt]=sum(days[f'{dt}-{d:02d}'] for d in range(1,nd+1))/nd
trainfeatures={r['sample_id']:r for r in cr(P4/'source/features.csv') if int(r['gauge_id']) in ids};monthly=[];decomp=[];trainsummary=[];trainstat={};models=[];maxdiff=0.
for g in ids:
 qp=Path(snap['source_paths'][str(g)]['Q']);ck('TRAIN_Q_SOURCE_'+str(g),str(qp).startswith(str(L)) and sha(qp)==snap['source_files'][str(qp)]);dd=defaultdict(list)
 for row in cr(qp,';'):
  dt=f'{int(row["YYYY"]):04d}-{int(row["MM"]):02d}'
  if dt<='2017-12':dd[dt].append(row)
 trainq={}
 for dt,rr in dd.items():
  vals=[]
  for row in rr:
   try:v=float(row['qobs'])
   except ValueError:continue
   if math.isfinite(v) and v>=0 and row['ckhs']=='1':vals.append(v)
  n=calendar.monthrange(int(dt[:4]),int(dt[5:]))[1]
  if len(rr)==n and len({r['DD'] for r in rr})==n and len(vals)==n:trainq[f'LAMAH_CE_PUBLIC_V1:{g}:{dt}']=sum(vals)/n
 for mid in ['C0+PT','P2-L1']:
  folder=P4/'models/V2'/f'ID_{g}'/mid.replace('+','_');pin=next(p for p in protocol['models'] if p['gauge_id']==g and p['path']==str(folder));ck('MODEL_PIN_'+str(g)+mid,all(sha(folder/n)==h for n,h in pin['files'].items()));model=load_model(folder);a=model.arrays;mm=model.meta;models.append({'gauge_id':g,'model_id':mid,'model_hash':model.hash,'snapshot_id':mm['snapshot_id'],'fields':mm['fields'],'beta_standardized':a['beta'].tolist(),'selected_alpha':mm['parameters']['selection']['selected_alpha'],'train_cutoff':mm['train_cutoff'],'actual_train_end':mm['actual_train_end']});tids=mm['train_ids'];yy=[trainq[s] for s in tids];digest=hashlib.sha256(json.dumps({s:trainq[s] for s in tids},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest();ck('TRAIN_LABEL_HASH_'+str(g)+mid,digest==mm['train_label_hash']);ck('TRAIN_PERIOD_'+str(g)+mid,all(s[-7:]<='2017-12' for s in tids))
  ty=np.array(yy);nmonths=np.array([int(s[-2:]) for s in tids]);qsd=[]
  for mo in range(1,13):
   vv=ty[nmonths==mo];ck(f'TRAIN_CLIMATE_{g}_{mid}_{mo}',near(np.mean(vv),a['climate'][mo-1]));qsd.append(float(np.std(vv,ddof=1)))
  rawtrain={f:np.array([float(trainfeatures[s][f]) for s in tids]) for f in mm['fields']};trainstat[g,mid]={'n':len(yy),'mean':float(ty.mean()),'std':float(ty.std()),'qsd':qsd,'Pmean':float(rawtrain['P'].mean()),'Tmean':float(rawtrain['T'].mean()),'Pstd':float(rawtrain['P'].std()),'Tstd':float(rawtrain['T'].std())};trainsummary.append({'gauge_id':g,'model_id':mid,**{k:v for k,v in trainstat[g,mid].items() if k!='qsd'},'model_hash':model.hash,'train_label_hash':digest,'train_ids_hash':mm['train_ids_hash']})
  for y in [2018,2019,2020]:
   for mo in range(1,13):
    dt=f'{y}-{mo:02d}';row=pred[g,dt,mid];stored=float(row['q_hat_raw']);pp=model.predict_month(list(met[g].values()),y,mo);ck(f'LOAD_RECONSTRUCT_{g}_{dt}_{mid}',near(pp['q_hat_raw'],stored) and pp['input_hash']==row['input_hash'] and model.hash==row['model_hash']);i=mo-1;vals=[]
    for j,f in enumerate(mm['fields']):vals.append(float(met[g][previous(dt) if f=='L1' else dt]['P' if f=='L1' else f]))
    z=[0. if a['constant'][i,j] else (v-a['mu'][i,j])/a['sd'][i,j] for j,v in enumerate(vals)];con={f:float(zj*b) for f,zj,b in zip(mm['fields'],z,a['beta'])};base=float(a['climate'][i]);rebuilt=base+sum(con.values());err=abs(rebuilt-stored);maxdiff=max(maxdiff,err);ck(f'ADDITIVE_{g}_{dt}_{mid}',near(rebuilt,stored));obs=q[g,dt]
    dr={'gauge_id':g,'date':dt,'year':y,'month':mo,'model_id':mid,'seasonal_baseline':base,'P_contribution':con['P'],'T_contribution':con['T'],'L1_contribution':con.get('L1',0.),'other_contribution':0.,'qsim_raw':stored,'qsim_reconstructed':rebuilt,'reconstruction_abs_error':err,'nonnegative_clipping_correction':float(row['q_hat_nonnegative'])-stored,'model_hash':model.hash,'input_hash':row['input_hash'],'P_raw':vals[0],'T_raw':vals[1],'lag_P_raw':vals[2] if len(vals)>2 else float(met[g][previous(dt)]['P']),'lag_date':previous(dt),'support_class':row['support_class'],'max_abs_z':float(row['max_abs_z']),'leverage_ratio':float(row['leverage_ratio']),'train_Q_mean':trainstat[g,mid]['mean'],'train_Q_std':trainstat[g,mid]['std'],'train_Q_month_std':qsd[i],'train_P_mean':trainstat[g,mid]['Pmean'],'train_T_mean':trainstat[g,mid]['Tmean'],'train_P_std':trainstat[g,mid]['Pstd'],'train_T_std':trainstat[g,mid]['Tstd'],'source_prediction_file':predsource[g,dt,mid]}
    for j,f in enumerate(mm['fields']):dr.update({f'{f}_z':float(z[j]),f'{f}_mu_month':float(a['mu'][i,j]),f'{f}_sd_month':float(a['sd'][i,j]),f'{f}_beta_standardized':float(a['beta'][j]),f'{f}_effective_raw_slope':float(a['beta'][j]/a['sd'][i,j]) if not a['constant'][i,j] else 0.,f'{f}_constant':bool(a['constant'][i,j])})
    decomp.append(dr)
 for y in [2018,2019,2020]:
  accum=0.
  for mo in range(1,13):
   dt=f'{y}-{mo:02d}';pc=pred[g,dt,'C0+PT'];pl=pred[g,dt,'P2-L1'];obs=q[g,dt];qc=float(pc['q_hat_raw']);ql=float(pl['q_hat_raw']);ec,el=qc-obs,ql-obs;delta=ec**2-el**2;accum+=delta/12;dc=next(d for d in decomp if d['gauge_id']==g and d['date']==dt and d['model_id']=='C0+PT');dl=next(d for d in decomp if d['gauge_id']==g and d['date']==dt and d['model_id']=='P2-L1');dp=ql-qc;cross=-2*ec*dp;cost=-dp**2
   ck(f'DELTA_IDENTITY_{g}_{dt}',near(delta,cross+cost));monthly.append({'sample_id':f'LAMAH_CE_PUBLIC_V1:{g}:{dt}','gauge_id':g,'date':dt,'year':y,'month':mo,'Qobs':obs,'Qsim_C0PT':qc,'Qsim_L1':ql,'error_C0PT':ec,'error_L1':el,'SE_C0PT':ec**2,'SE_L1':el**2,'delta_SE_C0_minus_L1':delta,'delta_annual_MSE_contribution':delta/12,'cumulative_annual_MSE_improvement':accum,'prediction_change_L1_minus_C0':dp,'delta_SE_baseline_error_alignment':cross,'delta_SE_prediction_change_cost':cost,'delta_prediction_lag_term':dl['L1_contribution'],'delta_prediction_currentP_term':dl['P_contribution']-dc['P_contribution'],'delta_prediction_currentT_term':dl['T_contribution']-dc['T_contribution'],'delta_prediction_seasonal_term':dl['seasonal_baseline']-dc['seasonal_baseline'],'strict_sensitivity_eligible':pc['strict_sensitivity_eligible']=='True' and pl['strict_sensitivity_eligible']=='True','support_C0PT':pc['support_class'],'support_L1':pl['support_class'],'Q_source_hash':qhash[g],'prediction_source_hash':sha(Path(predsource[g,dt,'C0+PT'])),'public_local_Qobs_export_authorized_by_P6D_request':True})
ck('PAIRED_864',len(monthly)==864);ck('DECOMPOSITION_1728',len(decomp)==1728);ck('FIT_CALLS_ZERO',not fit_events);cw(R/'P6D_MONTHLY_PAIRED_ERRORS.csv',monthly);cw(R/'P6D_PREDICTION_DECOMPOSITION.csv',decomp);cw(R/'P6D_TRAINING_REFERENCE.csv',trainsummary);jw(R/'evidence/MODEL_PARAMETERS_READ_ONLY.json',models);jw(R/'P6D_EXTRACTION_CHECKS.json',{'passed':sum(c['pass'] for c in checks),'failed':sum(not c['pass'] for c in checks),'checks':checks,'fit_calls':len(fit_events),'max_prediction_reconstruction_abs_error':maxdiff});jw(R/'evidence/READ_AUDIT.json',{'opened_files':sorted(set(opened)),'teacher_Q_read':False,'fit_calls':len(fit_events),'Qobs_local_export':'explicit P6D instruction, public eHYD only'});event('EXTRACTION_COMPLETE',paired_months=len(monthly),reconstructed_predictions=len(decomp),fit_calls=0,max_abs_reconstruction_error=maxdiff);print('PAIRED',len(monthly),'DECOMP',len(decomp),'CHECKS',len(checks),'MAX_ERROR',maxdiff,'FIT0')
