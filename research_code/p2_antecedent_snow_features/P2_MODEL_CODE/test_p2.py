import bootstrap,unittest,json,inspect
from pathlib import Path
import numpy as np
from calendar_features import previous_month,construct
from models import Inputs,MonthlyWeatherRidge,FIT_EVENTS
import public_runtime as src
P=Path(__file__).parents[1]
class P2Tests(unittest.TestCase):
 def fixture(self,zero_snow=False):
  rng=np.random.default_rng(20261026);pairs=[(y,m) for y in range(2000,2007) for m in range(1,13)]
  ids=tuple(f"SYNTHETIC_P2:1:{y}-{m:02d}" for y,m in pairs);years=np.array([y for y,m in pairs]);months=np.array([m for y,m in pairs]);n=len(ids)
  v={"P":rng.uniform(10,100,n),"T":rng.normal(5,5,n),"L1":rng.uniform(10,100,n),"S":np.zeros(n) if zero_snow else rng.uniform(0,100,n),"M":np.zeros(n) if zero_snow else rng.uniform(0,200,n)}
  x=Inputs(ids,years,months,v,"SYNTHETIC_ONLY",True);src.set_outer_train([i for i,y in zip(ids,years) if y<2006]);tx=x.take(src._train_ids);vx=x.take(set(ids)-src._train_ids)
  return tx,vx,30+3*tx.months+8*(tx.months==6)
 def test_calendar_not_previous_sparse_row(self):
  self.assertEqual(previous_month(1994,1),(1993,12));self.assertEqual(previous_month(1994,1,3),(1993,10))
 def test_snow_formula_and_zero_threshold(self):
  w={(1993,10):{"P":10.,"T":-1.,"met_complete":True},(1993,11):{"P":20.,"T":0.,"met_complete":True},(1993,12):{"P":30.,"T":1.,"met_complete":True},(1994,1):{"P":5.,"T":2.,"met_complete":True}}
  f,d=construct(1994,1,w);self.assertEqual(f["L1"],30);self.assertEqual(f["S"],30);self.assertEqual(f["M"],60)
 def test_missing_is_not_zero(self):
  f,d=construct(1994,1,{})
  self.assertIsNone(f);self.assertEqual(d["status"],"MISSING_REQUIRED_WEATHER");self.assertIn("1993-10",d["missing_dates"])
 def test_zero_snow_supported_no_fake_information(self):
  tx,vx,y=self.fixture(True);m=MonthlyWeatherRidge("P2-SNOW").fit(tx,y)
  np.testing.assert_array_equal(m.beta[-2:],[0,0]);self.assertTrue(m.constant[:,-2:].all());self.assertTrue(np.isfinite(m.predict(vx)).all())
 def test_month_means_unchanged(self):
  tx,vx,y=self.fixture();m=MonthlyWeatherRidge("P2-L1",1).fit(tx,y)
  np.testing.assert_allclose(m.climate,[y[tx.months==i].mean() for i in range(1,13)]);self.assertLess(max(abs(m.beta)),1e-12)
 def test_joint_ridge_dummy_equivalence(self):
  tx,vx,y=self.fixture();y=y+.1*tx.values["P"];m=MonthlyWeatherRidge("P2-SNOW",10).fit(tx,y)
  Z=m.transform(tx);X=np.column_stack([np.eye(12)[tx.months-1],Z]);pen=np.zeros((4,16));pen[:,-4:]=np.sqrt(10)*np.eye(4)
  beta=np.linalg.lstsq(np.vstack([X,pen]),np.r_[y,np.zeros(4)],rcond=None)[0]
  np.testing.assert_allclose(beta[-4:],m.beta,atol=1e-10);np.testing.assert_allclose(beta[:12],m.climate,atol=1e-10)
 def test_inner_refit_excludes_both_held_years(self):
  tx,vx,y=self.fixture();m=MonthlyWeatherRidge("P2-L1").fit(tx,y)
  for a in m.cv_trace:
   for f in a["folds"]:
    self.assertNotIn(2006,f["transform_fit_years"]);self.assertNotIn(f["held_year"],f["transform_fit_years"]);self.assertEqual(f["train_ids_hash"],f["transform_fit_ids_hash"])
 def test_test_labels_rejected(self):
  tx,vx,y=self.fixture()
  with self.assertRaises(AssertionError):MonthlyWeatherRidge("P2-L1",1).fit(vx,np.ones(len(vx.ids)))
 def test_label_not_accepted_by_predict(self):
  tx,vx,y=self.fixture();m=MonthlyWeatherRidge("P2-SNOW",1).fit(tx,y);before=m.predict(vx).copy()
  fake_test_labels=np.full(len(vx.ids),9999)
  np.testing.assert_array_equal(before,m.predict(vx));self.assertEqual(list(inspect.signature(m.predict).parameters),["features_test"])
 def test_train_label_sensitivity(self):
  tx,vx,y=self.fixture();a=MonthlyWeatherRidge("P2-L1",1).fit(tx,y);b=MonthlyWeatherRidge("P2-L1",1).fit(tx,y+2)
  np.testing.assert_allclose(b.predict(vx)-a.predict(vx),2)
 def test_centers_and_sample_sd_train_only(self):
  tx,vx,y=self.fixture();m=MonthlyWeatherRidge("P2-SNOW",1).fit(tx,y);z=m.transform(tx)
  for mo in range(1,13):
   np.testing.assert_allclose(z[tx.months==mo].mean(axis=0),0,atol=1e-12);np.testing.assert_allclose(z[tx.months==mo].std(axis=0,ddof=1),1,atol=1e-12)
 def test_constant_training_unseen_departure(self):
  tx,vx,y=self.fixture(True);vx.values["S"][:]=5;m=MonthlyWeatherRidge("P2-SNOW",1).fit(tx,y)
  self.assertTrue(m.constant_departures(vx)[:,2].all());self.assertTrue((m.transform(vx)[:,2]==0).all())
 def test_deterministic(self):
  tx,vx,y=self.fixture();a=MonthlyWeatherRidge("P2-L1").fit(tx,y);b=MonthlyWeatherRidge("P2-L1").fit(tx,y);np.testing.assert_array_equal(a.predict(vx),b.predict(vx))
if __name__=="__main__":
 s=unittest.defaultTestLoader.loadTestsFromTestCase(P2Tests);r=unittest.TextTestRunner(verbosity=2).run(s)
 (P/"P2_TEST_RESULTS.json").write_text(json.dumps({"only_synthetic_fixture_data":True,"tests_run":r.testsRun,"success":r.wasSuccessful(),"failures":[str(x) for x in r.failures],"errors":[str(x) for x in r.errors]},indent=2),encoding="utf-8")
 raise SystemExit(not r.wasSuccessful())
