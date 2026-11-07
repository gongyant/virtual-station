import bootstrap,unittest,json,tempfile
from pathlib import Path
import numpy as np
import public_runtime as src
from models import Inputs,MonthlyWeatherRidge
P=Path(__file__).parents[1]
class ForwardTests(unittest.TestCase):
 def setUp(self):src._scoring_released=False
 def test_real_calendar_boundary(self):self.assertEqual(src.previous_month(2005,1),(2004,12))
 def test_future_train_rejected(self):
  x=Inputs(("SYNTHETIC_P3:1:2005-01",),np.array([2005]),np.array([1]),{"P":np.array([1.]),"T":np.array([2.]),"L1":np.array([3.])},"SYNTHETIC_ONLY",True);src.set_outer_train(x.ids)
  with self.assertRaisesRegex(AssertionError,"CUTOFF"):src.admit_training_matrix(x,np.array([1.]))
 def test_score_before_seal_rejected(self):
  with self.assertRaisesRegex(AssertionError,"BEFORE_PREDICTION_COMMIT"):src.permit_metric(["x"],np.array([1.]))
 def test_missing_bundle_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaisesRegex(AssertionError,"NOT_SEALED"):src.release_scoring(Path(t))
 def test_Q_feature_rejected(self):
  x=Inputs(("SYNTHETIC_P3:1:2005-01",),np.array([2005]),np.array([1]),{"Qobs":np.array([1.])},"SYNTHETIC_ONLY",True)
  with self.assertRaisesRegex(AssertionError,"UNREGISTERED_FEATURE"):src.admit_input(x)
 def test_frozen_model_prediction_ignores_test_labels(self):
  rng=np.random.default_rng(20261026);pairs=[(y,m) for y in [1981,1982,1983,1984,1985,1986,2005] for m in range(1,13)]
  ids=tuple(f"SYNTHETIC_P3:1:{y}-{m:02d}" for y,m in pairs);yy=np.array([y for y,m in pairs]);mm=np.array([m for y,m in pairs])
  x=Inputs(ids,yy,mm,{"P":rng.uniform(1,100,len(ids)),"T":rng.normal(8,3,len(ids)),"L1":rng.uniform(1,100,len(ids))},"SYNTHETIC_ONLY",True)
  tx=x.take([i for i,y in zip(ids,yy) if y<2005]);vx=x.take([i for i,y in zip(ids,yy) if y==2005]);src.set_outer_train(tx.ids)
  mod=MonthlyWeatherRidge("P2-L1",100).fit(tx,30+tx.months)
  before=mod.predict(vx).copy();src._score_labels={i:99999 for i in vx.ids}
  np.testing.assert_array_equal(before,mod.predict(vx));self.assertFalse(src._scoring_released)
if __name__=="__main__":
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(ForwardTests);r=unittest.TextTestRunner(verbosity=2).run(suite)
 (P/"evidence/P3_BOUNDARY_TESTS.json").write_text(json.dumps({"synthetic_fixtures_only":True,"tests_run":r.testsRun,"success":r.wasSuccessful(),"errors":[str(x) for x in r.errors],"failures":[str(x) for x in r.failures]},indent=2),encoding="utf-8")
 raise SystemExit(not r.wasSuccessful())
