"""Freeze first actual public-data results; never overwrite a previous seal."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for block in iter(lambda:f.read(4*1024*1024),b""):h.update(block)
 return h.hexdigest()
assert not (R/"DELIVERY_SHA256.json").exists()
(R/"evidence/RUN_ATTEMPTS_FIRST_PUBLIC.jsonl").write_bytes((R/"RUN_ATTEMPTS.jsonl").read_bytes())
rows=[{"file":p.relative_to(R).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(R.rglob("*")) if p.is_file() and p.name not in ("DELIVERY_SHA256.json","SHA256SUMS.txt","RUN_ATTEMPTS.jsonl") and "__pycache__" not in p.parts]
log=(R/"RUN_ATTEMPTS.jsonl").read_bytes();run=next((R/"runs").glob("PUBLIC_DATA_REAL_EXPERIMENT-*"))
doc={"created_UTC":datetime.now(timezone.utc).isoformat(),"experiment_label":"PUBLIC_DATA_REAL_EXPERIMENT","scope":"first public-data delivery; future runs appended separately, no overwrite of first run","first_real_run":run.relative_to(R).as_posix(),"attempt_log_initial_prefix":{"bytes":len(log),"sha256":hashlib.sha256(log).hexdigest()},"files":rows}
with (R/"DELIVERY_SHA256.json").open("x",encoding="utf-8") as f:json.dump(doc,f,indent=2)
with (R/"SHA256SUMS.txt").open("x",encoding="utf-8") as f:
 for row in rows:f.write(row["sha256"]+"  "+row["file"]+"\n")
 f.write(sha(R/"DELIVERY_SHA256.json")+"  DELIVERY_SHA256.json\n")
print(json.dumps({"sealed_files":len(rows),"delivery_manifest_sha256":sha(R/"DELIVERY_SHA256.json")}))
