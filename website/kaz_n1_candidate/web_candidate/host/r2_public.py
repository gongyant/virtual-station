"""Mount the frozen R1 adapter inside the original v0.6 host.
Production hook has no invented callback; candidate-only display is a separate namespace.
"""
import sys,json,hashlib,re
from pathlib import Path
R2ROOT=Path(__file__).resolve().parent.parent
R1ROOT=Path(r"E:\VHS_Public_Baseline_Lab\vhs_web_r1_public_results_bridge")
sys.path.insert(0,str(R1ROOT/"code"))
from bridge import PublicResultsBridge,V06PublicResultsHook,Refused
from s1_research import ResearchEvidence
from kaz_national import KazNationalEvidence
class R2HostGateway:
 def __init__(self,candidate_local=False):
  self.bridge=PublicResultsBridge();self.production=V06PublicResultsHook(self.bridge)
  self.candidate_local=candidate_local
  self.s1=ResearchEvidence()
  self.kaz=KazNationalEvidence()
  self.u1_paths={"diagnostics":R2ROOT/"diagnostics/UI_DECOMPOSITION.json","research-status":R2ROOT/"p6/P6_STATUS.json"}
  self.u1_pins={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in self.u1_paths.items() if p.exists()}
 def handle(self,path,qs):
  if path.startswith("/api/v6/public-kaz/"):return 403,{"status":"PRODUCTION_DISPLAY_NOT_GRANTED"}
  if path.startswith("/api/v6/candidate-kaz/"):
   if not self.candidate_local:return 403,{"status":"CANDIDATE_DISPLAY_DISABLED"}
   if any(len(v)!=1 for v in qs.values()):return 400,{"status":"DUPLICATE_PARAM"}
   return self.kaz.handle(path,{k:v[0] for k,v in qs.items()})
  if path.startswith("/api/v6/public/"):return self.production.handle(path,{k:v[0] for k,v in qs.items()})
  if not path.startswith("/api/v6/candidate-public/"):return None
  if not self.candidate_local:return 403,{"status":"CANDIDATE_DISPLAY_DISABLED","prediction":None}
  if any(len(v)!=1 for v in qs.values()):return 400,{"status":"DUPLICATE_PARAM","prediction":None}
  q={k:v[0] for k,v in qs.items()}
  if path.startswith("/api/v6/candidate-public/research/"):return self.s1.handle(path,q,self.bridge)
  if path.endswith("/execute") or path.endswith("/predict"):return 403,{"status":"MODEL_EXECUTION_NOT_AUTHORIZED","prediction":None}
  try:self.bridge.validate_sources()
  except Refused as e:return e.status,{"status":e.code,"prediction":None}
  leaf=path.rsplit("/",1)[-1]
  if leaf in ["diagnostics","research-status","selection-source"]:
   try:
    kind,uid,model=self.bridge.scope(q,True)
    if leaf=="selection-source":
     start=q.get("start","2015-01");end=q.get("end","2017-12")
     if not all(re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])",d) for d in [start,end]) or start>end:raise Refused(400,"INVALID_TIME_WINDOW")
     rows=[r for r in self.bridge.bundle["predictions"] if r["station_uid"]==uid and r["model_id"]==model and r["prediction_kind"]==kind]
     selected=[r for r in rows if start<=f'{r["year"]}-{r["month"]:02d}'<=end]
     data={"dataset_id":self.bridge.bundle["registry"]["dataset_id"],"station_uid":uid,"model_id":model,"prediction_kind":kind,"start":start,"end":end,"source_scope":self.bridge.releases[kind],"station_model_kind_total":len(rows),"selected_records":len(selected),"global_counts":self.bridge.bundle["counts"],"provenance_hashes":sorted({r["provenance_hash"] for r in selected}),"Qobs":None}
    else:
     p=self.u1_paths[leaf]
     if leaf not in self.u1_pins or hashlib.sha256(p.read_bytes()).hexdigest()!=self.u1_pins[leaf]:raise Refused(409,"U1_DIAGNOSTIC_SOURCE_MISMATCH")
     raw=json.loads(p.read_text(encoding="utf-8"))
     g=int(uid.rsplit(":",1)[-1])
     if leaf=="research-status":data={"station_uid":uid,"P6":(self.s1.validation_status(g) or next((x for x in raw["stations"] if x["gauge_id"]==g),{"gauge_id":g,"status":"NOT_RUN_NOT_IN_P6A_COHORT"})),"business_certification":"NOT_CERTIFIED"}
     else:data={"station_uid":uid,"model_id":model,"prediction_kind":kind,"summary":raw["summary"],"records":[r for r in raw["records"] if r["gauge_id"]==g and r["prediction_kind"]==kind],"station_summary":[r for r in raw["station_summary"] if r["gauge_id"]==g],"alpha":[r for r in raw["alpha"] if r["gauge_id"]==g],"definition":raw["definition"],"classification":"DESCRIPTIVE_FROZEN_DIAGNOSTICS_NOT_P6"}
    return 200,{**data,"display_scope":"USER_REQUEST_LOCAL_CANDIDATE_ONLY","production_display_permission":"NOT_GRANTED"}
   except Refused as e:return e.status,{"status":e.code,"prediction":None}
  st,data=self.bridge.handle(path.replace("/api/v6/candidate-public/","/api/v6/public/",1),q)
  if isinstance(data,dict):data={**data,"host_integration":"ORIGINAL_V06_CANDIDATE","display_scope":"USER_REQUEST_LOCAL_CANDIDATE_ONLY","production_display_permission":"NOT_GRANTED"}
  return st,data
