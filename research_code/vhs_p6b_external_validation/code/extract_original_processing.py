import tarfile,json,hashlib
from pathlib import Path
L=Path(r'E:\VHS_Public_Baseline_Lab');R=L/'vhs_p6b_external_validation';out=[]
names={'Timeseries_met_ERA5L.R','Merge_met_timeseries_basinwise.R','Transform_timeseries_hourly_to_daily.R','API_download_ERA5L.R'}
with tarfile.open(L/'source/archive/2_LamaH-CE_daily.tar.gz','r|gz') as t:
 for m in t:
  if m.isfile() and Path(m.name).name in names:
   b=t.extractfile(m).read();p=R/'driver'/Path(m.name).name;p.write_bytes(b);out.append({'archive_member':m.name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)});print(m.name,flush=True)
(R/'driver/ORIGINAL_PROCESSING_CODE_RECEIPTS.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
