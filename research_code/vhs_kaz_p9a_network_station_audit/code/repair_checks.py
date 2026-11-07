from common import *
import shutil
for name in ['P9A_INDEPENDENT_QA.json']:
    shutil.copyfile(ROOT/name,ROOT/'evidence'/('INITIAL_FAILED_'+name))
shutil.copyfile(ROOT/'code/verify.py',ROOT/'evidence/verify_initial_failed.py')
raw=read(P8/'source/qazsu_hydroposts_response.json');f={str(x['properties']['code']):x for x in raw['features']}
d=pd.read_csv(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str})
exact=0;errs=[]
for ix,r in d.iterrows():
    a=f[r.station_code];lon,lat=a['geometry']['coordinates'];p=a['properties'];ex=abs(float(p['x'])-lat);ey=abs(float(p['y'])-lon);errs.append(max(ex,ey));exact+=int(max(ex,ey)<1e-7)
    d.loc[ix,'attribute_x_lat_verified']=ex<=0.00005001;d.loc[ix,'attribute_y_lon_verified']=ey<=0.00005001;d.loc[ix,'attribute_coordinate_decimal_places']=4
csv(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',d)
q=read(ROOT/'evidence/GAUGE_IDENTITY_AUDIT.json');q['coordinate_axis_checks_passed']=int((d.coordinate_axis_verified & d.attribute_x_lat_verified & d.attribute_y_lon_verified).sum());q['attribute_coordinate_precision_degrees']=0.0001;q['attribute_rounding_tolerance_degrees']=0.00005001;q['attribute_exact_1e7_degree_matches']=exact;q['maximum_attribute_rounding_difference_degrees']=max(errs)
js(ROOT/'evidence/GAUGE_IDENTITY_AUDIT.json',q)
js(ROOT/'evidence/CORRECTION_LOG.json',dict(source_axis_revision='GeoJSON has up to8 decimals, x/y attributes4 decimals. Compare axis-order consistency at half4-decimal-unit; exact1e-7matches preserved separately; no station coordinates changed.',independent_snap_revision='Initial independent audit used unsplit national geometry. ID97063 differs by0.008857272090494916m because P8 distances projected basin-split chords. Recompute on actual P8 basin fragments; retain original failed result; no relaxation of500m or1e-4m exact comparison.',initial_failed_checks=1,original_failure_retained=True,projection_revision='P9A original protocol preserved; explicit P8 LAEA central longitude68 applied; no Q scores involved'))
event('audit_recovery',initial_failures=1,primary_snap_threshold_m=500,exact_comparison_tolerance_m=0.0001,coordinates_changed=False)
