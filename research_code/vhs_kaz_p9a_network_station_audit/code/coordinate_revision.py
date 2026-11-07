from common import *
import shutil,requests
old=ROOT/'P9A_FROZEN_PROTOCOL.json';before=sha(old)
shutil.copyfile(old,ROOT/'evidence/P9A_PROTOCOL_INITIAL.json')
p=read(old);p['revision']='P9A_COORDINATE_IMPLEMENTATION_V2';p['projected_CRS']='+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs';p['revision_reason']='Make station-offset and pilot-spacing projection explicitly identical to P8; source graph and original P8 snap eligibility unchanged; no model scores involved'
js(old,p);js(ROOT/'evidence/PROTOCOL_REVISION.json',dict(old_sha256=before,new_sha256=sha(old),reason=p['revision_reason'],pre_Q_scoring=True,old_retained='evidence/P9A_PROTOCOL_INITIAL.json'))
event('coordinate_projection_revision',before=before,after=sha(old),reason=p['revision_reason'])
url='https://meteo.kazhydromet.kz/database_hydro_en';r=dict(url=url,selection='exact Hydrological database link on official meteo_db page',utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
try:
    resp=requests.get(url,timeout=(10,25));dest=ROOT/'source/OFFICIAL_HYDRO_DATABASE.html';dest.write_bytes(resp.content);r.update(status=resp.status_code,final_url=resp.url,bytes=len(resp.content),sha256=sha(dest))
except Exception as e:r['error']=f'{type(e).__name__}: {e}'
js(ROOT/'source/OFFICIAL_HYDRO_DATABASE_ATTEMPT.json',r);event('official_hydro_database_attempt',**r)
