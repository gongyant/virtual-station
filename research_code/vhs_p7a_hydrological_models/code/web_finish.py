"""Publish only this local candidate's immutable evidence pointers, never production flags."""
from common import *
status=readj(ROOT/'P7A_FINAL_STATUS.json');status['cv_train_max_date']=status['train_max_date'];status['final_train_max_date']='2017-12';status['training_label_cutoff']='2017-12';status['protocol_hash']=sha(ROOT/'P7A_FROZEN_PROTOCOL.json');status['research_model_registry_hash']=sha(ROOT/'P7A_MODEL_REGISTRY.json')
put(ROOT/'P7A_FINAL_STATUS.json',status);put(WEB/'research/P7A_SUMMARY.json',status)
contract=readj(WEB/'WEB_S1_DATA_CONTRACT.json');contract['source_pins'][str(WEB/'research/P7A_SUMMARY.json')]=sha(WEB/'research/P7A_SUMMARY.json');put(WEB/'WEB_S1_DATA_CONTRACT.json',contract);put(WEB/'evidence/WEB_SOURCE_PINS.json',contract['source_pins'])
rp=WEB/'host/r2_public.py';text=rp.read_text(encoding='utf-8')
old='next((x for x in raw["stations"] if x["gauge_id"]==g),{"gauge_id":g,"status":"NOT_RUN_NOT_IN_P6A_COHORT"})'
if 'self.s1.validation_status(g)' not in text:
 assert old in text
 text=text.replace(old,'(self.s1.validation_status(g) or '+old+')');rp.write_text(text,encoding='utf-8')
put(WEB/'evidence/INITIAL_ACCEPTANCE_FAILURES.json',{'resolved':[{'stage':'live HTTP acceptance','error':'IndexError due empty combined-period metrics','cause':'Python int accepted underscore period strings; 2018_2019 became20182019','fix':'period remains exact string; strict numeric grammar for other fields; full API regression passed'},{'stage':'UI review','error':'P7 sidebar inherited P6 P4-V2 source context','fix':'separate P7 protocol/model-registry provenance sidebar; global developmental evidence page'}],'no_source_results_changed':True})
put(ROOT/'evidence/RECOVERY_AND_ATTEMPTS.json',{'initial_CV_attempt':{'status':'FITS_AND_PREDICTIONS_COMPLETED_BOOKKEEPING_FAILED','reason':'self-output prediction hash read not in training-role allowlist','completed_fits':11210,'recovery':'summary-only; original predictions unchanged'},'initial_final_attempt':{'status':'FIRST_MODEL_COMPLETED_SELF_HASH_READ_FAILED','completed_model':'ID2 C0+PT','real_fits':16,'recovery':'reuse saved model and inner selection; original elapsed timings unavailable, explicitly marked'},'scoring_and_verification':'separate processes after prediction seal; fit_calls=0','automatic_review_interruption':'one final WEB copy/restart was not executed because approval service hit usage limit; resumed after explicit user continuation','all_real_fits_including_recovered':13082})
reg=readj(LAB/'vhs_web_r1_public_results_bridge/PUBLIC_MODEL_REGISTRY.json');ident=[]
for r in reg['models']:
 m=readj(pathlib.Path(r['artifact_path'])/'model.json')
 ident.append({'gauge_id':r['gauge_id'],'model_id':r['model_id'],'model_release_id':r['model_release_id'],'snapshot_id':r['source_snapshot_id'],'actual_train_start':m['actual_train_start'],'actual_train_end':m['actual_train_end'],'train_n':len(m['train_ids']),'P7A24cohort':r['gauge_id'] in GAUGES,'model_json_sha256':r['model_json_hash'],'units':str(r['source_units'])})
csvout(ROOT/'P7A_ORIGINAL_27_MODEL_IDENTITIES.csv',ident)
