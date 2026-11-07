"""Source-table-driven field classification; blacklisted tables read header ONLY."""
from pathlib import Path
import csv,json
import pyogrio
H=Path(__file__).resolve().parents[1];O=H/'open_metadata';Q=H/'quarantine';E=H/'evidence';rows=[]
def add(source,fields,category,table,note):
    for field in fields:rows.append(dict(source=source,field=field,category=category,source_table=table,future_model_input=category in ('STATIC_ADMISSIBLE','FORCING'),note=note))
clim='p_mean et0_mean eta_mean arid_1 arid_2 p_season frac_snow hi_prec_fr hi_prec_du hi_prec_ti lo_prec_fr lo_prec_du lo_prec_ti'.split()
topo='area_calc elev_mean elev_med elev_std elev_ran slope_mean mvert_dist mvert_ang elon_ratio strm_dens'.split()
land='lc_dom agr_fra bare_fra forest_fra glac_fra lake_fra urban_fra'.split();veg='lai_max lai_diff ndvi_max ndvi_min gvf_max gvf_diff'.split()
soil='bedrk_dep root_dep soil_poros soil_condu soil_tawc sand_fra silt_fra clay_fra grav_fra oc_fra'.split()
for p in O.glob('*/1_attributes/Catchment_attributes.csv'):
    with p.open(encoding='utf-8-sig') as f:fields=f.readline().strip().split(';')
    for field in fields:
        table='A3' if field in topo else 'A4' if field in clim else 'A6' if field in land else 'A7' if field in veg else 'A8' if field in soil else 'A9' if field.startswith(('gc_','geol_')) else 'A1' if field in ('ID','NEXTDOWNID') else 'UNKNOWN'
        cat='TOPOLOGY' if field in ('ID','NEXTDOWNID') else 'UNKNOWN' if table=='UNKNOWN' else 'STATIC_ADMISSIBLE'
        add(str(p.relative_to(O)),[field],cat,table,'Q-independent source table; climate reference periods are retrospective, availability must be frozen in B2')
g=O/'D_gauges/1_attributes/Gauge_attributes.csv'
with g.open(encoding='utf-8-sig') as f:fields=f.readline().strip().split(';')
for field in fields:
    cat='ELIGIBILITY_ONLY' if field in ('typimpact','degimpact','diur_art','diur_glac','gaps_pre','gaps_post','obsbeg_day','obsbeg_hr','obsend') else 'TOPOLOGY' if field in ('ID','govnr','name','river','region','nrs_euhyd','nrs_rivat','area_ratio') else 'STATIC_ADMISSIBLE' if field in ('area_gov','elev','lon','lat','country','fedstate') else 'UNKNOWN'
    add(str(g.relative_to(O)),[field],cat,'A1','lon/lat columns are EPSG:3035 meters, verified against official geometry; impact flags never predictors')
for p in Q.rglob('*.csv'):
    if p.name.startswith('Hydro_indices') or p.name=='Water_balance.csv':
        with p.open(encoding='utf-8-sig') as f:fields=f.readline().strip().split(';')
        add(str(p.relative_to(Q)),fields,'LABEL_DERIVED','A5' if p.name.startswith('Hydro_indices') else 'A10','Entire source table excluded; header-only identification, no signature values decoded')
for p in O.glob('*/1_attributes/Gauge_hierarchy.csv'):
    with p.open(encoding='utf-8-sig') as f:fields=f.readline().strip().split(';')
    add(str(p.relative_to(O)),fields,'TOPOLOGY','A1','Comma-separated NEXTUPID; true directed graph, not same region assumption')
ra=O/'E_stream_network/RiverATLAS.shp';fields=list(pyogrio.read_info(ra)['fields'])
sample=O/'A_basins_total_upstrm/2_timeseries/daily/ID_1.csv'
with sample.open(encoding='utf-8-sig') as f:forcing_fields=f.readline().strip().split(';')
add('A/B/C basins:2_timeseries/daily/ID_*.csv',forcing_fields,'FORCING','A2','Header verified across 2172 files; per-variable units/publication times require B2 whitelist review')
allow={'HYRIV_ID','NEXT_DOWN','MAIN_RIV','LENGTH_KM','UPLAND_SKM'}
for field in fields:add(str(ra.relative_to(O)),[field],'TOPOLOGY' if field in allow else 'UNKNOWN','RiverATLAS technical schema','Only explicit routing/geometry columns decoded; full enriched table not a feature whitelist')
with (H/'field_dictionary.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
(E/'field_dictionary_summary.json').write_text(json.dumps(dict(fields=len(rows),blacklisted_source_tables=['Table A5 Hydro_indices_*','Table A10 Water_balance.csv','Entire F_hydrol_model'],unknown_default_denied=True,impact_fields_eligibility_only=True,signature_payloads_read=False),indent=2),encoding='utf-8')
print('Field classification complete',len(rows),'entries; no signature payload read')
