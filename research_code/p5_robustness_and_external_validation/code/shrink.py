"""Strict forward temporal development experiment. No2015-2017 target access."""
from p5lib import *
sys.path.insert(0,str(R/"code/vendor_public"));sys.path.insert(0,str(P2/"P2_MODEL_CODE"));sys.path.insert(0,str(P/"code"))
import public_runtime as rt
import models as mathmodels
from models import Inputs,MonthlyWeatherRidge
from collections import defaultdict
import time,traceback
pro=jl(P/"P5_SHRINK_PROTOCOL.json");alllabels=labels("2014-12")
features=[]
for r in cr(P4/"source/features.csv"):
 features.append({k:(int(v) if k in ["gauge_id","year","month"] else float(v) if k in ["P","T","L1"] else v) for k,v in r.items()})
fm={r["sample_id"]:r for r in features};snapshot="lamah-public-p5-"+digest({"protocol":sha(P/"P5_SHRINK_PROTOCOL.json"),"feature":sha(P4/"source/features.csv")})[:20]
run=P/"runs/P5_SHRINK_BLOCKED_V1";run.mkdir(exist_ok=False)
def xof(ids):
 rr=[fm[i] for i in ids];return Inputs(tuple(ids),np.array([r["year"] for r in rr]),np.array([r["month"] for r in rr]),{k:np.array([r[k] for r in rr]) for k in ["P","T","L1"]},snapshot)
def fitpair(g,cutoff,testids,kind):
 train=sorted(i for i in alllabels if i in fm and fm[i]["gauge_id"]==g and i[-7:]<=cutoff)
 assert not set(train)&set(testids)
 rt.register(features,{i:alllabels[i] for i in train},snapshot,cutoff);rt.set_outer_train(train)
 out={};records=[]
 for mid in ["C0+PT","P2-L1"]:
  mathmodels.FIT_CONTEXT.clear();mathmodels.FIT_CONTEXT.update(gauge_id=g,cutoff=cutoff,kind=kind)
  start=time.perf_counter();m=MonthlyWeatherRidge(mid).fit(xof(train),rt.read_training(train));pred=m.predict(xof(testids))
  out[mid]=pred;records.append({"gauge_id":g,"kind":kind,"train_ids":train,"test_ids":testids,"cutoff":cutoff,"fit_seconds":time.perf_counter()-start,**m.record()})
 return out,records
predrows=[];selections=[];parameters=[];outer=inner=0
attempt("SHRINK_TRAIN_START",protocol_hash=sha(P/"P5_SHRINK_PROTOCOL.json"))
try:
 for g in pro["all_stations"]:
  mathmodels.FIT_EVENTS.clear()
  for fold in pro["outer"]:
   c=int(fold["train_end"][:4]);innerloss={w:[] for w in pro["weights"]};evidence=[]
   for trainyear,valfirst,vallast in [(c-6,c-5,c-3),(c-3,c-2,c)]:
    ids=sorted(i for i in alllabels if i in fm and fm[i]["gauge_id"]==g and f"{valfirst}-01"<=i[-7:]<=f"{vallast}-12")
    raw,rec=fitpair(g,f"{trainyear}-12",ids,"INNER_FORWARD_WEIGHT_SELECTION");parameters.extend(rec)
    # Legal training-window validation labels are joined after inner predictions.
    y=np.array([alllabels[i] for i in ids])
    for w in pro["weights"]:innerloss[w].append(float(np.mean((raw["C0+PT"]+w*(raw["P2-L1"]-raw["C0+PT"])-y)**2)))
    evidence.append({"inner_train_cutoff":f"{trainyear}-12","validation_ids":ids,"outer_Q_unavailable":True})
   means={w:float(np.mean(v)) for w,v in innerloss.items()};ses={w:float(np.std(v,ddof=1)/np.sqrt(len(v))) for w,v in innerloss.items()}
   best=min(pro["weights"],key=lambda w:(means[w],w));threshold=means[best]+ses[best];w=min(w for w in pro["weights"] if means[w]<=threshold+1e-12*max(1,abs(threshold)))
   selections.append({"gauge_id":g,"outer_train_cutoff":fold["train_end"],"outer_test_start":fold["test_start"],"selected_weight":w,"minimum_loss_weight":best,"oneSE_cutoff":threshold,"mean_MSE":means,"SE":ses,"inner_block_MSE":innerloss,"evidence":evidence})
   ids=sorted(i for i in alllabels if i in fm and fm[i]["gauge_id"]==g and fold["test_start"]<=i[-7:]<=fold["test_end"])
   raw,rec=fitpair(g,fold["train_end"],ids,"OUTER_FORWARD_DEVELOPMENT");parameters.extend(rec)
   for mid,values in [("C0+PT",raw["C0+PT"]),("P2-L1",raw["P2-L1"]),("P5-L1-SHRINK",raw["C0+PT"]+w*(raw["P2-L1"]-raw["C0+PT"]))]:
    for i,v in zip(ids,values):
     predrows.append({"label":"PUBLIC_DATA_EXPLORATORY_P5","validation":"DEVELOPMENT_BLOCKED_VALIDATION","gauge_id":g,"sample_id":i,"date":i[-7:],"outer_train_cutoff":fold["train_end"],"test_start":fold["test_start"],"model_id":mid,"selected_w":w if mid=="P5-L1-SHRINK" else None,"Qsim_raw":float(v),"Qsim_nonnegative":max(float(v),0)})
  outer+=sum(e["level"]=="outer" for e in mathmodels.FIT_EVENTS);inner+=sum(e["level"]=="inner" for e in mathmodels.FIT_EVENTS)
  with (run/"fit_events.jsonl").open("a",encoding="utf-8") as f:
   for e in mathmodels.FIT_EVENTS:f.write(json.dumps(e)+"\n")
  print(json.dumps({"gauge_id":g,"outer_fits":outer,"inner_fits":inner,"predictions":len(predrows)}),flush=True)
 bundle=run/"prediction_bundle";bundle.mkdir();cw(bundle/"PREDICTIONS_WITHOUT_QOBS.csv",predrows);jw(bundle/"WEIGHT_SELECTION.json",selections);jw(bundle/"MODEL_PARAMETERS.json",parameters);jw(bundle/"COMMITMENT.json",{"UTC":now(),"outer_score_labels_joined":False,"predictions":len(predrows),"Q2015_2017_access":False});seal(bundle)
 # No scoring/selection until prediction and chosen weights committed.
 groups={r["gauge_id"]:r["macro"] for r in jl(P4/"P4_TEST_SPLIT_FROZEN.json")["splits"]}
 results=[];yearly=[];comparison=[]
 for g in pro["all_stations"]:
  rr=[r for r in predrows if r["gauge_id"]==g]
  for start in ["ALL"]+[f["test_start"] for f in pro["outer"]]:
   subset=[r for r in rr if start=="ALL" or r["test_start"]==start];met={}
   for mid in ["C0+PT","P2-L1","P5-L1-SHRINK"]:
    rows=[r for r in subset if r["model_id"]==mid];y=[alllabels[r["sample_id"]] for r in rows];pv=[r["Qsim_raw"] for r in rows]
    out=metric(y,pv);met[mid]=out
    results.append({"gauge_id":g,"macro":groups[g],"outer_test_start":start,"model_id":mid,"validation":"DEVELOPMENT_BLOCKED_VALIDATION",**out})
   for mid in ["P2-L1","P5-L1-SHRINK"]:
    comparison.append({"gauge_id":g,"macro":groups[g],"outer_test_start":start,"candidate":mid,"skill_vs_C0PT":1-met[mid]["MSE"]/met["C0+PT"]["MSE"],"skill_vs_L1":1-met[mid]["MSE"]/met["P2-L1"]["MSE"],"n":met[mid]["n"]})
  for year in range(1995,2015):
   for mid in ["C0+PT","P2-L1","P5-L1-SHRINK"]:
    rows=[r for r in rr if r["model_id"]==mid and r["date"].startswith(str(year))]
    if rows:yearly.append({"gauge_id":g,"year":year,"model_id":mid,**metric([alllabels[r["sample_id"]] for r in rows],[r["Qsim_raw"] for r in rows])})
 cw(P/"P5_SHRINK_INTERNAL_RESULTS.csv",results);cw(P/"P5_SHRINK_COMPARISON.csv",comparison);cw(P/"P5_SHRINK_YEARLY_RESULTS.csv",yearly)
 jw(run/"MANIFEST.json",{"snapshot":snapshot,"base_model_outer_fits":outer,"inner_alpha_fits":inner,"shrink_weight_selections":len(selections),"prediction_records":len(predrows),"unique_target_months":len({r["sample_id"] for r in predrows}),"teacher_access":False,"Q2015_2017_for_selection":False,"protocol_hash":sha(P/"P5_SHRINK_PROTOCOL.json"),"external_test":False})
 seal(run);attempt("SHRINK_COMPLETE",outer_fits=outer,inner_alpha_fits=inner,predictions=len(predrows))
 print(json.dumps({"complete":True,"outer_fits":outer,"inner_fits":inner,"predictions":len(predrows)}))
except Exception as e:attempt("SHRINK_FAILED",error=repr(e),traceback=traceback.format_exc());raise
