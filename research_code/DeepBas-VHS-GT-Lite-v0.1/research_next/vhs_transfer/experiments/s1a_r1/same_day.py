"""S0.1 fixed same-day regime. No target inputs at prediction time."""
from dataclasses import dataclass
import numpy as np
from methods_v2 import months, positions, monthly_fit, ols, FitLabels

def windows(up,anchors):
    return np.column_stack([np.mean(up.q[positions(up.dates,np.asarray(anchors)[:,None]-np.arange(w))],axis=1)
                            for w in (1,7,30)])

@dataclass(frozen=True)
class SameDayModel:
    target_climate: np.ndarray
    source_climate: np.ndarray
    scale: np.ndarray
    beta: np.ndarray

    def design(self,up,dates):
        return (windows(up,dates)-self.source_climate[months(dates)])/self.scale

    def predict(self,up,dates):
        b=self.target_climate[months(dates)]
        raw=b+self.design(up,dates)@self.beta
        return {'dates':dates.copy(),'baseline':np.maximum(b,0),'prediction':np.maximum(raw,0),
                'unclipped':raw,'role':'SAME_DAY_SECONDARY_UNVERIFIED_AVAILABILITY'}

def fit_same_day(up,labels,fold):
    if type(labels) is not FitLabels or not np.array_equal(labels.dates,fold.train):
        raise ValueError('Same-day fit accepts only fold training labels')
    c=monthly_fit(labels.dates,labels.q)
    w=windows(up,fold.train); cw=monthly_fit(fold.train,w)
    a=w-cw[months(fold.train)]; s=a.std(axis=0,ddof=0)
    if np.any(s<=1e-12): raise ValueError('Zero same-day train anomaly scale')
    beta=ols(a/s,labels.q-c[months(labels.dates)],3)
    return SameDayModel(c,cw,s,beta)

def diagnostics(model,up,train):
    z=model.design(up,train); s=np.linalg.svd(z,compute_uv=False); vif=[]
    for j in range(3):
        a=np.column_stack([np.ones(len(z)),np.delete(z,j,axis=1)])
        e=z[:,j]-a@np.linalg.pinv(a,rcond=1e-12)@z[:,j]
        denominator=np.sum((z[:,j]-z[:,j].mean())**2)
        r=np.sum(e**2)/denominator if denominator>0 else 0
        vif.append(float(1/r) if r>1e-12 else None)
    return {'correlation':np.corrcoef(z,rowvar=False).tolist(),'singular_values':s.tolist(),
            'condition_number':float(s[0]/s[-1]),'VIF':vif,'beta':model.beta.tolist(),
            'beta_signs':np.sign(model.beta).astype(int).tolist()}
