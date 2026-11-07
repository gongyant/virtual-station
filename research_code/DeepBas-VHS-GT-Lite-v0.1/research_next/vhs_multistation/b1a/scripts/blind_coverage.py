"""Restricted date/missing/QC counter. Never converts nonmissing Q to a number."""
import csv,io,json,datetime,collections
from pathlib import Path
MISSING=frozenset(('', '-999','-999.0','-999.00','nan','na','NaN','NA'))
def summarize(stream,q_column='qobs',qc_column='checked'):
    reader=csv.DictReader(stream,delimiter=';')
    fields=reader.fieldnames or []
    if not {'YYYY','MM','DD',q_column,qc_column}<=set(fields):raise ValueError('Unsupported coverage schema; no payload returned')
    # Unknown fields cannot silently become predictors. This function emits no row payloads.
    years={};seen=set();duplicates=0;first=None;last=None
    for row in reader:
        try:date=datetime.date(int(row['YYYY']),int(row['MM']),int(row['DD']))
        except Exception:raise ValueError('Invalid date in restricted coverage input') from None
        if date in seen:duplicates+=1
        seen.add(date);first=date if first is None else min(first,date);last=date if last is None else max(last,date)
        y=years.setdefault(date.year,dict(rows=0,missing=0,nonmissing=0,qc_counts={},nonmissing_qc_counts={}))
        # Compare missing tokens only. No float conversion, sums, extrema or quantiles.
        missing=row[q_column].strip() in MISSING;qc=row[qc_column].strip()
        if len(qc)>32:raise ValueError('Invalid QC code length')
        y['rows']+=1;y['missing' if missing else 'nonmissing']+=1
        y['qc_counts'][qc]=y['qc_counts'].get(qc,0)+1
        if not missing:y['nonmissing_qc_counts'][qc]=y['nonmissing_qc_counts'].get(qc,0)+1
    return dict(first_date=first.isoformat() if first else None,last_date=last.isoformat() if last else None,unique_dates=len(seen),duplicate_dates=duplicates,years=years,qc_semantics='UNVERIFIED_UNTIL_OFFICIAL_CODEBOOK',Q_numeric_statistics_emitted=False)
def synthetic_test():
    a='YYYY;MM;DD;qobs;checked\n2000;1;1;2.3;1\n2000;1;2;-999;0\n2001;1;1;500;1\n'
    b=a.replace(';2.3;',';900000000;').replace(';500;',';-128.42;')
    out=summarize(io.StringIO(a));mut=summarize(io.StringIO(b));assert out==mut
    changed=summarize(io.StringIO(a.replace(';500;',';-999;')));assert changed!=out
    changedqc=summarize(io.StringIO(a.replace(';500;1',';500;0')));assert changedqc!=out
    try:summarize(io.StringIO('date;Q\n2000-01-01;3\n'))
    except ValueError:bad_schema=True
    else:bad_schema=False
    assert bad_schema
    forbidden={'mean','variance','std','min_Q','max_Q','quantile','correlation','NSE','KGE'}
    def keys(x):
        if isinstance(x,dict):return set(x)|set().union(*(keys(v) for v in x.values()))
        return set()
    assert not keys(out)&forbidden
    return dict(status='PASS',synthetic_only=True,tests={'nonmissing_Q_replacement_invariance':True,'missing_change_detected':True,'QC_change_detected':True,'unknown_schema_rejected':True,'no_numeric_Q_summary_keys':True},real_Q_files_read=0)
if __name__=='__main__':
    result=synthetic_test();p=Path(__file__).resolve().parents[1]/'evidence/blind_coverage_synthetic.json'
    p.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
