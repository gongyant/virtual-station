# GitHub push exclusions — VHS DEMO snapshot 2026-11-05 / pushed 2026-11-07

## Excluded from this repository (by policy)

| Item | Reason |
|------|--------|
| research_code.7z (~904 MB) | Single file >100MB; GitHub hard reject. Unpacked tree is in research_code/ |
| VHS_FULL_SOURCE_AND_DEMO.zip / VHS_RESEARCH_RESULTS.zip | Same size limit; content already expanded |
| browser-profile/ directories | Chromium runtime profiles (cookies/tokens risk) |
| quarantine/, sealed_runoff/, teacher_q/, SYRDARYA_teacher/, raw_qobs/ | Restricted teacher/research Q — not licensed for public share |
| .env (real values), *.pem, *.key | Secrets |
| __pycache__, .venv, node_modules, *.pyc | Build/runtime junk |

## Included (user chose full DEMO)

- website/ — real 8794/8795-derived frontends + P8–P9C pages
- research_code/ — stage code + public LamaH-CE daily CSV copies (~3.3 GB of open data)
- scripts/, demo_data/, results/, provenance/, model_registry/, config/.env.example
- Chinese handoff docs (START_HERE, timeline, data/model, Ridge/LSTM note)

## Security scan (2026-11-07 Asia/Singapore)

- Files >95MB in push tree: **none**
- Path-name hits for quarantine/teacher_q/sealed/.env: **none**
- Content keyword scan (api_key/private key/ghp_/AKIA): **none**
- Status: **CLEAR_TO_PUSH** (Public repo reminder: contains public LamaH copies; restricted Q not present)

## Not claimed READY

HANDOFF_PARTIAL: no teacher Q, no future forecast product, Git first-commit date UNKNOWN for GT-Lite.
## Push strategy note (2026-11-07)

Initial monolithic HTTPS push failed: HTTP 408 (pack ~799 MiB).
Split strategy: commit/push core first without `open_metadata` (~3.3 GB LamaH public daily tables),
then add `open_metadata` in follow-up commits and push each batch.

## open_metadata 状态 (2026-11-07)

`research_code/DeepBas-VHS-GT-Lite-v0.1/research_next/vhs_multistation/b1a/open_metadata/`
约 **3160 MB** 公开 LamaH-CE 日流量/元数据副本。已列入 `.gitignore`，**未推送到本仓库**，
因本机到 GitHub 的 HTTPS 大包易 408/连接重置。

获取方式：按 `REPRODUCE.md` / LamaH-CE 官方渠道自行下载；本地交接 ZIP
`VHS_FULL_SOURCE_AND_DEMO` 中仍有完整副本（仅开发机）。
