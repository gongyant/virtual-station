"""Synthetic perturbation audit of existing normalization and target masking.

No neural model is instantiated; all tensors are CPU synthetic placeholders.
"""
import ast, copy, json, os, sys, warnings
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
os.environ['CUDA_VISIBLE_DEVICES']='-1'
import numpy as np
import torch
from torch.utils.data import Dataset
ROOT=Path(__file__).resolve().parents[3]
source=ROOT/'src/vhs/data.py'
tree=ast.parse(source.read_text(encoding='utf-8'))
tree.body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in {'Normalization','fit_normalization','WindowDataset'}]
exec(compile(tree,str(source),'exec'),globals())
rng=np.random.default_rng(19)
b=SimpleNamespace(x=rng.uniform(1,10,(12,2,2)).astype(np.float32),y=rng.uniform(1,10,(12,2)).astype(np.float32),y_mask=np.ones((12,2),bool),static=np.array([[1.],[2.]],np.float32),station_ids=np.array(['UP','TARGET']),feature_names=np.array(['obs_q','physical_reference_q']),edge_index=np.array([[0],[1]]))
out=[]
for mode in ['global','station_reference']:
    n=fit_normalization(b,6,['TARGET'],'obs_q',mode,'physical_reference_q')
    changed=copy.deepcopy(b);changed.x[:,1,0]=999999;changed.y[:,1]=888888;changed.x[6:,0,:]=777777;changed.y[6:,0]=666666
    n2=fit_normalization(changed,6,['TARGET'],'obs_q',mode,'physical_reference_q')
    for k in n.__dict__:np.testing.assert_array_equal(getattr(n,k),getattr(n2,k))
    common=dict(indices=np.array([8]),history=1,flow_feature='obs_q',target_station_ids=['TARGET'],input_feature_names=['obs_q','physical_reference_q'],current_snapshot=True,output_reference_feature='physical_reference_q')
    d=WindowDataset(b,normalization=n,**common);dd=WindowDataset(changed,normalization=n2,**common)
    np.testing.assert_array_equal(d.x[:,1],dd.x[:,1]);assert np.all(d.x[:,1,[0,2]]==0)
    # This retained reference is why unknown MQ lineage remains a separate risk.
    assert bool(d[0]['output_reference_mask'][1])
    out.append({'mode':mode,'target_obs_changes_leave_target_features_unchanged':True,'target_obs_and_nontraining_changes_leave_scalers_unchanged':True,'target_reference_retained':True,'status':'PASS'})
payload={'label':'SYNTHETIC_UNIT_TEST_ONLY','scope':'current source normalization/window definitions; not proof of historical checkpoint implementation or reference provenance','results':out,'torch_version':torch.__version__,'cuda_tasks_started':False}
path=ROOT/'research_next/vhs_transfer/tests/synthetic_input_boundary.json';path.write_text(json.dumps(payload,indent=2),encoding='utf-8');print(json.dumps(payload,indent=2))
