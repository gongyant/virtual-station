"""Independent national arithmetic, real GIS identities and serialized PUB predictions."""
from intake import *
import numpy as np,geopandas as gpd
from pyproj import Transformer
from shapely.geometry import shape,Point
from scipy.spatial import cKDTree
CHECKS=[]
def ck(n,v):CHECKS.append({'name':n,'passed':bool(v)});assert v,n
def rows(p):
 with open(p,encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def main():
 b=readj(ROOT/'KAZ_N1_OFFICIAL_BASELINE.json');ck('official_partitions',b['N_real_all']==b['N_real_river']+b['lake_posts']+b['marine_posts']+b['marine_hydrometeorological_stations']==b['permanent']+b['seasonal'])
 for r in rows(ROOT/'KAZ_N1_BASELINE_DENSITY.csv'):
  ck(r['scope']+'_density',abs(float(r['stations_per_km2'])-int(r['N'])/2724900)<1e-18);ck(r['scope']+'_per10000',abs(float(r['stations_per_10000_km2'])-int(r['N'])/272.49)<1e-12)
 for r in rows(ROOT/'KAZ_N1_NATIONAL_DENSITY_SCENARIOS.csv'):ck('actual_no_density_gain_'+r['scenario'],int(r['added_actual_virtual_count'])==0 and abs(float(r['density_per_km2'])-394/2724900)<1e-18)
 for p,h in readj(ROOT/'evidence/GIS_SOURCE_HASHES.json').items():ck('GIS_source_hash_'+p,sha(p)==h)
 country=gpd.read_file(ROOT/'source/KAZ_COUNTRY_BOUNDARY.geojson').geometry.iloc[0];forward=Transformer.from_crs(4326,'+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs',always_xy=True)
 from shapely.ops import transform
 cp=transform(forward.transform,country);geo=readj(ROOT/'KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson');ids=[r['properties']['station_id'] for r in geo['features']];ck('actual_geometry_count1230',len(ids)==1230 and len(set(ids))==len(ids));xy=[]
 source=gpd.read_file(REPO/'data/raw/hydrorivers/HydroRIVERS_v10_as.shp',bbox=tuple(country.bounds),columns=['HYRIV_ID','NEXT_DOWN','LENGTH_KM','DIST_DN_KM','UPLAND_SKM','CATCH_SKM'],engine='pyogrio').to_crs('+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs');rivers={int(r.HYRIV_ID):r for r in source.itertuples()}
 for f in geo['features']:
  p=f['properties'];lon,lat=f['geometry']['coordinates'];x,y=forward.transform(lon,lat);pt=Point(x,y);xy.append((x,y));rv=rivers[p['reach_id']]
  ck('real_country_point_'+p['station_id'],cp.contains(pt) and pt.distance(cp.boundary)>=1999.99)
  ck('real_assigned_river_'+p['station_id'],pt.distance(rv.geometry)<.1)
  ck('fixed_distance_grid_'+p['station_id'],p['network_distance_from_sink_km']%25==0 and p['upstream_area_lower_bound_km2']>=1000)
  ck('no_false_model_capability_'+p['station_id'],p['virtual_prediction_available'] is False and p['research_admitted'] is False and p['candidate_admitted'] is False)
 ck('no_duplicate_geometry_within3km',not cKDTree(np.array(xy)).query_pairs(2999.99))
 seal=readj(ROOT/'pub/PREDICTIONS_SEALED.json');ck('prediction_seal',sha(ROOT/'KAZ_N1_UG_PREDICTIONS.csv')==seal['sha256']);pred=rows(ROOT/'KAZ_N1_UG_PREDICTIONS.csv');ck('unique_PUB_prediction_identity',len(pred)==len({(r['scheme'],r['gauge_id'],r['date'],r['model_id']) for r in pred}))
 features=readj(ROOT/'pub/cache/FEATURES_WITHOUT_Q.json');static=readj(ROOT/'pub/cache/STATIC_METADATA_WITHOUT_Q.json');models={};maxerr=0
 for r in pred:
  g=r['gauge_id'];key=(r['scheme'],g)
  if key not in models:
   p=ROOT/f'pub/models/{key[0]}/ID_{g}/model.json';models[key]=readj(p);ck('model_hash_'+str(key),sha(p)==r['model_hash']);ck('heldout_mask_'+str(key),int(g) not in models[key]['allowed_Q_donors'] and int(g) in models[key]['removed_Q_stations_all_dates'])
  m=models[key];fs=next(a for a in features[g] if a['date']==r['date']);mi=fs['month']-1;method=r['model_id'];area=static[g]['area_km2']
  if method=='DONOR_CLIMATOLOGY_BASELINE':value=m['donor_climate_baseline_specific'][mi]*area/86.4
  else:
   if method=='REGIONAL_SHARED_RIDGE':
    mm=m['regional'];ss=(np.array(static[g]['similarity_vector'][:2])-np.array(m['donor_static_mean']))/np.array(m['donor_static_sd']);angle=2*np.pi*fs['month']/12;X=fs['z']+ss.tolist()+(ss*np.sin(angle)).tolist()+(ss*np.cos(angle)).tolist()
   else:
    donor=m['nearest_donor'] if method=='GEOGRAPHIC_DONOR_TRANSFER' else m['similar_donor'];mm=m['donor_models'][str(donor)];X=fs['z']
   value=(mm['climate_specific_mm_day'][mi]+sum((x-mu)*beta for x,mu,beta in zip(X,mm['X_train_month_mean'][mi],mm['beta'])))*area/86.4
  err=abs(value-float(r['qsim_raw']));maxerr=max(maxerr,err);ck('PUB_parameter_reconstruction_'+str((key,r['date'],method)),err<1e-10*max(1,abs(value)))
 for a in readj(ROOT/'pub/TARGET_MASK_AUDIT.json'):
  ck('all_Q_template_mask_'+str((a['scheme'],a['target'])),a['target_all_Q_excluded'] and a['all_nested_donors_excluded'] and a['target_Q_file_open_denied'] and a['future_score_Q_open_denied'])
  if a['scheme']=='LEAVE_MACRO_REGION_OUT':ck('macro_Q_mask_'+str(a['target']),a['same_macro_Q_excluded'])
 labels={int(g):readj(ROOT/f'pub/cache/score/ID_{g}.json') for g in static}
 for r in rows(ROOT/'KAZ_N1_UG_VALIDATION_METRICS.csv'):
  rs=[a for a in pred if a['scheme']==r['scheme'] and a['gauge_id']==r['gauge_id'] and a['model_id']==r['model_id'] and a['date'] in labels[int(r['gauge_id'])]];y=np.array([labels[int(r['gauge_id'])][a['date']] for a in rs]);pp=np.array([float(a['qsim_raw']) for a in rs]);pp=np.maximum(pp,0) if r['analysis']=='NONNEGATIVE_SECONDARY' else pp;e=pp-y
  direct={'MSE':float(e@e/len(y)),'RMSE':float(np.sqrt(e@e/len(y))),'MAE':float(np.mean(abs(e))),'NSE':float(1-e@e/np.sum((y-y.mean())**2)),'KGE':float(1-np.sqrt((np.corrcoef(y,pp)[0,1]-1)**2+(np.std(pp)/np.std(y)-1)**2+(pp.mean()/y.mean()-1)**2)) if np.std(pp)>0 and np.std(y)>0 and abs(y.mean())>1e-12 else None,'PBIAS':float(100*e.sum()/y.sum())}
  for name,value in direct.items():ck('independent_metric_'+str((r['scheme'],r['gauge_id'],r['model_id'],r['analysis'],name)),r[name]=='' and 'UNDEFINED_KGE_COMPONENT' in r['reason'] if value is None else abs(value-float(r[name]))<=1e-9*max(1,abs(value)))
 put(ROOT/'evidence/INDEPENDENT_NUMERICAL_VERIFICATION.json',{'passed':len(CHECKS),'failed':0,'fit_calls':0,'max_PUB_prediction_reconstruction_error_m3s':maxerr,'checks':CHECKS})
 print('independent checks',len(CHECKS),'passed; prediction max error',maxerr,flush=True)
if __name__=='__main__':main()
