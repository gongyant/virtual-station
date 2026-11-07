"""Read-only delivery seal/history/source verifier. No fitting, scoring, or network."""
from intake import *

def main():
 results=[]
 for label,pins in [('historical',readj(ROOT/'evidence/HISTORY_BEFORE.json')),('GIS_input',readj(ROOT/'evidence/GIS_SOURCE_HASHES.json')),('web_input',readj(ROOT/'WEB_KAZ_SOURCE_PINS.json'))]:
  for p,h in pins.items():
   f=pathlib.Path(p);results.append((label,p,f.is_file() and sha(f)==h))
 for line in (ROOT/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
  h,rel=line.split('  ',1);f=ROOT/rel
  assert f.resolve().is_relative_to(ROOT.resolve()),rel
  results.append(('delivery',rel,f.is_file() and sha(f)==h))
 bad=[{'kind':a,'path':b} for a,b,ok in results if not ok]
 out={'passed':sum(ok for _,_,ok in results),'failed':len(bad),'failures':bad,'by_kind':dict(collections.Counter(a for a,_,_ in results)),'fit_calls':0,'score_calls':0,'network_calls':0,'SHA256SUMS_sha256':sha(ROOT/'SHA256SUMS.txt')}
 print(json.dumps(out,ensure_ascii=False,indent=2));assert not bad
if __name__=='__main__':main()
