from common import *
import numpy as np,pandas as pd,geopandas as gpd,shapely,math
from pyproj import Geod
G=Geod(ellps='WGS84');CHECK=[]
def ck(n,v,**detail):CHECK.append({'check':n,'passed':bool(v),**detail})
def vincenty(p1,p2):
 # Independent WGS84 inverse implementation, no PROJ/Geod call.
 a=6378137.;f=1/298.257223563;b=a*(1-f);lon1,lat1=map(math.radians,p1);lon2,lat2=map(math.radians,p2)
 if p1==p2:return 0.
 U1=math.atan((1-f)*math.tan(lat1));U2=math.atan((1-f)*math.tan(lat2));s1,c1=math.sin(U1),math.cos(U1);s2,c2=math.sin(U2),math.cos(U2);L=lon2-lon1;lam=L
 for _ in range(200):
  sn,cs=math.sin(lam),math.cos(lam);sins=math.hypot(c2*sn,c1*s2-s1*c2*cs)
  if sins==0:return 0.
  coss=s1*s2+c1*c2*cs;sigma=math.atan2(sins,coss);sina=c1*c2*sn/sins;cos2a=1-sina*sina;cos2m=coss-2*s1*s2/cos2a if cos2a>1e-20 else 0;C=f/16*cos2a*(4+f*(4-3*cos2a));nlam=L+(1-C)*f*sina*(sigma+C*sins*(cos2m+C*coss*(-1+2*cos2m*cos2m)))
  if abs(nlam-lam)<1e-13:break
  lam=nlam
 else:raise ValueError('VINCENTY_NOT_CONVERGED')
 usq=cos2a*(a*a-b*b)/(b*b);A=1+usq/16384*(4096+usq*(-768+usq*(320-175*usq)));B=usq/1024*(256+usq*(-128+usq*(74-47*usq)));ds=B*sins*(cos2m+B/4*(coss*(-1+2*cos2m*cos2m)-B/6*cos2m*(-3+4*sins*sins)*(-3+4*cos2m*cos2m)))
 return b*A*(sigma-ds)/1000
def independent(g):
 return sum(vincenty(tuple(a),tuple(b)) for line in shapely.get_parts(g) if line.geom_type=='LineString' for a,b in zip(list(line.coords)[:-1],list(line.coords)[1:]))
def main():
 event('independent_spatial_QA','STARTED');path=ROOT/'P8_NATIONAL_RIVER_REACHES.gpkg';n=gpd.read_file(path,layer='national_reaches');f=gpd.read_file(path,layer='basin_fragments');b=gpd.read_file(path,layer='basins_source');p=read(ROOT/'P8_FROZEN_PROTOCOL.json');csv=pd.read_csv(ROOT/'P8_RIVER_LENGTH_BY_BASIN_ORDER.csv');aq=read(ROOT/'evidence/BASIN_AREA_QA.json');src=read(ROOT/'evidence/GLOBAL_RIVER_SOURCE_CHECK.json')
 ck('frozen_protocol',sha(ROOT/'P8_FROZEN_PROTOCOL.json')==read(ROOT/'evidence/PROTOCOL_FREEZE.json')['sha256']);ck('official_global_source_count',src['features']==8477883);ck('global_unique_ids',src['unique_HYRIV_ID']==src['features']);ck('national_unique_ids',not n.HYRIV_ID.duplicated().any());ck('fragment_unique_ids',not f.fragment_id.duplicated().any());ck('eight_valid_basins',len(b)==8 and b.is_valid.all());ck('global_KAZ_regions_AS_EU_SI',set(src['regional_ID_prefix_counts'])=={'2','3','4'})
 ck('partition_length_conservation_20m',abs(aq['partition_length_difference_km'])<0.02,difference_km=aq['partition_length_difference_km']);ck('positive_lengths',bool((n.length_km>0).all() and (f.length_km>0).all()));ck('valid_national_geometry',bool(n.is_valid.all()));ck('valid_fragment_geometry',bool(f.is_valid.all()))
 ck('vincenty_known_equatorial_degree',abs(vincenty((0,0),(1,0))-111.31949079327357)<1e-7)
 rng=np.random.default_rng(804);inds=set(rng.choice(len(f),min(1000,len(f)),replace=False).tolist())
 for _,d in f.groupby(['basin_id','ORD_CLAS_GROUP']):inds.add(int(d.index[0]))
 sample=[]
 for i in sorted(inds):
  r=f.iloc[i];v=independent(r.geometry);err=abs(v-float(r.length_km));ck('independent_vincenty_'+str(r.fragment_id),err<1e-5,error_km=err);sample.append({'fragment_id':r.fragment_id,'HYRIV_ID':int(r.HYRIV_ID),'basin_id':int(r.basin_id),'ORD_CLAS':int(r.ORD_CLAS),'Geod_saved_km':float(r.length_km),'Vincenty_independent_km':v,'absolute_error_km':err})
 csvout(ROOT/'evidence/INDEPENDENT_LENGTH_SAMPLE.csv',sample)
 # Independent aggregation from persisted geometry; no import of production stats functions.
 lengths=np.array([G.geometry_length(g)/1000 for g in f.geometry]);ck('persisted_geometry_recalculates_lengths',bool(np.allclose(lengths,f.length_km,rtol=1e-10,atol=1e-9)))
 for _,r in csv.iterrows():
  d=n if r.scope=='NATIONAL' else f
  if r.scope=='EIGHT_BASIN' or r.scope=='UNASSIGNED':d=d[d.basin_id==int(r.basin_id)]
  elif r.scope=='EIGHT_ASSIGNED_TOTAL':d=d[d.basin_id>0]
  elif r.scope=='SIX_SUBSET_TOTAL':d=d[d.basin_name.isin(p['six_scope'])]
  k=str(r.order_group)
  if k in ['1','2','3']:d=d[d[r.order_system]==int(k)]
  elif k=='4_PLUS':d=d[d[r.order_system]>=4]
  elif k=='UNCLASSIFIED':d=d[d[r.order_system].isna()|(d[r.order_system]<1)]
  ck('aggregate_'+str(r.scope)+'_'+str(r.basin_id)+'_'+r.order_system+'_'+k,abs(float(d.length_km.sum())-r.river_length_km)<1e-7)
 for (scope,bid,order),d in csv.groupby(['scope','basin_id','order_system']):ck('grade_sum_'+scope+'_'+str(bid)+'_'+order,abs(d.loc[d.order_group!='ALL','river_length_km'].sum()-d.loc[d.order_group=='ALL','river_length_km'].iloc[0])<1e-7)
 dupgeom=int(pd.Series(shapely.to_wkb(shapely.normalize(n.geometry.array))).duplicated().sum());ck('no_duplicate_national_geometries',dupgeom==0,count=dupgeom)
 gauges=pd.read_csv(ROOT/'P8_OFFICIAL_GAUGE_CROSSWALK.csv');cand=pd.read_csv(ROOT/'P8_KAZ_N1_CANDIDATE_RECHECK.csv');den=pd.read_csv(ROOT/'P8_REAL_GAUGE_DENSITY.csv')
 ck('334_actual_QazSu_records',len(gauges)==334);ck('no_duplicate_gauge_codes',not gauges.station_code.duplicated().any());ck('1230_readonly_candidate_rechecks',len(cand)==1230);ck('candidate_admission_stays0',not cand.admitted_virtual_gauge.any());ck('unreconciled_density_is_NA',den.complete_official_density_per_1000km.isna().all());ck('no_Q_columns_in_crosswalk',not set(gauges.columns)&{'q','q_mean','q_08'})
 for i,r in den.iterrows():
  if r.river_length_km>0:ck('density_equation_'+str(i),abs(r.matched_subset_density_per_1000km-1000*r.matched_QazSu_geometric_subset_count/r.river_length_km)<1e-10)
 hist=read(ROOT/'evidence/HISTORY_BEFORE.json');bad=[x for x,h in hist.items() if not pathlib.Path(x).exists() or sha(x)!=h];put(ROOT/'evidence/HISTORY_FINAL_CHECK.json',{'checked':len(hist),'passed':len(hist)-len(bad),'failed':len(bad),'failures':bad});ck('historical_hashes_unchanged',not bad,count=len(hist))
 result={'passed':sum(r['passed'] for r in CHECK),'failed':sum(not r['passed'] for r in CHECK),'checks':CHECK,'independent_length_algorithm':'WGS84 Vincenty inverse per vertex, independent of PROJ','independent_sample_n':len(sample),'max_independent_length_error_km':max(x['absolute_error_km'] for x in sample),'fit_calls':0,'Q_scoring_calls':0,'history_checked':len(hist),'basin_area_QA':aq,'national_source_metadata':src}
 put(ROOT/'P8_SPATIAL_QA.json',result);event('independent_spatial_QA','FINISHED',passed=result['passed'],failed=result['failed']);print(json.dumps({k:v for k,v in result.items() if k not in ['checks','national_source_metadata','basin_area_QA']},ensure_ascii=False));assert result['failed']==0
if __name__=='__main__':main()
