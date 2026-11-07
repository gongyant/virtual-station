"""Read-only national assessment collection, with foreign benchmarks explicitly namespaced."""
import pathlib,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2];DS="KAZAKHSTAN_PUBLIC_NETWORK"
def load(p):return json.loads(pathlib.Path(p).read_text(encoding="utf-8-sig"))
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def _pin_path(key):
  p=pathlib.Path(key)
  if p.is_file():
    return p
  cand=ROOT/key
  if cand.is_file():
    return cand
  hits=list(ROOT.rglob(p.name))
  return hits[0] if hits else p
class KazNationalEvidence:
 def __init__(self):
  raw=load(ROOT/"WEB_KAZ_SOURCE_PINS.json")
  self.pins={str(_pin_path(k)):v for k,v in raw.items()}
  self.bundle=load(ROOT/"data/NATIONAL_WEB_BUNDLE.json");self.map=load(ROOT/"data/KAZ_NATIONAL_MAP.json")
 def handle(self,path,q):
  env={"dataset_id":DS,"source_snapshot_id":self.bundle["source_snapshot_id"],"display_scope":"LOCAL_CANDIDATE_RESEARCH_ONLY","production_display_permission":"NOT_GRANTED","model_execution":"NOT_AUTHORIZED","Kazakhstan_NSE":None,"Kazakhstan_KGE":None,"reach_status":"REACH_PREDICTION_NOT_AVAILABLE"}
  leaf=path.rsplit("/",1)[-1]
  if q.get("dataset")!=DS:return 403,{**env,"status":"DATASET_NOT_AUTHORIZED"}
  if leaf in ["execute","predict","train","export","download"] or any(k in q for k in ["format","Qobs","qobs","file","path"]):return 403,{**env,"status":"OPERATION_NOT_AUTHORIZED"}
  for pth,h in self.pins.items():
   try:ok=sha(pth)==h
   except OSError:ok=False
   if not ok:return 409,{**env,"status":"SOURCE_DATA_MISMATCH","failed_pin":pth}
  if leaf!="catalog" and q.get("snapshot")!=self.bundle["source_snapshot_id"]:return 409,{**env,"status":"SOURCE_DATA_MISMATCH"}
  if leaf=="catalog":return 200,{**env,"counts":self.bundle["counts"],"official":self.bundle["official"],"density":self.bundle["density"],"GIS":self.bundle["GIS"],"basins":self.bundle["basins"],"four_answers":self.bundle["four_answers"],"notice":"1230 is a real partial-coverage geometry screening pool, not admitted or predicted virtual gauges. European PUB scores are not Kazakhstan scores."}
  if leaf=="map":return 200,{**env,**self.map}
  if leaf=="readiness":return 200,{**env,"records":self.bundle["readiness"],"source_pins":{pathlib.Path(k).name:v for k,v in self.pins.items()}}
  if leaf=="pub":
   result=self.bundle["European_PUB_benchmark"];return 200,{**env,"benchmark_dataset_id":result["dataset_id"],"classification":result["classification"],"not_Kazakhstan_accuracy":True,"summary":result["summary"],"records":result["metrics"],"known_gauge_context":self.bundle["P7_known_gauge_context"]}
  return 404,{**env,"status":"NOT_FOUND"}
