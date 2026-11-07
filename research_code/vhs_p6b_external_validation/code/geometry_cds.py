import struct,json,sys,hashlib,time,urllib.request,urllib.error
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,MultiPolygon,mapping
from shapely.ops import transform,unary_union
from pyproj import Transformer
sys.stdout.reconfigure(encoding='utf-8');R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation');D=R/'driver'
def jw(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def dbf(path):
 b=path.read_bytes();n=struct.unpack_from('<I',b,4)[0];h,rl=struct.unpack_from('<HH',b,8);fields=[]
 for pos in range(32,h-1,32):
  if b[pos]==13:break
  x=b[pos:pos+32];fields.append((x[:11].split(b'\0')[0].decode('ascii'),x[16]))
 rows=[]
 for i in range(n):
  line=b[h+i*rl:h+(i+1)*rl];off=1;row={}
  for k,l in fields:row[k]=line[off:off+l].decode('latin1').strip();off+=l
  rows.append(row)
 return rows
def shapes(path):
 b=path.read_bytes();p=100;out=[]
 while p<len(b):
  n=struct.unpack_from('>i',b,p+4)[0]*2;data=b[p+8:p+8+n];p+=8+n;st=struct.unpack_from('<i',data,0)[0]
  assert st==5,st
  parts,npoints=struct.unpack_from('<ii',data,36);starts=list(struct.unpack_from('<'+'i'*parts,data,44))+[npoints];coords=np.frombuffer(data,dtype='<f8',offset=44+4*parts,count=npoints*2).reshape(-1,2)
  # ESRI clockwise exterior, counterclockwise hole. Group containment independent of order.
  rings=[Polygon(coords[starts[i]:starts[i+1]]) for i in range(parts)];geom=rings[0]
  for poly in rings[1:]:geom=geom.symmetric_difference(poly)
  if not geom.is_valid:geom=geom.buffer(0)
  out.append(geom)
 return out
if sys.argv[1]=='geometry':
 attrs=dbf(D/'Basins_A.dbf');grid=dbf(D/'Grid_ERA5L.dbf');print('DBF_EXAMPLES',attrs[0],grid[0],flush=True)
 basins=shapes(D/'Basins_A.shp');cells=shapes(D/'Grid_ERA5L.shp');idx=next(i for i,a in enumerate(attrs) if a.get('ID')=='818');basin=basins[idx];w=[];tf=Transformer.from_crs(3035,4326,always_xy=True)
 for a,g in zip(grid,cells):
  area=basin.intersection(g).area
  if area>0:
   lon,lat=tf.transform(g.centroid.x,g.centroid.y);w.append({'grid_attributes':a,'intersection_area_m2':area,'weight':area/basin.area,'lon_centroid':lon,'lat_centroid':lat})
 assert abs(sum(x['weight'] for x in w)-1)<1e-8
 geo=transform(tf.transform,basin);jw(D/'ID818_BASIN.geojson',{'type':'Feature','properties':attrs[idx],'geometry':mapping(geo)})
 jw(D/'ID818_OFFICIAL_GRID_WEIGHTS.json',{'crs':'EPSG:3035','basin_attributes':attrs[idx],'basin_area_m2':basin.area,'weights_sum':sum(x['weight'] for x in w),'weights':w,'method':'intersection area / basin area, official LamaH basin A and Grid_ERA5L polygons','basin_bounds_wgs84':list(geo.bounds)})
 # Correct initial precision assumption from observed source formatting, before new meteorology downloaded/compared.
 old=json.loads((D/'PARITY_CRITERIA_FROZEN.json').read_text());jw(D/'PARITY_CRITERIA_INITIAL_SUPERSEDED.json',old)
 old.update(version=2,amendment_reason='Read actual LamaH daily header/data: P published to .01 mm, T to .1C, not .0001/.001 as initially assumed. No new driving time series or Q scores inspected.',strict_tolerance={'P_absolute_mm_month':.18,'P_relative_when_month_P_ge36mm':.005,'T_absolute_degC':.052},tolerance_basis='31*.005mm <= .155mm monthly rounding; .05C daily rounding bound. Modest .025mm/.002C numerical allowance. All monthly checks must pass; no bias adjustment or Q-conditioned tuning.')
 jw(D/'PARITY_CRITERIA_FROZEN.json',old);print('WEIGHTS',w,flush=True)
else:
 fields={}
 for line in (Path.home()/'.cdsapirc').read_text().splitlines():
  if ':' in line:k,v=line.split(':',1);fields[k.strip()]=v.strip()
 headers={'PRIVATE-TOKEN':fields['key'],'Content-Type':'application/json','User-Agent':'VHS-P6B-research/1.0'};base=fields['url'].rstrip('/')+'/retrieve/v1'
 def request(url,payload=None):
  try:
   req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload else None,headers=headers)
   with urllib.request.urlopen(req,timeout=45) as f:return {'http':f.status,'body':json.load(f)}
  except urllib.error.HTTPError as e:return {'http':e.code,'body':e.read(50000).decode().replace(fields['key'],'[REDACTED]')}
  except Exception as e:return {'http':'FAILED','body':str(e).replace(fields['key'],'[REDACTED]')}
 if sys.argv[1]=='submit':
  assert not (D/'CDS_YEAR_JOBS.json').exists();geo=json.loads((D/'ID818_OFFICIAL_GRID_WEIGHTS.json').read_text());ws=geo['weights'];lons=[x['lon_centroid'] for x in ws];lats=[x['lat_centroid'] for x in ws];area=[round(max(lats)+.1,1),round(min(lons)-.1,1),round(min(lats)-.1,1),round(max(lons)+.1,1)];jobs=[]
  for y in range(2015,2021):
   payload={'inputs':{'variable':['2m_temperature','total_precipitation'],'year':[str(y)],'month':[f'{m:02d}' for m in range(1,13)],'day':[f'{d:02d}' for d in range(1,32)],'time':[f'{h:02d}:00' for h in range(24)],'area':area,'data_format':'netcdf','download_format':'unarchived'}}
   result=request(base+'/processes/reanalysis-era5-land/execution',payload);jobs.append({'year':y,'request':payload,'submission':result});jw(D/'CDS_YEAR_JOBS.json',jobs);print('SUBMITTED',y,result['http'],result['body'].get('jobID') if isinstance(result['body'],dict) else result['body'][:200],flush=True)
  # Jan1 2021 UTC00 supplies Dec31 2020 precipitation, Jan1 2015 original request already supplies preceding boundary.
  payload={'inputs':{'variable':['total_precipitation'],'year':['2021'],'month':['01'],'day':['01'],'time':['00:00'],'area':area,'data_format':'netcdf','download_format':'unarchived'}}
  jobs.append({'year':2021,'request':payload,'submission':request(base+'/processes/reanalysis-era5-land/execution',payload)});jw(D/'CDS_YEAR_JOBS.json',jobs)
 elif sys.argv[1]=='poll':
  records=[]
  jobs=json.loads((D/'CDS_YEAR_JOBS.json').read_text()) if (D/'CDS_YEAR_JOBS.json').exists() else []
  initial=json.loads((D/'CDS_REAL_ACCESS_RESULT.json').read_text());jobs.append({'year':'minimal2020','submission':{'body':initial.get('response',{})}})
  for j in jobs:
   jobid=j['submission']['body'].get('jobID') if isinstance(j['submission']['body'],dict) else None
   if not jobid:continue
   res=request(base+'/jobs/'+jobid);records.append({'year':j['year'],'jobID':jobid,**res});print('CDS_STATUS',j['year'],res['body'].get('status') if isinstance(res['body'],dict) else res['body'],flush=True)
   if isinstance(res['body'],dict) and res['body'].get('status')=='successful':
    out=request(base+'/jobs/'+jobid+'/results');jw(D/f'CDS_RESULTS_{j["year"]}.json',out)
    for link in (out['body'].get('asset',{}).get('value',{}),):
     url=link.get('href');p=D/f'ERA5L_{j["year"]}.nc'
     if url and not p.exists():
      with urllib.request.urlopen(url,timeout=60) as f:b=f.read(200_000_001)
      assert len(b)<=200_000_000;p.write_bytes(b);print('DOWNLOADED_CDS',j['year'],len(b),flush=True)
  jw(D/'CDS_CURRENT_STATUS.json',records)
