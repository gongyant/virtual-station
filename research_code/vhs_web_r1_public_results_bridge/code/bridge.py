"""Public result adapter; explicit snapshot keys, no observation reader or model fitter."""
from core import *
class Refused(Exception):
 def __init__(self,status,code):self.status=status;self.code=code
class PublicResultsBridge:
 def __init__(self):
  self.bundle=jl(BASE/"data/bundle.json");self.registry=self.bundle["registry"];self.geo=jl(BASE/"SPATIAL_STATION_RESULTS.geojson");self.prov=jl(BASE/"RESULT_PROVENANCE.json")
  self.releases={}
  for kind,key in [("TEMPORAL_HOLDOUT","evaluation_models"),("FINAL_MODEL_APPLICATION","models"),("MASKED_GAP_EVALUATION","masked_evaluation_models")]:
   values=self.registry[key];self.releases[kind]={"source_snapshot_id":values[0]["source_snapshot_id"],"model_release_id":values[0]["model_release_id"],"model_version":values[0]["model_version"]}
  self.pin=sha(BASE/"data/bundle.json")
 def validate_sources(self):
  if sha(BASE/"data/bundle.json")!=self.pin:raise Refused(409,"SOURCE_DATA_MISMATCH")
  for r in self.prov["sources"]:
   try: valid=sha(r["path"])==r["sha256"]
   except OSError:valid=False
   if not valid:raise Refused(409,"SOURCE_DATA_MISMATCH")
 def scope(self,q,station=False):
  self.validate_sources()
  if q.get("dataset")!=DS:
   raise Refused(403 if q.get("dataset")=="SYRDARYA" else 409,"DATASET_NOT_AUTHORIZED" if q.get("dataset")=="SYRDARYA" else "SOURCE_DATA_MISMATCH")
  kind=q.get("kind","TEMPORAL_HOLDOUT")
  if kind not in self.releases:raise Refused(400,"PREDICTION_KIND_NOT_AVAILABLE")
  if q.get("snapshot")!=self.releases[kind]["source_snapshot_id"]:raise Refused(409,"SOURCE_DATA_MISMATCH")
  uid=q.get("station")
  if station and uid not in {r["station_uid"] for r in self.bundle["stations"]}:raise Refused(400,"STATION_DATASET_MISMATCH")
  if uid is not None and uid not in {r["station_uid"] for r in self.bundle["stations"]}:raise Refused(400,"STATION_DATASET_MISMATCH")
  model=q.get("model","P2-L1")
  if model not in ["C0+PT","P2-L1"]:raise Refused(400,"MODEL_NOT_RELEASED")
  return kind,uid,model
 def envelope(self,**obj):return {"dataset_id":DS,"preview_only":True,"production_display_permission":"NOT_GRANTED","model_execution":"MODEL_EXECUTION_NOT_AUTHORIZED","notice":NOTICE,**obj}
 def catalog(self):
  return self.envelope(counts=self.bundle["counts"],stations=self.bundle["stations"],releases=self.releases,models=[{k:m[k] for k in ["station_uid","gauge_id","model_id","model_version","training_cutoff","model_release_id","source_snapshot_id","model_hash","parameters_hash"]} for m in self.registry["models"]],reports=self.bundle["reports"],true_gap_status="NO_ELIGIBLE_TRUE_GAPS",reach_status="REACH_PREDICTION_NOT_AVAILABLE")
 def results(self,q):
  kind,uid,model=self.scope(q,True)
  rr=[r for r in self.bundle["predictions"] if r["prediction_kind"]==kind and r["station_uid"]==uid and r["model_id"]==model]
  return self.envelope(status="GAUGE_PREDICTION_AVAILABLE" if rr else "NO_RESULTS_FOR_SELECTION",prediction_kind=kind,scope=self.releases[kind],station=uid,model_id=model,records=rr,qobs=None,qobs_status="NOT_EXPORTED",evaluation_eligible=kind!="FINAL_MODEL_APPLICATION",reach_id=None,geometry=None,reach_status="REACH_PREDICTION_NOT_AVAILABLE")
 def evaluation(self,q):
  kind,uid,model=self.scope(q)
  if kind!="TEMPORAL_HOLDOUT":raise Refused(409,"APPLICATION_NOT_INDEPENDENT_EVALUATION")
  metrics=[r for r in self.bundle["evaluation"] if r["model_id"]==model and (uid is None or r["station_uid"]==uid)]
  if uid and not metrics:return self.envelope(status="NOT_EVALUATED",reason="NO_ELIGIBLE_TEST_SUPPORT",station=uid,metrics={k:None for k in ["NSE","KGE","RMSE","MAE","PBIAS"]},records=[],yearly=[],coverage=[])
  rows=list(metrics)
  if uid is None:
   for station in self.bundle["stations"]:
    if station["evaluation_status"]=="NOT_EVALUATED":rows.append({"dataset_id":DS,"station_uid":station["station_uid"],"gauge_id":station["gauge_id"],"model_id":model,"evaluation_status":"NOT_EVALUATED","reason":"NO_ELIGIBLE_TEST_SUPPORT","n_months":None,**{k:None for k in ["NSE","KGE","RMSE","MAE","PBIAS"]}})
  return self.envelope(status="GAUGE_EVALUATION_AVAILABLE",prediction_kind=kind,scope=self.releases[kind],records=rows,yearly=[r for r in self.bundle["yearly"] if r["model_id"]==model and (uid is None or f'{DS}:{r["gauge_id"]}'==uid)],coverage=[r for r in self.bundle["coverage"] if r["model_id"]==model and (uid is None or f'{DS}:{r["gauge_id"]}'==uid)])
 def spatial(self,q):
  kind,uid,model=self.scope(q);dt=q.get("date","2016-01")
  if len(dt)!=7 or not dt[:4].isdigit() or not dt[5:].isdigit() or not 1<=int(dt[5:])<=12:raise Refused(400,"BAD_DATE")
  features=[]
  for f in self.geo["features"]:
   props=dict(f["properties"]);g=props["gauge_id"]
   selected=[r for r in self.bundle["predictions"] if r["prediction_kind"]==kind and r["gauge_id"]==g and r["model_id"]==model and (r["year"],r["month"])==(int(dt[:4]),int(dt[5:]))]
   r=selected[0] if selected else None;em=props["evaluation"].get(model)
   props.update({"selected_model":model,"selected_date":dt,"prediction_kind":kind,"qsim":r["qsim_raw"] if r else None,"qsim_status":"GAUGE_PREDICTION_AVAILABLE" if r else "NO_RESULTS_FOR_SELECTION","qsim_source_snapshot_id":r["source_snapshot_id"] if r else None,"qsim_provenance_hash":r["provenance_hash"] if r else None,"NSE":em["NSE"] if em else None,"evaluation_source_snapshot_id":self.releases["TEMPORAL_HOLDOUT"]["source_snapshot_id"] if em else None,"input_support_status":r["input_support_status"] if r else None})
   features.append({**f,"properties":props})
  return self.envelope(type="FeatureCollection",metadata={"geometry_crs":"EPSG:4326","display_crs":"EPSG:3035","scope":self.releases[kind],"evaluation_scope":self.releases["TEMPORAL_HOLDOUT"],"reach_id":None,"reach_geometry":None},layers={"gauges":{"status":"GAUGE_APPLICABILITY_AVAILABLE","count":27},"prediction":{"status":"GAUGE_PREDICTION_AVAILABLE" if any(f["properties"]["qsim"] is not None for f in features) else "NOT_AVAILABLE","count":sum(f["properties"]["qsim"] is not None for f in features)},"evaluation":{"status":"GAUGE_EVALUATION_AVAILABLE","count":25},"uncertainty":{"status":"GAUGE_UNCERTAINTY_AVAILABLE","count":25},"reach":{"status":"REACH_PREDICTION_NOT_AVAILABLE","count":0}},features=features)
 def report(self,q):
  if q.get("dataset")!=DS:raise Refused(403,"DATASET_NOT_AUTHORIZED")
  item=next((r for r in self.bundle["reports"] if r["id"]==q.get("id")),None)
  if item is None:raise Refused(404,"REPORT_NOT_FOUND")
  path=BASE/"reports"/item["filename"]
  if sha(path)!=item["local_sha256"]:raise Refused(409,"SOURCE_DATA_MISMATCH")
  return self.envelope(id=item["id"],content=path.read_text(encoding="utf-8-sig"),sha256=item["local_sha256"])
 def handle(self,path,q):
  try:
   if path.endswith("/execute") or path.endswith("/predict"):raise Refused(403,"MODEL_EXECUTION_NOT_AUTHORIZED")
   if path.endswith("/export"):raise Refused(403,"QOBS_EXPORT_NOT_AUTHORIZED")
   if path in ["/api/public/catalog","/api/v6/public/catalog"]:
    if q.get("dataset",DS)!=DS:raise Refused(403,"DATASET_NOT_AUTHORIZED")
    return 200,self.catalog()
   if path in ["/api/public/results","/api/v6/public/results/station"]:return 200,self.results(q)
   if path in ["/api/public/evaluation","/api/v6/public/results/evaluation"]:return 200,self.evaluation(q)
   if path in ["/api/public/spatial","/api/v6/public/results/spatial"]:return 200,self.spatial(q)
   if path in ["/api/public/report","/api/v6/public/results/report"]:return 200,self.report(q)
   return 404,{"status":"NOT_FOUND"}
  except Refused as e:return e.status,{"status":e.code,"error":e.code,"prediction":None}
class V06PublicResultsHook:
 """Production hook defaults denied; host permission mechanism must supply a verified callback.
 No JSON flag or dataset name constitutes authorization. Legacy routes are untouched.
 """
 def __init__(self,bridge,verified_display_permission=None):self.bridge=bridge;self.check=verified_display_permission
 def handle(self,path,qs):
  if not path.startswith("/api/v6/public/"):return None
  if self.check is None or self.check(DS,"DISPLAY_FROZEN_PUBLIC_RESULTS") is not True:return 403,{"status":"PUBLIC_RESULT_DISPLAY_NOT_AUTHORIZED","prediction":None}
  return self.bridge.handle(path,qs)
