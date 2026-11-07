"""Load exact frozen pure-Python definitions, avoiding Numba import/cache writes.

No equations are copied/reimplemented. The AST is compiled with the original
filename. No historical main(), JIT or real-data routine is executed.
"""
import ast
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'scripts/bd1m_physics_routing_model.py'
NAMES={'RoutingParameters','ordered_reaches','residence_times','substep_count','route_daily','initialize_steady_state'}
tree=ast.parse(SOURCE.read_text(encoding='utf-8'),filename=str(SOURCE))
tree.body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in NAMES]
exec(compile(tree,str(SOURCE),'exec'),globals())
