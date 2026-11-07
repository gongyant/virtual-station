from common import *
import ast
def main():
 assert not (ROOT/'SHA256SUMS.txt').exists();status=read(ROOT/'P8_FINAL_STATUS.json');assert status['QA_failed']==0 and status['fit_calls']==0
 hist=read(ROOT/'evidence/HISTORY_BEFORE.json');bad=[p for p,h in hist.items() if not pathlib.Path(p).is_file() or sha(p)!=h];assert not bad,bad
 put(ROOT/'evidence/HISTORY_FINAL_CHECK.json',{'checked':len(hist),'passed':len(hist),'failed':0,'teacher_Q_read':False,'scope':'historical manifest entries only; operational runtime files excluded'})
 for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
 for p in ROOT.glob('*.md'):assert not [c for c in p.read_text(encoding='utf-8') if ord(c)<32 and c not in '\n\r\t'],p
 put(ROOT/'P8_PROVENANCE.json',{'protocol_sha256':sha(ROOT/'P8_FROZEN_PROTOCOL.json'),'global_archive_sha256':sha(ROOT/'source/HydroRIVERS_v10_shp.zip'),'basin_archive_sha256':sha(ROOT/'source/ver.2.zip'),'country_boundary_sha256':sha(read(ROOT/'P8_FROZEN_PROTOCOL.json')['country_boundary']),'GPKG_sha256':sha(ROOT/'P8_NATIONAL_RIVER_REACHES.gpkg'),'QazSu_public_response_sha256':sha(ROOT/'source/qazsu_hydroposts_response.json'),'KAZ_N1_recheck_source_sha256':sha(pathlib.Path(read(ROOT/'evidence/DISCOVERY.json')['KAZ_N1'])/'KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson'),'country_correction_evidence':read(ROOT/'evidence/COUNTRY_BOUNDARY_AMENDMENT.json'),'QazSu_ID_namespace':'QazSu and Zenodo research ids compared by names, not strings or numeric equality','fit_calls':0,'Q_scoring_calls':0})
 event('delivery_seal','SEALED',scientific_QA_passed=status['QA_passed'],scientific_QA_failed=status['QA_failed'],historical_hashes=len(hist),fit_calls=0)
 excluded={'runtime','__pycache__'};files=[p for p in ROOT.rglob('*') if p.is_file() and not set(p.relative_to(ROOT).parts)&excluded and p.name!='SHA256SUMS.txt']
 (ROOT/'SHA256SUMS.txt').write_text('\n'.join(f'{sha(p)}  {p.relative_to(ROOT).as_posix()}' for p in sorted(files))+'\n',encoding='utf-8');print(json.dumps({'sealed_files':len(files),'SHA256SUMS_sha256':sha(ROOT/'SHA256SUMS.txt'),'history_passed':len(hist)}))
if __name__=='__main__':main()
