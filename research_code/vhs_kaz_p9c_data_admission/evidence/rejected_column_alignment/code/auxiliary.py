from acquire import *
import pandas as pd,numpy as np,geopandas as gpd,pyogrio,shapely
from shapely.geometry import Point
from pyproj import Geod
from catchment import area
def out(name,rows):pd.DataFrame(rows).to_csv(ROOT/name,index=False,encoding='utf-8-sig',na_rep='N/A',float_format='%.12g')
if __name__=='__main__':
 p=ROOT/'source/Water_cycle_components_in_BLB.xlsx';actual_md5=hashlib.md5(p.read_bytes()).hexdigest();assert actual_md5=='53a83e76e786fe28dbf9768da1e25a5f'
 windows={'Uushzharma':(1939,1985),'Kapchagay_down':(1930,2000),'Dobyn':(1929,2014),'Yamate':(1949,1986),
 'Tekes_kafuqihai':(1956,1979),'Kunes_zeketai':(1960,1979),'Kashi_tuohai':(1953,2015),'Tekeli':(1940,1985),'Ushtobe':(1939,1985),'Lepsy':(1936,1985),'Lepsinsk':(1936,1985),'Chann':(1936,1981),'Ayaguz':(1949,1986)}
 x=pd.ExcelFile(p);summ=[];annual=[]
 for name in x.sheet_names:
  d=x.parse(name);lo,hi=windows[name];qs=pd.to_numeric(d['Runoff (mm)'],errors='coerce');years=pd.to_numeric(d.Time,errors='raise').astype(int)
  assert years.is_unique
  for i,r in d.iterrows():
   y=int(r.Time);q=r['Runoff (mm)'];within=lo<=y<=hi
   annual.append(dict(sheet=name,year=y,runoff_mm_annual=q,T_K_annual=r['Ta (K)'],P_mm_annual=r['Pre (mm)'],
    stated_observation_period=f'{lo}-{hi}',origin_class='WITHIN_DECLARED_OBSERVATION_WINDOW_BUT_ROW_OBSERVED_FLAG_NOT_PROVIDED' if within else 'OUTSIDE_STATED_OBSERVATION_WINDOW_CONSTRUCTED_OR_INFILL',
    runoff_available=bool(pd.notna(q)),independent_observed_monthly_Q_admitted=False))
  summ.append(dict(sheet=name,rows=len(d),climate_start=int(years.min()),climate_end=int(years.max()),annual_runoff_nonmissing=int(qs.notna().sum()),
   annual_runoff_first=int(years[qs.notna()].min()),annual_runoff_last=int(years[qs.notna()].max()),
   stated_observation_first=lo,stated_observation_last=hi,raw_observed_rows_separately_identified=0,
   runoff_unit='mm_annual_not_m3s',raw_monthly_Q_available=False,training_label_status='NOT_ADMITTED_RECONSTRUCTED_MIXTURE_WITHOUT_ROW_MASK'))
 out('data/ZENODO_ANNUAL_MIXED_RUNOFF_AUDIT.csv',annual);out('data/ZENODO_SHEET_INVENTORY.csv',summ)
 js(ROOT/'evidence/ZENODO_ACTUAL_CONTENT_QC.json',dict(file_bytes=p.stat().st_size,MD5=actual_md5,official_MD5_matches=True,
  sheets=len(summ),annual_rows=len(annual),nonmissing_annual_runoff=sum(x['annual_runoff_nonmissing'] for x in summ),
  actual_runoff_period='1950-2014',climate_period='1950-2021',time_resolution='annual',raw_observed_row_flag_available=False,
  no_monthly_inference=True,license='CC_BY4.0_ZENODO_API',formal_observed_labels_admitted=0))
 # Recheck the existing interior-point/source-host conflict without modifying P9B.
 status=pd.read_csv(OLD/'P9B_CATCHMENT_DELINEATION_STATUS.csv');points=pyogrio.read_dataframe(OLD/'P9B_FIRST_BASIN_GIS.gpkg',layer='engineering_candidates').set_index('station_id')
 hb_path=Path('E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/data/raw/hydrobasins/hybas_as_lev12_v1c.shp')
 conflicts=[];geo=[]
 for r in status[status.catchment_state.str.contains('SOURCE_CONFLICT')].itertuples():
  pt=points.loc[r.candidate_id].geometry;near=pyogrio.read_dataframe(hb_path,bbox=(pt.x-.1,pt.y-.1,pt.x+.1,pt.y+.1))
  containing=near[near.geometry.map(lambda a:a.covers(pt))]
  assigned=pyogrio.read_dataframe(hb_path,where=f'HYBAS_ID = {int(r.source_host_HYBAS_L12)}')
  for typ,d in [('SOURCE_REACH_ASSIGNED_HOST',assigned),('ACTUAL_POINT_CONTAINING_L12_UNIT',containing)]:
   for row in d.itertuples():
    geo.append(dict(candidate_id=r.candidate_id,role=typ,HYBAS_ID=int(row.HYBAS_ID),NEXT_DOWN=int(row.NEXT_DOWN),UP_AREA=float(row.UP_AREA),geometry=row.geometry))
  conflicts.append(dict(candidate_id=r.candidate_id,source_assigned_host=int(r.source_host_HYBAS_L12),source_host_contains_point=bool(assigned.geometry.iloc[0].covers(pt)),
   point_containing_hosts='|'.join(str(int(a)) for a in containing.HYBAS_ID),containing_host_count=len(containing),
   finding='SOURCE_REACH_HOST_DIFFERS_FROM_INTERIOR_POINT_UNIT;retainednotcertified;neitheroutletproxyequalsanexactpointcatchment',
   exact_point_area_km2=None,source_point_longitude=pt.x,source_point_latitude=pt.y))
 out('data/P9C_LEGACY_HOST_CONFLICTS.csv',conflicts)
 if geo:gpd.GeoDataFrame(geo,geometry='geometry',crs=4326).to_file(ROOT/'P9C_CATCHMENT_GIS.gpkg',layer='legacy_host_conflict',driver='GPKG',engine='pyogrio')
 duplicates=[];G=Geod(ellps='WGS84')
 for host,d in status.groupby('source_host_HYBAS_L12'):
  if len(d)<2:continue
  for i,a in enumerate(d.itertuples()):
   for b in list(d.itertuples())[i+1:]:
    pa,pb=points.loc[a.candidate_id],points.loc[b.candidate_id]
    duplicates.append(dict(candidate_a=a.candidate_id,candidate_b=b.candidate_id,source_host=host,
     point_geodesic_distance_m=G.inv(pa.geometry.x,pa.geometry.y,pb.geometry.x,pb.geometry.y)[2],
     exact_area_a_km2=None,exact_area_b_km2=None,area_equality_proven=False,
     limitation='SAME_OUTLET_PROXY_NOT_SAME_POINT_CATCHMENT;crossborderupstreamrequiresadditionaltiles;notdelineatedthispilot'))
 out('data/P9C_DUPLICATE_PROXY_DIAGNOSTICS.csv',duplicates)
 js(ROOT/'evidence/NEW_INPUT_EXPOSURE_LEDGER.json',dict(WB='1936-2020 archive parsed for numericalQC and coverage;all4targetQused for admission;notblindfuturetest',
  Zenodo='all13sheets1950-2014constructedannualrunoffand1950-2021climateparsed;notindependentQ',
  P9B='2021-03..2024-02reportedmonthlyQand194pagebulletinpreviouslyexposed;36Lepsyconflictsremainquarantined;nohistoricalstitch',
  future_holdout='FUTURE_HOLDOUT_NOT_AVAILABLE',models_scored=0))
 event(stage='auxiliary_real_source_and_host_checks_complete',annual_sheets=len(summ),annual_Q_not_admitted=True,legacy_conflicts=len(conflicts),duplicate_proxy_pairs=len(duplicates))
