from pathlib import Path
import csv,json,shutil,collections
H=Path(__file__).resolve().parents[1];E=H/'evidence'
src=H/'open_metadata/G_appendix/2_codes/R/2_timeseries/Merge_met_timeseries_basinwise.R';dst=H/'quarantine/G_appendix/2_codes/R/2_timeseries/Merge_met_timeseries_basinwise.R'
assert src.resolve().is_relative_to(H.resolve()) and dst.resolve().is_relative_to(H.resolve()) and not dst.exists()
dst.parent.mkdir(parents=True,exist_ok=True);src.rename(dst)
p=E/'extraction_manifest.csv';shutil.copyfile(p,E/'extraction_manifest_initial.csv')
with p.open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
for r in rows:
    if r['member']=='G_appendix/2_codes/R/2_timeseries/Merge_met_timeseries_basinwise.R':r['category']='UNKNOWN';r['path']=dst.relative_to(H).as_posix()
with p.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
p=E/'extraction_summary.json';shutil.copyfile(p,E/'extraction_summary_initial.json');s=json.loads(p.read_text());s['categories']=dict(collections.Counter(r['category'] for r in rows));p.write_text(json.dumps(s,indent=2),encoding='utf-8')
corrections=dict(coordinate_correction='Initial metadata-only distances incorrectly treated lon/lat as degrees. Official EPSG:3035 point geometry proved projected meters; corrected before final gates and reran all matching. No Q values involved.',classification_correction='One appendix R source initially path-classified FORCING was reclassified UNKNOWN and moved within B1A to quarantine; source bytes preserved and never executed. Initial extraction manifest preserved.',initial_matching_zero_controls_superseded=True,final_matching='141 provisional pairs,92 targets,70 targets with >=1 control,2 unique control gauges,0 with3')
(E/'correction_log.json').write_text(json.dumps(corrections,indent=2),encoding='utf-8')
print('Metadata corrections recorded; source bytes retained')
