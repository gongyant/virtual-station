"""P1 exploratory controls. Frozen S2 C0/E3n numerical code is imported unchanged."""
import numpy as np
from vhs_sci.models.baselines import BaseModel,linear_solve,season,ALPHAS
from vhs_sci.contracts import TrainingBatch,ScienceError,ids_hash
from vhs_sci.features import MeteorologyTransform
FIT_EVENTS=[]
class HarmonicSeasonal(BaseModel):
 model_id="H0";no_upstream=True;required_fields=()
 def fit(self,train):
  x,y=self._begin(train)
  self.beta,self.diagnostics=linear_solve(np.column_stack([np.ones(len(x.keys)),season(x)]),y)
  self.parameters={"coefficients":self.beta.tolist(),"formula":"a+c*sin(2*pi*m/12)+d*cos(2*pi*m/12)"}
  return self
 def predict(self,features_test):
  self._check(features_test)
  return self._prediction(features_test,np.column_stack([np.ones(len(features_test.keys)),season(features_test)])@self.beta)
 def record(self):
  r=super().record();r.update(model_version="PUBLIC_P1_H0_1",authorization_status="PUBLIC_DATA_EXPLORATORY_P1",input_feature_lineage={"source":"month only","fit_scope":"train_fold","fit_ids_hash":self.train_ids_hash,"held_out_labels_used":False});return r

class ClimatologyPT(BaseModel):
 model_id="C0+PT";required_fields=("P","T","met_complete");no_upstream=True
 def __init__(self,alpha=None):
  if alpha is not None and (not np.isfinite(alpha) or alpha<=0):raise ScienceError("INVALID_ALPHA")
  self.alpha=alpha
 def fit(self,train):
  x,y=self._begin(train)
  event={"model_id":self.model_id,"level":"outer" if self.alpha is None else "inner","train_ids_hash":self.train_ids_hash,"n_train":len(y),"status":"STARTED"}
  FIT_EVENTS.append(event)
  self.cv_trace=[]
  if self.alpha is None:
   years=sorted(set(x.years.tolist()))
   if len(years)<4:raise ScienceError("RIDGE_INSUFFICIENT_INNER_YEARS")
   for alpha in ALPHAS:
    losses=[];records=[]
    for held in years:
     tx=x.take([k.sample_id for k in x.keys if k.year!=held]);vx=x.take([k.sample_id for k in x.keys if k.year==held])
     inner=ClimatologyPT(alpha).fit(TrainingBatch(tx,y[x.years!=held]))
     p=inner.predict(vx).raw;losses.append(float(np.mean((p-y[x.years==held])**2)))
     records.append({"held_year":held,"train_ids_hash":inner.train_ids_hash,"validation_ids_hash":ids_hash(vx.ids),"transform_fit_ids_hash":inner.transformer.record()["fit_ids_hash"],"transform_fit_years":sorted(set(tx.years.tolist()))})
    self.cv_trace.append({"alpha":alpha,"mean_year_MSE_raw":float(np.mean(losses)),"standard_error":float(np.std(losses,ddof=1)/np.sqrt(len(losses))),"year_losses":losses,"folds":records})
   best=min(self.cv_trace,key=lambda r:(r["mean_year_MSE_raw"],r["alpha"]))
   cutoff=best["mean_year_MSE_raw"]+best["standard_error"];tol=1e-12*max(1.,abs(cutoff))
   self.selected_alpha=max(r["alpha"] for r in self.cv_trace if r["mean_year_MSE_raw"]<=cutoff+tol)
   self.selection={"rule":"ONE_STANDARD_ERROR_LARGEST_ALPHA","best_alpha":best["alpha"],"cutoff":cutoff,"comparison_tolerance":tol,"selected_alpha":self.selected_alpha}
  else:self.selected_alpha=float(self.alpha);self.selection={"rule":"FIXED_ALPHA","selected_alpha":self.selected_alpha}
  self.climate={}
  for m in range(1,13):
   mask=x.months==m
   if len(set(x.years[mask]))<3:raise ScienceError("C0_INSUFFICIENT_MONTH_SUPPORT")
   self.climate[m]=float(y[mask].mean())
  self.transformer=MeteorologyTransform().fit(train)
  Z=self.transformer.transform(x);residual=y-np.array([self.climate[k.month] for k in x.keys])
  max_center=max(float(abs(Z[x.months==m].mean(axis=0)).max()) for m in range(1,13))
  if max_center>1e-10:raise ScienceError("MET_ANOMALY_NOT_MONTH_CENTERED")
  aug=np.vstack([Z,np.sqrt(self.selected_alpha)*np.eye(2)])
  self.beta,_,rank,_=np.linalg.lstsq(aug,np.concatenate([residual,[0.,0.]]),rcond=None)
  assert rank==2 and np.isfinite(self.beta).all()
  self.parameters={"monthly_climatology":{str(k):v for k,v in self.climate.items()},"beta_P_T":self.beta.tolist(),"selection":self.selection,"penalty_scope":"P_T_ONLY","monthly_intercept_refitted":False}
  self.diagnostics={"max_monthly_mean_standardized_anomaly":max_center,"solver":"AUGMENTED_SVD_2COEF","rank":int(rank),"condition":float(np.linalg.cond(aug))}
  event["status"]="COMPLETED"
  return self
 def predict(self,features_test):
  self._check(features_test)
  return self._prediction(features_test,np.array([self.climate[k.month] for k in features_test.keys])+self.transformer.transform(features_test)@self.beta)
 def record(self):
  return {"model_id":self.model_id,"model_version":"PUBLIC_P1_C0PT_1","synthetic":False,"authorization_status":"PUBLIC_DATA_EXPLORATORY_P1","train_ids_hash":self.train_ids_hash,"train_years":sorted(set(int(s[-7:-3]) for s in self.train_ids)),"parameters":self.parameters,"diagnostics":self.diagnostics,"meteorology_transform":self.transformer.record(),"nested_CV":self.cv_trace,"parameter_label_dependency":{"uses_training_target_labels":True,"held_out_labels_used":False},"constraint_rule":"PRIMARY_RAW_SECONDARY_MAX_ZERO"}
