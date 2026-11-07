from p6d_common import *
import subprocess,os
sys.stdout.reconfigure(encoding='utf-8');skill=Path(r'C:\Users\Administrator\.codex\skills\nature-figure\scripts');env=dict(os.environ,PYTHONIOENCODING='utf-8');out=[]
def run(label,args):
 cmd=[sys.executable,'-B',*map(str,args)];p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',env=env);(R/'figure_qa'/f'{label}.stdout.txt').write_text(p.stdout,encoding='utf-8');(R/'figure_qa'/f'{label}.stderr.txt').write_text(p.stderr,encoding='utf-8');r={'label':label,'command':cmd,'exit_code':p.returncode,'status':'PASS' if p.returncode==0 else 'NOT_AUDITABLE' if p.returncode==2 and label.endswith('collision') else 'FAIL'};out.append(r);print(label,r['status']);return r
run('source_preflight',[skill/'validate_figure.py',R/'code/figures.py','--json'])
for pdf in sorted((R/'figures').glob('*.pdf')):
 run(pdf.stem+'_text',[skill/'audit_pdf_text.py',pdf,'--min-pt','5','--json'])
 run(pdf.stem+'_collision',[skill/'audit_figure_collisions.py',pdf,'--json-out',R/'figure_qa'/f'{pdf.stem}.collision.json','--overlay-pdf',R/'figure_qa'/f'{pdf.stem}.collision.pdf'])
jw(R/'P6D_FIGURE_AUTOMATED_QA.json',{'checks':out,'passed':sum(r['status']=='PASS' for r in out),'failed':sum(r['status']=='FAIL' for r in out),'not_auditable':sum(r['status']=='NOT_AUDITABLE' for r in out),'initial_preflight_corrections':'4 initial source checks failed: generic font declaration, dynamic export suffix detection, raster220dpi. Fixed explicit sans-serif, literal PDF/SVG/PNG exports, 300dpi. Date label clipping repaired. No scientific data changed.','collision_dependency':'PyMuPDF not installed in existing scientific/bundled environments; no install performed; unavailable is not PASS'})
