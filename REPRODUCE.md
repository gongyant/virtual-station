# Reproduce notes

## Website sealed-results mode
`scripts/start_windows.ps1` starts the copied 8795-based host on a new localhost port.
P8–P9C pages read `results/**` via `/api/v6/p89/*` (read-only). No training.

## Research code
Each phase under `research_code/` retains its original scripts and reports. Full retrain may need licensed raw Q / ERA5 which are **not** bundled. See `MISSING_AND_PERMISSION_BLOCKERS.md`.

## Numeric anchors
- P8 national length km = 659769.8483656237
- P9A: 334 / 237 / 519
- P9B: 20 + 10
- P9C valid: 4 stations, 705 station-months; C0 NSE 0.695836401015 / KGE 0.709320135242
