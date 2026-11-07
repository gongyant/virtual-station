# MISSING AND PERMISSION BLOCKERS

## RESTRICTED_EXCLUDED (not in shareable ZIP)
- Teacher / Syr Darya raw Q CSVs (adapter default empty; SOURCE_MISSING expected)
- Real `.env` secrets, CDS tokens, cookies, private keys
- Any path matching teacher_q / SYRDARYA_teacher / raw_qobs content dumps

## INTERNAL_LICENSED / may need re-application
- World Bank daily Q raw archives beyond sealed monthly admission tables
- Full ERA5-Land NetCDF cubes (only derived driver summaries included where present)
- Some official bulletin microdata with unresolved redistribution rights
- Lepsy / conflicting bulletin rows (documented, not silently fixed)

## Functional gaps (honest)
- Original 8794 UI is included as `website/web_s1_research_8794` source tree; integrated runtime base is 8795 copy with P6/P7 research views retained in that host family. Dual-port original lab services are NOT required.
- Formal Kazakhstan PUB / future forecast product: **not done** (P9D is PoC/plan only; not promoted).
- Official identity certification of 394 river gauges: not complete (0 certified in P9A status).
- Git earliest-commit exact date for GT-Lite: UNKNOWN in this run (git log exit 128 on machine); timeline uses sealed JSON timestamps + directory evidence.
- Large unaudited binaries default-excluded from shareable zip if security scan flags them.

## Website absolute-path remediation
- `WEB_KAZ_SOURCE_PINS.json` remapped to package-relative paths (see provenance/KAZ_PINS_REMAP.json)
- `VHS_SYR_SOURCE` / `VHS_SANDBOX` env-driven; empty by default

## 本轮从交付副本剔除的大体量/风险项（见 provenance/PRUNED_FROM_SHAREABLE.json）
- 全球 HydroRIVERS 原始 shp/dbf（保留 gis/ 派生全国 gpkg）
- LamaH-CE daily tar.gz 原始归档
- TOPOLOGY_ARRAYS.npz 未审计大二进制
- 误入的 quarantine（含 Qobs.txt）与 sealed_runoff
- 抓取的官方登录页 HTML（仅含前端 password 字段名）
- 重复巨型 gpkg（research_code 内副本；正式空间数据在 gis/）
- 部分超大 crossfit/streamflow/EU-Hydro 中间文件（代码与指标表仍保留）
