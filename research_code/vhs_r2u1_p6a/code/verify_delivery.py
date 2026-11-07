import hashlib,json
from pathlib import Path
r=Path(__file__).resolve().parents[1];bad=[];n=0
for l in (r/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
 h,s=l.split('  ',1);p=r/s;n+=1
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:bad.append(s)
print(json.dumps({'files':n,'mismatches':bad,'status':'PASS' if not bad else 'FAIL'}));raise SystemExit(bool(bad))
