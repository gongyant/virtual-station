"""Read-only hash, state and history verification; no fit or score."""
from acquire import *
def main():
 p=ROOT/'SHA256SUMS.txt';rows=[s.split('  ',1) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()];bad=[];seen=set()
 for h,name in rows:
  target=(ROOT/name).resolve()
  if not target.is_relative_to(ROOT.resolve()) or name in seen:bad.append(dict(path=name,reason='UNSAFE_OR_DUPLICATE_PATH'));continue
  seen.add(name)
  if not target.is_file() or sha(target)!=h:bad.append(dict(path=name,reason='MISSING_OR_HASH_CHANGED'))
 actual={x.relative_to(ROOT).as_posix() for x in ROOT.rglob('*') if x.is_file() and x!=ROOT/'SHA256SUMS.txt'}
 unsealed=sorted(actual-seen)
 old=json.loads((ROOT/'evidence/HISTORY_BASELINE.json').read_text(encoding='utf-8'));changed=[x for x,h in old.items() if not Path(x).is_file() or sha(x)!=h]
 qa=json.loads((ROOT/'P9C_INDEPENDENT_QA.json').read_text(encoding='utf-8'));status=json.loads((ROOT/'P9C_FINAL_STATUS.json').read_text(encoding='utf-8'))
 rejected=[]
 for folder in ['exploratory_temporal/run','exploratory_temporal_REJECTED_COLUMN_ALIGNMENT/run']:
  base=ROOT/folder
  for s in (base/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
   h,name=s.split('  ',1)
   if sha(base/name)!=h:rejected.append(str(base/name))
 ok=not(bad or unsealed or changed or rejected or qa['failed']) and status['formal_P10_fit_calls']==0 and status['E2_prediction_records']==96
 result=dict(verified=ok,sealed_files=len(rows),hash_mismatches=bad,unsealed_files=unsealed,history_checked=len(old),history_changed=changed,
  independent_QA_passed=qa['passed'],independent_QA_failed=qa['failed'],accepted_E2_predictions=96,rejected_schema_predictions=120,
  effective_E2_models=2,rejected_schema_models=2,formal_P10_fit_calls=0,P10='P10_NOT_READY',
  source_schema_publisher_confirmation=False,run_hash_mismatches=rejected,manifest_sha256=sha(p))
 print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
