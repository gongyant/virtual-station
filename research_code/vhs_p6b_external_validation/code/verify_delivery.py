"""Read-only verification. Does not request network, fit, infer, or score."""
import hashlib,json
from pathlib import Path
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation');bad=[];n=0
for line in (R/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
 h,name=line.split('  ',1);p=R/name;n+=1
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:bad.append(name)
print(json.dumps({'status':'PASS' if not bad else 'FAIL','files':n,'mismatches':bad}));raise SystemExit(bool(bad))
