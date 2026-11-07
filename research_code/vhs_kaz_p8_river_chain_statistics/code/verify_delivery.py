from common import *
def main():
 rs=[]
 for name,hist in [('history',read(ROOT/'evidence/HISTORY_BEFORE.json')),('delivery',{str(ROOT/line.split('  ',1)[1]):line.split('  ',1)[0] for line in (ROOT/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()})]:
  for p,h in hist.items():rs.append({'kind':name,'path':p,'passed':pathlib.Path(p).is_file() and sha(p)==h})
 out={'passed':sum(x['passed'] for x in rs),'failed':sum(not x['passed'] for x in rs),'failures':[x for x in rs if not x['passed']],'by_kind':dict(collections.Counter(x['kind'] for x in rs)),'fit_calls':0,'Q_scoring_calls':0,'network_calls':0,'SHA256SUMS_sha256':sha(ROOT/'SHA256SUMS.txt')};print(json.dumps(out,ensure_ascii=False,indent=2));assert out['failed']==0
if __name__=='__main__':main()
