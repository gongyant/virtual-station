"""Copy original host code only and bind frozen P6 evidence, no teacher mount."""
from common import *
import shutil
u=LAB/'vhs_r2u1_p6a';d=LAB/'vhs_p6d_failure_diagnostics'
assert not (WEB/'host/server.py').exists(),'Candidate already exists; do not recopy historical host'
host=WEB/'host';host.mkdir(parents=True,exist_ok=True)
copied=[]
for p in (u/'host').glob('*.py'):
 shutil.copy2(p,host/p.name);copied.append(str(p))
for directory,ext in [('static',None),('research',{'.py'}),('manifest',{'.json'}),('pilot',{'.csv','.json'})]:
 for p in (u/'host'/directory).rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or (ext is not None and p.suffix not in ext):continue
  dest=host/p.relative_to(u/'host');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);copied.append(str(p))
for src in ['diagnostics/UI_DECOMPOSITION.json','p6/P6_STATUS.json']:
 dest=WEB/src;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(u/src,dest)
for name in ['start_host.ps1','stop_host.ps1']:
 text=(u/name).read_text(encoding='utf-8-sig').replace('8793','8794').replace('R2U1','WEB-S1')
 (WEB/name).write_text(text,encoding='utf-8-sig')
# Add adapter to candidate namespace only, leaving production callback and teacher policy intact.
rp=host/'r2_public.py';text=rp.read_text(encoding='utf-8-sig')
text=text.replace('class R2HostGateway:', 'from s1_research import ResearchEvidence\nclass R2HostGateway:')
text=text.replace('self.candidate_local=candidate_local','self.candidate_local=candidate_local\n  self.s1=ResearchEvidence()')
text=text.replace('q={k:v[0] for k,v in qs.items()}', 'q={k:v[0] for k,v in qs.items()}\n  if path.startswith("/api/v6/candidate-public/research/"):return self.s1.handle(path,q,self.bridge)')
rp.write_text(text,encoding='utf-8')
server=host/'server.py';text=server.read_text(encoding='utf-8-sig').replace('default=8793','default=8794')
text=text.replace('if args.port in (8772,8773,8774,8775):','if args.syr_source:\n        raise SystemExit("WEB-S1 does not mount teacher sources")\n    if args.port in (8772,8773,8774,8775,8791,8792,8793):')
server.write_text(text,encoding='utf-8')
html=host/'static/index.html';text=html.read_text(encoding='utf-8-sig').replace('R2U1科研解释修复候选','WEB-S1科研证据集成候选')
text=text.replace('</body>','<script src="/static/view_research_evidence.js"></script>\n</body>');html.write_text(text,encoding='utf-8')
vp=host/'static/view_public_results.js';text=vp.read_text(encoding='utf-8-sig')
text=text.replace("{key:'report',label:'科研报告'}]","{key:'report',label:'科研报告'},{key:'research',label:'P6外部验证与解释'},{key:'p7',label:'P7实验候选'}]")
vp.write_text(text,encoding='utf-8')
app=host/'static/app.js';text=app.read_text(encoding='utf-8-sig')
text=text.replace("publicReport:'p4_report'", "publicReport:'p4_report',researchPeriod:'2018_2020'")
text=text.replace("report:VHS.state.publicReport}","report:VHS.state.publicReport,researchPeriod:VHS.state.researchPeriod}")
text=text.replace("VHS.state.publicReport='p4_report';", "VHS.state.publicReport='p4_report';VHS.state.researchPeriod='2018_2020';")
text=text.replace("if(ctx.q.report)VHS.state.publicReport=ctx.q.report;", "if(ctx.q.report)VHS.state.publicReport=ctx.q.report;\n      if(ctx.q.researchPeriod)VHS.state.researchPeriod=ctx.q.researchPeriod;")
app.write_text(text,encoding='utf-8')
sourcefiles=[d/f for f in ['P6D_MONTHLY_PAIRED_ERRORS.csv','P6D_STATION_YEAR_FAILURES.csv','P6D_SEASONAL_AND_DRIFT.csv','P6D_PREDICTION_DECOMPOSITION.csv','P6D_INTERVAL_AND_QC_DIAGNOSTICS.csv','P6D_RESEARCH_REPORT_ZH.md','P6D_EVIDENCE_GRADE.csv','P6D_FINAL_STATUS.json']]
sourcefiles += [LAB/'vhs_p6b_external_validation/P6B_INDEPENDENT_VALIDATION_REPORT_ZH.md',LAB/'vhs_p6c_2020_validation/P6C_EXTERNAL_VALIDATION_REPORT_ZH.md',LAB/'vhs_web_r1_public_results_bridge/PUBLIC_MODEL_REGISTRY.json']
pins={str(p):sha(p) for p in sourcefiles}
put(WEB/'evidence/WEB_SOURCE_PINS.json',pins)
periods={}
for key,dates,kind,origin in [('2018_2019',['2018-01','2019-12'],'EXTERNAL_TEMPORAL_VALIDATION','P6B'),('2020',['2020-01','2020-12'],'EXTERNAL_TEMPORAL_VALIDATION','P6C'),('2018_2020',['2018-01','2020-12'],'POSTHOC_POOLED_DIAGNOSTICS','P6D')]:
 periods[key]={'period':key,'start':dates[0],'end':dates[1],'prediction_kind':kind,'origin':origin,'source_snapshot_id':'web-s1-'+origin.lower()+'-'+digest({k:v for k,v in pins.items() if str(d) in k})[:24],'source_run':str(LAB/({'P6B':'vhs_p6b_external_validation','P6C':'vhs_p6c_2020_validation','P6D':'vhs_p6d_failure_diagnostics'}[origin])),'model_release':'P4-V2_FROZEN_ORIGINAL','train_cutoff':'2017-12','external_station_count':24,'quality':'OFFICIAL_ARCHIVE_DESCRIPTIVE_NOT_DAILY_QC_CERTIFIED','not_new_prediction_or_training':True}
contract={'dataset_id':'LAMAH_CE_PUBLIC_V1','evidence_collection':'WEB_S1_P6_READONLY','periods':periods,'source_pins':pins,'station_universe':27,'external_cohort':GAUGES,'models':['C0+PT','P2-L1'],'local_display_scope':'USER_REQUEST_LOCAL_CANDIDATE_RESEARCH_ONLY','production_display_permission':'NOT_GRANTED','dynamic_execution':'NOT_AUTHORIZED','Qobs_policy':'default not returned; one-station controlled local chart only with explicit local_qobs=1; bulk download/export forbidden','true_gaps':0,'reach_status':'REACH_PREDICTION_NOT_AVAILABLE','business_certification':'NOT_CERTIFIED'}
reg=readj(LAB/'vhs_web_r1_public_results_bridge/PUBLIC_MODEL_REGISTRY.json')
for scope in periods.values():
 scope['model_release']=reg['models'][0]['model_release_id'];scope['model_source_snapshot_id']=reg['models'][0]['source_snapshot_id']
 scope['evidence_snapshot_note']='Derived selected evidence snapshot pinned to exact P6 run paths, P6D tables and original P4-V2 model release; not an alias of metadata-only LamaH snapshot'
put(WEB/'WEB_S1_DATA_CONTRACT.json',contract)
put(WEB/'evidence/HOST_COPY_MANIFEST.json',{'source':str(u/'host'),'copied_files':copied,'excluded':['logs','tmp','var','research_ready','teacher CSV or source mount'],'root_homepage':'original v0.6 navigation and state retained','port':8794})
print('WEB host copied code/static',len(copied),'files; source pins',len(pins),flush=True)
