import sys,json,hashlib,shutil,platform,importlib.metadata,time
from pathlib import Path
from admit import R,L,P4,jl,jw,sha
sys.stdout.reconfigure(encoding='utf-8');stage=Path(__file__).parent
historical={'init_probe.py','correct_coordinate_attempt.py','fetch_probe.ps1','cds_monthly_submit.py','cds_error_check.py','cds_status_inventory.py','cds_split.py','acquire.py','ehyd_catalog.py','ehyd_discover.py','ehyd_q.py','geometry_cds.py','gkd_attempt.py','local_driver_audit.py','extract_original_processing.py'}
# Main safe entry points and exact already-executed source; retain failed acquisition scripts as provenance too.
for p in stage.iterdir():
 if not p.is_file() or p.suffix not in ['.py','.ps1']:continue
 dst=R/'code'/p.name;shutil.copyfile(p,dst)
(R/'code/historical_attempts').mkdir(exist_ok=True)
for name in historical:
 p=stage/name
 if p.exists():shutil.copyfile(p,R/'code/historical_attempts'/name)
env={'python':sys.version,'python_executable':sys.executable,'platform':platform.platform(),'packages':{k:importlib.metadata.version(k) for k in ['numpy','xarray','netCDF4','pyproj','shapely']},'dependency_installations':0,'credentials_copied':False};jw(R/'ENVIRONMENT.json',env)
assert sha(R/'code/run_fixed.py')==jl(R/'runs/P6B_EHYD_2018_2019/COMMITMENT.json')['code_hash'];assert sha(R/'code/run_818_2020.py')==jl(R/'runs/P6B_ID818_2020/COMMITMENT.json')['code_hash']
jw(R/'P6B_RESULT_PROVENANCE.json',{'experiment':'PUBLIC_DATA_P6B_EXTERNAL_TEMPORAL_VALIDATION','protocol_hash':sha(R/'P6B_FROZEN_PROTOCOL.json'),'admission_hash':sha(R/'P6B_ADMISSION_FROZEN.json'),'2020_admission_hash':sha(R/'P6B_2020_ADMISSION_FROZEN.json'),'P4_source_snapshot_hash':sha(P4/'source/SNAPSHOT.json'),'code_files':{p.relative_to(R).as_posix():sha(p) for p in (R/'code').rglob('*') if p.is_file()},'new_Q_sources':jl(R/'P6B_ADMISSION_FROZEN.json')['source_hashes'],'prediction_seal':sha(R/'runs/P6B_EHYD_2018_2019/SHA256SUMS.txt'),'scoring_seal':sha(R/'runs/P6B_EHYD_2018_2019_SCORING/SHA256SUMS.txt'),'2020_prediction_seal':sha(R/'runs/P6B_ID818_2020/SHA256SUMS.txt'),'2020_scoring_seal':sha(R/'runs/P6B_ID818_2020_SCORING/SHA256SUMS.txt'),'historical_seals_hash':sha(R/'HISTORICAL_INTEGRITY_REPORT.json'),'environment_hash':sha(R/'ENVIRONMENT.json'),'all_raw_and_nonnegative_metrics':True,'P6A_reused_as_new_results':False,'fit_calls':0,'2020_scored':True,'driver_parity_hash':sha(R/'driver/ARCO_LEGACY_PARITY_RESULT.json'),'CDS_final_acquisition_status':sha(R/'driver/DRIVER_ACQUISITION_FINAL_STATUS.json')})
manifest=R/'SHA256SUMS.txt';files=[p for p in sorted(R.rglob('*')) if p.is_file() and p!=manifest and '__pycache__' not in p.parts];manifest.write_text(''.join(f'{sha(p)}  {p.relative_to(R).as_posix()}\n' for p in files),encoding='utf-8');print('SEALED',len(files),'files',sha(manifest))
