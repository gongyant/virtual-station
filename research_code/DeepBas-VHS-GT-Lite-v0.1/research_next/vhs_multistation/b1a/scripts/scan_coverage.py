"""One restricted pass over sealed Q: dates, missing tokens and existing QC only."""
from pathlib import Path
import csv,json,datetime,calendar,io
from blind_coverage import MISSING,synthetic_test
H=Path(__file__).resolve().parents[1];E=H/'evidence'
def restricted(stream):
    reader=csv.reader(stream,delimiter=';');head=next(reader)
    if head!=['YYYY','MM','DD','qobs','ckhs','qceq','qcol']:raise ValueError('Unsupported real schema: STOP')
    years={};seen=set();first=None;last=None;duplicates=0
    for row in reader:
        if len(row)!=7:raise ValueError('Malformed restricted row: STOP')
        try:d=datetime.date(int(row[0]),int(row[1]),int(row[2]))
        except Exception:raise ValueError('Invalid date: STOP') from None
        if d in seen:duplicates+=1
        seen.add(d);first=d if first is None else min(first,d);last=d if last is None else max(last,d)
        y=years.setdefault(d.year,dict(days=0,missing=0,nonmissing=0,checked_nonmissing=0,ckhs={},qceq={},qcol={},checked_mask=0))
        missing=row[3].strip() in MISSING
        y['days']+=1;y['missing' if missing else 'nonmissing']+=1
        for col,idx in [('ckhs',4),('qceq',5),('qcol',6)]:
            code=row[idx].strip()
            if code not in ('0','1','-999','-999.0','NA','NaN','nan',''):raise ValueError('Unknown QC code: STOP')
            y[col][code]=y[col].get(code,0)+1
        if not missing and row[4].strip()=='1':
            y['checked_nonmissing']+=1;y['checked_mask']|=1<<(d.timetuple().tm_yday-1)
    return dict(first_date=first.isoformat() if first else '',last_date=last.isoformat() if last else '',unique_dates=len(seen),duplicate_dates=duplicates,years=years)
def tests():
    synthetic_test()
    a='YYYY;MM;DD;qobs;ckhs;qceq;qcol\n2000;1;1;2.8;1;0;0\n2000;1;2;-999;0;0;0\n2001;1;1;900;1;1;0\n'
    b=a.replace(';2.8;',';900000000000;').replace(';900;',';-3.141592;')
    x=restricted(io.StringIO(a));assert x==restricted(io.StringIO(b))
    assert x!=restricted(io.StringIO(a.replace(';900;',';-999;')))
    assert x!=restricted(io.StringIO(a.replace(';2.8;1;',';2.8;0;')))
    return dict(status='PASS',actual_schema_synthetic=True,nonmissing_Q_replacement_invariant=True,missing_and_QC_changes_detected=True,checked_mask_invariance=True,real_Q_files_read_before_test=0)
result=tests();(E/'actual_schema_synthetic.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
allrows=[];summary={};masks={}
paths=sorted((H/'sealed_runoff/D_gauges/2_timeseries/daily').glob('ID_*.csv'))
assert len(paths)==882
for count,p in enumerate(paths,1):
    sid=int(p.stem[3:])
    with p.open(encoding='utf-8-sig',newline='') as f:s=restricted(f)
    assert s['duplicate_dates']==0,'Duplicate dates: STOP'
    masks[sid]={year:y['checked_mask'] for year,y in s['years'].items()}
    eligible=0
    for year,y in sorted(s['years'].items()):
        ndays=366 if calendar.isleap(year) else 365
        if y['checked_nonmissing']/ndays>=.9:eligible+=1
        allrows.append(dict(ID=sid,year=year,calendar_days=ndays,rows=y['days'],missing_days=y['missing'],nonmissing_days=y['nonmissing'],checked_nonmissing_days=y['checked_nonmissing'],checked_fraction=y['checked_nonmissing']/ndays,ckhs_counts=json.dumps(y['ckhs'],sort_keys=True),qceq_counts=json.dumps(y['qceq'],sort_keys=True),qcol_counts=json.dumps(y['qcol'],sort_keys=True)))
    summary[sid]=dict(first_date=s['first_date'],last_date=s['last_date'],unique_dates=s['unique_dates'],years_ge90pct_checked=eligible,coverage_10years_pass=eligible>=10)
    if count%200==0:print('Restricted date/QC files',count,flush=True)
with (H/'coverage_by_year.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,list(allrows[0]));w.writeheader();w.writerows(allrows)
(E/'coverage_station_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(E/'checked_date_masks.json').write_text(json.dumps({i:{y:hex(mask) for y,mask in ys.items()} for i,ys in masks.items()}),encoding='utf-8')
out=dict(status='PASS',files=len(paths),station_year_rows=len(allrows),stations_ge10_checked_years=sum(x['coverage_10years_pass'] for x in summary.values()),checked_definition='qobs not missing token AND ckhs=1; 90% of complete calendar year; qceq/qcol codes recorded only',codebook_source='Official G_appendix Timeseries_runoff.R maps Geprueft/ja/validierte Daten to 1 and Rohdaten/nein/provisorische Daten to 0; never executed',Q_numeric_conversions=0,Q_numeric_statistics=0,existing_QC_counts_only=True,synthetic_test_passed_before_real_reads=True)
(E/'coverage_scan_summary.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
