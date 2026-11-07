# VHS-NEXT-B1B-S0D-R1 完整性报告（integrity_report_r1.md）

> 状态：PROPOSED。全部数据为 SYNTHETIC。本文件只记录 R1 这一轮的情况；S0D 原报告见 integrity_report.md（原文未改动，只在末尾追加了 R1 附注）。
> 时间均为 Asia/Singapore（UTC+8），2026-10-17。“PC”指用户 Windows 电脑（machine 49574e1c）；“盒子”指 Grok Bot 的 Linux 沙箱。

## 1. 结论摘要

- **只读区域未变化**（PC 实测）：B1B-S0（b1b_s0_deepbas_mvp）、b1a、evidence、reports、scripts 五个白名单目录在前后快照中逐文件比较（大小、mtime、SHA-256），added/removed/changed 均为空，`old_dirs_identical=true`。
- **封存目录**：`b1a\sealed_runoff`、`b1a\quarantine` 只记录了目录项自身的 mtime_ns（前后相同：1792123375343036500 / 1792123381802710800），没有进入、没有列举子项。
- 项目根一级、research_next 一级的条目没有变化；vhs_multistation 一级只有 `b1b_s0d_io_demo`（即 D）的 mtime 变化。
- .venv 只比较了元数据（30010 个文件），没有变化，即没有产生 __pycache__ 或 pyc。D 内递归检查 __pycache__ 的结果为 0。
- **D 外已知新增 1 个文件**：`C:\Users\Administrator\terminals\708052.txt`，约 1.1 MB，由远程 Shell 工具机制生成，原因见 incident_audit.md 的 E-2/INC-4。该文件未读取、未删除。

## 2. 方法

1. `tools\integrity_snapshot_r1.py`（SHA c2cca62d…）：
   - 对项目根、research_next、vhs_multistation 各做一级非递归列举；
   - 只对白名单子目录递归，使用自写的 walk_pruned；
   - 目录名含 sealed 或 quarantin（不区分大小写）时剪枝，只取该目录项自身的 stat；
   - 不跟随链接或目录联接；
   - 输出只允许写到 D 内。
2. pre 快照：`integrity\r1_pre_snapshot.json`，16:56，在 R1 改动落盘之前生成。post 快照：`integrity\r1_post_snapshot.json`，约 17:37，在测试、冒烟和文档追加完成之后生成。对比结果：`integrity\r1_compare.json`。
3. README.md、compat_report.md、integrity_report.md、incident_audit.md 的追加方式都是“原字节 + 追加字节”。逐个校验原文前缀的 SHA 等于备份或追加前的值，并确认没有 BOM。
4. 为避免误伤，测试中的 R1-SEAL-01/02/03 用假文件系统、静态扫描和运行时 open/scandir/listdir/stat 拦截三种方式，证明代码不会进入封存目录。

## 3. D 内对比（pre → post）

- **removed：空。** 本轮没有删除任何文件。
- added 与 changed 都在 D 内，明细见第 4 节。文件改名（`*_attempt1.txt`）也只在 D 内进行，用于保留第 1 次日志。
- post 快照之后又在 D 内写入了 `smoke\box_headless_check_r1.txt` 和本文件 `integrity_report_r1.md`，均为新增，没有修改其他文件。本文件自身的 SHA 无法写进本文件，见最终汇报。

## 4. R1 新增或修改的文件（PC 上计算的 SHA-256）

| 路径（相对 D） | 字节 | SHA-256 | 说明 |
|---|---|---|---|
| `README.md` | 10517 | `df4ade7fc28f76f79ec58fef1673a03a4baa7f9b03bdbb85abecdc4a00788edb` | 修改（仅追加 R1 章节；原文前缀 = 备份 a097656d…） |
| `compat_report.md` | 10028 | `8ee9746f2b9b9dc1e8190cd6735b16968516d9723f8c41310464a24ac4fc77ba` | 修改（仅追加 R1 章节；原文前缀 = 备份 b26a7f52…） |
| `incident_audit.md` | 11719 | `94e23bc226cd464b66767e92d2f55411109ccd1af5e14ae58ae657392c10ae58` | 新增（INC-1/2/3 + R1 执行记录 E-1…E-6） |
| `integrity_report.md` | 12055 | `f6dbdf87a1aa5498668f768625dc87537fbc685177a66acacfde4e926f24e8eb` | 修改（仅追加 R1 附注；原文前缀 = 0036572d…） |
| `interface_decisions.md` | 9516 | `7feb7c5a83a01b74f6ece14c159ed91f7cc0044143adefd83bc3eb0b21b0ce16` | 新增 |
| `app.js` | 16345 | `712ea5366e1231f0584cf4b7f991b4d0396cf6770cd4197c81c6d83695423f88` | 修改（D3/D4/D7/D8 显示） |
| `demo_cli.py` | 4776 | `a28440e461a6884c5e9e00e9c2aad1a4a39285c45b590590646cfce2f2c83db9` | 修改 |
| `demo_core.py` | 51485 | `b9df3c8d66456c850c4fd93d035fea67caa609ea0e90d08413ff2c853267bdaa` | 修改 |
| `demo_server.py` | 13382 | `b3fc6d31d895cee7878bb50fa90b16f543b4712ef2863d96e12951e489d3272d` | 修改 |
| `geo_map.js` | 2588 | `d05a2258de76050cfc905a06573f1cfd1de8c45bee885bad1736e0bac3eec745` | 新增（D7 纯函数） |
| `index.html` | 7687 | `ec024d7b54eb99735875fe36a794bc65f5a975c70a48cd0bac273cad33e853b1` | 修改 |
| `offline_snapshot.js` | 1412557 | `2e3d291dbdd597a35798042c23fb8a68d97c85710aafbf74855f6c8ce84f1d2d` | 重新生成（build_artifacts） |
| `io_examples_r1.json` | 339181 | `27ed00fa4eff67de2aa377fd3ca9954414307ce6b5b2fe8a3a985ebde0d3c229` | 新增（PC 生成，29 HTTP + 8 CLI） |
| `io_examples_r1.md` | 6883 | `dd59b92a9edd316009e67b97cc9029d2993e43c084a421259fd8f85aa2f0e39e` | 新增 |
| `schema_draft/error_codes_v0.2.draft.json` | 7186 | `464c96fa674968b5494e3591d78a6841c53325969880240b28b40df994c050fb` | 新增 |
| `schema_draft/vhs_response_v0.2.draft.schema.json` | 14242 | `1dea0978463ab4073149af8e6a84c340b192b66c434cc49dc93a11ca10bd6a25` | 新增 |
| `synthetic_data/audit_graph.json` | 982 | `98ac379d36767eca03b2c9e3f8c1815687fdd90fe87af890e31ba0de789706e6` | 重新生成 |
| `synthetic_data/cycle_graph.json` | 1377 | `b189af4c74ea60bc1b371038f4690061f705379b60972a3bcbe8c8488b3ff62c` | 重新生成 |
| `synthetic_data/main_graph.json` | 3562 | `df1ec819a97bb49eb1232f97dee342f1bc81fa364e027655d7979f4ffc0ddb15` | 重新生成 |
| `synthetic_data/stations.json` | 18471 | `c9a3d21d33c11a2357189bb20866f71e542bfe15e96fe0fdc0fcf3b8a302cacd` | 重新生成 |
| `tests/axis_ref.py` | 827 | `f0a850cc9fb7b4a7f5e0ca1684c0d065820db57c65855c784c08098cd11c0954` | 新增 |
| `tests/fixtures/axis_cases.json` | 7467 | `e29b954da544a007f0400d383318537c2279a3fc2d7aea4c465f54b0b84f01d9` | 新增 |
| `tests/js/test_geo_map.js` | 2938 | `787c338735f79cae849dd348dc2231694ba9c227c28e6240ab91fbb7f09e6fbb` | 新增（node，仅盒子可跑） |
| `tests/mini_schema.py` | 4499 | `9cc28e252d5195726b145f29c6a6941a55073c349ff6220feabdfb4e2272cd0c` | 修改（扩展关键字） |
| `tests/test_demo.py` | 33259 | `9491e424f916486d0ea7fd7f0b6726cf8ec36def17ca887dd83e1d7ebd8ae6c0` | 修改（M1–M4） |
| `tests/test_r1.py` | 56030 | `40ed0a89f34cb5c33f5314d221ef1eba480c7eafccda5bddf5b18f0b546d9960` | 新增（含 E-3 修正） |
| `tests/test_run_output_r1_baseline.txt` | 4323 | `15ff47d17631957a9ce36a61c061610445c6de0e58c2b1475d0b707e9221610b` | 新增（改动前 42 项基线） |
| `tests/test_run_output_r1_attempt1.txt` | 11069 | `831951bf2f7a227d0de4e5d42235ca9cf68319d9217e64668ce67af085bb75ba` | 新增（第 1 次：1 ERROR） |
| `tests/test_run_output_r1.txt` | 10089 | `bb63356a5ca710b7efdd6a507483f2d33857ca14caf739048818d64f0569c71c` | 新增（第 2 次：88/89） |
| `tests/test_run_output_r1_final.txt` | 10023 | `296465fd3ab42f3d03fecf1bc7b417bb3a484a62205b54fdb36efcba15b16c4b` | 新增（文档追加后复跑：88/89） |
| `tools/gen_io_examples_r1.py` | 9684 | `ce3a112b8724ad18d286b93c1ca589a8b8602597f3e0dd9de7aad9fe6835e2df` | 新增 |
| `tools/integrity_snapshot_r1.py` | 9987 | `c2cca62d9eb076048b9f5ccf791fc22a431bcb4ba9f91118fecdaa83d7da026c` | 新增 |
| `smoke/smoke_test_log_r1.txt` | 8118 | `5a5741b56d14596ffca2faed2edc665ab9b1e1c204ca1006960511ec5d30c371` | 新增（20/20） |
| `smoke/smoke_test_log_r1_attempt1.txt` | 5220 | `22c648dfabce32782d9e7218fd9480fcaccebb371c4092f0316653a7d62d5d91` | 新增（第 1 次，见 E-4） |
| `smoke/server_stderr_r1.txt` | 5397 | `2588577a2fe47cbbc16b249f9108db8f3ae2155d92d046abf6fabcd566618b2d` | 新增 |
| `smoke/server_stdout_r1.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 新增（空） |
| `smoke/server_stderr_r1_attempt1.txt` | 4861 | `c7b7fee84427dbf27ca89f07aee65239c961762c57bdd7afc969927de699ede6` | 新增 |
| `smoke/server_stdout_r1_attempt1.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 新增（空） |
| `smoke/body_bad_json_r1.txt` | 21 | `a0ec7c991bd56cd248e11dbf0befdabb1fd1d9421862e4b5f82d55608b5be7cf` | 新增（冒烟请求体） |
| `smoke/body_big_r1.json` | 70046 | `3f45b0bd62f26e57b8b43320ac1b006add5c35c05c3b8ffeed5988598b69638b` | 新增（413 用例） |
| `smoke/body_predict_ok_r1.json` | 37 | `b3cd2090a3af6b7da8bd4a582c6d23e3dd0abc7ffeb80b1dc5fab1e67753902a` | 新增 |
| `smoke/body_predict_unknown_r1.json` | 39 | `3314a8f820393078c3b65796ef060eedeabece2baeaa27a9c0414eca0cf95ac8` | 新增 |
| `smoke/box_headless_check_r1.txt` | 1850 | `432617843e7042f1d9d4e1681335674d1aa33d21a979f98dd3e30f4eb4820593` | 新增（盒子上执行的页面检查记录） |
| `integrity/r1_pre_snapshot.json` | 3483406 | `5d5e5d9867bf9a98938113ba5b45d157e37b6115c7f16d9d048db4c71b1d70e0` | 新增 |
| `integrity/r1_post_snapshot.json` | 3488105 | `d5f54f4abf768f655dbbd86b0aeaed32e27d658e7cffef05e423abab839e4c0f` | 新增 |
| `integrity/r1_post_snapshot_stdout.txt` | 1230 | `c64007074c61a6348428de9a978ef04564be480232d33f3ae040644f1360ad7f` | 新增 |
| `integrity/r1_compare.json` | 2892 | `8a37c768291daecadcf3514abf31d5f7d7d7ab1f7c7214fe64bd0c4450866624` | 新增 |
| `integrity/r1_compare_stdout.txt` | 3019 | `014b82be7a0e982c995784b11cd301d9b3927517703dee437f9137acd1487346` | 新增 |
| `backup_pre_r1/MANIFEST_SHA256.txt` | 3477 | `5b0639c01791f4a0b3f9a8f60c703612b39471460327ad1889e4f0d7c6477a68` | 新增（备份清单；另含 29 个备份文件） |
| `_r1_transfer/chunk_00.b64` | 15000 | `7cb47189b666562019aabc5e25f8f20da54e870385e23813e372ff5e0fd12377` | 中转（保留） |
| `_r1_transfer/chunk_01.b64` | 15000 | `b7616245c13ac92b04704248b8f2e27bd73c137a7c081de8fe553bb892980e4b` | 中转（保留） |
| `_r1_transfer/chunk_02.b64` | 15000 | `d55bb0b83a494000f23ffd6622eac05e864470b10371dd652aa36eb3d17f0009` | 中转（保留） |
| `_r1_transfer/chunk_03.b64` | 15000 | `d43a4b6ec429a997845ae72967adea6686f0ed883bb042b8991406554d80e871` | 中转（保留） |
| `_r1_transfer/chunk_04.b64` | 15000 | `624a55dfba82243a33ddb08ad217e546838ec29e27a018a0fe2f8edfc1b49804` | 中转（保留） |
| `_r1_transfer/chunk_05.b64` | 15000 | `083b5c67cfc93cf57b429c6414355361042571e567f06a32333e3c94bc4fae96` | 中转（保留） |
| `_r1_transfer/chunk_06.b64` | 8876 | `92e90229ef5e79648de7f5aec87963e336cd89fbd80aaf5675926de1fc344b78` | 中转（保留） |
| `_r1_transfer/readme_r1_append.md` | 2640 | `815e2c45fc90252861ba9dc08520387757b66fd3b4cd8ce16f0dd3343767771f` | 中转（保留） |
| `_r1_transfer/compat_r1_append.md` | 2206 | `e5a757baf08fa1c989b523871cd3f08f9528615a10ba899921721ba128291342` | 中转（保留） |

backup_pre_r1\ 下另有 29 个备份文件，是 R1 改动前的原样副本，清单与哈希见 MANIFEST_SHA256.txt。

## 5. 测试变更说明（不放松安全断言）

- test_demo.py 的 M1–M4 见 interface_decisions.md §4。
- test_r1.py 在 R1 执行中有三处修正：
  - SEAL-01 假文件系统的 Windows 路径规范化（E-3）；
  - "%2e%2e" 用例改为期望 404 E002，因为 ".." 符合旧 STATION_ID_RE，旧正则按 D1 保持不变；
  - 畸形查询串用例改为允许 400 INVALID_REQUEST 下的 QUERY_INVALID 或 UNKNOWN_PARAMETER 两种原因码；
  - 另外，日志计数用例改为“最多等 2 秒再断言”，断言内容本身不变。

  这些修正都没有删除或弱化“prediction 必须为 null”“不得含 prediction_authorized”“不得进入封存目录”等安全断言。

## 6. 证据边界（如实说明）

- **C: 盘**：按要求未访问 C:\ 下任何路径，因此 D 以外 C 盘上是否有变化无法证明。已知 C 盘上至少有两类由工具机制写入的文件：
  - 远程 Shell 的临时脚本 `C:\Users\Administrator\AppData\Local\Temp\ps-script-*.ps1`，路径来自一次报错信息；
  - 输出缓存 `C:\Users\Administrator\terminals\*.txt`。

  两类文件都没有读取或清理。
- **%TEMP%**：未列举、未清理。Python 以 -B 运行并设置了 PYTHONDONTWRITEBYTECODE=1；curl.exe 的请求体文件放在 D\smoke 内；Start-Process 的重定向文件也在 D 内。
- **agent-tools**：未重新读取，待用户授权。本轮输出可能仍被工具缓存（INC-3 机制），无法核验。
- **项目根以外的 E: 盘**：未检查。
- **盒子**：盒子上的副本、页面截图和 DOM 不属于用户电脑，不计入 D。
- **快照工具本身**：基于 mtime、大小和 SHA-256 判断，无法发现“内容相同、仅访问时间变化”的读取行为。封存目录本身的 atime 未比较。
- **中转文件**：_r1_transfer\ 下 9 个文件保留，未自动删除，是否清理请用户决定。
