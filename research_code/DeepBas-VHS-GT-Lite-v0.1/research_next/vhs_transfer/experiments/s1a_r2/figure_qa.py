"""QA uses the read-only isolated R1 PDF library; Python -B suppresses cache writes."""
from analyze import *
import subprocess, os
def main():
    skill=Path.home()/'.codex/skills/nature-figure/scripts'
    env=os.environ.copy();env['PYTHONPATH']=str(R1/'qa_dependencies');env['PYTHONDONTWRITEBYTECODE']='1'
    names=['s1a_r2_1_strata','s1a_r2_2_concentration','s1a_r2_3_orthogonal','s1a_r2_4_year_swap','s1a_r2_5_four_cell']
    commands=[('source',[str(skill/'validate_figure.py'),str(HERE/'plot_results.py'),'--json'])]
    for name in names:
        commands.extend([(name+'_text',[str(skill/'audit_pdf_text.py'),str(HERE/f'{name}.pdf'),'--min-pt','5','--json']),(name+'_collision',[str(skill/'audit_figure_collisions.py'),str(HERE/f'{name}.pdf'),'--json-out',str(HERE/f'{name}.collision.json'),'--overlay-pdf',str(HERE/f'{name}.collision.pdf')])])
    results=[]
    for name,args in commands:
        p=subprocess.run([sys.executable,'-B',*args],capture_output=True,text=True,encoding='utf-8',env=env)
        (HERE/f'figure_qa_{name}.txt').write_text(p.stdout+p.stderr,encoding='utf-8');results.append(dict(check=name,returncode=p.returncode))
    dump('figure_qa_summary.json',results);print(results)
if __name__=='__main__':main()
