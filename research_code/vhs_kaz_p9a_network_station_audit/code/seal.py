from common import *
import ast
if (ROOT/'SHA256SUMS.txt').exists():raise RuntimeError('Refuse resealing existing delivery; create a new output directory')
qa=read(ROOT/'P9A_INDEPENDENT_QA.json');assert qa['failed']==0
combined=read(ROOT/'evidence/COMBINED_INDEPENDENT_QA.json');assert combined['failed']==0
fqa=read(ROOT/'evidence/FIGURE_AUTOMATED_QA.json');assert fqa['failed']==0
assert fqa['visual_review']=='ALL4_PNGS_INSPECTED'
for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
history_check(ROOT/'evidence/HISTORY_PRESEAL_CHECK.json')
required=['P9A_COMPLETE_REPORT_ZH.md','P9A_ORDER_1_TO_7.csv','P9A_EIGHT_BASIN_ORDER_SUMMARY.csv','P9A_SIX_BASIN_ORDER_SUMMARY.csv','P9A_GAUGE_IDENTITY_CROSSWALK.csv','P9A_UPSTREAM_CHAIN_LENGTH.csv','P9A_VHS_CANDIDATE_SCREENING.csv','P9A_FIRST_BASIN_READINESS.md','P9A_SCI_PAPER_OUTLINE.md','P9A_REPRODUCTION_GUIDE.md','P9A_SEVEN_ORDER_NETWORK.gpkg']
assert all((ROOT/n).is_file() for n in required)
# Capture actual stage invocations from this run's append-only event evidence.
events=[json.loads(s) for s in (ROOT/'RUN_ATTEMPTS.jsonl').read_text(encoding='utf-8').splitlines()]
stage_map={'START':'init_orders.py','global_topology_start':'topology.py','official_source_attempt':'source_audit.py','official_observed_link_attempt':'source_followup.py','coordinate_projection_revision':'coordinate_revision.py','screening_complete':'screening.py','audit_recovery':'repair_checks.py','independent_QA_complete':'verify.py','additional_independent_QA_complete':'verify_extra.py','figure_render_complete':'figures.py','extra_source_and_topology_audit':'extra_audit.py','figure_automated_QA':'figure_qa.py','reports_written':'finalize.py'}
cmd=[]
for ev in events:
    if ev['stage'] in stage_map:
        cmd.append(dict(observed_utc=ev['time_utc'],command=[sys.executable,'-B',str(ROOT/'code'/stage_map[ev['stage']])],event_stage=ev['stage'],evidence='actual stage event; repeated source-page attempts may refer to one script invocation',passed=ev.get('failed',0)==0))
js(ROOT/'evidence/EXECUTED_COMMANDS.json',cmd)
state=read(ROOT/'P9A_FINAL_STATUS.json');state['figure_QA_passed']=fqa['passed'];state['figure_collision_NOT_AUDITABLE']=fqa['not_auditable'];state['sealed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();state['history_preseal_verified']=read(ROOT/'evidence/HISTORY_PRESEAL_CHECK.json')['passed'];js(ROOT/'P9A_FINAL_STATUS.json',state)
event('SEALED',fit_calls=0,Q_scoring_calls=0)
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt' and '__pycache__' not in p.parts)
text=''.join(f'{sha(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in files)
(ROOT/'SHA256SUMS.txt').write_text(text,encoding='utf-8')
print(json.dumps(dict(sealed_files=len(files),manifest_sha256=sha(ROOT/'SHA256SUMS.txt'),GPKG_sha256=sha(ROOT/'P9A_SEVEN_ORDER_NETWORK.gpkg'))),flush=True)
