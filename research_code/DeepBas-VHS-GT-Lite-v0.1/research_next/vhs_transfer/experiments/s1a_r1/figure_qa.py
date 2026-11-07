"""Rendered QA only; isolated PyMuPDF dependency, no change to numerical environment."""
import os
import subprocess
import sys
from pathlib import Path
from common import HERE,dump

def main():
    skill=Path.home()/'.codex/skills/nature-figure/scripts'
    env=os.environ.copy(); env['PYTHONPATH']=str(HERE/'qa_dependencies')
    commands=[('source',[str(skill/'validate_figure.py'),str(HERE/'plot_results.py'),'--json'])]
    for name in ('s1a_r1_placebo_gain','s1a_r1_conditional_gain','s1a_r1_residuals'):
        commands.append((name+'_text',[str(skill/'audit_pdf_text.py'),str(HERE/f'{name}.pdf'),'--min-pt','5','--json']))
        commands.append((name+'_collision',[str(skill/'audit_figure_collisions.py'),str(HERE/f'{name}.pdf'),
            '--json-out',str(HERE/f'{name}.collision.json'),'--overlay-pdf',str(HERE/f'{name}.collision.pdf')]))
    results=[]
    for name,args in commands:
        p=subprocess.run([sys.executable,'-B',*args],capture_output=True,text=True,encoding='utf-8',env=env)
        (HERE/f'figure_qa_{name}.txt').write_text(p.stdout+p.stderr,'utf-8')
        results.append({'check':name,'returncode':p.returncode})
    dump(HERE/'figure_qa_summary.json',results)
    print(results)

if __name__=='__main__': main()
