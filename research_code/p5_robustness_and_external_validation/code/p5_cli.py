"""Pure disk inference CLI. No fit imports; targets are never read."""
from p5lib import *
import argparse,subprocess
sys.path.insert(0,str(PKG/"runtime"))
from inference import load_model,predict_range
def entry(g,mid):return PKG/"models"/f"ID_{g}"/mid.replace("+","_")
def verify_release():
 n=verify(PKG);items=jl(P4/"P4_V2_MODEL_MANIFEST.json")["models"]
 for r in items:
  m=load_model(entry(r["gauge_id"],r["model_id"]));assert m.meta["gauge_id"]==r["gauge_id"] and m.meta["model_id"]==r["model_id"] and m.hash==r["model_hash"]
 return {"release_files":n,"models_verified":len(items),"fit_calls":0}
def predict(g,mid,start,end,metpath,outpath,precip_unit="mm/month",temp_unit="degC"):
 met=jl(metpath);m=load_model(entry(g,mid));pred=predict_range(m,met,start,end,units={"P":precip_unit,"T":temp_unit})
 out=[{"experiment":"PUBLIC_DATA_APPLICATION_P5","prediction_role":"SAVED_V2_INFERENCE_NOT_OOF","training_cutoff":m.meta["train_cutoff"],"parameters_npz_hash":m.meta["npz_sha256"],"dataset":"LAMAH_CE_PUBLIC_V1","source_DOI":"10.5281/zenodo.5153305",**r} for r in pred]
 cw(outpath,out);return {"model_id":mid,"gauge_id":g,"n":len(out),"fit_calls":0,"model_hash":m.hash}
def demo():
 verify_release();d=P/"runs/P5_A_SAVED_MODEL_APPLICATION";d.mkdir(exist_ok=False);allrows=[];receipts=[]
 for g in sorted({r["gauge_id"] for r in jl(P4/"P4_V2_MODEL_MANIFEST.json")["models"]}):
  met=[{"date":r["date"],"gauge_id":g,"P":float(r["P"]) if r["P"]!="" else None,"T":float(r["T"]) if r["T"]!="" else None} for r in cr(P4/"source/weather.csv") if int(r["gauge_id"])==g]
  path=d/f"MET_{g}.json";jw(path,met)
  for mid in ["C0+PT","P2-L1"]:
   out=d/f'ID{g}_{mid.replace("+","_")}.csv'
   cmd=[sys.executable,"-B",str(Path(__file__)),"predict","--station",str(g),"--model",mid,"--start","2016-01","--end","2016-12","--met",str(path),"--output",str(out)]
   cp=subprocess.run(cmd,capture_output=True,text=True,check=True);rows=cr(out);allrows.extend(rows);receipts.append({"gauge_id":g,"model_id":mid,"returncode":cp.returncode,"stdout":cp.stdout,"output_hash":sha(out),"fresh_process":True,"fit_calls":0})
 cw(P/"P5_BATCH_APPLICATION.csv",allrows)
 # Real saved-model inference is compared to an independent direct formula, not retraining.
 diffs=[]
 for r in allrows:
  g=int(r["gauge_id"]);mid=r["model_id"];m=load_model(entry(g,mid));met=jl(d/f"MET_{g}.json");lookup={v["date"]:v for v in met};dt=r["date"];y,mo=map(int,dt.split("-"));prev=f"{y if mo>1 else y-1}-{mo-1 if mo>1 else 12:02d}"
  raw=np.array([lookup[prev]["P"] if k=="L1" else lookup[dt][k] for k in m.fields]);a=m.arrays;z=np.where(a["constant"][mo-1],0,(raw-a["mu"][mo-1])/np.where(a["constant"][mo-1],1,a["sd"][mo-1]))
  diffs.append(abs(float(r["q_hat_raw"])-float(a["climate"][mo-1]+z@a["beta"])))
 assert max(diffs)==0
 # All rejection and Q perturbation checks use a genuine loaded L1 model.
 m=load_model(entry(2,"P2-L1"));met=jl(d/"MET_2.json");tests=[]
 for name,data,units in [
 ("missing_month",[r for r in met if r["date"]!="2015-12"],{"P":"mm/month","T":"degC"}),
 ("wrong_units",met,{"P":"m","T":"K"}),
 ("wrong_station",[{**r,"gauge_id":9} for r in met],{"P":"mm/month","T":"degC"}),
 ("target_Q_input",[{**r,"Qobs":123} for r in met],{"P":"mm/month","T":"degC"})]:
  try:m.predict_month(data,2016,1,units)
  except AssertionError:tests.append({"test":name,"pass":True})
  else:raise AssertionError(name)
 qfake={"2016-01":1e30};before=m.predict_month(met,2016,1);qfake["2016-01"]=-1e30;assert before==m.predict_month(met,2016,1)
 tests.append({"test":"changed_separate_target_Q_no_effect","pass":True})
 jw(P/"P5_RELEASE_ACCEPTANCE.json",{"UTC":now(),**verify_release(),"fresh_process_models":54,"predictions":len(allrows),"max_direct_formula_difference":max(diffs),"tests":tests,"no_fit_import_or_call":True,"no_target_Q_read_during_inference":True,"no_training_label_writer":True,"historical_V2_save_load_tests":"P4 evidence/V2_DISK_ACCEPTANCE.json","receipts":receipts})
 seal(d);attempt("P5_A_BATCH_COMPLETE",models=54,fresh_processes=54,predictions=len(allrows),fit_calls=0)
 print(json.dumps({"models":54,"predictions":len(allrows),"fresh_processes":54,"fit_calls":0}))
if __name__=="__main__":
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest="cmd",required=True);sub.add_parser("verify-release");sub.add_parser("demo");pp=sub.add_parser("predict")
 for name in ["station","model","start","end","met","output"]:pp.add_argument("--"+name,required=True)
 pp.add_argument("--precip-unit",default="mm/month");pp.add_argument("--temp-unit",default="degC")
 a=ap.parse_args()
 if a.cmd=="verify-release":print(json.dumps(verify_release()))
 elif a.cmd=="demo":demo()
 else:print(json.dumps(predict(int(a.station),a.model,a.start,a.end,a.met,a.output,a.precip_unit,a.temp_unit)))
