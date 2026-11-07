"""SYNTHETIC_UNIT_TEST_ONLY; CPU, no historical data fitted or predicted."""
import json, sys, traceback
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'research_next/vhs_transfer/physics'))
from frozen_router_adapter import route_daily,initialize_steady_state,substep_count,RoutingParameters
OUT=ROOT/'research_next/vhs_transfer/tests'
results=[]
def record(name,fn):
    try: results.append({'test':name,'status':'PASS',**(fn() or {})})
    except Exception as exc: results.append({'test':name,'status':'FAIL','error':str(exc),'traceback':traceback.format_exc()})
def constant():
    tau=np.full(68,.1); initial=initialize_steady_state(5.,tau)
    y,s,e=route_daily(np.full(20,5.),tau,20,initial)
    np.testing.assert_allclose(y,5.,atol=1e-12); np.testing.assert_allclose(s,initial,atol=1e-12)
    # Also test approach from empty state, not only a preinitialized equilibrium.
    cold,_,_=route_daily(np.full(60,5.),tau,20)
    assert abs(cold[-1]-5)<1e-10
    return {'max_output_error':float(abs(y-5).max()),'cold_final_error':float(abs(cold[-1]-5))}
def impulse():
    u=np.zeros(100);u[4]=10.;tau=np.full(68,.1)
    y,s,e=route_daily(u,tau,20)
    assert np.all(y[:4]==0) and np.all(y>=0) and y.argmax()>4
    assert abs(y.sum()+s.sum()-10)<1e-10
    assert s.sum()<1e-10
    return {'pulse_day_index':4,'output_peak_day_index':int(y.argmax()),'input_q_day':10.,'output_q_day':float(y.sum()),'remaining_storage_q_day':float(s.sum())}
def conservation():
    tau=np.linspace(.1,.3,68);u=np.random.default_rng(17).uniform(0,10,60);s0=initialize_steady_state(3.,tau)
    y,s,e=route_daily(u,tau,20,s0);closure=s0.sum()+u.sum()-y.sum()-s.sum()
    assert abs(closure)<1e-9 and abs(e).max()<1e-9
    return {'max_daily_closure_q_day':float(abs(e).max()),'cumulative_closure_q_day':float(closure),'cumulative_closure_m3_if_q_is_m3s':float(closure*86400)}
def causal_delay():
    u=np.zeros(60);u[4]=10;tau=np.full(68,.1);lag=3
    delayed=np.r_[np.zeros(lag),u[:-lag]]
    y,_,_=route_daily(u,tau,20); yd,_,_=route_daily(delayed,tau,20)
    np.testing.assert_allclose(yd[lag:],y[:-lag],atol=1e-12)
    assert np.all(yd[:4+lag]==0)
    # Future boundary perturbations cannot change the already-predicted prefix.
    v=u.copy();v[30:]=999.
    yp,_,_=route_daily(v,tau,20)
    np.testing.assert_array_equal(y[:30],yp[:30])
    return {'known_delay_days':lag,'measured_peak_delay_days':int(yd.argmax()-y.argmax()),'future_prefix_exact':True}
def timestep():
    tau=np.full(68,.1);u=np.zeros(30);u[2]=10.
    ys=[];errs=[]
    for steps in [20,40,80,160]:
        y,s,e=route_daily(u,tau,steps);assert np.isfinite(y).all() and np.all(y>=0) and np.all(s>=0)
        assert abs(u.sum()-y.sum()-s.sum())<1e-9
        ys.append(y);errs.append(float(abs(e).max()))
    diffs=[float(abs(ys[i+1]-ys[i]).sum()) for i in range(3)]
    assert diffs[2]<diffs[1]<diffs[0]
    return {'substep_dt_days':[.05,.025,.0125,.00625],'successive_L1_output_differences':diffs,'max_daily_closure':max(errs),'scope':'internal Euler timestep; public daily forcing step remains one day'}
def invalid():
    cases=[('negative inflow',lambda:route_daily(np.array([-1.]),np.ones(68),2)),('nonfinite inflow',lambda:route_daily(np.array([np.nan]),np.ones(68),2)),('zero tau',lambda:route_daily(np.ones(2),np.zeros(68),2)),('nonfinite tau',lambda:route_daily(np.ones(2),np.full(68,np.nan),2)),('wrong reach count',lambda:route_daily(np.ones(2),np.ones(67),2)),('unstable dt',lambda:route_daily(np.ones(2),np.full(68,.1),1)),('negative initial state',lambda:route_daily(np.ones(2),np.ones(68),2,-np.ones(68))),('zero substeps',lambda:route_daily(np.ones(2),np.ones(68),0)),('invalid tau parameter',lambda:RoutingParameters(0.).validate()),('out of range exponent',lambda:RoutingParameters(1.,a=3.).validate())]
    messages={}
    for label,fn in cases:
        try:fn()
        except ValueError as exc: messages[label]=str(exc)
        else: raise AssertionError(f'Invalid case accepted: {label}')
    return {'rejected_cases':messages}
def continuity():
    tau=np.linspace(.1,.3,68);u=np.linspace(1,5,20);initial=initialize_steady_state(1,tau)
    full,fs,_=route_daily(u,tau,20,initial);y1,s1,_=route_daily(u[:11],tau,20,initial);y2,s2,_=route_daily(u[11:],tau,20,s1)
    np.testing.assert_array_equal(full,np.r_[y1,y2]);np.testing.assert_array_equal(fs,s2)
    return {'output_and_final_state_exact':True}
for name,fn in [('T1_constant',constant),('T2_impulse',impulse),('T3_conservation',conservation),('T4_known_lag_and_causality',causal_delay),('T5_internal_timestep_stability',timestep),('T6_invalid_parameters',invalid),('T7_split_state_continuity',continuity)]:record(name,fn)
payload={'label':'SYNTHETIC_UNIT_TEST_ONLY','device':'CPU','real_flow_data_used':False,'real_models_trained':False,'router':'exact AST-selected frozen route_daily; no JIT','tests':results,'passed':sum(r['status']=='PASS' for r in results),'failed':sum(r['status']=='FAIL' for r in results),'numpy_version':np.__version__,'python':sys.version}
(OUT/'synthetic_results.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
(OUT/'synthetic_results.log').write_text('\n'.join([payload['label'],f'Python {sys.version}',f'NumPy {np.__version__}']+[json.dumps(r) for r in results]),encoding='utf-8')
print(json.dumps(payload,indent=2));sys.exit(bool(payload['failed']))
