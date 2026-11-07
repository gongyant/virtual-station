"""Read-only verification of first public experiment delivery and immutable run."""
import hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
def main():
 seal=json.loads((R/"DELIVERY_SHA256.json").read_text(encoding="utf-8"));bad=[]
 for row in seal["files"]:
  p=(R/row["file"]).resolve()
  if not p.is_relative_to(R) or not p.is_file() or sha(p)!=row["sha256"]:bad.append(row["file"])
 p=R/"RUN_ATTEMPTS.jsonl";pin=seal["attempt_log_initial_prefix"]
 if hashlib.sha256(p.read_bytes()[:pin["bytes"]]).hexdigest()!=pin["sha256"]:bad.append("RUN_ATTEMPTS initial prefix")
 for line in (R/"SHA256SUMS.txt").read_text().splitlines():
  digest,name=line.split("  ",1);p=(R/name).resolve()
  if not p.is_relative_to(R) or not p.is_file() or sha(p)!=digest:bad.append(name)
 from verify_public_run import verify_run
 run=R/seal["first_real_run"]
 result=verify_run(run)
 print(json.dumps({"delivery_status":"FAIL" if bad else "PASS","sealed_files":len(seal["files"]),"changed_or_missing":bad,"public_real_run_verification":result,"SyrDarya_status":"NOT_GRANTED","model_retraining_during_verification":False},ensure_ascii=False,indent=2))
 return 1 if bad else 0
if __name__=="__main__":raise SystemExit(main())
