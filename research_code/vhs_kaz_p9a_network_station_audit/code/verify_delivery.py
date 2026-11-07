from common import *
import sys
def main():
    m=ROOT/'SHA256SUMS.txt';bad=[];total=0
    for line in m.read_text(encoding='utf-8-sig').splitlines():
        h,name=line.split('  ',1);p=(ROOT/name).resolve()
        if not p.is_relative_to(ROOT.resolve()):raise ValueError('Manifest escapes delivery root')
        total+=1
        if not p.is_file() or sha(p)!=h:bad.append(name)
    hist=read(ROOT/'evidence/HISTORY_BASELINE.json');hb=[]
    for p,h in hist.items():
        if not Path(p).is_file() or sha(p)!=h:hb.append(p)
    print(json.dumps(dict(delivery_checked=total,delivery_passed=total-len(bad),delivery_failed=len(bad),delivery_failures=bad,history_checked=len(hist),history_passed=len(hist)-len(hb),history_failed=len(hb),history_failures=hb,manifest_sha256=sha(m)),ensure_ascii=False),flush=True)
    return 1 if bad or hb else 0
if __name__=='__main__':sys.exit(main())
