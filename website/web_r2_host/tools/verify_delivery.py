"""Verify immutable delivery files without starting services or loading observations."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];bad=[];n=0
for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    expected,rel=line.split('  ',1);p=root/rel;n+=1
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:bad.append(rel)
print(json.dumps({'listed_files':n,'mismatches':bad,'status':'PASS' if not bad else 'FAIL'}))
raise SystemExit(bool(bad))
