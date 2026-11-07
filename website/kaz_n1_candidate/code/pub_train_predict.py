"""Spatial CV: each current heldout task forbids its target Q; no test Q is read."""
from intake import *
import numpy as np,sys,time
from pyproj import Geod
METHODS=['DONOR_CLIMATOLOGY_BASELINE','GEOGRAPHIC_DONOR_TRANSFER','STATIC_CLIMATE_SIMILARITY_TRANSFER','REGIONAL_SHARED_RIDGE']
ALLOWED_LABELS=set();READS=set();DENIED=[];FIT_LOG=[]
def install_guard():
 def hook(event,args):
  if event!='open' or not isinstance(args[0],(str,bytes)):return
  s=str(pathlib.Path(args[0]).resolve());mode=args[1] or ''
  if not isinstance(mode,str) or ('r' not in mode and mode!=''):return
  if 'vhs_workbuddy' in s.lower():raise PermissionError('TEACHER_FORBIDDEN')
  if str(LAB) not in s:return
  allowed_files=[ROOT/'pub/cache/FEATURES_WITHOUT_Q.json',ROOT/'pub/cache/STATIC_METADATA_WITHOUT_Q.json',ROOT/'pub/cache/GAUGE_HIERARCHY_WITHOUT_Q.json',ROOT/'KAZ_N1_FROZEN_PROTOCOL.json',ROOT/'evidence/PROTOCOL_FREEZE.json',ROOT/'KAZ_N1_UG_PREDICTIONS.csv']
  if s in ALLOWED_LABELS or s in {str(p) for p in allowed_files} or s.startswith(str(ROOT/'code')):READS.add(s);return
  if s.startswith(str(ROOT/'pub/models')) or s.startswith(str(ROOT/'pub/PREDICTIONS')):READS.add(s);return
  DENIED.append(s);raise PermissionError('PUB_ROLE_FORBIDS_HELDOUT_OR_FUTURE_Q: '+s)
 sys.addaudithook(hook)
def ridge_fit(X,y,months,weights=None):
 w=np.ones(len(y)) if weights is None else weights;cl=[];xm=[]
 for m in range(1,13):
  ix=months==m;assert sum(ix)>=3;cl.append(float(np.average(y[ix],weights=w[ix])));xm.append(np.average(X[ix],weights=w[ix],axis=0))
 cl=np.array(cl);xm=np.array(xm);Z=X-xm[months-1];v=y-cl[months-1];sw=np.sqrt(w)
 beta=np.linalg.lstsq(np.vstack([Z*sw[:,None],np.sqrt(100)*np.eye(X.shape[1])]),np.r_[v*sw,np.zeros(X.shape[1])],rcond=None)[0]
 return {'climate_specific_mm_day':cl.tolist(),'X_train_month_mean':xm.tolist(),'beta':beta.tolist(),'alpha':100,'coefficient_count':len(beta),'month_intercepts_unpenalized':12}
def predict(model,X,months,area):return (np.array(model['climate_specific_mm_day'])[months-1]+(X-np.array(model['X_train_month_mean'])[months-1])@np.array(model['beta']))*area/86.4
def regression_features(fs,static,smu,ssd):
 ss=(np.array(static['similarity_vector'][:2])-smu)/ssd;out=[]
 for r in fs:
  sin=np.sin(2*np.pi*r['month']/12);cos=np.cos(2*np.pi*r['month']/12);out.append(r['z']+ss.tolist()+(ss*sin).tolist()+(ss*cos).tolist())
 return np.array(out)
def main():
 if (ROOT/'pub/PREDICTIONS_SEALED.json').exists():raise FileExistsError('SEALED_PUB_PREDICTIONS_EXIST: use a new experiment root, never refit this run')
 install_guard();p=readj(ROOT/'KAZ_N1_FROZEN_PROTOCOL.json');assert sha(ROOT/'KAZ_N1_FROZEN_PROTOCOL.json')==readj(ROOT/'evidence/PROTOCOL_FREEZE.json')['sha256']
 features=readj(ROOT/'pub/cache/FEATURES_WITHOUT_Q.json');static=readj(ROOT/'pub/cache/STATIC_METADATA_WITHOUT_Q.json');hier=readj(ROOT/'pub/cache/GAUGE_HIERARCHY_WITHOUT_Q.json');gauges=p['PUB']['stations']
 down={int(r['ID']):int(r['NEXTDOWNID']) for r in hier if str(r['NEXTDOWNID']).isdigit() and int(r['NEXTDOWNID'])>0}
 def descendants(g):
  seen=set();cur=g
  while cur in down and down[cur] not in seen:cur=down[cur];seen.add(cur)
  return seen
 desc={g:descendants(g) for g in gauges};preds=[];audit=[];gdist=Geod(ellps='WGS84');start=time.perf_counter()
 for scheme in p['PUB']['schemes']:
  for target in gauges:
   removed=[g for g in gauges if g==target or (g in desc[target] or target in desc[g]) or (scheme=='LEAVE_MACRO_REGION_OUT' and static[str(g)]['macro']==static[str(target)]['macro'])]
   donors=[g for g in gauges if g not in removed];assert len(donors)>=2
   ALLOWED_LABELS.clear();ALLOWED_LABELS.update(str(ROOT/f'pub/cache/train/ID_{g}.json') for g in donors)
   for denied in [ROOT/f'pub/cache/train/ID_{target}.json',ROOT/f'pub/cache/score/ID_{target}.json']:
    try:readj(denied);raise AssertionError('Guard failed')
    except PermissionError:pass
   labels={g:readj(ROOT/f'pub/cache/train/ID_{g}.json') for g in donors};assert all(date<='2013-12' for ll in labels.values() for date in ll)
   tref=static[str(target)];nearest=min(donors,key=lambda g:(gdist.inv(tref['lon'],tref['lat'],static[str(g)]['lon'],static[str(g)]['lat'])[2],g))
   sv=np.array([static[str(g)]['similarity_vector'] for g in donors]);mu=sv.mean(0);sd=sv.std(0,ddof=1);sd=np.where(sd>1e-12,sd,1);targetsv=np.array(tref['similarity_vector']);similar=min(donors,key=lambda g:(float(np.sum(((np.array(static[str(g)]['similarity_vector'])-targetsv)/sd)**2)),g))
   test=[r for r in features[str(target)] if 2014<=r['year']<=2017];months=np.array([r['month'] for r in test]);assert len(test)==48
   donor_models={};climates=[];Xpool=[];ypool=[];mpool=[];weights=[]
   smu=sv[:,:2].mean(0);ssd=np.where(sv[:,:2].std(0,ddof=1)>1e-12,sv[:,:2].std(0,ddof=1),1)
   for donor in donors:
    fs=[r for r in features[str(donor)] if r['date'] in labels[donor]];y=np.array([labels[donor][r['date']]*86.4/static[str(donor)]['area_km2'] for r in fs]);mm=np.array([r['month'] for r in fs]);climates.append([float(y[mm==m].mean()) for m in range(1,13)])
    if donor in [nearest,similar]:
     model=ridge_fit(np.array([r['z'] for r in fs]),y,mm);donor_models[donor]=model;FIT_LOG.append({'scheme':scheme,'target':target,'fit':'DONOR_RIDGE','donor':donor,'n':len(y),'target_in_train':False,'max_Q_date':max(labels[donor]),'beta_n':3})
    Xpool.extend(regression_features(fs,static[str(donor)],smu,ssd));ypool.extend(y);mpool.extend(mm);weights.extend([1/len(y)]*len(y))
   ww=np.array(weights);ww*=len(ww)/ww.sum();regional=ridge_fit(np.array(Xpool),np.array(ypool),np.array(mpool),ww);FIT_LOG.append({'scheme':scheme,'target':target,'fit':'REGIONAL_SHARED_RIDGE','donor':';'.join(map(str,donors)),'n':len(ypool),'target_in_train':False,'max_Q_date':'2013-12','beta_n':9})
   raw={'DONOR_CLIMATOLOGY_BASELINE':np.array(climates).mean(0)[months-1]*tref['area_km2']/86.4,'GEOGRAPHIC_DONOR_TRANSFER':predict(donor_models[nearest],np.array([r['z'] for r in test]),months,tref['area_km2']),'STATIC_CLIMATE_SIMILARITY_TRANSFER':predict(donor_models[similar],np.array([r['z'] for r in test]),months,tref['area_km2']),'REGIONAL_SHARED_RIDGE':predict(regional,regression_features(test,tref,smu,ssd),months,tref['area_km2'])}
   modelrecord={'scheme':scheme,'heldout_target':target,'removed_Q_stations_all_dates':removed,'allowed_Q_donors':donors,'nearest_donor':nearest,'similar_donor':similar,'donor_models':donor_models,'regional':regional,'donor_climate_baseline_specific':np.array(climates).mean(0).tolist(),'donor_static_mean':smu.tolist(),'donor_static_sd':ssd.tolist(),'all_model_Q_dates_max':'2013-12','target_met_normalization':'1983-2013 exogenous met only','target_Q_template_or_fitted_parameter':False}
   folder=ROOT/f'pub/models/{scheme}/ID_{target}';put(folder/'model.json',modelrecord);ph=sha(folder/'model.json')
   for model,pp in raw.items():
    for r,z in zip(test,pp):preds.append({'experiment':'EUROPEAN_PUB_DEVELOPMENT','dataset_id':'LAMAH_CE_PUBLIC_V1','scheme':scheme,'gauge_id':target,'macro':tref['macro'],'date':r['date'],'year':r['year'],'month':r['month'],'model_id':model,'qsim_raw':float(z),'qsim_nonnegative':max(float(z),0),'model_hash':ph,'prediction_kind':'SPATIALLY_HELDOUT_AND_LATER_BLOCK_DEVELOPMENT_NOT_KAZAKHSTAN','Qobs':None})
   audit.append({'scheme':scheme,'target':target,'removed_all_Q_station_ids':removed,'allowed_Q_station_ids':donors,'target_all_Q_excluded':target not in donors,'same_macro_Q_excluded':all(static[str(g)]['macro']!=tref['macro'] for g in donors) if scheme=='LEAVE_MACRO_REGION_OUT' else None,'all_nested_donors_excluded':all(g not in desc[target] and target not in desc[g] for g in donors),'target_Q_file_open_denied':True,'future_score_Q_open_denied':True,'fit_Q_max_date':'2013-12','target_met_fields_only':['P','T','L1']})
   print('PUB',scheme,target,'donors',len(donors),'nearest',nearest,'similar',similar,flush=True)
 assert len(preds)==24*2*4*48
 csvout(ROOT/'KAZ_N1_UG_PREDICTIONS.csv',preds);csvout(ROOT/'pub/FIT_CALLS.csv',FIT_LOG);put(ROOT/'pub/TARGET_MASK_AUDIT.json',audit)
 put(ROOT/'pub/PREDICTIONS_SEALED.json',{'sha256':sha(ROOT/'KAZ_N1_UG_PREDICTIONS.csv'),'n':len(preds),'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fit_calls':len(FIT_LOG),'climatology_baseline_fits':48,'target_Q_reads':0,'test_period_Q_reads':0,'read_files':sorted(READS),'intentional_guard_rejections':len(DENIED),'classification':'EUROPEAN_PUB_DEVELOPMENT_NOT_KAZ_ACCURACY','elapsed_s':time.perf_counter()-start})
 print('SEALED EUROPEAN PUB',len(preds),'predictions;',len(FIT_LOG),'regression fits',flush=True)
if __name__=='__main__':main()
