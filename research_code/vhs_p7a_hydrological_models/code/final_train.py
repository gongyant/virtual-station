"""Only globally admitted candidates + matched-support baselines. <=2017 Q only."""
from engine import *
def main_final():
 if (ROOT/'SHA256SUMS.txt').exists():raise FileExistsError('FROZEN_P7A_NO_REFIT_OR_OVERWRITE')
 install_training_read_boundary();p=readj(ROOT/'P7A_FROZEN_PROTOCOL.json');f=readj(ROOT/'evidence/FREEZE.json')
 assert sha(ROOT/'P7A_FROZEN_PROTOCOL.json')==f['protocol_hash']
 assert sha(ROOT/'cache/TRAINING_ONLY_2017.json')==p['training_cache_sha256']
 decisions=readj(ROOT/'P7A_PROMOTION_DECISION.json');candidates=[m for m,d in decisions.items() if d['promoted']]
 if not candidates:print('NO_CANDIDATE_PROMOTED');return
 assert candidates==['P7-MEM'],'Only predeclared admitted model supported'
 data=readj(ROOT/'cache/TRAINING_ONLY_2017.json');registry=[]
 for g in GAUGES:
  train=data[str(g)]
  for model in ['C0+PT','P2-L1']+candidates:
   folder=ROOT/f'models/ID_{g}/{model.replace("+","_")}'
   if (folder/'model.json').exists() and (folder/'inner_selection.json').exists():
    record=readj(folder/'model.json');trace=readj(folder/'inner_selection.json');selected=trace['selection']
    assert record['training_cache_hash']==p['training_cache_sha256'] and record['protocol_hash']==f['protocol_hash']
    # One model completed before self-output hash read was refused. Recover it, no refit.
    for choice in trace['candidates']:
     for cutoff in [2011,2013,2015]:FIT_LOG.append({'gauge_id':g,'model_id':model,'level':'inner','inner_cutoff':cutoff,'alpha':choice['alpha'],'rho':choice['rho'],'train_max_date':f'{cutoff}-12','recovered_completed_fit':'saved selection trace, initial self-hash-read failure; timing unavailable'})
    FIT_LOG.append({'gauge_id':g,'model_id':model,'level':'final','alpha':selected['alpha'],'rho':selected['rho'],'train_max_date':'2017-12','recovered_completed_fit':'saved model; no repeat fit'})
   else:
    selected,trace=tune(model,train,2017,{'gauge_id':g,'level':'final_inner'})
    # predict on own feature matrix only to exercise serialization, never call this evaluation.
    _,record=fit_predict(model,train,train,selected['alpha'],selected['rho'] or .25,{'gauge_id':g,'level':'final'})
    put(folder/'model.json',{**record,'gauge_id':g,'train_start':train[0]['date'],'train_end':train[-1]['date'],'train_cutoff':'2017-12','training_cache_hash':p['training_cache_sha256'],'protocol_hash':f['protocol_hash'],'classification':'P7A_RESEARCH_CANDIDATE_NOT_RELEASED','default_model':False,'input_units':{'P':'mm/month','T':'degC'},'memory_warmup':24 if model=='P7-MEM' else None})
    put(folder/'inner_selection.json',trace)
   registry.append({'gauge_id':g,'model_id':model,'model_path':str(folder/'model.json'),'sha256':sha(folder/'model.json'),'alpha':selected['alpha'],'rho':selected['rho'],'training_months':len(train),'train_cutoff':'2017-12','status':'RESEARCH_ONLY_NO_PRODUCTION_REPLACEMENT'})
  print('final training ID',g,flush=True)
 csvout(ROOT/'evidence/FINAL_FIT_CALLS.csv',FIT_LOG);put(ROOT/'P7A_MODEL_REGISTRY.json',{'old_references':'P7A_REFERENCE_MODEL_REGISTRY.json','research_models':registry,'published_default':'P2-L1_UNCHANGED','created_utc':utc()})
 put(ROOT/'evidence/FINAL_MODELS_SEALED.json',{'models':registry,'fit_calls':len(FIT_LOG),'final_fits':sum(x['level']=='final' for x in FIT_LOG),'inner_fits':sum(x['level']=='inner' for x in FIT_LOG),'label_max_date':'2017-12','future_Q_reads':0,'opened_public_files':sorted(AUDIT_READS),'created_utc':utc()})
if __name__=='__main__':main_final()
