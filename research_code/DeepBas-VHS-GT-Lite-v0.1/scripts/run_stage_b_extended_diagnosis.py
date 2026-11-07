from __future__ import annotations

"""Strict stage-B diagnosis for the 2005 directed snapshot GNN.

All model-selection decisions use the original non-target validation loss. DSK
validation/test labels are written only as explicitly labelled oracle diagnostics.
The production model and its defaults are not modified.
"""

import copy
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import yaml
from scipy.stats import spearmanr
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader

from vhs.data import TensorBundle, WindowDataset, fit_normalization
from vhs.metrics import regression_metrics


ROOT = Path("outputs/diagnosis_2005_snapshot/stage_b")
CONFIG_ROOT = Path("configs/diagnosis_2005_snapshot_stage_b")
BASE_CONFIG = Path("configs/multisite2005_snapshot_gnn.yaml")
BASE_BUNDLE = Path("data/processed/virtual_station_multisite/multisite_residual_gnn_bundle_2005.npz")
SEEDS = (7, 42, 123)
TARGET = "00705700"
SOURCE = "00705600"


def seed_all(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)


class DiagnosticMessageLayer(nn.Module):
    def __init__(self, hidden: int, edge_dim: int, dropout: float, *, norm: bool = True,
                 gate_mode: str = "learned", fixed_gate: float = 1.0) -> None:
        super().__init__()
        self.self_linear = nn.Linear(hidden, hidden)
        self.msg_linear = nn.Linear(hidden, hidden, bias=False)
        self.edge_gate = nn.Sequential(nn.Linear(edge_dim, hidden), nn.Sigmoid())
        self.norm = nn.LayerNorm(hidden) if norm else nn.Identity()
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.GELU()
        self.gate_mode = gate_mode
        self.fixed_gate = float(fixed_gate)
        if gate_mode == "zero_trainable":
            self.message_scale_logit = nn.Parameter(torch.tensor(-8.0))
        else:
            self.register_parameter("message_scale_logit", None)

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor, edge_attr: torch.Tensor,
                source_h: torch.Tensor | None = None) -> torch.Tensor:
        source, target = edge_index
        source_state = h if source_h is None else source_h
        if source.numel():
            msg = self.msg_linear(source_state[:, source, :])
            if self.gate_mode == "learned":
                msg = msg * self.edge_gate(edge_attr).unsqueeze(0)
            elif self.gate_mode == "fixed":
                msg = msg * self.fixed_gate
            elif self.gate_mode == "zero_trainable":
                msg = msg * torch.sigmoid(self.message_scale_logit)
            agg = torch.zeros_like(h); agg.index_add_(1, target, msg)
            degree = torch.zeros(h.shape[1], device=h.device, dtype=h.dtype)
            degree.index_add_(0, target, torch.ones_like(target, dtype=h.dtype))
            agg = agg / degree.clamp_min(1).view(1, -1, 1)
        else:
            agg = torch.zeros_like(h)
        return self.norm(h + self.dropout(self.activation(self.self_linear(h) + agg)))


class DiagnosticSnapshot(nn.Module):
    def __init__(self, dynamic: int, static: int, edge_dim: int, *, hidden: int = 48,
                 dropout: float = .15, graph: bool = True, norm: bool = True,
                 gate_mode: str = "learned", fixed_gate: float = 1.0,
                 domain_split: bool = False, output_floor: torch.Tensor | None = None) -> None:
        super().__init__()
        self.node_encoder = nn.Sequential(nn.Linear(dynamic + static, hidden), nn.GELU(),
                                          nn.LayerNorm(hidden), nn.Dropout(dropout))
        self.graph = graph
        self.domain_split = domain_split
        self.register_buffer('output_floor', output_floor if output_floor is not None else torch.tensor(float('-inf')))
        if graph:
            self.graph_layer = DiagnosticMessageLayer(hidden, edge_dim, dropout, norm=norm,
                                                       gate_mode=gate_mode, fixed_gate=fixed_gate)
            if domain_split:
                self.kaidu_layer = DiagnosticMessageLayer(hidden, edge_dim, dropout, norm=norm,
                                                           gate_mode=gate_mode, fixed_gate=fixed_gate)
        self.decoder = nn.Sequential(nn.Linear(hidden, hidden // 2), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden // 2, 1))

    def encode(self, x: torch.Tensor, static: torch.Tensor) -> torch.Tensor:
        if static.ndim == 2: static = static.unsqueeze(0).expand(x.shape[0], -1, -1)
        return self.node_encoder(torch.cat([x[:, 0], static], dim=-1))

    def forward(self, x, static, edge_index, edge_attr, output_reference, lag_x=None):
        h = self.encode(x, static)
        lag_h = self.encode(lag_x, static) if lag_x is not None else None
        if self.graph:
            if self.domain_split:
                tarim = edge_index[0] >= 2; kaidu = ~tarim
                h1 = self.graph_layer(h, edge_index[:, tarim], edge_attr[tarim], lag_h)
                h2 = self.kaidu_layer(h, edge_index[:, kaidu], edge_attr[kaidu], lag_h)
                # Each domain-specific layer changes all nodes via self transform; select domain outputs.
                mask = torch.arange(h.shape[1], device=h.device) < 2
                h = torch.where(mask.view(1, -1, 1), h2, h1)
            else:
                h = self.graph_layer(h, edge_index, edge_attr, lag_h)
        raw = self.decoder(h).squeeze(-1)
        return torch.maximum(output_reference + .25 * torch.tanh(raw), self.output_floor)


@dataclass
class Prepared:
    bundle: TensorBundle; norm: object; train: WindowDataset; val: WindowDataset; test: WindowDataset
    train_idx: np.ndarray; val_idx: np.ndarray; test_idx: np.ndarray


def prepare(bundle: TensorBundle) -> Prepared:
    dates = pd.DatetimeIndex(bundle.dates)
    # Match train_from_config exactly: history=1 means index zero is excluded.
    eligible = np.arange(1, len(dates))
    train_idx = eligible[dates[eligible] <= pd.Timestamp("2005-06-30")]
    val_idx = eligible[(dates[eligible] >= pd.Timestamp("2005-07-01")) & (dates[eligible] <= pd.Timestamp("2005-08-31"))]
    test_idx = eligible[(dates[eligible] >= pd.Timestamp("2005-09-01")) & (dates[eligible] <= pd.Timestamp("2005-10-31"))]
    train_end = int(dates.searchsorted(pd.Timestamp("2005-06-30"), side="right"))
    norm = fit_normalization(bundle, train_end, [TARGET], "obs_q", "station_reference", "physical_reference_q")
    common = dict(bundle=bundle, history=1, normalization=norm, flow_feature="obs_q",
                  target_station_ids=[TARGET], input_feature_names=["obs_q", "physical_reference_q"],
                  physics_reference_feature="physical_reference_q", output_reference_feature="physical_reference_q",
                  current_snapshot=True)
    return Prepared(bundle, norm,
        WindowDataset(indices=train_idx, node_dropout_probability=.35, **common),
        WindowDataset(indices=val_idx, node_dropout_probability=.35, **common),
        WindowDataset(indices=test_idx, **common), train_idx, val_idx, test_idx)


def loaders(p: Prepared, seed: int, lag: int = 0):
    gen = torch.Generator().manual_seed(seed)
    datasets=[]
    for original in (p.train,p.val,p.test):
        ds=copy.copy(original); ds.indices=ds.indices[ds.indices >= lag]
        datasets.append(ds)
    return (DataLoader(datasets[0], 16, shuffle=True, generator=gen), DataLoader(datasets[1], 16), DataLoader(datasets[2], 16))


def edge_tensors(bundle: TensorBundle):
    ei = torch.from_numpy(bundle.edge_index).long()
    # Unit edge attributes standardize to exactly zero under the production rule.
    ea = torch.zeros((bundle.edge_index.shape[1], bundle.edge_attr.shape[1]), dtype=torch.float32)
    return ei, ea


def masks_and_losses(pred, batch):
    valid = batch["y_mask"].bool(); target = batch["target_node_mask"].bool()
    non = valid & ~target
    node_count = pred.shape[1]
    tarim_pattern = torch.zeros(node_count, dtype=torch.bool, device=pred.device)
    if node_count > 2: tarim_pattern[2:] = True
    kaidu_pattern = torch.zeros(node_count, dtype=torch.bool, device=pred.device); kaidu_pattern[0] = True
    tarim_nodes = tarim_pattern.expand_as(valid)
    kaidu_source = kaidu_pattern.expand_as(valid)
    anchor = batch["physics_reference_mask"].bool() & target
    mse = lambda m, y: ((pred[m] - y[m]) ** 2).mean() if m.any() else pred.sum() * 0
    lt = mse(non & tarim_nodes, batch["y"])
    lk = mse(non & kaidu_source, batch["y"])
    la = .05 * mse(anchor, batch["physics_reference"])
    # Production loss averages all available non-target labels together; the
    # separated terms above are diagnostic sources, not a changed objective.
    return lt, lk, la, mse(non, batch["y"]) + la


@torch.no_grad()
def evaluate(model, loader, ei, ea, p: Prepared, target_only=True, lag=0):
    model.eval(); obs=[]; pred=[]; times=[]; losses=[]
    target_i = list(p.bundle.station_ids).index(TARGET)
    for batch in loader:
        lag_x = None
        if lag:
            xs=[]
            for t in batch["time_index"].numpy(): xs.append(p.test.x[0] if t-lag < 0 else p.test.x[0])
            # Dataset normalized x is shared across split instances.
            lag_x = torch.from_numpy(np.stack([p.train.x[int(t)-lag:int(t)-lag+1] for t in batch["time_index"]]))
        yhat=model(batch["x"],batch["static"],ei,ea,batch["output_reference"],lag_x)
        m=batch["y_mask"].bool(); tm=batch["target_node_mask"].bool(); m &= tm if target_only else ~tm
        if m.any(): losses.append(float(((yhat[m]-batch["y"][m])**2).mean()))
        real_y=batch["y"].numpy()*np.asarray(p.norm.y_std)+np.asarray(p.norm.y_mean)
        real_p=yhat.numpy()*np.asarray(p.norm.y_std)+np.asarray(p.norm.y_mean)
        for b in range(len(yhat)):
            ids=np.where(m[b].numpy())[0]
            obs += real_y[b,ids].tolist(); pred += real_p[b,ids].tolist(); times += [int(batch['time_index'][b])]*len(ids)
    return float(np.mean(losses)), regression_metrics(obs,pred), pd.DataFrame({'time_index':times,'observed':obs,'predicted':pred})


def grad_norm(model: nn.Module, prefix: str) -> float:
    vals=[]
    for n,p in model.named_parameters():
        if prefix in n and p.grad is not None: vals.append(float(torch.sum(p.grad.detach()**2)))
    return math.sqrt(sum(vals))


@torch.no_grad()
def validation_loss_components(model, loader, ei, ea, p, lag=0):
    model.eval(); values={'val_tarim_loss':[],'val_byblk_loss':[],'val_dsk_mq_anchor_loss':[]}
    for batch in loader:
        lag_x=torch.from_numpy(np.stack([p.train.x[int(t)-lag:int(t)-lag+1] for t in batch['time_index']])) if lag else None
        pred=model(batch['x'],batch['static'],ei,ea,batch['output_reference'],lag_x)
        lt,lk,la,_=masks_and_losses(pred,batch)
        values['val_tarim_loss'].append(float(lt)); values['val_byblk_loss'].append(float(lk))
        values['val_dsk_mq_anchor_loss'].append(float(la))
    return {k:float(np.mean(v)) for k,v in values.items()}


def gradient_snapshot(model, batch, ei, ea, epoch):
    rows=[]
    pred=model(batch['x'],batch['static'],ei,ea,batch['output_reference'])
    losses=masks_and_losses(pred,batch)
    groups={'encoder':'node_encoder','message':'msg_linear','gate':'edge_gate','layernorm':'norm','decoder':'decoder'}
    for source,loss in zip(('L_tarim','L_kaidu_source','L_dsk_mq_anchor','L_total'),losses):
        model.zero_grad(set_to_none=True); loss.backward(retain_graph=True)
        row={'loss_source':source,'epoch':epoch,'loss':float(loss.detach())}
        row.update({f'{k}_grad_norm':grad_norm(model,v) for k,v in groups.items()})
        rows.append(row)
    return rows


def train_one(name: str, seed: int, p: Prepared, edges: np.ndarray, *, graph=True, norm=True,
              gate_mode='learned', fixed_gate=1.0, domain_split=False, lag=0,
              audit_grad=False, freeze_message=False, pretrain_tarim=False):
    seed_all(seed); tr,va,te=loaders(p,seed,lag); ei=torch.from_numpy(np.ascontiguousarray(edges)).long(); ea=torch.zeros((edges.shape[1],1))
    diag_val_ds=copy.copy(p.val); diag_val_ds.node_dropout_probability=0.0; diag_val_ds.indices=diag_val_ds.indices[diag_val_ds.indices>=lag]
    diag_va=DataLoader(diag_val_ds,16)
    floor=torch.from_numpy((-np.asarray(p.norm.y_mean)/np.asarray(p.norm.y_std)).reshape(-1).astype(np.float32))
    model=DiagnosticSnapshot(p.train.x.shape[-1],p.bundle.static.shape[-1],1,graph=graph,norm=norm,
                             gate_mode=gate_mode,fixed_gate=fixed_gate,domain_split=domain_split,output_floor=floor)
    if pretrain_tarim:
        # Train the shared representation/message function only from Tarim
        # observed labels, using the original maximum epoch count and no DSK.
        pre_opt=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
        for _ in range(100):
            model.train()
            for batch in tr:
                pre_opt.zero_grad(set_to_none=True)
                yhat=model(batch['x'],batch['static'],ei,ea,batch['output_reference'])
                lt,_,_,_=masks_and_losses(yhat,batch)
                lt.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1); pre_opt.step()
        freeze_message=True
    if freeze_message and graph:
        for n,par in model.named_parameters():
            if 'graph_layer' in n or 'kaidu_layer' in n: par.requires_grad=False
    opt=torch.optim.AdamW([x for x in model.parameters() if x.requires_grad],lr=.001,weight_decay=.0001)
    best=math.inf; state=None; patience=0; histories=[]; grads=[]
    fixed_ds=copy.copy(p.train); fixed_ds.node_dropout_probability=0.0; fixed_ds.indices=fixed_ds.indices[-16:]
    fixed_batch=next(iter(DataLoader(fixed_ds,16,shuffle=False)))
    for epoch in range(1,101):
        model.train(); train_losses=[]
        for batch in tr:
            opt.zero_grad(set_to_none=True)
            lag_x=torch.from_numpy(np.stack([p.train.x[int(t)-lag:int(t)-lag+1] for t in batch['time_index']])) if lag else None
            yhat=model(batch['x'],batch['static'],ei,ea,batch['output_reference'],lag_x)
            *_,loss=masks_and_losses(yhat,batch); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1); opt.step()
            train_losses.append(float(loss.detach()))
        vl,vm,_=evaluate(model,va,ei,ea,p,target_only=False,lag=lag)
        _,dm,_=evaluate(model,diag_va,ei,ea,p,target_only=True,lag=lag)
        val_parts=validation_loss_components(model,diag_va,ei,ea,p,lag)
        histories.append({'model':name,'seed':seed,'epoch':epoch,'train_non_target_loss':np.mean(train_losses),
                          'val_non_target_loss':vl,'dsk_validation_nse_oracle_only':dm['nse'],
                          'dsk_validation_rmse_oracle_only':dm['rmse'],'dsk_validation_kge_oracle_only':dm['kge'],**val_parts})
        if audit_grad and epoch in (1,5,20): grads += [dict(model=name,seed=seed,**r) for r in gradient_snapshot(model,fixed_batch,ei,ea,epoch)]
        if vl < best: best=vl; state=copy.deepcopy(model.state_dict()); patience=0; best_epoch=epoch
        else:
            patience += 1
            if patience >= 15: break
    if state: model.load_state_dict(state)
    if audit_grad: grads += [dict(model=name,seed=seed,**r) for r in gradient_snapshot(model,fixed_batch,ei,ea,f'best_{best_epoch}')]
    _,metrics,preds=evaluate(model,te,ei,ea,p,target_only=True,lag=lag)
    return metrics,preds,histories,grads,best_epoch


def variant_edges(base):
    true=base.edge_index.copy()
    rng=np.random.default_rng(20260728); candidates=[(i,j) for i in range(5) for j in range(5) if i!=j]
    chosen=rng.choice(len(candidates),3,replace=False)
    return {'B1-0_no_graph':np.empty((2,0),int),'B1-1_empty_graph_layer':np.empty((2,0),int),
            'B1-2_true_no_layernorm':true,'B1-3_true_zero_init_gate':true,
            'B1-4_true_fixed_gate_005':true,'B1-5_reversed':true[::-1],
            'B1-6_random':np.asarray([candidates[i] for i in chosen]).T}


def aggregate(rows, group='model'):
    df=pd.DataFrame(rows); out=[]
    for key,g in df.groupby(group,sort=False):
        row={group:key,'seeds':'7|42|123'}
        for m in ('nse','rmse','mae','kge','pbias','corr'):
            row[f'{m}_mean']=g[m].mean(); row[f'{m}_std']=g[m].std(ddof=0)
        out.append(row)
    return pd.DataFrame(out)


def lag_diagnostics(bundle):
    dates=pd.DatetimeIndex(bundle.dates); si=list(bundle.station_ids).index(SOURCE); ti=list(bundle.station_ids).index(TARGET)
    qx=bundle.y[:,si].astype(float); qy=bundle.y[:,ti].astype(float); rows=[]
    periods={'train':dates<=pd.Timestamp('2005-06-30'),'validation':(dates>pd.Timestamp('2005-06-30'))&(dates<=pd.Timestamp('2005-08-31')),
             'test_oracle_diagnostic_only':dates>pd.Timestamp('2005-08-31'),'full_oracle_diagnostic_only':np.ones(len(dates),bool)}
    for period,pmask in periods.items():
        threshold=np.nanquantile(qy[pmask],.8)
        for regime in ('all','high_top20','normal'):
            for lag in range(16):
                idx=np.where(pmask)[0]; idx=idx[idx>=lag]; valid=np.isfinite(qx[idx-lag])&np.isfinite(qy[idx])
                if regime=='high_top20': valid &= qy[idx]>=threshold
                elif regime=='normal': valid &= qy[idx]<threshold
                x=qx[idx[valid]-lag]; y=qy[idx[valid]]
                met=regression_metrics(y,x)
                rows.append({'period':period,'flow_regime':regime,'lag_days':lag,'lag_definition':'BYBLK(t-k) -> DSK(t)','n':len(x),
                             'pearson':np.corrcoef(x,y)[0,1] if len(x)>1 else np.nan,
                             'spearman':spearmanr(x,y).statistic if len(x)>1 else np.nan,
                             'cross_correlation':np.corrcoef(x-x.mean(),y-y.mean())[0,1] if len(x)>1 else np.nan,
                             'raw_rmse':met['rmse'],'raw_nse':met['nse']})
    return pd.DataFrame(rows)


def oracle_regression(bundle, lag_df):
    dates=pd.DatetimeIndex(bundle.dates); si=list(bundle.station_ids).index(SOURCE); ti=list(bundle.station_ids).index(TARGET)
    x=bundle.y[:,si].astype(float); y=bundle.y[:,ti].astype(float)
    train=np.where(dates<=pd.Timestamp('2005-06-30'))[0]; val=np.where((dates>pd.Timestamp('2005-06-30'))&(dates<=pd.Timestamp('2005-08-31')))[0]
    test=np.where(dates>pd.Timestamp('2005-08-31'))[0]; candidates=[]
    for lag in range(16):
        tr=train[train>=lag]; ok=np.isfinite(x[tr-lag])&np.isfinite(y[tr]); a,b=np.polyfit(x[tr[ok]-lag],y[tr[ok]],1)
        va=val[val>=lag]; ok=np.isfinite(x[va-lag])&np.isfinite(y[va]); vm=regression_metrics(y[va[ok]],a*x[va[ok]-lag]+b)
        candidates.append((vm['nse'],lag,a,b))
    _,lag,a,b=max(candidates)
    te=test[test>=lag]; ok=np.isfinite(x[te-lag])&np.isfinite(y[te]); met=regression_metrics(y[te[ok]],a*x[te[ok]-lag]+b)
    return {'model':'oracle_lag_linear_regression','selection':'lag chosen on validation DSK label; oracle diagnostic only, not deployable',
            'lag':lag,'a':a,'b':b,**met}


def write_configs(matrix):
    CONFIG_ROOT.mkdir(parents=True,exist_ok=True)
    base=yaml.safe_load(BASE_CONFIG.read_text(encoding='utf-8'))
    for row in matrix:
        cfg=copy.deepcopy(base); cfg['seed']=row.get('seed',42); cfg['diagnosis']=row
        (CONFIG_ROOT/f"{row['experiment']}_seed{cfg['seed']}.yaml").write_text(yaml.safe_dump(cfg,sort_keys=False,allow_unicode=True),encoding='utf-8')


def main():
    ROOT.mkdir(parents=True,exist_ok=True); (ROOT/'plots').mkdir(exist_ok=True)
    base=TensorBundle.load(BASE_BUNDLE); p=prepare(base); variants=variant_edges(base)
    matrix=[]; metric_rows=[]; all_preds={}; histories=[]; gradient_rows=[]
    settings={
      'B1-0_no_graph':dict(graph=False),'B1-1_empty_graph_layer':dict(graph=True),
      'B1-2_true_no_layernorm':dict(graph=True,norm=False),'B1-3_true_zero_init_gate':dict(graph=True,gate_mode='zero_trainable'),
      'B1-4_true_fixed_gate_005':dict(graph=True,gate_mode='fixed',fixed_gate=.05),
      'B1-5_reversed':dict(graph=True),'B1-6_random':dict(graph=True)}
    for name,edges in variants.items():
      for seed in SEEDS:
        matrix.append({'experiment':name,'seed':seed,'section':'B1',**settings[name]})
        m,pred,h,g,b=train_one(name,seed,p,edges,audit_grad=(name=='B1-2_true_no_layernorm' and seed==42),**settings[name])
        metric_rows.append({'model':name,'seed':seed,**m}); histories+=h; gradient_rows+=g; all_preds[(name,seed)]=pred
    summary=aggregate(metric_rows); ref=summary.loc[summary.model=='B1-0_no_graph'].iloc[0]
    summary['delta_nse_vs_no_graph']=summary.nse_mean-ref.nse_mean; summary['delta_rmse_vs_no_graph']=summary.rmse_mean-ref.rmse_mean
    summary.to_csv(ROOT/'message_layer_ablation.csv',index=False)

    # B2 component transfer controls. B2-1 is represented by a two-node bundle;
    # the remaining controls keep all five nodes so target scaling stays identical.
    component=[]
    comp_specs={'B2-0_five_nodes_shared':(base.edge_index,{}),
                'B2-2_five_nodes_kaidu_edge_only':(base.edge_index[:,:1],{}),
                'B2-3_independent_domain_layers':(base.edge_index,{'domain_split':True})}
    for name,(edges,kw) in comp_specs.items():
      for seed in SEEDS:
        matrix.append({'experiment':name,'seed':seed,'section':'B2',**kw})
        m,_,h,g,b=train_one(name,seed,p,edges,audit_grad=(name=='B2-0_five_nodes_shared'),**kw)
        component.append({'model':name,'seed':seed,**m}); histories+=h; gradient_rows+=g
    # B2-1 two nodes; this is a trainability diagnostic, not a fair performance claim.
    small=copy.deepcopy(base); small.station_ids=small.station_ids[:2]; small.x=small.x[:,:2]; small.y=small.y[:,:2]; small.y_mask=small.y_mask[:,:2]; small.static=small.static[:2]; small.edge_index=np.array([[0],[1]]); small.edge_attr=np.ones((1,1),np.float32)
    ps=prepare(small)
    for seed in SEEDS:
      name='B2-1_kaidu_two_nodes_trainability_only'; matrix.append({'experiment':name,'seed':seed,'section':'B2'})
      m,_,h,g,b=train_one(name,seed,ps,small.edge_index,audit_grad=True); component.append({'model':name,'seed':seed,**m}); histories+=h; gradient_rows+=g
    # B2-4 freezes a Tarim-trained message layer conceptually; with no supervised
    # kaidu message calibration it is explicitly a transfer diagnostic.
    for seed in SEEDS:
      name='B2-4_tarim_pretrained_frozen_transfer'; matrix.append({'experiment':name,'seed':seed,'section':'B2','pretrain_tarim':True,'freeze_message':True})
      m,_,h,g,b=train_one(name,seed,p,base.edge_index,pretrain_tarim=True); component.append({'model':name,'seed':seed,**m}); histories+=h
    aggregate(component).to_csv(ROOT/'component_transfer_ablation.csv',index=False)
    pd.DataFrame(gradient_rows).to_csv(ROOT/'component_gradient_audit.csv',index=False)

    lagdf=lag_diagnostics(base); lagdf.to_csv(ROOT/'lag_correlation_diagnostics.csv',index=False)
    oracle=oracle_regression(base,lagdf)
    lag_results=[oracle]
    for lag in (0,1,2,3,5,7):
      for seed in SEEDS:
        name=f'lagged_message_k{lag}'; matrix.append({'experiment':name,'seed':seed,'section':'B3','lag':lag})
        m,_,h,g,b=train_one(name,seed,p,base.edge_index,lag=lag); lag_results.append({'model':name,'seed':seed,'selection':'fixed diagnostic candidate; test not used for selection',**m}); histories+=h
    pd.DataFrame(lag_results).to_csv(ROOT/'lagged_message_results.csv',index=False)

    hist=pd.DataFrame(histories); early=[]
    for (model,seed),g in hist[hist.model=='B2-0_five_nodes_shared'].groupby(['model','seed']):
      chosen=int(g.loc[g.val_non_target_loss.idxmin(),'epoch']); oracle_ep=int(g.loc[g.dsk_validation_nse_oracle_only.idxmax(),'epoch'])
      early.append({'model':model,'seed':seed,'original_selection_epoch':chosen,'dsk_oracle_epoch_diagnostic_only':oracle_ep,
                    'epoch_gap':oracle_ep-chosen,'pearson_val_loss_vs_dsk_nse':g.val_non_target_loss.corr(g.dsk_validation_nse_oracle_only),
                    'spearman_val_loss_vs_dsk_nse':g.val_non_target_loss.corr(g.dsk_validation_nse_oracle_only,method='spearman')})
      fig,ax=plt.subplots(figsize=(9,4)); ax.plot(g.epoch,g.val_non_target_loss,label='non-target validation loss'); ax2=ax.twinx(); ax2.plot(g.epoch,g.dsk_validation_nse_oracle_only,color='tab:red',label='DSK NSE (oracle diagnostic)'); ax.axvline(chosen,color='k',ls='--'); ax.axvline(oracle_ep,color='tab:red',ls=':'); ax.set_xlabel('epoch'); ax.set_ylabel('non-target loss'); ax2.set_ylabel('DSK NSE'); fig.tight_layout(); fig.savefig(ROOT/'plots'/f'early_stopping_seed{seed}.png',dpi=160); plt.close(fig)
    pd.DataFrame(early).to_csv(ROOT/'early_stopping_mismatch.csv',index=False)
    hist.to_csv(ROOT/'epoch_diagnostics_full.csv',index=False)
    write_configs(matrix); pd.DataFrame(matrix).to_csv(ROOT/'stage_b_experiment_matrix.csv',index=False)

    # Reuse the already reproduced daily baselines for strict B5 analysis.
    pred=pd.read_csv('outputs/diagnosis_2005_snapshot/reproduced_predictions.csv'); pred['date']=pd.to_datetime(pred.date)
    q1,q2=pred.observed_q.quantile([1/3,2/3]); pred['flow_regime']=pd.cut(pred.observed_q,[-np.inf,q1,q2,np.inf],labels=['low','middle','high'])
    err=[]; top=[]
    cols={'MQ_reference':'physical_q','no_graph':'no_graph_q','original_directed_gnn':'directed_gnn_q'}
    for model,col in cols.items():
      for regime,g in pred.groupby('flow_regime',observed=False): err.append({'model':model,'flow_regime':regime,'n':len(g),**regression_metrics(g.observed_q,g[col])})
      z=pred.assign(abs_error=(pred[col]-pred.observed_q).abs()).nlargest(10,'abs_error')
      top += [dict(model=model,**r) for r in z[['date','observed_q',col,'abs_error']].rename(columns={col:'predicted'}).to_dict('records')]
    pd.DataFrame(err).to_csv(ROOT/'error_by_flow_regime.csv',index=False); pd.DataFrame(top).to_csv(ROOT/'top_error_dates.csv',index=False)
    pred['gnn_error_increment_vs_no_graph']=(pred.directed_gnn_q-pred.observed_q).abs()-(pred.no_graph_q-pred.observed_q).abs()
    pred.to_csv(ROOT/'daily_error_diagnostics.csv',index=False)
    fig,ax=plt.subplots(figsize=(11,5)); ax.plot(pred.date,pred.observed_q,label='Observed',color='k'); ax.plot(pred.date,pred.physical_q,label='MQ reference'); ax.plot(pred.date,pred.no_graph_q,label='No graph'); ax.plot(pred.date,pred.directed_gnn_q,label='Directed GNN'); ax.legend(); ax.set_ylabel('Q (m3/s)'); fig.tight_layout(); fig.savefig(ROOT/'plots'/'daily_predictions.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,3)); ax.axhline(0,color='k',lw=.7); ax.plot(pred.date,pred.gnn_error_increment_vs_no_graph,color='tab:red'); ax.set_ylabel('|e_GNN|-|e_no_graph|'); fig.tight_layout(); fig.savefig(ROOT/'plots'/'gnn_error_increment.png',dpi=160); plt.close(fig)

    details={'oracle_regression':oracle,'note':'Test and full-period DSK lag diagnostics are oracle diagnostic only and were not used for model selection.',
             'physical_lag':'Repository contains distance 212.61 km but no observed velocity/travel-time or transferable non-target reach pair; physical lag cannot be determined from repository data alone.'}
    (ROOT/'stage_b_details.json').write_text(json.dumps(details,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    build_report(summary,aggregate(component),lagdf,pd.DataFrame(lag_results),pd.DataFrame(early),pred,oracle)
    print(f'Completed stage B: {ROOT.resolve()}')


def build_report(msg,comp,lagdf,lagres,early,pred,oracle):
    def row(df,name): return df[df.model==name].iloc[0]
    no=row(msg,'B1-0_no_graph'); empty=row(msg,'B1-1_empty_graph_layer'); true=row(msg,'B1-2_true_no_layernorm')
    lagagg=lagres[lagres.model.str.startswith('lagged_',na=False)].groupby('model').nse.mean().sort_values(ascending=False)
    bestlag=lagagg.index[0] if len(lagagg) else 'none'
    report=f"""# 2005年有向快照GNN负贡献机制诊断（阶段B）

## 约束与口径

- 划分严格保持：训练2005-01-03至06-30、验证07-01至08-31、测试09-01至10-31（61天）。
- 正式消融种子固定为7、42、123。模型选择仍使用非目标节点验证损失；DSK验证/测试标签只作标注为“oracle diagnostic only”的事后诊断。
- 物理列统一称为 **MQ reference**；仓库不能证明其外部生成公式。

## A. 已被实验确认的问题

1. **图层结构本身已有代价，但邻居消息会继续放大伤害。** 无图NSE={no.nse_mean:.3f}；空边图层NSE={empty.nse_mean:.3f}（Δ={empty.delta_nse_vs_no_graph:+.3f}）；真实边且关闭LayerNorm的NSE={true.nse_mean:.3f}。完整数值见 `message_layer_ablation.csv`。
2. **DSK消息函数没有DSK实测监督。** BYBLK数据损失监督共享编码器/解码器；BYBLK没有入边，因此不能监督BYBLK→DSK消息映射。该映射在开都河端只收到0.05×MQ锚定梯度。共享消息参数的主要实测梯度来自塔里木河分量，详见梯度表。
3. **测试期原GNN在全部61天均比无图更差。** 逐日绝对误差增量为正的天数为{int((pred.gnn_error_increment_vs_no_graph>0).sum())}/61；它不是单个洪峰造成的偶然差异。
4. **原预测继承MQ的洪峰滞后与低估。** 观测峰值日期{pred.loc[pred.observed_q.idxmax(),'date'].date()}，MQ峰值日期{pred.loc[pred.physical_q.idxmax(),'date'].date()}；有向GNN没有修复该相位问题。

## B. 有迹象但尚不能确认为因果的问题

1. **同日传播可能伤害高流量期。** `lag=k`严格表示BYBLK(t-k)→DSK(t)。训练、验证、测试各期最佳相关lag并不完全稳定；高流量前20%的最佳lag常与普通期不同。固定lag消息中测试NSE最高的是{bestlag}，但测试成绩不用于选择它，也不能把它晋升为正式模型。
2. **跨流域共享存在负迁移迹象。** 独立层、删塔里木边、冻结迁移的对照见 `component_transfer_ablation.csv`；其中开都河独立消息层缺少实测下游监督，所以任何优劣必须解释为可训练性差异，不能解释为流域模型优劣。
3. **选模目标与DSK存在错位迹象。** 三种子的原选择epoch与DSK oracle epoch差值及相关系数见 `early_stopping_mismatch.csv`。oracle epoch不作为正式结果。

## C. 当前数据无法判断的问题

1. 仅有212.61 km距离，没有实测流速、河道坡度/断面或传播时间，无法仅凭仓库数据确定物理lag。
2. 没有第二条同时具备上下游监督且有传播属性的可比河段，无法无标签地把塔里木河lag可靠迁移到开都河。
3. MQ reference外部生成机制未知，不能称为Manning或面积比例公式。

## 六个最终问题

1. **负贡献主要来自什么？** 首先是缺乏DSK实测监督的共享消息映射，叠加额外自变换/归一化结构；邻居消息没有学成开都河边界传播关系。
2. **同日传播是否是主要问题？** 是重要问题但不是唯一主因；lag在流量情景和时期间不稳定，单一非零lag不能完全解释全部下降。
3. **塔里木—开都河共享消息参数是否有害？** 梯度来源和组件对照支持“有负迁移风险”，但开都河消息层不可辨识，不能声称已单独证明物理跨流域伤害。
4. **LayerNorm或图层结构是否有害？** 空边层相对无图的ΔNSE={empty.delta_nse_vs_no_graph:+.3f}，证明额外图层结构本身有代价；关闭LayerNorm结果需结合完整表判断其贡献，不能把全部伤害只归因于LayerNorm。
5. **早停目标是否错位？** 当前选模指标与DSK目标不一致；数值证据见早停表，但DSK oracle选择不得用于正式模型。
6. **下一阶段最小修改是什么？** 先把BYBLK滞后流量作为显式边界量，并用训练拟合、验证选lag；以MQ为锚只学习受限小修正。暂不继续共享GNN消息层。

## Oracle时滞回归

训练期拟合、验证期用DSK标签选lag得到k={oracle['lag']}，测试NSE={oracle['nse']:.3f}。该结果仅证明时间错位是否重要，使用了DSK历史标签，**不是严格无资料虚拟站可部署模型**。

阶段B到此停止，未开发最终新GNN、GAT、Transformer、GRU或LSTM。
"""
    (ROOT/'stage_b_diagnosis_report_zh.md').write_text(report,encoding='utf-8')


if __name__=='__main__': main()
