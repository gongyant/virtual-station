"""Read-only final check; safe to repeat. No fit, no model selection and no scoring."""
from common import *
def main():
 results=[]
 for root in [ROOT,WEB]:
  passed=0;failed=[]
  for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
   h,rel=line.split('  ',1);p=root/rel
   if p.is_file() and sha(p)==h:passed+=1
   else:failed.append(rel)
  results.append({'root':str(root),'passed':passed,'failed':failed,'manifest_sha256':sha(root/'SHA256SUMS.txt')})
 history=verify_history(readj(ROOT/'evidence/HISTORY_BEFORE.json'))
 result={'delivery':results,'history_checked':history['checked'],'history_passed':history['passed'],'history_failed':history['failed'],'fit_calls':0,'scoring_calls':0,'status':'PASS' if not history['failed'] and all(not x['failed'] for x in results) else 'FAIL'}
 print(json.dumps(result,ensure_ascii=False));assert result['status']=='PASS'
if __name__=='__main__':main()
