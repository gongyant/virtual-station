"""Bounded byte-hash verification, never parses runoff values."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
REPORTS = ROOT / 'research_next/vhs_transfer/reports'
HERE = Path(__file__).resolve().parent

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def check(mode):
    prior = json.loads((REPORTS / 'vhs_next_s01_integrity_after.json').read_text('utf-8'))
    manifest = json.loads((REPORTS / 'vhs_next_s01_delivery_manifest.json').read_text('utf-8'))
    expected = {k: v['sha256'] for k, v in prior.items()}
    expected.update({k: v['sha256'] for k, v in manifest.items()})
    # Fixed, already-known reports, not a historical filesystem rescan.
    for p in REPORTS.glob('vhs_next_s0_*.md'):
        expected.setdefault(p.relative_to(ROOT).as_posix(), digest(p))
    for name in ('vhs_next_s0_status.txt', 'vhs_next_s01_delivery_manifest.json',
                 'vhs_next_s01_integrity_after.json'):
        p = REPORTS / name
        expected.setdefault(p.relative_to(ROOT).as_posix(), digest(p))
    out = HERE / 'integrity_before.json'
    if mode == 'after':
        expected = json.loads(out.read_text('utf-8'))['hashes']
    actual = {k: digest(ROOT / k) for k in expected}
    mismatch = [k for k in expected if expected[k] != actual[k]]
    result = {'scope': 'targeted inherited registry plus S0/S0.1 reports; no full S0 rerun',
              'files': len(actual), 'mismatch': mismatch, 'hashes': actual}
    (HERE / f'integrity_{mode}.json').write_text(json.dumps(result, indent=2), 'utf-8')
    if mismatch:
        raise RuntimeError(mismatch)
    print(json.dumps({'mode': mode, 'files': len(actual), 'mismatch': mismatch}))

if __name__ == '__main__':
    check(sys.argv[1])
