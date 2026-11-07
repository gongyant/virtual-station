from common import *
import subprocess
SKILL=Path('C:/Users/Administrator/.codex/skills/nature-figure/scripts')
records=[]
def run(label,command):
    r=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
    records.append(dict(check=label,command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
run('figure_source_preflight',[sys.executable,'-B',str(SKILL/'validate_figure.py'),str(ROOT/'code/figures.py'),'--backend','python','--json'])
for name in ['P9B_SOURCE_COVERAGE_MAP','P9B_CANDIDATE_PROXY_MAP']:
    pdf=ROOT/'figures'/f'{name}.pdf'
    run(name+'_glyph_floor',[sys.executable,'-B',str(SKILL/'audit_pdf_text.py'),str(pdf),'--json'])
    run(name+'_collision',[sys.executable,'-B',str(SKILL/'audit_figure_collisions.py'),str(pdf),'--json-out',str(ROOT/'figures'/f'{name}.collision.json')])
js(ROOT/'figures/FIGURE_AUTOMATED_QA.json',records)
js(ROOT/'figures/FIGURE_VISUAL_QA.json',dict(
    reviewed_pngs=['P9B_SOURCE_COVERAGE_MAP.png','P9B_CANDIDATE_PROXY_MAP.png'],
    source='Rendered final PNGs inspected with local image viewer',
    revised='Legend moved to reserved upper whitespace after first render crossed boundary strokes',
    checks=['All six CA source positions retained; all 49 provisional points retained',
            'Twenty mainstem and ten alternate records use distinct symbols; natural overlap is not removed',
            'Largest proxy boundary includes foreign upstream; exact point area never claimed',
            'Titles, legends and notes separated; no model performance colors or fictitious reach Q'],
    collision_claim='NOT_AUDITABLE if PyMuPDF unavailable; do not claim automatic collision PASS',
    single_panel_alignment='NOT_APPLICABLE; two independent figure files, each one axes'))
event('figure_QA_recorded',checks=len(records),returncodes=[x['returncode'] for x in records])
