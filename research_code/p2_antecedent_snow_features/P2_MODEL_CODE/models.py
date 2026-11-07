"""Frozen twelve-month mean + jointly penalized meteorological block.
C0+PT matches P1's solver/objective; two new models only add fixed requested features.
"""
import numpy as np
from dataclasses import dataclass
import public_runtime as src
from vhs_sci.contracts import ids_hash
ALPHAS=(.01,.1,1.,10.,100.)
FIELDS={"C0+PT":("P","T"),"P2-L1":("P","T","L1"),"P2-SNOW":("P","T","S","M")}
FIT_CONTEXT={};FIT_EVENTS=[]
@dataclass
class Inputs:
 ids:tuple
 years:np.ndarray
 months:np.ndarray
 values:dict
 snapshot:str
 synthetic:bool=False
 def take(self,ids):
  wanted=set(ids);ix=np.array([z for z,i in enumerate(self.ids) if i in wanted],int);assert len(ix)==len(wanted)
  return Inputs(tuple(self.ids[z] for z in ix),self.years[ix],self.months[ix],{k:np.asarray(v)[ix] for k,v in self.values.items()},self.snapshot,self.synthetic)
class MonthlyWeatherRidge:
 def __init__(self,model_id,alpha=None):
  assert model_id in FIELDS
  if alpha is not None:assert np.isfinite(alpha) and alpha>0
  self.model_id=model_id;self.fields=FIELDS[model_id];self.alpha=alpha
 def fit(self,x,y):
  y=np.asarray(y,float);src.admit_training_matrix(x,y)
  self.snapshot=x.snapshot;self.train_ids=tuple(x.ids);self.train_ids_hash=ids_hash(x.ids)
  event={**FIT_CONTEXT,"model_id":self.model_id,"level":"outer" if self.alpha is None else "inner","n_train":len(y),"train_ids_hash":self.train_ids_hash,"status":"STARTED"};FIT_EVENTS.append(event)
  self.cv_trace=[]
  if self.alpha is None:
   years=sorted(set(x.years.tolist()));assert len(years)>=4
   for alpha in ALPHAS:
    loss=[];records=[]
    for held in years:
     tx=x.take([i for i,yy in zip(x.ids,x.years) if yy!=held]);vx=x.take([i for i,yy in zip(x.ids,x.years) if yy==held])
     inner=MonthlyWeatherRidge(self.model_id,alpha).fit(tx,y[x.years!=held])
     pred=inner.predict(vx);loss.append(float(np.mean((pred-y[x.years==held])**2)))
     records.append({"held_year":held,"train_ids_hash":inner.train_ids_hash,"transform_fit_ids_hash":inner.train_ids_hash,"validation_ids_hash":ids_hash(vx.ids),"transform_fit_years":sorted(set(tx.years.tolist()))})
    self.cv_trace.append({"alpha":alpha,"mean_year_MSE_raw":float(np.mean(loss)),"standard_error":float(np.std(loss,ddof=1)/np.sqrt(len(loss))),"year_losses":loss,"folds":records})
   best=min(self.cv_trace,key=lambda r:(r["mean_year_MSE_raw"],r["alpha"]));cutoff=best["mean_year_MSE_raw"]+best["standard_error"];tol=1e-12*max(1.,abs(cutoff))
   self.selected_alpha=max(r["alpha"] for r in self.cv_trace if r["mean_year_MSE_raw"]<=cutoff+tol)
   self.selection={"rule":"ONE_STANDARD_ERROR_LARGEST_ALPHA","best_alpha":best["alpha"],"cutoff":cutoff,"comparison_tolerance":tol,"selected_alpha":self.selected_alpha}
  else:self.selected_alpha=float(self.alpha);self.selection={"rule":"FIXED_ALPHA","selected_alpha":self.selected_alpha}
  raw=np.column_stack([x.values[k] for k in self.fields])
  self.mu=np.zeros((12,len(self.fields)));self.sd=self.mu.copy();self.constant=np.zeros(self.mu.shape,bool);self.climate=np.zeros(12);self.support={}
  for month in range(1,13):
   ix=x.months==month
   assert len(set(x.years[ix]))>=3,"INSUFFICIENT_MONTH_REFERENCE"
   v=raw[ix];self.mu[month-1]=v.mean(axis=0);self.sd[month-1]=v.std(axis=0,ddof=1)
   self.constant[month-1]=self.sd[month-1]<=1e-12*np.maximum(1.,np.max(abs(v),axis=0))
   self.climate[month-1]=float(y[ix].mean())
  Z=self.transform(x);residual=y-self.climate[x.months-1]
  maxcenter=max(float(np.max(abs(Z[x.months==m].mean(axis=0)))) for m in range(1,13))
  assert maxcenter<1e-10,"TRAIN_MONTH_ANOMALY_NOT_CENTERED"
  aug=np.vstack([Z,np.sqrt(self.selected_alpha)*np.eye(len(self.fields))])
  self.beta,_,rank,_=np.linalg.lstsq(aug,np.r_[residual,np.zeros(len(self.fields))],rcond=None)
  assert rank==len(self.fields) and np.isfinite(self.beta).all()
  self.diagnostics={"month_mean_standardized_maxabs":maxcenter,"solver":"AUGMENTED_SVD","rank":int(rank),"condition":float(np.linalg.cond(aug)),"monthly_constant_flags":[f"{name}/{m+1}:ZERO_STD_ZERO_ANOMALY" for m in range(12) for z,name in enumerate(self.fields) if self.constant[m,z]],"nonzero_training_rows":{name:int(np.count_nonzero(raw[:,z])) for z,name in enumerate(self.fields)}}
  event["status"]="COMPLETED";return self
 def transform(self,x):
  src.admit_input(x);assert x.snapshot==self.snapshot,"WRONG_SNAPSHOT"
  raw=np.column_stack([x.values[k] for k in self.fields]);ix=x.months-1
  sd=np.where(self.constant[ix],1.,self.sd[ix])
  return np.where(self.constant[ix],0.,(raw-self.mu[ix])/sd)
 def predict(self,features_test):
  assert hasattr(self,"beta")
  return self.climate[features_test.months-1]+self.transform(features_test)@self.beta
 def constant_departures(self,x):
  raw=np.column_stack([x.values[k] for k in self.fields]);ix=x.months-1
  return self.constant[ix]&(abs(raw-self.mu[ix])>1e-12*np.maximum(1,abs(self.mu[ix])))
 def response_current_T_plus1(self,x):
  # Conditional covariate sensitivity, NOT physical causal effect or a new prediction task.
  ix=x.months-1;out=np.zeros(len(x.ids))
  z=self.fields.index("T");out+=np.where(self.constant[ix,z],0,self.beta[z]/np.where(self.constant[ix,z],1,self.sd[ix,z]))
  if "M" in self.fields:
   z=self.fields.index("M");delta=x.values["S"]*(np.maximum(x.values["T"]+1,0)-np.maximum(x.values["T"],0))
   out+=np.where(self.constant[ix,z],0,self.beta[z]*delta/np.where(self.constant[ix,z],1,self.sd[ix,z]))
  return out
 def record(self):
  return {"model_id":self.model_id,"version":"PUBLIC_P2_MONTHLY_RIDGE_1","synthetic":False,"train_ids_hash":self.train_ids_hash,"train_years":sorted(set(int(s[-7:-3]) for s in self.train_ids)),"fields":list(self.fields),"parameters":{"monthly_climatology":self.climate.tolist(),"beta_standardized":self.beta.tolist(),"selection":self.selection,"penalty_scope":"ALL_METEOROLOGICAL_COEFFICIENTS_ONLY","month_intercept_refitted":False},"transform":{"fit_ids_hash":self.train_ids_hash,"fit_years":sorted(set(int(s[-7:-3]) for s in self.train_ids)),"monthly_mean":self.mu.tolist(),"monthly_sample_std":self.sd.tolist(),"monthly_constant":self.constant.tolist()},"diagnostics":self.diagnostics,"nested_CV":self.cv_trace,"no_test_label_dependency":True}
