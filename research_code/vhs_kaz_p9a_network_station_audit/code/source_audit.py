from common import *
import requests,re
from urllib.parse import urljoin
s=requests.Session();s.headers['User-Agent']='VHS-P9A public research source verification'
urls=[('kazhydromet_network','https://www.kazhydromet.kz/en/hydrological-monitoring/interaktivnaya-karta-gidrologicheskogo-monitoringa'),('kazhydromet_map','http://ecodata.kz:3838/app_dg_map_en/'),('kazhydromet_archive','https://www.kazhydromet.kz/en/archive')]
records=[];links=[]
for label,url in urls:
    rec=dict(label=label,url=url,accessed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),timeout_seconds=25)
    try:
        r=s.get(url,timeout=(10,25));rec.update(status=r.status_code,final_url=r.url,bytes=len(r.content),content_type=r.headers.get('Content-Type'))
        p=ROOT/'source'/f'{label}.html';p.write_bytes(r.content);rec['sha256']=sha(p);rec['path']=str(p)
        if r.ok:
            for href,title in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',r.text,re.S|re.I):
                title=re.sub('<[^>]+>',' ',title);links.append(dict(source=url,title=re.sub(r'\s+',' ',title).strip(),url=urljoin(r.url,href)))
            if label=='kazhydromet_network':
                txt=re.sub('<[^>]+>',' ',r.text);txt=re.sub(r'\s+',' ',txt)
                (ROOT/'source/kazhydromet_network_text.txt').write_text(txt,encoding='utf-8')
                rec['numeric_claims_found']={str(x):bool(re.search(r'\b'+str(x)+r'\b',txt)) for x in [442,394,38,10,381,61]}
    except Exception as e:rec['error']=f'{type(e).__name__}: {e}'
    records.append(rec);event('official_source_attempt',**rec)
csv(ROOT/'source/OFFICIAL_PAGE_LINKS.csv',links);js(ROOT/'source/DOWNLOAD_LOG.json',records)
raw=read(P8/'source/qazsu_hydroposts_response.json');features=raw['features']
cross=pd.read_csv(P8/'P8_OFFICIAL_GAUGE_CROSSWALK.csv',dtype={'station_code':str})
properties={str(f['properties']['code']):f for f in features}
out=[]
for r in cross.to_dict('records'):
    f=properties[r['station_code']];p=f['properties'];lon,lat=f['geometry']['coordinates'][:2]
    # The archived public feature includes current/average Q; values are NOT copied to P9A.
    r.update(official_certification='NOT_CONFIRMED',identity_grade='GEOMETRIC_PROVISIONAL' if r['primary_500m_geometric_match'] else ('AMBIGUOUS_GEOMETRY' if 'AMBIG' in str(r['reason_codes']).upper() else 'NOT_GEOMETRICALLY_ADMITTED'),
        coordinate_axis_verified=(abs(lon-r['longitude'])<1e-8 and abs(lat-r['latitude'])<1e-8),attribute_x_lat_verified=abs(float(p['x'])-lat)<=0.00005001,attribute_y_lon_verified=abs(float(p['y'])-lon)<=0.00005001,attribute_coordinate_decimal_places=4,
        source_name_exact_match=p.get('name')==r['station_name'],source_code_exact_match=str(p['code'])==r['station_code'],source_record_identity='QAZSU_ARCHIVED_PUBLIC_FEATURE',
        official394_membership='UNVERIFIED_NO_EXPORTABLE_CANONICAL_CATALOG',historical_Q_state='NOT_ACQUIRED',historical_Q_start='N/A',historical_Q_end='N/A',Q_unit='UNVERIFIED',daily_QC='NOT_PROVIDED',historical_Q_license='NOT_ESTABLISHED',
        current_mean_Q_not_a_training_series=True,source_public_map_not_automatically_open_reuse_license=True,hydrorivers_named_river_identity='UNVERIFIABLE_NO_NAME_FIELD')
    out.append(r)
csv(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',out)
js(ROOT/'evidence/GAUGE_IDENTITY_AUDIT.json',dict(records=len(out),primary_provisional=int(cross.primary_500m_geometric_match.sum()),official_certified=0,continuous_Q_acquired=0,coordinate_axis_checks_passed=sum(r['coordinate_axis_verified'] and r['attribute_x_lat_verified'] and r['attribute_y_lon_verified'] for r in out),original_source_sha256=sha(P8/'source/qazsu_hydroposts_response.json'),reuse_license='No explicit bulk reuse/redistribution license verified; local audit only',official_current_totals=dict(all_posts=442,river_posts=394,period='current webpage; statistical reference year not stated'),do_not_subtract_334_from_394=True))
event('station_identity_complete',records=len(out),provisional=int(cross.primary_500m_geometric_match.sum()),certified=0,historical_Q_series=0)
