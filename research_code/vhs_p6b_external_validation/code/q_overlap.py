"""Post-score source-vintage continuity diagnostic; does not select test samples."""
import math,calendar,collections,json
from pathlib import Path
import numpy as np
from admit import R,L,P4,jl,jw,cw,readcsv,ehyd,sha
snap=jl(P4/'source/SNAPSHOT.json');cross=readcsv(R/'P6B_STATION_CROSSWALK.csv');rows=[]
for s in cross:
 if s['country']!='AUT':continue
 g=int(s['gauge_id']);source=Path(snap['source_paths'][str(g)]['Q']);assert sha(source)==snap['source_files'][str(source)];old=collections.defaultdict(list)
 for rr in readcsv(source,';'):
  if 2015<=int(rr['YYYY'])<=2017:old[f'{int(rr["YYYY"]):04d}-{int(rr["MM"]):02d}'].append(rr)
 _,new,_=ehyd(R/'external'/f'EHYD_{s["official_id"]}_file5.txt',True);diffs=[];relative=[]
 for dt,rr in old.items():
  n=calendar.monthrange(int(dt[:4]),int(dt[5:]))[1];days=[f'{dt}-{d:02d}' for d in range(1,n+1)]
  if len(rr)!=n or any(float(r['qobs'])<0 or not math.isfinite(float(r['qobs'])) or r['ckhs']!='1' for r in rr):continue
  if not all(d in new and new[d]['Q'] is not None and new[d]['Q']>=0 for d in days):continue
  om=float(np.mean([float(r['qobs']) for r in rr]));nm=float(np.mean([new[d]['Q'] for d in days]));diffs.append(nm-om);relative.append(abs(nm-om)/om if om>0 else None)
 rows.append({'gauge_id':g,'overlap_period':'2015-2017','complete_matched_checked_LamaH_months':len(diffs),'mean_signed_monthly_Q_difference_m3s':float(np.mean(diffs)) if diffs else None,'max_absolute_monthly_Q_difference_m3s':max(map(abs,diffs)) if diffs else None,'max_relative_monthly_Q_difference':max(x for x in relative if x is not None) if any(x is not None for x in relative) else None,'note':'post-score source-vintage/civil-day diagnostic, not test admission or evidence of causal hydrological change'})
cw(R/'P6B_Q_SOURCE_OVERLAP_CONTINUITY.csv',rows);print(json.dumps(rows,indent=2))
