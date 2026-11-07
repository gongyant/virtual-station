"""Document-only correction; archive the initial seal, never alter numerical results."""
from intake import *
import shutil,ast

def main():
 initial=ROOT/'evidence/SHA256SUMS.initial.txt';assert not initial.exists()
 old=sha(ROOT/'SHA256SUMS.txt');shutil.copy2(ROOT/'SHA256SUMS.txt',initial)
 p=ROOT/'KAZ_N1_REPRODUCTION_GUIDE.md';s=p.read_text(encoding='utf-8');assert '\x0berify_delivery.py' in s
 s=s.replace('\x0berify_delivery.py',r'\verify_delivery.py');p.write_text(s,encoding='utf-8')
 for p in ROOT.glob('*.md'):
  bad=[ord(c) for c in p.read_text(encoding='utf-8') if ord(c)<32 and c not in '\t\r\n'];assert not bad,(p,bad)
 for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
 put(ROOT/'evidence/SEAL_DOCUMENT_AMENDMENT.json',{'initial_manifest_sha256':old,'initial_manifest_preserved':str(initial),'changes':['fix Windows \\verify path escaped as a vertical tab in reproduction command','raw f-strings in finalize.py prevent future path escape warnings','add this explicit document-only amendment script/evidence'],'no_changes_to_models_predictions_scores_protocol_or_source_snapshots':True})
 excluded={'runtime','logs','tmp','var','__pycache__'}
 files=[p for p in ROOT.rglob('*') if p.is_file() and not set(p.relative_to(ROOT).parts)&excluded and p.name!='SHA256SUMS.txt']
 (ROOT/'SHA256SUMS.txt').write_text('\n'.join(f'{sha(p)}  {p.relative_to(ROOT).as_posix()}' for p in sorted(files))+'\n',encoding='utf-8')
 print(json.dumps({'sealed_files':len(files),'current_manifest_sha256':sha(ROOT/'SHA256SUMS.txt'),'initial_manifest_sha256':old}))
if __name__=='__main__':main()
