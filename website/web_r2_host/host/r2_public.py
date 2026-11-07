"""Mount the frozen R1 adapter inside the original v0.6 host.
Production hook has no invented callback; candidate-only display is a separate namespace.
"""
import sys
from pathlib import Path
R2ROOT=Path(__file__).resolve().parent.parent
R1ROOT=R2ROOT.parent/"vhs_web_r1_public_results_bridge"
sys.path.insert(0,str(R1ROOT/"code"))
from bridge import PublicResultsBridge,V06PublicResultsHook,Refused
class R2HostGateway:
 def __init__(self,candidate_local=False):
  self.bridge=PublicResultsBridge();self.production=V06PublicResultsHook(self.bridge)
  self.candidate_local=candidate_local
 def handle(self,path,qs):
  if path.startswith("/api/v6/public/"):return self.production.handle(path,{k:v[0] for k,v in qs.items()})
  if not path.startswith("/api/v6/candidate-public/"):return None
  if not self.candidate_local:return 403,{"status":"CANDIDATE_DISPLAY_DISABLED","prediction":None}
  if any(len(v)!=1 for v in qs.values()):return 400,{"status":"DUPLICATE_PARAM","prediction":None}
  q={k:v[0] for k,v in qs.items()}
  if path.endswith("/execute") or path.endswith("/predict"):return 403,{"status":"MODEL_EXECUTION_NOT_AUTHORIZED","prediction":None}
  try:self.bridge.validate_sources()
  except Refused as e:return e.status,{"status":e.code,"prediction":None}
  st,data=self.bridge.handle(path.replace("/api/v6/candidate-public/","/api/v6/public/",1),q)
  if isinstance(data,dict):data={**data,"host_integration":"ORIGINAL_V06_CANDIDATE","display_scope":"USER_REQUEST_LOCAL_CANDIDATE_ONLY","production_display_permission":"NOT_GRANTED"}
  return st,data
