from common import *
import ast,platform,importlib.metadata
if (ROOT/'SHA256SUMS.txt').exists():raise RuntimeError('Refuse resealing an existing frozen delivery')
required=['P9B_COMPLETION_REPORT_ZH.md','P9B_HISTORICAL_Q_SOURCE_AUDIT.csv',
 'P9B_AVAILABLE_Q_INVENTORY.csv','P9B_GAUGE_IDENTITY_CROSSWALK.csv',
 'P9B_CATCHMENT_DELINEATION_STATUS.csv','P9B_CANDIDATE_NETWORK_RELATIONSHIPS.csv',
 'P9B_BASIN_DRIVERS_STATUS.csv','P9B_P10_VALIDATION_PROTOCOL.md','P9B_FIRST_BASIN_READINESS.md',
 'P9B_SCI_WRITING_PROGRESS.md','P9B_REPRODUCTION_GUIDE.md','P9B_FIRST_BASIN_GIS.gpkg',
 'figures/P9B_SOURCE_COVERAGE_MAP.pdf','figures/P9B_CANDIDATE_PROXY_MAP.pdf']
missing=[s for s in required if not (ROOT/s).is_file() or (ROOT/s).stat().st_size==0]
if missing:raise RuntimeError(str(missing))
scripts=sorted((ROOT/'code').glob('*.py'))
for p in scripts:ast.parse(p.read_text(encoding='utf-8'))
qa=read(ROOT/'P9B_INDEPENDENT_QA.json');assert qa['failed']==0
fqa=read(ROOT/'figures/FIGURE_AUTOMATED_QA.json')
assert all(x['returncode']==0 for x in fqa if not x['check'].endswith('_collision'))
h=history_check('HISTORY_PRESEAL_CHECK.json')
js(ROOT/'evidence/ENVIRONMENT.json',dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
    packages={n:importlib.metadata.version(n) for n in ['pandas','numpy','geopandas','pyogrio','shapely','pyproj','rasterio','matplotlib']},
    PDF_readonly_runtime='Existing bundled pypdf/pdfplumber/PDFium; no packages installed'))
js(ROOT/'evidence/DELIVERY_ACCEPTANCE.json',dict(required_files_checked=len(required),required_missing=missing,
    AST_scripts_passed=len(scripts),numeric_passed=qa['passed'],numeric_failed=qa['failed'],
    source_QC_passed=qa['source_arithmetic_QC_passed'],source_QC_failed=qa['source_arithmetic_QC_failed'],
    historical_checked=h['checked'],historical_changed=h['failed'],
    figure_source_preflight='PASS_WITH_RESEARCH_EXPORT_WARNINGS',PDF_glyph_floor='PASS',
    rendered_collision_QA='NOT_AUDITABLE_PYMUPDF_UNAVAILABLE',
    data_training_admission='Q_NOT_ADMITTED',P10='P10_NOT_READY',model_fit_calls=0,formal_VHS=0))
event('P9B_delivery_sealed',numeric_passed=qa['passed'],numeric_failed=qa['failed'],historical_unchanged=h['passed'],Q_status='Q_NOT_ADMITTED',P10='P10_NOT_READY')
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt')
(ROOT/'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in files),encoding='utf-8')
print(json.dumps(dict(sealed_files=len(files),manifest_sha256=digest(ROOT/'SHA256SUMS.txt')),ensure_ascii=False))
