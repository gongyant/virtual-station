"""Reuse frozen S2; only public provenance/metadata changes, no mathematical changes."""
import ast,hashlib,json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];S2=Path(r"E:\VHS_WorkBuddy_S1T_Sandbox\output\vhs_sci_s2_baseline_engine")
dest=R/"code/vendor_public/vhs_sci";dest.mkdir(parents=True,exist_ok=False)
for src in (S2/"vhs_sci").rglob("*.py"):
 target=dest/src.relative_to(S2/"vhs_sci");target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
def parse(body):return ast.parse(body).body
p=dest/"contracts.py";tree=ast.parse(p.read_text(encoding="utf-8"));tree.body.insert(1,ast.Import(names=[ast.alias(name="public_runtime")]))
for c in tree.body:
 if not isinstance(c,ast.ClassDef):continue
 if c.name in ("FeatureBatch","PredictionBatch"):
  for n in c.body:
   if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name):
    if n.target.id=="synthetic":n.value=ast.Constant(False)
    if n.target.id=="authorization_status":n.value=ast.Constant("PUBLIC_DATA_REAL_EXPERIMENT")
 if c.name=="FeatureBatch":
  fn=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=="require_synthetic");fn.body=parse('public_runtime.admit_batch(self)')
 if c.name=="TrainingBatch":
  fn=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=="__post_init__");fn.body+=parse('public_runtime.admit_training(self)')
p.write_text(ast.unparse(ast.fix_missing_locations(tree))+"\n",encoding="utf-8")
p=dest/"models/baselines.py";tree=ast.parse(p.read_text(encoding="utf-8"))
for c in tree.body:
 if isinstance(c,ast.ClassDef) and c.name=="BaseModel":
  fn=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=="record")
  for node in ast.walk(fn):
   if isinstance(node,ast.Dict):
    for i,k in enumerate(node.keys):
     if isinstance(k,ast.Constant) and k.value=="synthetic":node.values[i]=ast.Constant(False)
     if isinstance(k,ast.Constant) and k.value=="authorization_status":node.values[i]=ast.Constant("PUBLIC_DATA_REAL_EXPERIMENT")
p.write_text(ast.unparse(ast.fix_missing_locations(tree))+"\n",encoding="utf-8")
p=dest/"evaluate.py";tree=ast.parse(p.read_text(encoding="utf-8"));tree.body.insert(1,ast.Import(names=[ast.alias(name="public_runtime")]))
for fn in tree.body:
 if isinstance(fn,ast.FunctionDef) and fn.name in ("metric_bundle","same_sample_skill"):
  for i,n in enumerate(fn.body):
   if isinstance(n,ast.If) and "synthetic" in ast.unparse(n.test) and "REAL_EVALUATION_NOT_AUTHORIZED" in ast.unparse(n):
    v="predicted" if fn.name=="metric_bundle" else "predictions";fn.body[i]=parse(f"public_runtime.admit_metric(observed, {v}, synthetic)")[0];break
p.write_text(ast.unparse(ast.fix_missing_locations(tree))+"\n",encoding="utf-8")
def methods(path):
 t=ast.parse(path.read_text(encoding="utf-8"));out={}
 for n in t.body:
  if isinstance(n,ast.FunctionDef):out[n.name]=n
  if isinstance(n,ast.ClassDef):
   for f in n.body:
    if isinstance(f,ast.FunctionDef):out[n.name+"."+f.name]=f
 return out
proof={}
for name in ("models/baselines.py","features.py","folds.py","evaluate.py"):
 a,b=methods(S2/"vhs_sci"/name),methods(dest/name)
 for key in a:
  if key=="BaseModel.record":continue
  aa,bb=a[key],b[key]
  if key in ("metric_bundle","same_sample_skill"):
   aa.body=[n for n in aa.body if not (isinstance(n,ast.If) and "REAL_EVALUATION_NOT_AUTHORIZED" in ast.unparse(n))]
   bb.body=[n for n in bb.body if not (isinstance(n,ast.Expr) and "public_runtime.admit_metric" in ast.unparse(n))]
  proof[name+":"+key]=ast.dump(aa,include_attributes=False)==ast.dump(bb,include_attributes=False)
assert all(proof.values()),[k for k,v in proof.items() if not v]
report={"status":"PASS","source":"frozen S2; mathematical AST unchanged","arithmetic_methods_checked":len(proof),"method_checks":proof,"changes":["public source/value binding replaces synthetic-only boundary","training labels validated against public source and outer-train IDs","PredictionBatch and record synthetic=False, PUBLIC_DATA_REAL_EXPERIMENT","metric provenance guard only; numerical bodies unchanged"],"S2_original_modified":False,"public_values_ever_marked_synthetic":False}
(R/"evidence/S2_NUMERICAL_REUSE.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"status":"PASS","arithmetic_methods":len(proof)}))
