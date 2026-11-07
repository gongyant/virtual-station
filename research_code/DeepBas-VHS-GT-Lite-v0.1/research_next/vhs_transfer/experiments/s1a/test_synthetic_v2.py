"""CPU-only artificial signals. No hydrological observations are loaded."""
import json
from pathlib import Path
import platform
import time
import unittest
import numpy as np
from methods_v2 import (days, Fold, Upstream, FitLabels, EvalLabels, positions, raw_windows,
                       months, fourier2, fit_model, common_support, DISPLACEMENTS,
                       score, paired_bootstrap, block_indices, design_diagnostics, primary_decision,
                       placebo_predictions, placebo_summary)
from real_data_gate_v2 import load_fit_views, load_evaluation_labels

HERE = Path(__file__).resolve().parent
DETAILS = {}

def artificial(seed=20261011, delay=1, linked=True, shared_season=True):
    d = days('1978-01-01','1983-12-31')
    rng = np.random.default_rng(seed)
    u_noise = rng.normal(0,12,len(d))
    phase = fourier2(d)[:,1] if shared_season else np.zeros(len(d))
    u = 100+30*phase+u_noise
    n = rng.normal(0,2 if linked else 10,len(d))
    signal = np.zeros(len(d))
    signal[delay:] = u_noise[:-delay]
    y = 100+25*phase+(0.8*signal if linked else 0)+n
    return d, Upstream(d,u), y

def train_labels(d,y,fold):
    return FitLabels(fold.train,y[positions(d,fold.train)])

def gain(y,p0,p1):
    return float(1-np.sqrt(np.mean((y-p1)**2))/np.sqrt(np.mean((y-p0)**2)))

class SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.d,self.up,self.y = artificial()
        self.fold = Fold(1983)
        self.labels = train_labels(self.d,self.y,self.fold)

    def test_01_no_synchronization_no_fixed_high_gain(self):
        gains=[]
        for seed in (101,202,303,404,505,606):
            d,up,y=artificial(seed,linked=False,shared_season=False)
            f=Fold(1983)
            m=fit_model(up,train_labels(d,y,f),f)
            p=m.predict(up,f.dev)
            gains.append(gain(y[positions(d,f.dev)],p['baseline'],p['prediction']))
        DETAILS['independent_signal_gains_six_fixed_seeds']=gains
        self.assertLess(max(gains),0.08)
        self.assertLess(abs(np.mean(gains)),0.03)

    def test_02_injected_alignment_detected(self):
        fit,dev=common_support(self.fold,self.up)
        yy=self.y[positions(self.d,dev)]
        results={}
        for k in DISPLACEMENTS:
            m=fit_model(self.up,self.labels,self.fold,k=k,placebo=True)
            p=m.predict(self.up,dev)
            results[k]=gain(yy,p['baseline'],p['prediction'])
        DETAILS['synthetic_lag1_placebo_gain']=results
        self.assertGreater(results[0],0.60)
        self.assertGreater(results[0]-max(results[k] for k in results if abs(k)>=30),0.50)

    def test_03_known_four_day_delay_peaks_at_k3(self):
        d,up,y=artificial(delay=4)
        labels=train_labels(d,y,self.fold)
        dev=common_support(self.fold,up)[1]
        gains={}
        for k in DISPLACEMENTS:
            p=fit_model(up,labels,self.fold,k=k,placebo=True).predict(up,dev)
            gains[k]=gain(y[positions(d,dev)],p['baseline'],p['prediction'])
        DETAILS['synthetic_lag4_placebo_gain']=gains
        self.assertEqual(max(gains,key=gains.get),3)

    def test_04_destroy_alignment_weakens_signal(self):
        rng=np.random.default_rng(777)
        shuffled=Upstream(self.d,self.up.q[rng.permutation(len(self.d))])
        dev=common_support(self.fold,self.up)[1]
        p=fit_model(shuffled,self.labels,self.fold,placebo=True).predict(shuffled,dev)
        g=gain(self.y[positions(self.d,dev)],p['baseline'],p['prediction'])
        DETAILS['permuted_upstream_gain']=g
        self.assertLess(g,0.08)

    def test_05_past_only_never_reads_t_or_future(self):
        t=np.array([np.datetime64('1983-06-01')])
        m=fit_model(self.up,self.labels,self.fold)
        q=self.up.q.copy()
        q[self.d>=t[0]]+=10000
        changed=Upstream(self.d,q)
        np.testing.assert_array_equal(raw_windows(self.up,t),raw_windows(changed,t))
        np.testing.assert_array_equal(m.predict(self.up,t)['prediction'],m.predict(changed,t)['prediction'])
        expected=[self.up.q[positions(self.d,t-np.timedelta64(1,'D'))][0],
                  self.up.q[positions(self.d,t[0]-np.arange(1,8))].mean(),
                  self.up.q[positions(self.d,t[0]-np.arange(1,31))].mean()]
        np.testing.assert_allclose(raw_windows(self.up,t)[0],expected)

    def test_06_negative_k_is_diagnostic_only(self):
        m=fit_model(self.up,self.labels,self.fold,k=-3,placebo=True)
        self.assertEqual(m.role,'NONCAUSAL_FUTURE_UPSTREAM_PLACEBO')
        with self.assertRaises(ValueError):
            fit_model(self.up,self.labels,self.fold,k=-3)
        with self.assertRaises(PermissionError):
            m.predict(self.up,self.fold.dev[:1],operational=True)

    def test_07_dev_label_mutation_cannot_change_predictions(self):
        m=fit_model(self.up,self.labels,self.fold)
        altered=self.y.copy()
        altered[positions(self.d,self.fold.dev)]+=5000
        m2=fit_model(self.up,train_labels(self.d,altered,self.fold),self.fold)
        np.testing.assert_array_equal(m.beta,m2.beta)
        np.testing.assert_array_equal(m.predict(self.up,self.fold.dev)['prediction'],
                                      m2.predict(self.up,self.fold.dev)['prediction'])
        with self.assertRaises(ValueError):
            fit_model(self.up,EvalLabels(self.fold.dev,altered[-365:]),self.fold)
        with self.assertRaises(ValueError):
            fit_model(self.up,FitLabels(self.d,self.y),self.fold)

    def test_08_future_upstream_cannot_fit_scaler_or_beta(self):
        changed=self.up.q.copy()
        changed[self.d>self.fold.train[-1]]+=10000
        for k in DISPLACEMENTS:
            a=fit_model(self.up,self.labels,self.fold,k=k,placebo=True)
            b=fit_model(Upstream(self.d,changed),self.labels,self.fold,k=k,placebo=True)
            np.testing.assert_array_equal(a.transform.climate,b.transform.climate)
            np.testing.assert_array_equal(a.transform.scale,b.transform.scale)
            np.testing.assert_array_equal(a.beta,b.beta)
            np.testing.assert_array_equal(a.target_climate,b.target_climate)

    def test_09_all_displacements_share_train_and_score_support(self):
        counts={}
        for year in (1981,1982,1983):
            f=Fold(year)
            train,dev=common_support(f,self.up)
            for k in DISPLACEMENTS:
                m=fit_model(self.up,train_labels(self.d,self.y,f),f,k=k,placebo=True)
                np.testing.assert_array_equal(m.fit_dates,train)
                np.testing.assert_array_equal(m.predict(self.up,dev)['dates'],dev)
                s=train-np.timedelta64(k,'D')
                self.assertGreaterEqual(s[0],f.train[0])
                self.assertLessEqual(s[-1],f.train[-1])
            self.assertEqual(len(dev),275)
            counts[year]={'primary_train':len(f.train),'placebo_train':len(train),
                          'primary_dev':len(f.dev),'placebo_dev':len(dev),
                          'placebo_train_start':str(train[0]),'placebo_train_end':str(train[-1]),
                          'placebo_dev_end':str(dev[-1])}
        DETAILS['calendar_counts_not_real_Q_counts']=counts

    def test_10_no_source_boundary_wrapping(self):
        with self.assertRaises(ValueError):
            raw_windows(self.up,self.d[:1])
        with self.assertRaises(ValueError):
            raw_windows(self.up,np.array([np.datetime64('1984-01-02')]))
        m=fit_model(self.up,self.labels,self.fold,k=-90,placebo=True)
        with self.assertRaises(ValueError):
            m.predict(self.up,self.fold.dev[-1:])

    def test_11_source_month_used_before_shift(self):
        m=fit_model(self.up,self.labels,self.fold,k=30,placebo=True)
        t=np.array([np.datetime64('1983-03-10')])
        s=t-np.timedelta64(30,'D')
        z=m.transform.apply(self.up,s)
        right=(raw_windows(self.up,s)-m.transform.climate[months(s)])/m.transform.scale
        wrong=(raw_windows(self.up,s)-m.transform.climate[months(t)])/m.transform.scale
        np.testing.assert_allclose(z,right)
        self.assertGreater(np.max(abs(z-wrong)),0.1)

    def test_12_bootstrap_years_never_concatenated(self):
        rng=np.random.default_rng(1)
        for dd in (np.concatenate([days('1981-01-01','1981-12-31'),days('1983-01-01','1983-12-31')]),
                   days('1981-01-01','1982-12-31')):
            with self.assertRaises(ValueError):
                block_indices(dd,30,10,rng)
        idx=block_indices(self.fold.dev,60,100,rng,circular=False)
        self.assertGreaterEqual(idx.min(),0)
        self.assertLess(idx.max(),365)
        # Each complete block stays within calendar; concatenation jumps are permitted.
        shaped=idx[:,:360].reshape(100,6,60)
        self.assertTrue(np.all(np.diff(shaped,axis=2)==1))

    def test_13_bootstrap_pairing_seed_and_presets(self):
        years=[]
        for year in (1981,1982,1983):
            dd=Fold(year).dev
            yy=np.full(365,100.)
            pp=yy+np.sin(np.arange(365))+2
            years.append((dd,yy,pp,pp.copy()))
        DETAILS['synthetic_bootstrap_10000']=[]
        for block in (30,60):
            result=paired_bootstrap(years,block=block)
            self.assertEqual(result['reps'],10000)
            self.assertEqual(result['seed'],20261011)
            self.assertEqual(result['gain_CI_95'],[0.,0.])
            DETAILS['synthetic_bootstrap_10000'].append(result)
        self.assertEqual(paired_bootstrap(years,reps=100),paired_bootstrap(years,reps=100))
        with self.assertRaises(ValueError):
            paired_bootstrap([years[0],years[0],years[2]],reps=10)

    def test_14_smooth_calendar_and_primary_separation(self):
        m=fit_model(self.up,self.labels,self.fold)
        before=m.predict(self.up,self.fold.dev)['prediction'].copy()
        smooth=fit_model(self.up,self.labels,self.fold,calendar='fourier2')
        self.assertEqual(smooth.target_climate.shape,(5,))
        self.assertEqual(smooth.beta.shape,(3,))
        np.testing.assert_array_equal(before,m.predict(self.up,self.fold.dev)['prediction'])
        phi=fourier2(np.array(['1980-02-28','1980-02-29','1980-03-01','1981-03-01'],dtype='datetime64[D]'))
        np.testing.assert_allclose(phi[2],phi[3])
        self.assertTrue(np.isfinite(phi).all())
        with self.assertRaises(ValueError):
            fit_model(self.up,self.labels,self.fold,calendar='fourier6')

    def test_15_diagnostics_do_not_change_fit(self):
        m=fit_model(self.up,self.labels,self.fold)
        beta=m.beta.copy()
        diag=design_diagnostics(m,self.up)
        self.assertEqual(len(diag['VIF']),3)
        self.assertTrue(np.isfinite(diag['condition_number']))
        np.testing.assert_array_equal(beta,m.beta)
        DETAILS['synthetic_design_diagnostics']=diag

    def test_16_zero_scale_and_invalid_dates_stop(self):
        with self.assertRaises(ValueError):
            fit_model(Upstream(self.d,np.full(len(self.d),100.)),self.labels,self.fold)
        with self.assertRaises(ValueError):
            Upstream(np.delete(self.d,10),np.delete(self.up.q,10))
        bad=self.up.q.copy(); bad[0]=np.nan
        with self.assertRaises(ValueError):
            Upstream(self.d,bad)

    def test_17_scoring_edge_cases_and_immutable_labels(self):
        dev=self.fold.dev
        y=np.zeros(len(dev)); pred=np.zeros(len(dev))
        s=score(EvalLabels(dev,y),dev,pred,0)
        self.assertIsNone(s['NSE']); self.assertIsNone(s['PBIAS'])
        self.assertEqual(s['peak_date_error_days'],0)
        with self.assertRaises(ValueError):
            self.labels.q[0]=900

    def test_18_real_data_gate_rejects_before_file_access(self):
        cfg={'phase':'VHS-NEXT-S1A-R0','real_execution_authorized':False}
        with self.assertRaises(PermissionError):
            load_fit_views(cfg,'this_path_does_not_exist',self.fold)
        with self.assertRaises(PermissionError):
            load_evaluation_labels(cfg,'this_path_does_not_exist',self.fold,'nonexistent_prediction')

    def test_19_primary_rule_fixed_and_cost_guard(self):
        a=[{'RMSE':10.,'PBIAS':1.,'low_RMSE':10.} for _ in range(3)]
        b=[{'RMSE':9.,'PBIAS':1.,'low_RMSE':10.} for _ in range(3)]
        d=primary_decision(a,b,[0.01,0.2],[0.01,0.2])
        self.assertEqual(d['decision'],'CONSISTENT_DEVELOPMENT_GAIN')
        b[1]['low_RMSE']=11.
        self.assertEqual(primary_decision(a,b,[0.01,0.2],[0.01,0.2])['robust_usefulness'],'NOT_ROBUST_USEFULNESS')
        b[1]['RMSE']=10.1
        self.assertEqual(primary_decision(a,b,[0.01,0.2],[0.01,0.2])['decision'],'MIXED_OR_UNCERTAIN')

    def test_20_shared_smooth_season_can_mimic_small_monthly_increment(self):
        d,up,y=artificial(404,linked=False,shared_season=True)
        labels=train_labels(d,y,self.fold)
        gains={}
        for cal in ('monthly','fourier2'):
            p=fit_model(up,labels,self.fold,calendar=cal).predict(up,self.fold.dev)
            gains[cal]=gain(y[positions(d,self.fold.dev)],p['baseline'],p['prediction'])
        DETAILS['shared_season_without_daily_link_sensitivity']=gains
        # This is a confounding positive example, NOT a guarantee of calibrated false-positive rate.
        self.assertGreater(gains['monthly'],gains['fourier2'])
        self.assertLess(gains['fourier2'],0.03)

    def test_21_primary_matches_original_equations(self):
        m=fit_model(self.up,self.labels,self.fold)
        w=raw_windows(self.up,self.fold.train)
        mm=months(self.fold.train)
        cy=np.array([self.labels.q[mm==i].mean() for i in range(12)])
        cw=np.stack([w[mm==i].mean(axis=0) for i in range(12)])
        scale=(w-cw[mm]).std(axis=0,ddof=0)
        z=(w-cw[mm])/scale
        beta=np.linalg.pinv(z,rcond=1e-12)@(self.labels.q-cy[mm])
        np.testing.assert_array_equal(m.target_climate,cy)
        np.testing.assert_array_equal(m.transform.scale,scale)
        np.testing.assert_array_equal(m.beta,beta)

    def test_22_placebo_aggregation_rejects_mismatched_dates_and_roles(self):
        pp=placebo_predictions(self.up,self.labels,self.fold)
        ev=EvalLabels(self.fold.dev,self.y[positions(self.d,self.fold.dev)])
        result=placebo_summary(pp,ev,float(np.quantile(self.labels.q,0.2)))
        self.assertEqual(len(result['gains']),13)
        self.assertNotIn('best_k',result)
        self.assertNotIn('p_value',result)
        old=pp[3]['dates']; pp[3]['dates']=old[1:]
        with self.assertRaises(ValueError):
            placebo_summary(pp,ev,100)
        pp[3]['dates']=old
        pp[-3]['role']='NOMINALLY_PAST_ONLY_PRIMARY'
        with self.assertRaises(ValueError):
            placebo_summary(pp,ev,100)

if __name__=='__main__':
    start=time.perf_counter()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticTests)
    with (HERE/'synthetic_test_log.txt').open('w',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    payload={'data_identity':'ARTIFICIAL_CPU_SIGNALS_ONLY_NOT_OBSERVATIONS',
             'real_data_files_opened_for_modeling':False,'GPU_used':False,
             'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
             'pass':result.wasSuccessful(),'python':platform.python_version(),'numpy':np.__version__,
             'elapsed_seconds':time.perf_counter()-start,'details':DETAILS}
    (HERE/'synthetic_test_results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in payload.items() if k!='details'},ensure_ascii=False))
    if not result.wasSuccessful():
        print((HERE/'synthetic_test_log.txt').read_text('utf-8'))
        raise SystemExit(1)
