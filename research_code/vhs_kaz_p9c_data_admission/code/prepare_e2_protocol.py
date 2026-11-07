from acquire import *
if __name__=='__main__':
 d=ROOT/'exploratory_temporal';d.mkdir(exist_ok=True)
 p=dict(experiment='KAZ_KNOWN_GAUGE_TEMPORAL_DEVELOPMENT_P9C_E2',station='WB10195/QazSu14187_PROVISIONALLY_CORROBORATED',
  enabled_only_if=['QALIGNED2000-2015driverfullmonthlyvalidationpasses','train2001-2011validcompleteQmonths;test2012-2015allcomplete;noimputation','D8/ACCnumericallyvalidatedand<=10%areaerror',
   'WBpublisherCCBYsource/unitsandobservation-sourceevidencepreserved','publiconly;teacherQneverread'],
  version='E2_V2_CORRECTED_SOURCE_TIME_FIELD_BEFORE_VALID_SCORES',
  source_schema_contract_sha256=sha(ROOT/'evidence/WB_CSV_COLUMN_ALIGNMENT_CONTRACT.json'),
  previous_attempt='WITHDRAWN_SOURCE_COLUMN_MISALIGNMENT;notanearliermodelresult',
  split_rule='Last4completeyearsasheldout(2012-2015);allearlier2001-2011completeMONTHSfortraining;2003Jul8missingdaysnotimputed;noothercompletedmonthsdiscarded;>=8completetrainyearsand>=3refspercalendar_month',
  training_years=list(range(2001,2012)),evaluation_years=list(range(2012,2016)),
  model_scope=['C0','C0+PT'],meteorological_features=['P_current_month','T_current_month'],
  algorithm_source='read-onlyP2/P2_MODEL_CODE/models.py MonthlyWeatherRidge',
  alpha=100,alpha_rule='FIXED_BEFORE_ANY_NEW_MODEL_SCORE;NO_TUNING_NO_MODEL_SELECTION',
  transform_fit='training2001-2011only;monthlyclimatology/means/std;testP/Tonlyobservedcovariates',
  scoring='separateprocessreadstestQonlyafterpredictionseal;rawprimary/nonnegativeprespecifiedsecondary;noQobsinpredictionCSV',
  metrics=['NSE','KGEandcomponents','RMSE','MAE','MSE','PBIAS','MSEskillrelativeC0','yearly'],
  negative_result='retainallfouryearsandall48months;noadjustalpha/samplewindow/modelafterseeingtestperformance',
  inference='NO_SIGNIFICANCE_OR_KAZ_PUB_CLAIM;oneknowngauge;notoperationalforecast',
  exposure='WBtestvaluesalreadyreadforfixeddataQCandcoverage;notblindedfuturevalidation;notP10PUB',
  additional_limits=['missingdailysourceQCandmigrationcertification','rasterboundary3snotfieldexact','reanalyzedP/Tobservedtargetmonth;notleadforecast'],
  P10='NOT_STARTED_FROZEN8gauge3group8yearprimarycriteriaunchanged')
 js(d/'E2_PROTOCOL_FROZEN.json',p)
 pins={}
 for x in [ROOT.parent/'p2_antecedent_snow_features/P2_MODEL_CODE/models.py',ROOT.parent/'code/vendor_public/vhs_sci/evaluate.py',ROOT.parent/'code/vendor_public/vhs_sci/contracts/__init__.py']:
  if x.is_file():pins[str(x)]=sha(x)
 js(ROOT/'evidence/REUSED_MODEL_CODE_PINS.json',pins)
 event(stage='E2_conditional_protocol_frozen_before_scores',protocol_sha256=sha(d/'E2_PROTOCOL_FROZEN.json'),models=p['model_scope'],alpha=100,formal_P10_started=False)
