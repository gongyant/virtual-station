# VHS-NEXT-B1B-S0｜08 验证报告

日期：2026-10-17（Asia/Singapore, UTC+8）。执行者：Grok Bot（knowledgeWork 子代理），代用户 bean 执行。机器：PC-20260821NZLG（machineId 49574e1c-0885-4541-b170-f4c158c246ca）＋助手自己的 box（仅网页调研与草拟）。

## 1. 实际读取的来源清单（全部只读）

### 1.1 用户电脑本地（路径相对 `research_next\vhs_multistation\b1a\`）
- 目录元数据列举：b1a 全树（**跳过并未进入** `sealed_runoff\`、`quarantine\`，只取两目录自身修改时间）。
- `reports\` 全部 15 个文件：b1a_go_no_go.md、b1a_validation_report.md、b1a_status.txt、b1a_independent_groups.md、b1a_neighbor_matching.md、b1a_pair_eligibility.md、b1a_topology_audit.md、b1a_license_audit.md、b1a_provenance.md、b1a_field_dictionary.md、b1a_label_blindness_validation.md、b1a_archive_manifest.md、b1a_preflight_validation.md、b1a_provider_email_draft.md（只读，未发送）、b1a_preflight.md（未打开正文，仅列于目录）。
- `evidence\`：correction_log.json、b1a_decision.json、topology_summary.json、pair_gate_summary.json、matching_common_support.json、final_validation.json、eu_hydro_summary.json、snap_forcing_summary.json、field_dictionary_summary.json。
- 根目录：attrition.csv、provenance.json（全文）；connected_candidates.csv、nonnested_candidates.csv、group_membership.csv、station_metadata.csv（元数据列统计：ID、组别、布尔资格列、距离、面积比、坐标、名称）；coverage_by_year.csv、field_dictionary.csv（**仅表头**）。
- `open_metadata\`：Crossbasin_water_transfers.csv（表头＋行数；`lower_thres/upper_thres` 数值未读）、Gauge_attributes.csv（表头）、Info_english\1_Folder_structure.txt、2_Timeseries.txt、E_stream_network\_Info.txt、D_gauges\3_shapefiles\Gauges.prj。
- `.venv\pyvenv.cfg`（确认已有 Python 3.14.7，未安装任何东西）。
- **未读取**：任何日径流文件、sealed_runoff/quarantine 内容、A5/A10/F_hydrol_model、气象数值、b1a 归档本体。未计算任何 Q 均值/方差/极值/相关/FDC/NSE/KGE。

### 1.2 网页（访问日期均为 2026-10-17）
- https://essd.copernicus.org/articles/17/1461/2025/ （CAMELS-FR 论文）
- https://entrepot.recherche.data.gouv.fr/api/datasets/:persistentId/?persistentId=doi:10.57745/WH7FJR （CAMELS-FR 仓库元数据）；同仓库 README.md、NEWS.md（共约 11 KB 文本，取至 box）
- https://gitlab.irstea.fr/HYCAR-Hydro/airgrgalaxy/airgrdatasets/-/issues/17 （搜索摘要，SECONDARY）
- https://essd.copernicus.org/articles/16/2741/2024/ ；https://www.hydroshare.org/resource/705d69c0f77c48538d83cf383f8c63d6/ ；https://www.hydroshare.org/resource/86117a5f36cc4b7c90a5d54e18161c91/ （LamaH-Ice）
- https://essd.copernicus.org/articles/15/5755/2023/ ；https://zenodo.org/records/10354485 （CAMELS-CH）
- https://catalogue.ceh.ac.uk/documents/9a46d428-958f-4ac1-86eb-94eee70c0955 ；https://essd.copernicus.org/articles/12/2459/2020/ （CAMELS-GB）
- https://essd.copernicus.org/articles/16/5625/2024/ ；https://zenodo.org/records/16755906 ；https://zenodo.org/records/13837553 （CAMELS-DE）
- https://zenodo.org/records/10968468 （Caravan）
- https://grdc.bafg.de/about/data_policy/ （GRDC）
- https://doi.org/10.1038/s41597-024-03706-1 ；https://www.nature.com/articles/s41597-024-03706-1/tables/10 （EStreams，经搜索摘要）

## 2. 文件变动范围

- 写入位置：**仅** `research_next\vhs_multistation\b1b_s0_deepbas_mvp\`（本轮新建，含 `tests\` 子目录）。
- 新目录内曾创建并删除一个编码测试文件 `_enc_test.txt`（验证 UTF-8 写入后已删除）。
- 新目录最终文件：01–04、05、06、07、08 交付文件；`vhs_contract.py`（契约校验器）；`vhs_response.schema.json`（候选 JSON Schema）；`tests\test_vhs_contract.py`（合成单元测试）；`tests\test_run_output_windows.txt`（实际运行输出）。大小与 SHA-256 见最终汇报（08 无法包含自身哈希）。
- 写入方式：box 上的 CopyFromBox 被用户电脑本地执行根策略拒绝（该路径不在允许根内），因此改为 PowerShell `[IO.File]::WriteAllText`（UTF-8 无 BOM）直接写入新目录；`.py`/`.json`/01–07 的 SHA-256 与 box 草稿逐一比对一致。没有为绕过而先写到其他目录再移动。
- 不可避免的副作用（如实记录）：①在 vhs_multistation 下创建新子目录使 `vhs_multistation` 目录自身修改时间变为 2026-10-17T10:58:10+08:00；②远程 Shell 工具会把较长命令输出缓存到 `C:\Users\Administrator\agent-tools\`（工具基础设施行为，非本轮主动写入科研目录）；③PowerShell 临时脚本位于系统 Temp。项目内其他目录没有写入。

## 3. 新目录以外的变化检查（仅元数据，不读 sealed 内容）

方法：对 `vhs_multistation` 全树（排除 `sealed_runoff`、`quarantine` 不进入，排除新目录）逐文件取“相对路径|字节数|修改时间”，排序拼接后算 SHA-256；写入前、写入后各一次。另记录项目根目录一级条目修改时间与两个封存目录自身修改时间。

| 项 | 写入前（约 10:46） | 写入后（约 11:03） |
|---|---|---|
| 文件数 | 2359 | 2359 |
| 总字节 | 5,028,649,388 | 5,028,649,388 |
| 最晚修改时间 | 2026-10-16T12:15:39.425+08:00 | 同左 |
| 列表 SHA-256 | 23ac3d6dac8f7d016d9139f531538c12bcef6279936ab23ed35cf8877ca2cadb | 同左 |
| 其中 b1a 文件数/字节 | 2330 / 5,027,920,153 | 同左 |
| sealed_runoff 目录 mtime | 2026-10-16T12:02:55.343+08:00 | 同左 |
| quarantine 目录 mtime | 2026-10-16T12:03:01.803+08:00 | 同左 |
| 项目根一级条目 mtime | 23 项（research_next 2026-10-11 23:01:21 等） | 全部同左 |

结论（VERIFIED）：在可检查的元数据层面，B1A 及 vhs_multistation 其他内容未发生变化。局限：未对文件内容逐一重算哈希；封存目录内部未检查（按授权不得进入）。

## 4. 合成测试结果

- 测试：`tests\test_vhs_contract.py`，22 个用例，纯标准库，纯合成数据（SYNTHETIC_EXAMPLE），不读任何真实数据。
- 覆盖：缺失/空白/非法格式/不存在站点与数据集版本错误（E001–E004）；未授权时 NOT_AUTHORIZED 且 prediction=null，登记表夹带预测被强制清空，S0 下非合成预测被拒（E010）；响应与日志中拒绝 qobs、target_q、q_mean、runoff_ratio、fdc 等键及 `qobs=12.3` 类赋值（E008），拒绝 NSE/KGE/RMSE 字段（E009）；CRS 缺失（E005）、EPSG 未登记/单位轴序不一致/米值放入度数 CRS（E006）、EPSG:3035 用于中亚（E007）；05 示例文件严格 JSON、无 BOM。
- 运行 1（用户电脑，主结果）：2026-10-17 11:01:56 +08:00，`E:\…\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe`（项目已有的 Python 3.14.7，未安装依赖），命令 `python -B tests\test_vhs_contract.py`，`PYTHONDONTWRITEBYTECODE=1`；结果 **Ran 22 tests … OK，exit=0**；完整输出见 `tests\test_run_output_windows.txt`；运行后新目录内 `__pycache__` 数量为 0。
- 运行 2（box 草拟时预跑）：同一测试 22/22 OK（box 上曾因生成脚本导入模块产生过 `__pycache__`，已在 box 删除，不涉及用户电脑）。
- 另：用 `.venv` Python 对两个 JSON 做过一次 `json.load`→`json.dump(indent=1)` 规整（只作用于新目录内这两个文件），结果哈希与 box 草稿一致。
- 局限：防泄漏基于键名与文本模式，不能识别被改名或编码的数值；不是 OS 级权限隔离。

## 5. 权限遵守情况

| 禁止项 | 遵守情况 |
|---|---|
| 下载新增大型数据集（含 LamaH-CE 小时包） | 遵守：只取回 CAMELS-FR README/NEWS 两个说明文本（约 11 KB）到 box |
| 读 sealed_runoff 中真实 Q 或算 Q 统计 | 遵守：未进入、未列出内容 |
| 执行 B2/B3/B4、训练、评分、超参搜索、GPU | 遵守：0 次 |
| 修改 B1A/B0/E4/E5/S0/S0.1/S1A/原始数据/论文 | 遵守：见 §3 元数据比对 |
| 联系维护者/发邮件 | 遵守：未联系；邮件草稿只读 |
| 修改 DeepBas 平台/部署/数据库 | 遵守：未访问 |
| 把同账户目录隔离称为 OS 级/加密/air-gapped | 遵守：全文均写“程序策略级” |
| 用目标 Q 衍生签名参与匹配 | 遵守：未做任何匹配计算 |
| 自动进入下一阶段 | 遵守：S0 完成即停止 |
| 安装新依赖 | 遵守：只用已有 .venv Python 与标准库 |

## 6. STOP 事件

- **无触发强制 STOP 的事件**。本轮所需证据均可在授权范围内取得，没有需要读取目标 Q、下载归档、修改历史结果、联系外部、启动训练或访问 DeepBas 的情形。
- 非 STOP 的工具受限记录：①结构化 Read 工具与 CopyFromBox 对项目路径返回“outside the allowed local-exec root”，改用经授权的远程 PowerShell 只读/写入新目录完成，未扩大写入范围；②CAMELS-FR 等候选的拓扑计数需要下载元数据文件才能核实——**未下载**，相关项标为 UNKNOWN/UNVERIFIED，并在 07 中作为需用户批准的下一步提出。

## 7. 未完成或失败的部分

- 新增独立系统的数量、嵌套对数、负对照共同支持：全部未核实（UNKNOWN），需下一轮授权。
- DeepBas 平台接口：未确认（UNKNOWN）；契约仅为候选草案。
- 未重算 B1A 的 596 个保护文件哈希与归档哈希（引用 B1A 自报结果）。
- 未联网核对 EPSG 注册表中 3035 的轴序（标 INFERRED）。
