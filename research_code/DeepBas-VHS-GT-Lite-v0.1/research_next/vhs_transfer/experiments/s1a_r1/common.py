"""R1 artifact utilities. No model fitting or observation loading on import."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import hashlib
import json
import platform
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
R0=HERE.parent/'s1a'
REPORTS=ROOT/'research_next/vhs_transfer/reports'
sys.path.insert(0,str(R0))

def now():
    # Fixed requested client timezone, independent of Windows host timezone.
    return datetime.now(ZoneInfo('Asia/Singapore')).isoformat()

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def dump(path,obj,exclusive=False):
    with Path(path).open('x' if exclusive else 'w',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')

def load(path):
    return json.loads(Path(path).read_text('utf-8'))

def write_csv(path,rows,exclusive=True):
    if not rows: raise ValueError('Empty output')
    with Path(path).open('x' if exclusive else 'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

def event(kind,**kwargs):
    with (HERE/'execution_events.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({'time':now(),'event':kind,**kwargs},ensure_ascii=False,allow_nan=False)+'\n')

def environment():
    import contextlib, io, os
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf): np.show_config()
    return {'python':platform.python_version(),'python_executable':sys.executable,
            'numpy':np.__version__,'platform':platform.platform(),'machine':platform.machine(),
            'numpy_config':buf.getvalue(),'GPU_used':False,
            'thread_environment':{k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')}}

def verify_freeze():
    frozen=load(HERE/'s1a_r1_execution_manifest.json')
    for k,v in frozen['frozen_hashes'].items():
        if sha(ROOT/k)!=v: raise RuntimeError('Frozen artifact changed: '+k)
    if sha(HERE/'execution_config.json')!=frozen['execution_config_sha256']:
        raise RuntimeError('Execution configuration changed')
    if environment()!=load(HERE/'environment.json'):
        raise RuntimeError('Numerical environment changed')
    return frozen
