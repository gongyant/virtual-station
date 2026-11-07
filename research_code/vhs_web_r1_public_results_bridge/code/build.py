"""Frozen result-only import. No target Q or source daily hydrology is read."""
from core import *
import shutil,csv
from pyproj import Transformer
for d in ["data","static","evidence","reports","tools","runtime","tmp"]:(BASE/d).mkdir(parents=True,exist_ok=True)
assert not (BASE/"data/bundle.json").exists(),"IMMUTABLE_IMPORT_ALREADY_EXISTS"
hist=history();assert all(not r["mismatches"] for k,r in hist.items() if k!=str(WEB)),"PUBLIC_HISTORY_CHANGED"
jw(BASE/"evidence/HISTORY_BEFORE.json",hist)
v1=jl(P4/"P4_V1_MODEL_MANIFEST.json");v2=jl(P4/"P4_V2_MODEL_MANIFEST.json");demo=jl(P4/"runs/PUBLIC_DATA_FINAL_P4_MASKED_DEMO/MANIFEST.json")
release_ids={"TEMPORAL_HOLDOUT":"p4-v1-"+sha(P4/"P4_V1_MODEL_MANIFEST.json")[:20],"FINAL_MODEL_APPLICATION":"p4-v2-"+sha(P4/"release/P4_PUBLIC_V2.zip")[:20],"MASKED_GAP_EVALUATION":"p4-masked-"+sha(P4/"runs/PUBLIC_DATA_FINAL_P4_MASKED_DEMO/MANIFEST.json")[:20]}
modelrefs={}
allmodels=[]
for kind,mm in [("TEMPORAL_HOLDOUT",v1["models"]),("FINAL_MODEL_APPLICATION",v2["models"]),("MASKED_GAP_EVALUATION",demo["models"])]:
 for item in mm:
  path=Path(item["path"]);assert not verify(path)["mismatches"];m=jl(path/"model.json");g=int(m["gauge_id"]);mid=m["model_id"]
  model={"dataset_id":DS,"source_snapshot_id":m["snapshot_id"],"model_release_id":release_ids[kind],"station_uid":f"{DS}:{g}","gauge_id":g,"model_id":mid,"model_version":m["version"],"release_version":m["release_version"],"prediction_kind":kind,"training_cutoff":m["train_cutoff"],"train_ids_hash":m["train_ids_hash"],"parameters_hash":m["npz_sha256"],"model_hash":sha(path/"SHA256SUMS.txt"),"model_json_hash":sha(path/"model.json"),"artifact_path":str(path),"fields":m["fields"],"transform":m["transform"],"parameters":m["parameters"],"calibration":m["calibration"],"source_units":{"P":"mm/month","T":"degC","Q":"m3/s"},"model_status":"SAVED_AND_LOAD_VERIFIED","reach_id":None,"reach_geometry":None,"reach_reason":"REACH_PREDICTION_NOT_AVAILABLE"}
  modelrefs[kind,g,mid]=model;allmodels.append(model)
registry={"dataset_id":DS,"preview_permission":"LOCAL_READONLY_PUBLIC_RESULT_PREVIEW_REQUESTED","production_display_permission":"NOT_GRANTED","web_execution":"MODEL_EXECUTION_NOT_AUTHORIZED","released_station_count":27,"released_model_count":54,"default_research_model":"P2-L1","models":[r for r in allmodels if r["prediction_kind"]=="FINAL_MODEL_APPLICATION"],"evaluation_models":[r for r in allmodels if r["prediction_kind"]=="TEMPORAL_HOLDOUT"],"masked_evaluation_models":[r for r in allmodels if r["prediction_kind"]=="MASKED_GAP_EVALUATION"],"not_published":["P5-L1-SHRINK"],"notice":NOTICE,"license_report":"license","provenance_note":"old LAMAHCE metadata snapshot is a different source; no fallback by dataset label"}
sources=[("TEMPORAL_HOLDOUT",P4/"P4_V1_PREDICTIONS.csv",v1["run_id"]),("FINAL_MODEL_APPLICATION",P5/"P5_BATCH_APPLICATION.csv","P5_A_SAVED_MODEL_APPLICATION"),("MASKED_GAP_EVALUATION",P4/"P4_MASKED_DEMO_PREDICTIONS.csv","PUBLIC_DATA_FINAL_P4_MASKED_DEMO")]
pred=[]
for kind,path,run in sources:
 for r in cr(path):
  assert not any(k.lower() in ["qobs","qobs_m3s"] for k in r),"OBSERVED_Q_EXPORT_REFUSED"
  g=int(r["gauge_id"]);mid=r["model_id"];m=modelrefs[kind,g,mid];dt=r["date"]
  assert r["model_hash"]==m["model_hash"],"PREDICTION_MODEL_HASH_MISMATCH"
  row={"dataset_id":DS,"source_snapshot_id":m["source_snapshot_id"],"model_release_id":m["model_release_id"],"station_uid":f"{DS}:{g}","gauge_id":g,"year":int(dt[:4]),"month":int(dt[5:]),"model_id":mid,"model_version":m["model_version"],"prediction_kind":kind,"qsim_raw":num(r["q_hat_raw"]),"qsim_nonnegative":num(r["q_hat_nonnegative"]),"interval_80_lower":num(r["lower80"]),"interval_80_upper":num(r["upper80"]),"interval_90_lower":num(r["lower90"]),"interval_90_upper":num(r["upper90"]),"evaluation_eligible":kind!="FINAL_MODEL_APPLICATION","evaluation_run_id":run if kind!="FINAL_MODEL_APPLICATION" else None,"source_run_id":run,"model_status":m["model_status"],"input_support_status":r["support_class"],"uncertainty_status":r["calibration_status"],"provenance_hash":digest({"source_file_hash":sha(path),"source_row":r,"model_hash":m["model_hash"]}),"model_hash":m["model_hash"],"input_hash":r["input_hash"],"training_cutoff":m["training_cutoff"],"unit":"m3/s","reach_id":None,"geometry":None,"geometry_reason":"NO_CERTIFIED_REACH_MAPPING","display_permission":"LOCAL_PREVIEW_ONLY"}
  row["prediction_key"]=digest([row[k] for k in ["dataset_id","source_snapshot_id","model_release_id","source_run_id","station_uid","year","month","model_id","prediction_kind"]]);pred.append(row)
assert len(pred)==2470 and len({r["prediction_key"] for r in pred})==len(pred)
evals=[]
for r in cr(P4/"P4_V1_EVALUATION.csv"):
 if r["prediction"]!="raw":continue
 g=int(r["gauge_id"]);m=modelrefs["TEMPORAL_HOLDOUT",g,r["model_id"]]
 evals.append({"dataset_id":DS,"source_snapshot_id":m["source_snapshot_id"],"model_release_id":m["model_release_id"],"evaluation_run_id":v1["run_id"],"station_uid":f"{DS}:{g}","gauge_id":g,"model_id":r["model_id"],"prediction_kind":"TEMPORAL_HOLDOUT","period_start":"2015-01","period_end":"2017-12","n_months":int(r["n"]),"evaluation_status":"EVALUATED_TEMPORAL_HOLDOUT","NSE":num(r["NSE"]),"KGE":num(r["KGE"]),"RMSE":num(r["RMSE"]),"MAE":num(r["MAE"]),"PBIAS":num(r["PBIAS"]),"KGE_r":num(r["KGE_r"]),"KGE_alpha":num(r["KGE_alpha"]),"KGE_beta":num(r["KGE_beta"]),"provenance_hash":digest({"source_hash":sha(P4/"P4_V1_EVALUATION.csv"),"row":r})})
yearly=[]
for r in cr(P4/"P4_V1_YEARLY_EVALUATION.csv"):
 yearly.append({"dataset_id":DS,"gauge_id":int(r["gauge_id"]),"model_id":r["model_id"],"year":int(r["year"]),"n_months":int(r["n"]),**{k:num(r[k]) for k in ["NSE","KGE","RMSE","MAE","PBIAS"]}})
coverage=[]
for r in cr(P4/"P4_V1_COVERAGE.csv"):
 if r["subset"]=="ALL":coverage.append({"gauge_id":int(r["gauge_id"]),"model_id":r["model_id"],"nominal":num(r["nominal"]),"coverage":num(r["coverage"]),"mean_width":num(r["mean_width"]),"n":int(r["n_defined"])})
metadata=LAB/"p1_seasonal_meteorology_ablation/source/metadata/D_gauges/1_attributes/Gauge_attributes.csv"
with metadata.open(encoding="utf-8-sig") as f:attrs={int(r["ID"]):r for r in csv.DictReader(f,delimiter=";")}
stations=[];mapping=[];geo=[]
to_wgs=Transformer.from_crs(3035,4326,always_xy=True);back=Transformer.from_crs(4326,3035,always_xy=True)
for g in sorted({r["gauge_id"] for r in registry["models"]}):
 a=attrs[g];x,y=float(a["lon"]),float(a["lat"]);lon,lat=to_wgs.transform(x,y);xx,yy=back.transform(lon,lat);assert max(abs(xx-x),abs(yy-y))<.02
 em=[r for r in evals if r["gauge_id"]==g];st={"dataset_id":DS,"station_uid":f"{DS}:{g}","gauge_id":g,"name":a["name"],"river":a["river"],"official_gauge_id":a["govnr"],"country":a["country"],"area_km2":float(a["area_gov"]),"coordinates_epsg3035":[x,y],"coordinates_wgs84":[lon,lat],"evaluation_status":"GAUGE_EVALUATION_AVAILABLE" if em else "NOT_EVALUATED","evaluation_reason":None if em else "NO_ELIGIBLE_TEST_SUPPORT","model_count":2,"model_execution":"MODEL_EXECUTION_NOT_AUTHORIZED","reach_status":"REACH_PREDICTION_NOT_AVAILABLE","true_gaps_status":"NO_ELIGIBLE_TRUE_GAPS"}
 stations.append(st)
 props={**st,"evaluation":{r["model_id"]:{k:r[k] for k in ["NSE","KGE","RMSE","MAE","PBIAS"]} for r in em},"uncertainty":[r for r in coverage if r["gauge_id"]==g],"reach_id":None,"reach_geometry":None,"reach_reason":"NO_CERTIFIED_REACH_MAPPING"}
 geo.append({"type":"Feature","id":st["station_uid"],"geometry":{"type":"Point","coordinates":[lon,lat]},"properties":props})
 for r in registry["models"]:
  if r["gauge_id"]==g:mapping.append({k:r[k] for k in ["dataset_id","source_snapshot_id","model_release_id","station_uid","gauge_id","model_id","model_version","training_cutoff","model_hash","parameters_hash"]})
reports={"p4_report":P4/"P4_SCIENTIFIC_REPORT_ZH.md","model_card":P4/"P4_MODEL_CARD_ZH.md","p5_report":P5/"P5_SCIENTIFIC_REPORT_ZH.md","license":P4/"SOURCE_LICENSE_AND_ATTRIBUTION.txt"}
reportrows=[]
for key,path in reports.items():
 target=BASE/"reports"/(key+path.suffix);shutil.copyfile(path,target);reportrows.append({"id":key,"filename":target.name,"source_sha256":sha(path),"local_sha256":sha(target)})
provenance={"dataset_id":DS,"created_UTC":now(),"sources":[{"prediction_kind":k,"path":str(p),"sha256":sha(p),"run_id":r} for k,p,r in sources],"V1_manifest_hash":sha(P4/"P4_V1_MODEL_MANIFEST.json"),"V2_zip_hash":sha(P4/"release/P4_PUBLIC_V2.zip"),"P5_manifest_hash":sha(P5/"runs/P5_A_SAVED_MODEL_APPLICATION/SHA256SUMS.txt"),"station_metadata_path":str(metadata),"station_metadata_hash":sha(metadata),"coordinates":"original EPSG3035 -> pyproj EPSG4326 GeoJSON; map consumes coordinates_epsg3035 in metres; roundtrip<0.02m","report_imports":reportrows,"website_candidate":str(WEB),"active_8775":"CONNECTION_REFUSED_AT_INSPECTION; running path not confirmed","old_authorization":"OPEN_METADATA_ONLY and execution403 retained","teacher_Q_read":False,"source_daily_Q_read":False}
contract={"schema_version":"VHS_PUBLIC_RESULTS_1","required_prediction_fields":list(pred[0]),"dataset_id":DS,"foreign_keys":["dataset_id+source_snapshot_id+model_release_id+station_uid+model_id","source_run_id"],"sample_key":["dataset_id","source_snapshot_id","station_uid","year","month"],"prediction_key_fields":["dataset_id","source_snapshot_id","model_release_id","source_run_id","station_uid","year","month","model_id","prediction_kind"],"prediction_kinds":{"TEMPORAL_HOLDOUT":"V1 original2015-2017 independent time test","FINAL_MODEL_APPLICATION":"V2 saved model application, NOT independent evaluation","MASKED_GAP_EVALUATION":"genuine fitted models excluded masked labels; not true gap","TRUE_GAP_RECONSTRUCTION":"currently0"},"null_policy":"undefined/absent are null plus reason, never zero","Qobs_export":"NOT_IN_CONTRACT_NOT_EXPORTED","reach_policy":"reach_id/geometry null until physical mapping and real reach results","dataset_alias":"LAMAHCE metadata is not interchangeable with public snapshots"}
bundle={"registry":registry,"stations":stations,"predictions":pred,"evaluation":evals,"yearly":yearly,"coverage":coverage,"reports":reportrows,"notice":NOTICE,"counts":{"released_stations":27,"released_models":54,"V1_stations":25,"V1_unique_months":899,"V1_predictions":1798,"V2_application_predictions":648,"masked_predictions":24,"true_gap_predictions":0}}
jw(BASE/"data/bundle.json",bundle);jw(BASE/"PUBLIC_MODEL_REGISTRY.json",registry);jw(BASE/"PUBLIC_RESULTS_CONTRACT.json",contract);jw(BASE/"RESULT_PROVENANCE.json",provenance);jw(BASE/"SPATIAL_STATION_RESULTS.geojson",{"type":"FeatureCollection","metadata":{"source_crs":"EPSG:3035","geometry_crs":"EPSG:4326","map_display_crs":"EPSG:3035","point_layers_only":True},"features":geo})
cw(BASE/"P4_V1_EVALUATION_IMPORT.csv",evals);cw(BASE/"P5_V2_APPLICATION_IMPORT.csv",[r for r in pred if r["prediction_kind"]=="FINAL_MODEL_APPLICATION"]);cw(BASE/"MODEL_TO_STATION_MAPPING.csv",mapping)
shutil.copyfile(WEB/"http_policy.py",BASE/"code/http_policy.py")
shutil.copyfile(WEB/"tools/cdp.py",BASE/"tools/cdp.py")
jw(BASE/"evidence/BASELINE_INSPECTION.json",{"candidate_path":str(WEB),"candidate_build":"v0.6.0-four-layer-20261024","active_service_confirmed":False,"loopback8775_connection":"REFUSED","process_introspection":"Get-CimInstance denied; no privileged process inspection used","routes":["/api/v6/results/station","/api/v6/results/evaluation","/api/v6/results/spatial","/api/v6/results/report"],"permission_mode":"LAMAHCE OPEN_METADATA_ONLY; GET/POST execute403","production_modified":False})
print(json.dumps(bundle["counts"]))
