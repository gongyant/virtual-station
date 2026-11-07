"""Read-only delivery and historical seal verifier. Never generates data."""
from common import *

def main():
    manifest=ROOT/'SHA256SUMS.txt'
    rows=[line.split('  ',1) for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip()]
    bad=[];seen=set()
    for expected,name in rows:
        p=(ROOT/name).resolve()
        if not p.is_relative_to(ROOT.resolve()) or name in seen:
            bad.append(dict(path=name,reason='UNSAFE_OR_DUPLICATE_MANIFEST_PATH'));continue
        seen.add(name)
        if not p.is_file() or digest(p)!=expected:bad.append(dict(path=name,reason='MISSING_OR_HASH_MISMATCH'))
    existing={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt'}
    unexpected=sorted(existing-seen)
    old=read(ROOT/'evidence/HISTORY_BASELINE.json')
    historical_bad=[name for name,sha in old.items() if not Path(name).is_file() or digest(name)!=sha]
    qa=read(ROOT/'P9B_INDEPENDENT_QA.json');status=read(ROOT/'P9B_FINAL_STATUS.json')
    checks=dict(sealed_files=len(rows),hash_mismatches=bad,unsealed_files=unexpected,
        history_checked=len(old),history_changed=historical_bad,numeric_passed=qa['passed'],numeric_failed=qa['failed'],
        source_arithmetic_failures_retained=qa['source_arithmetic_QC_failed'],
        Q_status=status['Q_status'],P10_status=status['P10_status'],fit_calls=status['fit_calls'],
        package_manifest_sha256=digest(manifest))
    checks['verified']=not(bad or unexpected or historical_bad or qa['failed']) and status['fit_calls']==0 and status['P10_status']=='P10_NOT_READY'
    print(json.dumps(checks,ensure_ascii=False,indent=2))
    return 0 if checks['verified'] else 1

if __name__=='__main__':raise SystemExit(main())
