"""Read-only historical file snapshots; all output remains under VHS-NEXT-S0."""
import hashlib, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research_next/vhs_transfer/data_audit'
def snapshot():
    result = {}
    for directory in ['scripts','src','configs','tests','reports','outputs','data/processed','data/raw']:
        for p in (ROOT/directory).rglob('*'):
            if not p.is_file() or any(x in p.parts for x in ['node_modules','__pycache__','.pytest_cache']):
                continue
            h = hashlib.sha256()
            with p.open('rb') as f:
                for block in iter(lambda: f.read(8*1024*1024), b''): h.update(block)
            result[p.relative_to(ROOT).as_posix()] = {'bytes':p.stat().st_size,'sha256':h.hexdigest()}
    for name in ['README.md','pyproject.toml','uv.lock','probe_e4a2.py']:
        p=ROOT/name
        if p.is_file(): result[name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    return result
if __name__ == '__main__':
    mode = sys.argv[1]
    current = snapshot()
    if mode == 'before':
        path=OUT/'historical_before.json'
        if path.exists(): raise SystemExit('Refusing to overwrite baseline')
        path.write_text(json.dumps(current,indent=2),encoding='utf-8')
        print(json.dumps({'files':len(current),'bytes':sum(v['bytes'] for v in current.values())}))
    elif mode == 'after':
        before=json.loads((OUT/'historical_before.json').read_text(encoding='utf-8'))
        delta={'changed':[p for p in before if p in current and before[p]!=current[p]],'removed':sorted(set(before)-set(current)),'added':sorted(set(current)-set(before))}
        report={'checked_files':len(before),'scope':'scripts/src/configs/tests/reports/outputs/data/processed/data/raw plus root project files; excludes node_modules and caches, .git, .venv, remote_sensing',**delta,'unchanged':not any(delta.values()),'git_status':'fatal: not a git repository; prior uncommitted state UNVERIFIED'}
        (OUT/'historical_after.json').write_text(json.dumps(current,indent=2),encoding='utf-8')
        (OUT/'integrity_result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
