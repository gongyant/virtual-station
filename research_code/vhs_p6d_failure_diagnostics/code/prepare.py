from common import *
import shutil
assert not R.exists(),'P6D_EXISTS_INSPECT_FIRST'
for d in ['code','evidence','figures','figure_source_data','figure_qa']:(R/d).mkdir(parents=True,exist_ok=True)
history=jl(C/'evidence/HISTORY_BEFORE.json');entries={}
for root,rec in history.items():
 for n,h in rec['files'].items():assert sha(Path(root)/n)==h;entries[str(Path(root)/n)]=h
 entries[str(Path(root)/'SHA256SUMS.txt')]=sha(Path(root)/'SHA256SUMS.txt')
for line in (C/'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines():
 h,n=line.split('  ',1);assert sha(C/n)==h;entries[str(C/n)]=h
for p in C.rglob('SHA256SUMS.txt'):entries[str(p)]=sha(p)
# Protect original website code and manifest only; never open teacher data.
web=Path(r'E:\VHS_WorkBuddy_S1T_Sandbox\output\sprint_w2_vhs_query_app\v0.6_four_layer_platform');webcount=0
if web.exists():
 for p in web.rglob('*'):
  if not p.is_file() or any(t.lower() in {'data','sealed_runoff','quarantine','node_modules','__pycache__','.git'} for t in p.relative_to(web).parts):continue
  if p.suffix.lower() in {'.py','.js','.html','.css','.ps1'} or p.name=='SHA256SUMS.txt':entries[str(p)]=sha(p);webcount+=1
jw(R/'evidence/HISTORY_BEFORE.json',entries)
a=jl(C/'P6C_ADMISSION_FROZEN.json');ids=sorted(map(int,a['sources']));assert len(ids)==24
protocol={'experiment':'PUBLIC_DATA_POSTHOC_P6D_DIAGNOSTICS','frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'gauge_ids':ids,'period':'2018-01/2020-12','models':['C0+PT','P2-L1'],'fit_calls_allowed':0,'posterior_explanation':True,'confirmatory_test':False,'Qobs_export':'user explicitly authorizes local public-data monthly paired output for P6D; not public redistribution or teacher Q','prediction_reconstruction_tolerance':{'absolute':1e-10,'relative':1e-10},'decomposition':'saved raw z=(x-mu_month)/sd_month; constant ->0; prediction=climate_month+sum(beta*z). C0PT/L1 difference decomposed across all terms, not assigned wholly to lagP. Nonnegative clipping correction separate. Conditional algebraic allocation, not causal attribution.','delta_MSE':'delta_SE=SE_C0PT-SE_L1, positive beneficial; per-month contribution delta_SE/n and cumulative chronological contribution sum(delta_SE)/n','seasons':{'DJF':[1,2,12],'MAM':[3,4,5],'JJA':[6,7,8],'SON':[9,10,11],'MAY_JUNE':[5,6]},'DJF':'calendar year Jan Feb Dec, not one contiguous winter','pooled':'recompute from matched36 rows, never average yearlyNSE','descriptive_classes':{'bias_sign':'mean prediction minus meanQ; positive over, negative under','mean_shift_flag':'abs(testQmean-trainQmean)>0.25trainQstd; posthoc descriptive threshold','amplitude_flag':'Qsim_std/Qobs_std outside[0.75,1.25]; descriptor only'},'QC':'main all2882020 and frozen2018-19; conservative frozen1322020 includes4completeyears; not certified daily QC','date_boundary':'preserve provider dates; reuse fixed +/-1day archived diagnostic; never choose best score shift','intervals':'frozen P4 halfwidths, no recalibration; normalized width by same-subset Qobs mean and std, each denominator reason explicit','evidence_grades':['CONFIRMED_NUMERICAL','CANDIDATE_EXPLANATION','UNRESOLVED_PHYSICAL_MECHANISM'],'P7':'no training; reserve post2020 never-scored Q or new physically independent basins if later authorized and available','source_protocol_C_hash':sha(C/'P6C_FROZEN_PROTOCOL.json'),'source_C_manifest_hash':sha(C/'SHA256SUMS.txt'),'source_B_manifest_hash':sha(B/'SHA256SUMS.txt'),'models':a['models']}
jw(R/'P6D_DIAGNOSTIC_PROTOCOL.json',protocol)
contracts={'backend':'python','archetype':'quantitative grid','exports':['PDF','SVG','PNG'],'figure1':{'question':'How do seasonal templates and corrections track observed hydrographs?','cases':[171,185,255,343,383,455,533,545],'role':'36month paired observations/predictions without inference claims'},'figure2':{'question':'Which matched months reverse net L1 gains?','cases':[455,171],'role':'monthly deltaSE/n plus cumulative gain and archived year context'},'figure3':{'question':'Relative seasonal gain and absolute NSE failure coexist?','role':'all24 stations raw DJF and MayJune matched skills, plus winter absolute NSE'},'figure4':{'question':'Are differences wholly attributable to lagP?','role':'saved term contributions and other-coefficient differences; no causal attribution'},'font_floor_pt':5,'panel_alignment_tolerance_pt':1.5,'statistics':'raw paired data or stationequal descriptive values, no CIs/significance implied','traceability':'each figure has source CSVs and file/script hashes'}
jw(R/'FIGURE_CONTRACT.json',contracts)
for p in Path(__file__).parent.glob('*.py'):shutil.copy2(p,R/'code'/p.name)
event('P6D_PREPARED',historical_entries=len(entries),original_website_code_entries=webcount,fit_calls=0)
print('P6D_INITIALIZED','HISTORY_ENTRIES',len(entries),'WEBSITE_CODE_ONLY',webcount,'STATIONS',ids)
