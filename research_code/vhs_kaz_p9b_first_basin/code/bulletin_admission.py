from common import *
from decimal import Decimal
import numpy as np
source=ROOT/'source/OFFICIAL_HYDROLOGICAL_BULLETIN_2023.pdf';pin=digest(source)
# Literal visual transcription of Table4 pp177-179. No value corrections or gap filling.
# Each tuple: water-year start, page, 12 monthly values III..XII,I,II, 3 seasonal sums, annual sum.
rows={
'Ili-Dobyn':[(2021,177,'274 305 426 337 174 221 382 393 439 362 265 265','2119 832 892','3843'),(2022,177,'263 388 600 448 269 315 333 302 340 326 247 286','2616 642 859','4117'),(2023,177,'343 377 371 345 323 269 404 432 418 241 274 274','2432 850 789','4071')],
'Tentek-Tonkeris':[(2021,177,'16.2 48.8 71.4 44.4 40.1 29.7 18.5 12.6 10.5 10.4 6.78 6.81','269 23.1 24.0','316'),(2022,178,'12.1 76.1 83.8 66.7 42.3 29.2 16.2 12.6 10.7 9.83 12.3 14.8','326 23.3 37.0','387'),(2023,178,'24.8 50.3 72.5 67.6 38.4 29.2 27.0 20.2 28.5 15.3 16.2 15.3','310 48.7 46.8','405')],
'Ili-Kapshagay':[(2021,178,'208 191 406 470 473 470 325 296 262 255 297 254','2543 558 806','3907'),(2022,178,'164 168 411 495 584 573 294 238 248 217 218 208','2689 486 643','3818'),(2023,178,'216 218 457 534 579 560 367 224 240 266 271 231','2931 464 768','4163')],
'Lepsy-Lepsy':[(2021,178,'7.42 5.96 3.55 182 3.34 10.3 9.73 5.96 4.07 3.55 3.38 3.34','162 10.0 10.3','182'),(2022,178,'5.08 6.38 4.72 211 4.06 12.9 11.6 6.38 5.57 4.72 4.17 4.06','186 11.9 12.9','211'),(2023,178,'8.66 10.2 5.92 246 4.68 17.7 22.1 10.2 8.59 5.92 7.11 4.68','209 18.8 17.7','246')],
'Chilik-Malybay':[(2021,178,'0.60 4.38 60.3 104 111 82.8 35.2 5.98 1.22 0.68 0.61 0.62','404 1.90 1.23','407'),(2022,178,'0.62 0.62 60.6 93.2 123 118 45.7 18.7 5.46 0.61 0.61 0.67','460 6.07 1.28','468'),(2023,179,'0.62 6.49 44.2 74.6 88.5 66.4 23.4 12.1 2.35 0.67 6.23 5.69','316 3.02 11.9','331')],
'Charyn-Sarytogay':[(2021,179,'22.9 45.8 60.9 59.0 57.1 43.4 38.2 11.5 30.2 42.2 19.3 15.4','339 72.4 34.7','446'),(2022,179,'14.1 35.6 53.8 60.1 49.1 46.2 36.7 9.86 24.9 31.8 14.0 17.6','305 56.7 31.5','394'),(2023,179,'25.1 29.5 35.7 36.3 39 35.8 27.1 6.91 27.6 32.5 22.0 22.4','235 60.1 44.4','340')],
'Ili-above-Kapshagay164km':[(2021,179,'238 274 339 300 156 181 296 306 334 281 229 215','2090 615 444','3149'),(2022,179,'204 307 440 347 190 221 234 212 275 249 259 306','2155 524 565','3244'),(2023,179,'306 293 288 264 259 182 312 347 359 334 274 274','2251 693 548','3492')]}
mapping={'Tentek-Tonkeris':'14561','Ili-Kapshagay':'14011','Chilik-Malybay':'14160','Charyn-Sarytogay':'14118','Ili-above-Kapshagay164km':'14004'}
monthly=[];qc=[]
def tolerance(token):return Decimal('0.5')*(Decimal(10)**Decimal(token).as_tuple().exponent)
for name,series in rows.items():
    for start,page,values,sums,annual in series:
        tok=values.split();season=sums.split();assert len(tok)==12 and len(season)==3
        cuts=[(0,7),(7,9),(9,12)] if name in ['Ili-Dobyn','Tentek-Tonkeris','Ili-Kapshagay','Lepsy-Lepsy'] else [(0,8),(8,10),(10,12)]
        failures=[]
        for j,(a,b) in enumerate(cuts):
            difference=abs(sum(Decimal(x) for x in tok[a:b])-Decimal(season[j]));limit=sum(tolerance(x) for x in tok[a:b])+tolerance(season[j]);ok=difference<=limit
            qc.append(dict(source_station=name,water_year=f'{start}-{start+1}',page=page,check=f'SEASON_{j+1}_PRINTED_ROUNDING',difference=float(difference),allowed_rounding=float(limit),passed=ok))
            if not ok:failures.append(f'SEASON_{j+1}_SUM_INCONSISTENT')
        difference=abs(sum(Decimal(x) for x in tok)-Decimal(annual));limit=sum(tolerance(x) for x in tok)+tolerance(annual);ok=difference<=limit
        qc.append(dict(source_station=name,water_year=f'{start}-{start+1}',page=page,check='ANNUAL_SUM_OF_MONTHS_PRINTED_ROUNDING',difference=float(difference),allowed_rounding=float(limit),passed=ok))
        if not ok:failures.append('ANNUAL_SUM_INCONSISTENT')
        for i,token in enumerate(tok):
            month=(i+2)%12+1;year=start if month>=3 else start+1
            monthly.append(dict(source_station=name,provisional_QazSu_code=mapping.get(name,'NOT_LINKED_TO_P9A49'),water_year=f'{start}-{start+1}',year=year,month=month,q_reported_m3s=float(token),source_token=token,source_page=page,source_table='AppendixTable4',source_SHA256=pin,source_monthly_semantics='PrintedmonthlyQ_m3s;mean_definition_requires_source_confirmation;annual_sum_is_not_annual_mean',source_QC_status='SOURCE_INTERNAL_SUM_CONFLICT' if failures else 'PRINTED_SUMS_CONSISTENT_WITH_ROUNDING_NOT_DAILY_QC',source_QC_reason='|'.join(failures) or 'NO_ARITHMETIC_CONFLICT_DETECTED',admission='Q_NOT_ADMITTED_LICENSE_IDENTITY_QC_AND_LENGTH_UNRESOLVED',license='PUBLIC_OFFICIAL_DOCUMENT_EXPLICIT_MODEL_TRAINING_AND_REUSE_TERMS_NOT_ESTABLISHED'))
csv(ROOT/'data/P9B_BULLETIN_MONTHLY_Q_TRANSCRIPTION.csv',monthly);csv(ROOT/'data/P9B_BULLETIN_TABLE_ARITHMETIC_QC.csv',qc)
inventory=pd.read_csv(ROOT/'P9B_AVAILABLE_Q_INVENTORY.csv')
inventory=inventory[inventory.source!='Kazhydromet official bulletin2023']
added=[]
for name in rows:
    d=[r for r in monthly if r['source_station']==name];n_bad=sum(x['source_QC_status']=='SOURCE_INTERNAL_SUM_CONFLICT' for x in d)
    added.append(dict(source='Kazhydromet official bulletin2023',dataset_DOI='N/A_OFFICIAL_URL',source_sha256=pin,source_CODE=name,country_label='KAZ_CONTEXT_NOT_CODE_CERTIFIED',inside_Balkhash_Alakol=True,river=name.split('-')[0],name_eng=name,name_ru='SEE_SOURCE_CORROBORATION',source_institution='Kazhydromet',has_actual_timeseries=True,available_resolutions='reportedmonthly',source_start='2021-03',source_end='2024-02',record_count=len(d),Q_unit='printedm3/s;monthlymean definition not independently certified',license='EXPLICIT_BULK_REUSE_AND_TRAINING_TERMS_UNCONFIRMED',quality=f'INTERNAL_ARITHMETIC_CONFLICT_ROWS={n_bad};NO_DAILY_QC',within_current_basin_scope=True,admission='Q_NOT_ADMITTED',norm_discharge_not_series=True,provisional_QazSu_code=mapping.get(name,'UNLINKED_P9A49')))
csv(ROOT/'P9B_AVAILABLE_Q_INVENTORY.csv',pd.concat([inventory,pd.DataFrame(added)],ignore_index=True))
# Manual corroboration uses source river + named site + independently printed catchment area.
evidence=[('14004','Ili r.-164km upstream of KapshagayHP',85400,'1971-2000',149),('14011','Ili r.-Kapshagay s.',111000,'1911-1970',149),('14118','Charyn r.-Sarytogay s.',7370,'1929-2010',149),('14160','Chilik r.-Malybay v.',4300,'1928-2010',149),('14561','Tentek r.-Tonkeris v.',3300,'1930-2023',149),('14419','Karoy r.-Tekeli v.',484,'1940-2023',149),('14421','Shyzhyn r.-Tekeli c.',479,'1981-2023',149),('14446','Koksu r.-Koksu v.',1590,'1956-2023',149),('14452','Koktal r.-Araltobe v.',293,'1946-2023',149),('14476','Byzhy r.-Karymsak v.',822,'1949-2019',149),('14014','Ili r.-Ushzharma v.',None,'Source descriptive statistics only',22)]
cross=pd.read_csv(ROOT/'P9B_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str});cross['history_start']=cross.history_start.astype('object');cross['history_end']=cross.history_end.astype('object');ev=[]
event('bulletin_metadata_dtype_recovery',reason='N/A date columns explicitly object typed; bulletin inventory idempotent; reported Q values unchanged')
for code,eng,area,period,page in evidence:
    ix=cross.index[cross.station_code==code][0];old_area=float(cross.loc[ix,'source_upstream_area_km2']);conflict=area is not None and old_area!=area
    cross.loc[ix,'name_english']=eng;cross.loc[ix,'official_document_page']=page;cross.loc[ix,'official_document_SHA256']=pin;cross.loc[ix,'official_document_area_km2']=area;cross.loc[ix,'documented_statistics_period_NOT_Q_acquisition']=period
    cross.loc[ix,'official_document_corroboration']='SOURCE_CONFLICT_AREA_DIFFERS' if conflict else 'RIVER_SITE_AREA_CORROBORATED_NOT_CODE_LOCATION_CERTIFIED' if area is not None else 'RIVER_SITE_CONTEXT_ONLY_NOT_CERTIFIED'
    if conflict:cross.loc[ix,'official_identity_status']='SOURCE_CONFLICT'
    name=next((name for name,c in mapping.items() if c==code),None)
    if name:
        cross.loc[ix,'actual_historical_Q']='OFFICIAL_BULLETIN_REPORTED_MONTHLY_VALUES_ACQUIRED_NOT_ADMITTED';cross.loc[ix,'history_start']='2021-03';cross.loc[ix,'history_end']='2024-02'
    ev.append(dict(provisional_station_code=code,QazSu_river_site=cross.loc[ix,'station_name'],document_river_site=eng,QazSu_area_km2=old_area,official_document_area_km2=area,source_conflict=conflict,document_statistics_period=period,page=page,SHA256=pin,identity='NOT_OFFICIAL_CERTIFICATION_NO_STATION_CODE_COORDINATES_OR_MIGRATION_RECORD'))
csv(ROOT/'P9B_GAUGE_IDENTITY_CROSSWALK.csv',cross);csv(ROOT/'data/P9B_OFFICIAL_STATION_CORROBORATION.csv',ev)
audit=pd.read_csv(ROOT/'P9B_HISTORICAL_Q_SOURCE_AUDIT.csv');mask=audit.source.str.contains('water bulletin',na=False);audit.loc[mask,'download']='PDF194pages14157668bytesSHAverified;252reportedmonthlyvalues7sites';audit.loc[mask,'status']='PUBLIC_REPORTED_Q_ACQUIRED_Q_NOT_ADMITTED';audit.loc[mask,'limitations']='5sites180months linked to49provisionalnames/areas;36Lepsy rows internally inconsistent;only3water-years;no dailyQC or explicit training/reuse terms;sourcewater-yearIIItoII'
csv(ROOT/'P9B_HISTORICAL_Q_SOURCE_AUDIT.csv',audit)
js(ROOT/'evidence/BULLETIN_Q_ADMISSION.json',dict(PDF_pages=194,reported_station_series=7,reported_month_rows=len(monthly),arithmetically_consistent_rows=sum(r['source_QC_status']!='SOURCE_INTERNAL_SUM_CONFLICT' for r in monthly),arithmetically_conflicting_rows=sum(r['source_QC_status']=='SOURCE_INTERNAL_SUM_CONFLICT' for r in monthly),provisionally_linked_P9A49_stations=len(mapping),provisionally_linked_rows=sum(r['provisional_QazSu_code']!='NOT_LINKED_TO_P9A49' for r in monthly),source_context_corroborated49_records=len(evidence),area_conflict_records=sum(r['source_conflict'] for r in ev),official_identity_certified=0,calendar_years_complete_per_series=2,water_years=3,P10_Q_admitted=0,raw_values_never_repaired=True,source_basin_gauge_count_claim_63_page20_not_current49_catalog_reconciliation=True,exposure='entire194pagebulletin parsed;2021-2024reported Q and aggregates exposed;not future blindtest'))
event('official_bulletin_Q_transcribed',rows=len(monthly),linked49_stations=len(mapping),linked49_rows=180,source_conflict_rows=sum(r['source_QC_status']=='SOURCE_INTERNAL_SUM_CONFLICT' for r in monthly),admitted=0,fit_calls=0)
