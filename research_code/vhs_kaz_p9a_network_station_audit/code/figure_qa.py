from common import *
import subprocess
SK=Path('C:/Users/Administrator/.codex/skills/nature-figure/scripts')
results=[]
commands=[('source',[str(SK/'validate_figure.py'),str(ROOT/'code/figures.py'),'--json'])]
for p in sorted((ROOT/'figures').glob('*.pdf')):
    commands.extend([(p.stem+'_text',[str(SK/'audit_pdf_text.py'),str(p),'--min-pt','5','--json']),(p.stem+'_collision',[str(SK/'audit_figure_collisions.py'),str(p),'--json-out',str(ROOT/'figures'/(p.stem+'.collision.json'))])])
for label,args in commands:
    proc=subprocess.run([sys.executable,'-B',*args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (ROOT/'logs'/f'FIGURE_QA_{label}.txt').write_text(proc.stdout+'\n'+proc.stderr,encoding='utf-8')
    results.append(dict(check=label,returncode=proc.returncode,status='PASS' if proc.returncode==0 else 'NOT_AUDITABLE' if proc.returncode==2 else 'FAIL',command=[sys.executable,'-B',*args]))
js(ROOT/'evidence/FIGURE_AUTOMATED_QA.json',dict(passed=sum(r['status']=='PASS' for r in results),failed=sum(r['status']=='FAIL' for r in results),not_auditable=sum(r['status']=='NOT_AUDITABLE' for r in results),results=results,accepted_warnings='300dpi PNG, no TIFF, group-meeting map dimensions; not a journal final',visual_review='PENDING_REVIEW_OF_ALL4_PNGS'))
event('figure_automated_QA',passed=sum(r['status']=='PASS' for r in results),failed=sum(r['status']=='FAIL' for r in results),not_auditable=sum(r['status']=='NOT_AUDITABLE' for r in results))
if any(r['status']=='FAIL' for r in results):raise RuntimeError('Figure QA failed')
