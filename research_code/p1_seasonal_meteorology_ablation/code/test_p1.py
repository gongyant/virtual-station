import bootstrap
import unittest,json,inspect
from unittest.mock import patch
from pathlib import Path
import numpy as np
import public_runtime as src
from vhs_sci.contracts import SampleKey,FeatureBatch,TrainingBatch,PredictionBatch
from vhs_sci.models.baselines import MonthlyClimatology
from p1_models import HarmonicSeasonal,ClimatologyPT,FIT_EVENTS
P=Path(__file__).parents[1]
class Controls(unittest.TestCase):
 def setUp(self):
  rng=np.random.default_rng(20261026);keys=tuple(SampleKey("SYNTHETIC_P1","SYNTHETIC_ONLY","SYNTHETIC_P1:1",y,m) for y in range(2000,2007) for m in range(1,13))
  self.x=FeatureBatch(keys,{"P":rng.uniform(10,100,len(keys)),"T":rng.normal(10,4,len(keys)),"met_complete":np.ones(len(keys),bool)},True,"SYNTHETIC_TEST_ONLY")
  self.y=np.array([30+10*np.sin(2*np.pi*k.month/12)+4*np.cos(2*np.pi*k.month/12) for k in keys])
  self.allowed={k.sample_id for k in keys if k.year<2006}
  self.tx=self.x.take(self.allowed);self.vx=self.x.take(set(self.x.ids)-self.allowed);self.ty=self.y[self.x.years<2006]
  def batch(b):
   if not b.synthetic or b.authorization_status!="SYNTHETIC_TEST_ONLY" or any(k.dataset_id!="SYNTHETIC_P1" for k in b.keys):raise ValueError("NOT_SYNTHETIC_FIXTURE")
  def train(b):
   batch(b.features)
   if not set(b.features.ids)<=self.allowed:raise ValueError("TEST_LABEL_IN_TRAIN")
  self.ps=[patch.object(src,"admit_batch",batch),patch.object(src,"admit_training",train),patch("vhs_sci.models.baselines.BaseModel._prediction",lambda model,x,p:PredictionBatch(x.keys,np.asarray(p,float),np.maximum(p,0),model.model_id,model.train_ids_hash,True))]
  for p in self.ps:p.start()
 def tearDown(self):
  for p in self.ps[::-1]:p.stop()
 def test_h0_recovers_harmonic(self):
  mod=HarmonicSeasonal().fit(TrainingBatch(self.tx.select([]),self.ty))
  np.testing.assert_allclose(mod.predict(self.vx.select([])).raw,self.y[self.x.years==2006],atol=1e-10)
 def test_nonharmonic_month_means_preserved(self):
  y=20+2*self.tx.months+8*(self.tx.months==5)
  mod=ClimatologyPT(1).fit(TrainingBatch(self.tx,y))
  for m in range(1,13):self.assertAlmostEqual(mod.climate[m],float(y[self.tx.months==m].mean()))
  self.assertLess(np.max(abs(mod.beta)),1e-12)
 def test_month_intercept_is_not_penalized(self):
  mod=ClimatologyPT(100).fit(TrainingBatch(self.tx,self.ty))
  mod2=ClimatologyPT(100).fit(TrainingBatch(self.tx,self.ty+3*(self.tx.months==5)))
  np.testing.assert_allclose(mod.beta,mod2.beta,atol=1e-12);self.assertAlmostEqual(mod2.climate[5]-mod.climate[5],3)
 def test_joint_dummy_ridge_equivalence(self):
  mod=ClimatologyPT(10).fit(TrainingBatch(self.tx,self.ty+self.tx.columns["P"]*.1))
  D=np.eye(12)[self.tx.months-1];Z=mod.transformer.transform(self.tx);X=np.column_stack([D,Z])
  penalty=np.zeros((2,14));penalty[:,-2:]=np.sqrt(10)*np.eye(2)
  beta=np.linalg.lstsq(np.vstack([X,penalty]),np.r_[self.ty+self.tx.columns["P"]*.1,[0,0]],rcond=None)[0]
  np.testing.assert_allclose(beta[-2:],mod.beta,atol=1e-10);np.testing.assert_allclose(beta[:12],[mod.climate[m] for m in range(1,13)],atol=1e-10)
 def test_n4_held_labels_cannot_affect_predict(self):
  mod=ClimatologyPT().fit(TrainingBatch(self.tx,self.ty));before=mod.predict(self.vx).raw.copy()
  self.y[self.x.years==2006]=99999
  np.testing.assert_array_equal(before,mod.predict(self.vx).raw)
  self.assertEqual(list(inspect.signature(mod.predict).parameters),["features_test"])
 def test_training_label_sensitivity(self):
  a=ClimatologyPT(1).fit(TrainingBatch(self.tx,self.ty));b=ClimatologyPT(1).fit(TrainingBatch(self.tx,self.ty+1))
  np.testing.assert_allclose(b.predict(self.vx).raw-a.predict(self.vx).raw,1)
 def test_inner_transform_refitted_and_outer_isolated(self):
  mod=ClimatologyPT().fit(TrainingBatch(self.tx,self.ty))
  self.assertEqual(len(mod.cv_trace),5)
  for r in mod.cv_trace:
   for f in r["folds"]:
    self.assertNotIn(2006,f["transform_fit_years"]);self.assertNotIn(f["held_year"],f["transform_fit_years"])
    self.assertEqual(f["train_ids_hash"],f["transform_fit_ids_hash"])
  self.assertEqual(set(mod.transformer.fit_ids),set(self.tx.ids))
 def test_centered_train_and_manual_standardization(self):
  mod=ClimatologyPT(1).fit(TrainingBatch(self.tx,self.ty));z=mod.transformer.transform(self.tx)
  for m in range(1,13):
   ix=self.tx.months==m
   np.testing.assert_allclose(z[ix].mean(axis=0),0,atol=1e-12);np.testing.assert_allclose(z[ix].std(axis=0,ddof=1),1,atol=1e-12)
 def test_test_labels_rejected_in_training(self):
  with self.assertRaises(ValueError):TrainingBatch(self.vx,self.y[self.x.years==2006])
 def test_repeat_deterministic(self):
  a=ClimatologyPT().fit(TrainingBatch(self.tx,self.ty));b=ClimatologyPT().fit(TrainingBatch(self.tx,self.ty));np.testing.assert_array_equal(a.predict(self.vx).raw,b.predict(self.vx).raw)
if __name__=="__main__":
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Controls);result=unittest.TextTestRunner(verbosity=2).run(suite)
 (P/"evidence/UNIT_LEAKAGE_TESTS.json").write_text(json.dumps({"synthetic_fixtures_only":True,"tests_run":result.testsRun,"failures":[str(x) for x in result.failures],"errors":[str(x) for x in result.errors],"success":result.wasSuccessful()},indent=2),encoding="utf-8")
 raise SystemExit(0 if result.wasSuccessful() else 1)
