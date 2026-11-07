import json,csv,hashlib,sys,math
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parents[1];LAB=BASE.parent;P4=LAB/"p4_final_reconstruction";P5=LAB/"p5_robustness_and_external_validation"
WEB=Path(r"E:\VHS_WorkBuddy_S1T_Sandbox\output\sprint_w2_vhs_query_app\v0.6_four_layer_platform")
DS="LAMAH_CE_PUBLIC_V1";NOTICE="仅为公开流域有历史Q校准的月尺度径流重建，不代表无资料站预测、提前流量预报或业务级预警。"
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def jw(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("x",encoding="utf-8") as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def cr(p):
 with Path(p).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def cw(p,rr,fields=None):
 with Path(p).open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=fields or list(rr[0]));w.writeheader();w.writerows(rr)
def num(v):return None if v is None or v=="" else float(v)
def verify(root,filename="SHA256SUMS.txt"):
 counts=0;diff=[]
 for line in (root/filename).read_text(encoding="utf-8-sig").splitlines():
  h,n=line.split("  ",1);p=root/n
  if not p.is_file() or sha(p)!=h:diff.append(n)
  counts+=1
 return {"listed_files":counts,"mismatches":diff,"manifest_hash":sha(root/filename)}
def history():
 roots=[(LAB,"SHA256SUMS.txt"),(LAB/"p1_seasonal_meteorology_ablation","SHA256SUMS.txt"),(LAB/"p2_antecedent_snow_features","SHA256SUMS.txt"),(LAB/"p3_forward_temporal_validation","SHA256SUMS.txt"),(P4,"SHA256SUMS.txt"),(P5,"SHA256SUMS.txt"),(WEB,"SHA256SUMS_v0.6.txt")]
 return {str(r):verify(r,f) for r,f in roots}
def seal(root):
 rr=[(sha(p),p.relative_to(root).as_posix()) for p in sorted(root.rglob("*")) if p.is_file() and p.name!="SHA256SUMS.txt" and not p.relative_to(root).parts[0] in ["runtime","tmp"]]
 (root/"SHA256SUMS.txt").write_text("".join(f"{h}  {n}\n" for h,n in rr),encoding="utf-8")
 return len(rr)
