"""Separate public donor-training labels, heldout score labels, and Q-free covariates."""
from intake import *
import numpy as np
from pyproj import Transformer
def main():
 p=readj(ROOT/'KAZ_N1_FROZEN_PROTOCOL.json');assert sha(ROOT/'KAZ_N1_FROZEN_PROTOCOL.json')==readj(ROOT/'evidence/PROTOCOL_FREEZE.json')['sha256']
 gauges=p['PUB']['stations'];base=LAB/'vhs_p7a_hydrological_models';cache=readj(base/'cache/TRAINING_ONLY_2017.json');weather=[]
 with (LAB/'p4_final_reconstruction/source/weather.csv').open(encoding='utf-8-sig') as f:weather=list(csv.DictReader(f))
 attrpath=LAB/'p1_seasonal_meteorology_ablation/source/metadata/D_gauges/1_attributes/Gauge_attributes.csv';hierpath=LAB/'p1_seasonal_meteorology_ablation/source/metadata/B_basins_intermediate_all/1_attributes/Gauge_hierarchy.csv'
 with attrpath.open(encoding='utf-8-sig') as f:attrs={int(r['ID']):r for r in csv.DictReader(f,delimiter=';')}
 with hierpath.open(encoding='utf-8-sig') as f:hier=list(csv.DictReader(f,delimiter=';'))
 metadata=[]
 with (LAB/'p4_final_reconstruction/source/observation_metadata.csv').open(encoding='utf-8-sig') as f:metadata=list(csv.DictReader(f))
 macros={int(r['gauge_id']):r['macro'] for r in metadata};forward=Transformer.from_crs(3035,4326,always_xy=True)
 features={};statics={};admission=[]
 for g in gauges:
  w={r['date']:{'P':float(r['P']),'T':float(r['T'])} for r in weather if int(r['gauge_id'])==g and r['date']<='2017-12' and r['P'] and r['T']}
  fs=[]
  for date,val in sorted(w.items()):
   y,m=map(int,date.split('-'));pr=f'{y-1}-12' if m==1 else f'{y}-{m-1:02d}'
   if date<'1983-01' or pr not in w:continue
   fs.append({'date':date,'year':y,'month':m,**val,'L1':w[pr]['P'],'lag_date':pr})
  train=[r for r in cache[str(g)] if r['date']<='2013-12'];score=[r for r in cache[str(g)] if '2014-01'<=r['date']<='2017-12']
  assert max(r['year'] for r in train)<=2013 and all(2014<=r['year']<=2017 for r in score)
  put(ROOT/f'pub/cache/train/ID_{g}.json',{r['date']:r['Q'] for r in train});put(ROOT/f'pub/cache/score/ID_{g}.json',{r['date']:r['Q'] for r in score})
  a=attrs[g];lon,lat=forward.transform(float(a['lon']),float(a['lat']));area=float(a['area_gov']);elev=float(a['elev']);assert area>0 and -20<lon<40 and 35<lat<60
  ref=[r for r in fs if r['year']<=2013];mu=[];sd=[]
  for m in range(1,13):
   arr=np.array([[r[k] for k in ['P','T','L1']] for r in ref if r['month']==m]);mu.append(arr.mean(0).tolist());sd.append(arr.std(0,ddof=1).tolist())
  for r in fs:r['z']=[0. if sd[r['month']-1][j]<1e-12 else (r[k]-mu[r['month']-1][j])/sd[r['month']-1][j] for j,k in enumerate(['P','T','L1'])]
  features[str(g)]=fs;statics[str(g)]={'gauge_id':g,'name':a['name'],'region':a['region'],'macro':macros[g],'area_km2':area,'outlet_elev_m':elev,'lon':lon,'lat':lat,'similarity_vector':[float(np.log(area)),elev,float(np.mean([r['P'] for r in ref])),float(np.mean([r['T'] for r in ref]))],'met_reference_period':'1983-2013 all valid met months independent of Q availability/values','met_mu':mu,'met_sd':sd}
  admission.append({'gauge_id':g,'region':a['region'],'macro':macros[g],'country':'EUROPE_NOT_KAZAKHSTAN','donor_training_Q_months':len(train),'test_label_months':len(score),'test_met_months':sum(2014<=r['year']<=2017 for r in fs),'coordinate_source_crs':'EPSG:3035 transformed to4326','area_km2':area,'outlet_elev_m':elev,'quality':'same frozen P4/P7 full-day ckhs=1 source admission','label_exposure':'2014-2017 previously exposed in prior phases, development only'})
 put(ROOT/'pub/cache/FEATURES_WITHOUT_Q.json',features);put(ROOT/'pub/cache/STATIC_METADATA_WITHOUT_Q.json',statics);put(ROOT/'pub/cache/GAUGE_HIERARCHY_WITHOUT_Q.json',hier);csvout(ROOT/'pub/EU_PUB_DATA_ADMISSION.csv',admission)
 pins={str(q):sha(q) for q in [base/'cache/TRAINING_ONLY_2017.json',attrpath,hierpath,LAB/'p4_final_reconstruction/source/weather.csv']};pins.update({str(q):sha(q) for q in (ROOT/'pub/cache').rglob('*.json')});put(ROOT/'pub/CACHE_SOURCE_PINS.json',pins)
 print('EU PUB split prepared',len(gauges),'stations, train labels only<=2013; labels2014-2017 scoring role only',flush=True)
if __name__=='__main__':main()
