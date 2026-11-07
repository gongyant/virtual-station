"""New R1 adapter/regime checks using artificial arrays only."""
import unittest
import numpy as np
from common import HERE, dump
from methods_v2 import days, Fold, Upstream, FitLabels, EvalLabels, positions, months, fit_model
from same_day import windows, fit_same_day

class Checks(unittest.TestCase):
    def setUp(self):
        self.d=days('1978-01-01','1983-12-31'); self.f=Fold(1983)
        rng=np.random.default_rng(20261011)
        self.up=Upstream(self.d,100+rng.normal(0,10,len(self.d)))
        y=150+0.3*self.up.q+rng.normal(0,5,len(self.d))
        self.labels=FitLabels(self.f.train,y[positions(self.d,self.f.train)])

    def test_same_day_windows_match_S01(self):
        d=np.array([np.datetime64('1983-06-01')])
        expected=[self.up.q[positions(self.d,d)][0],
                  np.mean(self.up.q[positions(self.d,d[0]-np.arange(7))]),
                  np.mean(self.up.q[positions(self.d,d[0]-np.arange(30))])]
        np.testing.assert_allclose(windows(self.up,d)[0],expected)
        changed=self.up.q.copy(); changed[self.d>d[0]]+=1000
        np.testing.assert_array_equal(windows(self.up,d),windows(Upstream(self.d,changed),d))

    def test_same_day_train_only_and_shared_monthly_climate(self):
        a=fit_same_day(self.up,self.labels,self.f)
        p=fit_model(self.up,self.labels,self.f)
        np.testing.assert_array_equal(a.target_climate,p.target_climate)
        changed=self.up.q.copy(); changed[self.d>self.f.train[-1]]+=10000
        b=fit_same_day(Upstream(self.d,changed),self.labels,self.f)
        np.testing.assert_array_equal(a.beta,b.beta)
        np.testing.assert_array_equal(a.scale,b.scale)
        with self.assertRaises(ValueError): fit_same_day(self.up,EvalLabels(self.f.dev,np.ones(365)),self.f)

    def test_same_day_matches_independent_three_coefficient_formula(self):
        m=fit_same_day(self.up,self.labels,self.f)
        mm=months(self.f.train); w=windows(self.up,self.f.train)
        c=np.array([self.labels.q[mm==j].mean() for j in range(12)])
        cw=np.stack([w[mm==j].mean(axis=0) for j in range(12)])
        a=w-cw[mm]; z=a/a.std(axis=0,ddof=0)
        np.testing.assert_array_equal(m.beta,np.linalg.pinv(z,rcond=1e-12)@(self.labels.q-c[mm]))

    def test_folds_and_common_masks_fixed(self):
        from methods_v2 import common_support
        for year,n in ((1981,1066),(1982,1431),(1983,1796)):
            f=Fold(year); train,dev=common_support(f,self.up)
            self.assertEqual(len(f.train),n); self.assertEqual(len(f.dev),365)
            self.assertEqual(len(train),n-180); self.assertEqual(len(dev),275)

if __name__=='__main__':
    with (HERE/'executor_synthetic_tests.log').open('w',encoding='utf-8') as f:
        r=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    dump(HERE/'executor_synthetic_tests.json',{'artificial_only':True,'tests':r.testsRun,
        'failures':len(r.failures),'errors':len(r.errors),'pass':r.wasSuccessful()})
    print({'tests':r.testsRun,'pass':r.wasSuccessful()})
    if not r.wasSuccessful(): raise SystemExit(1)
