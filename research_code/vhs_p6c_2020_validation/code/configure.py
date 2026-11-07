import json,math,collections,hashlib,shutil
from pathlib import Path
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_p6c_2020_validation');B=R.parent/'vhs_p6b_external_validation'
def jw(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
cells=json.loads((R/'driver/UNIQUE_REQUIRED_GRID_CELLS.json').read_text());groups=collections.defaultdict(list)
for c in cells:groups[(math.floor(c['lon']),math.floor(c['lat']))].append(c)
tiles=[]
def rectangle(cc):
 lo=min(c['lon'] for c in cc);hi=max(c['lon'] for c in cc);so=min(c['lat'] for c in cc);no=max(c['lat'] for c in cc)
 return [no+.001,lo-.001,so-.001,hi+.001],(round((hi-lo)*10)+1)*(round((no-so)*10)+1)
def split(cc):
 a,n=rectangle(cc)
 if n>60 and n>2*len(cc):
  axis='lon' if max(c['lon'] for c in cc)-min(c['lon'] for c in cc)>=max(c['lat'] for c in cc)-min(c['lat'] for c in cc) else 'lat'
  vals=sorted(set(c[axis] for c in cc));cut=vals[len(vals)//2]
  return split([c for c in cc if c[axis]<cut])+split([c for c in cc if c[axis]>=cut])
 return [cc]
weights=json.loads((R/'driver/ALL_BASIN_GRID_WEIGHTS_FROZEN.json').read_text());reps=[2,377,533,171];rep_cells={w['grid_id'] for g in reps for w in weights[str(g)]['weights']}
for k,cc in sorted(groups.items()):
 for part in split(cc):
  a,n=rectangle(part);tiles.append({'tile_id':f'T{len(tiles):02d}','required_cells':part,'area':a,'expected_rectangle_cells':n,'need_cells':len(part),'representative_needed':any(c['grid_id'] in rep_cells for c in part)})
tiles.sort(key=lambda t:(not t['representative_needed'],t['tile_id']))
jw(R/'driver/DOWNLOAD_TILES_FROZEN.json',tiles)
protocol={'experiment':'PUBLIC_DATA_FIXED_MODEL_P6C','task':'RECONSTRUCTION_WITH_OBSERVED_MET','year':2020,'gauge_ids':list(map(int,weights)),'representatives':reps,'models':['C0+PT','P2-L1'],'fit_calls_allowed':0,'test_months':'2020-01/2020-12','historical_parity_months':'2015-01/2019-12','parity_thresholds':{'P_abs_mm':.18,'T_abs_C':.052,'P_relative_if_P_ge_36':.005},'grid_rule':'official full-upstream intersection integer-truncated area weights; frozen before scores','tile_rule':'1degree groups; split rectangle >60cells if occupancy<0.5; bbox margin .001degree','driver':'ARCO hourly deaccumulated tp; never difference; P timestamp -1h; hourly T round1/P round2; 24hour daily Psum round2/Tmean round1; month daycomplete Psum/Tmean; original2019end padding only overlap; actual2021-01-01boundary for2020','lag_Jan2020':'original source2019-12 full-month P','Q_source':'previously obtained eHYD file5 daily-mean m3/s; no fill','prior_2020_Q_exposure':'P6B ehyd parser read full downloaded archive into memory; no prior24station2020 model scores located. Not wholly blind test. This run segregates inference and scoring.','QC':'MAIN_DESCRIPTIVE complete366 finite nonnegative daily values; STRICT_SENSITIVITY additionally exclude every OWF-Q footnote applicable to month (including background regulation). Neither means daily QC certification.','day_boundary':'provider midnight intervals; timezone UTC equivalence unverified. Primary provider calendar, no score-selected shift. Fixed +/-1calendar-day sensitivity descriptive only, not a timezone conversion.','subsets':['ALL2020','Q1','Q2','Q3','Q4','DJF','MAM','JJA','SON','MAY_JUNE','LOW_train_Q20','HIGH_train_Q80'],'prediction_views':['raw','nonnegative'],'statistics':'stationequal skills mean/median, separate macro water systems, no station independence or significance claim','prediction_before_scoring':True,'P7_training':False,'official_CDS_product':'reanalysis-era5-land-timeseries','source_doi':'10.24381/ee82e357','source_license':'CC-BY; see original CDS attribution','model_registry_source':str(B/'P6B_FROZEN_PROTOCOL.json')}
jw(R/'P6C_FROZEN_PROTOCOL.json',protocol)
for n in ['configure.py','cds_download.ps1']:
 p=Path(__file__).parent/n
 if p.exists():shutil.copy2(p,R/'code'/n)
print('TILES',len(tiles),'RECTANGLES',sum(t['expected_rectangle_cells'] for t in tiles),'REP_TILES',[t['tile_id'] for t in tiles if t['representative_needed']])
print('PROTOCOL_SHA256',hashlib.sha256((R/'P6C_FROZEN_PROTOCOL.json').read_bytes()).hexdigest())
