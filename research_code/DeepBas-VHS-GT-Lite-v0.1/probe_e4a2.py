import sys
sys.path.insert(0, "scripts")
import pandas as pd, numpy as np
from bd1m_physics_routing_model import ordered_reaches, residence_times, RoutingParameters, substep_count
nodes = ordered_reaches(pd.read_csv("outputs/vhs_bd1m/bd1m_reach_graph_nodes.csv"), pd.read_csv("outputs/vhs_bd1m/bd1m_reach_graph_edges.csv"))
for name, p in [("R1_default_tau0=2", RoutingParameters(2.0, 1.0, -0.5, 0.0)), ("R2_seed0_start", RoutingParameters(19.0, 0.5, -0.5, 0.0))]:
    tau = residence_times(nodes, p)
    steps = substep_count(tau)
    print(name, "min_tau=%.4f" % tau.min(), "max_tau=%.4f" % tau.max(), "substeps=%d" % steps,
          "updates_per_obj=%d" % (1461 * steps * 68), "inner_iter=%d" % (1461 * steps))
try:
    import numba
    print("numba", numba.__version__)
except Exception as e:
    print("numba_missing", e)
import os
for f in ["outputs/vhs_bd1m/experiments/e4a2_r2_multistart_train_fit_checkpoint.csv",
          "outputs/vhs_bd1m/experiments/e4a2_r2_multistart_train_fit.csv",
          "outputs/vhs_bd1m/experiments/e4a2_train_daily_q.csv"]:
    print(f, os.path.exists(f), os.path.getsize(f) if os.path.exists(f) else "-")
