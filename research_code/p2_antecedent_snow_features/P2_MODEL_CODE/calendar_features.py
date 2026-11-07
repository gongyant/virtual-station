"""Date-aware exogenous weather features; never accepts discharge."""
import math
def previous_month(year,month,k=1):
 v=year*12+month-1-k;return v//12,v%12+1
def construct(year,month,weather):
 keys=[(year,month)]+[previous_month(year,month,k) for k in (1,2,3)]
 rs=[weather.get(k) for k in keys]
 valid=[r is not None and r["met_complete"] and all(math.isfinite(r[n]) for n in ("P","T")) for r in rs]
 if not all(valid):return None,{"status":"MISSING_REQUIRED_WEATHER","missing_dates":[f"{y}-{m:02d}" for (y,m),v in zip(keys,valid) if not v],"antecedent_dates":[f"{y}-{m:02d}" for y,m in keys[1:]]}
 current=rs[0];cold=[r["P"] if r["T"]<=0 else 0. for r in rs[1:]];s=sum(cold)
 return {"P":current["P"],"T":current["T"],"L1":rs[1]["P"],"S":s,"M":s*max(current["T"],0.)},{"status":"SUPPORTED","antecedent_dates":[f"{y}-{m:02d}" for y,m in keys[1:]],"cold_months":sum(r["T"]<=0 for r in rs[1:]),"S_zero":s==0,"M_zero":s*max(current["T"],0.)==0}
