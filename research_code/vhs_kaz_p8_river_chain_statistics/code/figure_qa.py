from common import *
import subprocess
def main():
 scripts=pathlib.Path(r'C:\Users\Administrator\.codex\skills\nature-figure\scripts');out=ROOT/'evidence/figure_QA';out.mkdir(exist_ok=True);records=[]
 cmds=[('source_preflight',[str(scripts/'validate_figure.py'),str(ROOT/'code/figures.py'),'--backend','python','--json'])]
 for p in (ROOT/'figures').glob('*.pdf'):
  cmds +=[(p.stem+'_glyphs',[str(scripts/'audit_pdf_text.py'),str(p),'--min-pt','5','--json']),(p.stem+'_collision',[str(scripts/'audit_figure_collisions.py'),str(p),'--json-out',str(out/(p.stem+'.collision.json'))])]
 for name,args in cmds:
  r=subprocess.run([sys.executable,'-B',*args],capture_output=True,text=True,encoding='utf-8',errors='replace');(out/(name+'.log')).write_text(r.stdout+'\n'+r.stderr,encoding='utf-8');records.append({'name':name,'command':[sys.executable,'-B',*args],'exit_code':r.returncode,'status':'PASS' if r.returncode==0 else 'NOT_AUDITABLE_OR_REVIEW_REQUIRED','log':str(out/(name+'.log'))})
 put(ROOT/'evidence/FIGURE_QA.json',{'checks':records,'automated_pass':sum(r['exit_code']==0 for r in records),'automated_nonpass':sum(r['exit_code']!=0 for r in records),'visual_QA':'performed separately with rendered PNG; automatic nonpass never relabeled PASS','notes':'group-meeting geometry/bar figures; no model scores or synthetic values; single-axis alignment N/A; absent PyMuPDF must be reported'})
 print(json.dumps(records,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
