from pathlib import Path
import json
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation');a=json.loads((R/'P6B_ADMISSION_FROZEN.json').read_text());assert not a['descriptive_ids'];assert not list((R/'runs').iterdir())
out=R/'evidence/INITIAL_BMN_IMPLEMENTATION_FAILURE';out.mkdir()
for name in ['P6B_ADMISSION_FROZEN.json','P6B_STATION_CROSSWALK.csv','P6B_MONTHLY_ADMISSION.csv','P6B_SOURCE_Q_FOOTNOTES.csv']:(R/name).rename(out/name)
(out/'REASON.json').write_text(json.dumps({'reason':'BMN source carries false easting 150000/450000/750000. Initial code wrongly used local GK West/Central/East EPSG31254/55/56. Correct EPSG is31257/58/59, confirmed official BEV EPSG table. No quality or distance threshold changed; no model prediction/score existed.','official_source':'https://www.bev.gv.at/dam/bevgvat/PDF-Dateien/Vermessungswesen/Formatbeschreibungen-und-sonstige-Info/EPSG_Austria_BEV.pdf','rule_relaxation':False},indent=2),encoding='utf-8')
