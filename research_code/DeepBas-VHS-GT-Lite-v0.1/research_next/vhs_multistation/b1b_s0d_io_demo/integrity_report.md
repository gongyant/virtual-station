# VHS-NEXT-B1B-S0D｜完整性验证报告（09 风格）

日期：2026-10-17（Asia/Singapore, UTC+8）。执行：Grok Bot（knowledgeWork 子代理），代用户 bean。机器：PC-20260821NZLG（machineId 49574e1c-0885-4541-b170-f4c158c246ca），Python：`E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe`（3.14.7，项目已有，未安装任何依赖）。另用助手 box（Linux）做 JS 语法与无头浏览器渲染检查。

## 1. 读取范围（全部只读）

- `b1b_s0_deepbas_mvp\`：vhs_contract.py、vhs_response.schema.json、05_api_contract_example.json、tests\test_vhs_contract.py、tests\test_run_output_windows.txt、04、08 全文（VERIFIED）；其余文件只列元数据。
- `vhs_multistation` 全树：仅由 `tools/integrity_snapshot.py` 计算 路径|大小|mtime|SHA-256（只读打开），按目录名剪枝 `sealed_runoff`、`quarantine`：不进入，只记录目录自身 mtime。
- 项目根一级条目名称与 mtime（不递归）。
- **未读取**：任何真实 Q、sealed_runoff/quarantine 内文件内容、B1A 数据内容；没有任何外部网络访问、下载。

## 2. 本轮新增/修改文件（全部位于 `research_next\vhs_multistation\b1b_s0d_io_demo\`，均为本轮新建）

| 相对路径 | 字节 | SHA-256 |
|---|---|---|
| app.js | 14352 | 2712be77aa37309b3fcabd01c864cff224f85d01eb7b8dcb29c697ab5ead2a33 |
| compat_report.md | 7820 | b26a7f52c21af677a1071ccd909e1bbcc0a3102ab399017911b24944094073a8 |
| demo_cli.py | 4257 | da1d510c2e192a938115e29e1423d9e34a7bcaa138e52cc350b949a5bc0ee1ab |
| demo_core.py | 41889 | e2f1a7ca599673a3038cfd8c2f6463002e81bcb836ad18d1332e1f24d7a5c6fa |
| demo_data.py | 9922 | 5e96498726092ed45ae7643b69178d541765777bd293a07f7d971644f11bea99 |
| demo_server.py | 11071 | b3cf5f81253752dee42faca5837c3853da68a95f17cae4e908ed4746a9dfd70b |
| index.html | 5859 | 2207675717c9cb71e5b30f41fb2dc74ca53c5e464bc907ebec58c58c489a4b8b |
| integrity\baseline_pre.json | 416689 | 30200f199abc0d9601e141299cee978675d38136a5f2a56d9f5613c78bcd76b4 |
| integrity\project_root_level_post.txt | 1006 | 1209830ef781fae32654bc9bb8e5abd478694fa8a6d13d8c16fb3892c522ff39 |
| integrity\project_root_level_pre.txt | 1006 | 1209830ef781fae32654bc9bb8e5abd478694fa8a6d13d8c16fb3892c522ff39 |
| integrity\snapshot_post.json | 416690 | ab1728e6fdc3f55336da10bde25d7234ab0ba9bf912c34f9748fdd0ac8ab6f54 |
| io_examples.json | 198478 | f7f8456a00b6c28e7015aa205a694e440a1fb37260cdabbca9921f0a29c55f46 |
| io_examples.md | 2981 | 33f8ec0a8d16e3af1ee9c3fa666fdcd02a5af2d92b23eaaa10b38c82ad665be8 |
| offline_snapshot.js | 930147 | 1b54dfb403f199da922369c3f9d92afa1cb0cb241c2080c6a4f9cfb5325c2fd7 |
| README.md | 7875 | a097656dde26d854b6b56970fb23ac2a5278c5a6562ef376c2fb85eab0d878d6 |
| smoke\server_stderr.txt | 2549 | 046c4bfda95db9cbe07640071b22135fea899292157234d81661837ff9a7c74a |
| smoke\server_stdout.txt | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| smoke\smoke_test_log.txt | 19952 | a163f4a6282982a40e1a6aad18f06322054846afa82b29bc52425e01673dbafb |
| synthetic_data\audit_graph.json | 982 | 98ac379d36767eca03b2c9e3f8c1815687fdd90fe87af890e31ba0de789706e6 |
| synthetic_data\cycle_graph.json | 1377 | b189af4c74ea60bc1b371038f4690061f705379b60972a3bcbe8c8488b3ff62c |
| synthetic_data\main_graph.json | 3562 | df1ec819a97bb49eb1232f97dee342f1bc81fa364e027655d7979f4ffc0ddb15 |
| synthetic_data\stations.json | 18471 | c9a3d21d33c11a2357189bb20866f71e542bfe15e96fe0fdc0fcf3b8a302cacd |
| tests\mini_schema.py | 2688 | 57be2f6accab85047639112e890605921a563f3b3ed6138bad24a2c5ebc17ae6 |
| tests\test_demo.py | 31767 | e8260d7423f3e969dbb2af2e4954cfb11993f29a460ed86e407f42938fd2ebd1 |
| tests\test_run_output.txt | 4354 | 291bae73c4610e9ec62732bc0c6fe155608f6bbdee5089bc166f99a1d011a8a5 |
| tools\build_artifacts.py | 2008 | 30a4c5e6ad699d6a93e23d0fc9954a4264d4fc2ddb34f38823dae3776b84e478 |
| tools\gen_io_examples.py | 6670 | f4dc326d067b138cf3a7f3fe85260933cbbb77ec995db15adb641ceb6ca3d859 |
| tools\integrity_snapshot.py | 4491 | 427d536c771023a113c94c086e16a220cd61d76c426972bb6fb2e8dbf156119f |
| integrity_report.md（本文件） | 见最终汇报 | 本文件无法包含自身哈希 |

写入方式：PowerShell `[IO.File]::WriteAllText`（UTF-8 无 BOM，LF）直接写入新目录，以及 Python 工具写入新目录；`tools\integrity_snapshot.py` 写入后与 box 草稿 SHA-256 一致；前端/核心文件经 base64 回传到 box 后 SHA-256 逐一一致。新目录内 `__pycache__` 数量：0。冒烟测试期间曾在 `smoke\` 下产生 `_body.tmp`、`_req.tmp` 两个临时文件，已删除；`tests\_raw_out.txt` 临时文件已删除。

## 3. 旧目录前后对比（VERIFIED）

方法：`tools/integrity_snapshot.py` 对 `vhs_multistation` 全树（排除本轮新目录；剪枝 `sealed_runoff`、`quarantine`）逐文件计算 路径|大小|mtime_ns|**SHA-256 全量内容哈希**，开发前（13:05:27）与开发后（13:22:49）各一次；另在自动测试 T17 中再算一次并与开发前比较。

| 项 | 开发前 | 开发后 |
|---|---|---|
| 文件数 | 2371 | 2371 |
| 总字节 | 5,028,755,541 | 同左 |
| 清单 SHA-256 | 4835af2fd29185b8d44e67c36e60bcbd2e6e8e488863193144aeb82b08fd2478 | 同左 |
| 新增/删除/变化 | — | 0 / 0 / 0 |
| 其中 b1a | 2330 文件 / 5,027,920,153 B（与 08 报告一致） | 同左 |
| 其中 b1b_s0_deepbas_mvp | 12 文件（哈希见下） | 同左 |
| 其他（evidence/reports/scripts 等） | 29 文件 / 729,235 B | 同左 |
| b1a/sealed_runoff 目录 mtime | 2026-10-16T12:02:55.343+08:00 | 同左 |
| b1a/quarantine 目录 mtime | 2026-10-16T12:03:01.803+08:00 | 同左 |
| 项目根一级 23 个条目 mtime | 见 project_root_level_pre.txt | 完全相同 |
| 符号链接/联接 | 0 | 0 |

b1b_s0_deepbas_mvp 文件 SHA-256（前后一致）：01 `5c0e73d5…a842571`（13798 B）；02 `a1e17873…ba34fa`（15802）；03 `74f106ca…0f148`（8627）；04 `8e47276a…23deb`（8269）；05 `0693932c…e928b0`（12189）；06 `981eb53c…c0ab9`（2742）；07 `359ec568…9e13f`（2265）；08 `13470118…6a281e`（9633）；tests\test_run_output_windows.txt `3a228424…3f8e08`（2575）；tests\test_vhs_contract.py `b1cb682f…2226cd`（8740）；vhs_contract.py `38009ed258ca5f63bc9169917f5ab7cbe0310d9e644eeeac7708d576e163595b`（12847）；vhs_response.schema.json `4e21e4d1b1c3a13eed05b248bb8dc61680ecf15744db2ec39180905590fa1158`（8666）。完整 64 位哈希见 `integrity\snapshot_post.json`。

不可避免的副作用：创建新目录使 `vhs_multistation` 目录自身 mtime 由 2026-10-17T10:58:10.08 变为 13:01:59.81（+08:00）。

## 4. 测试

- 用户电脑（主结果，VERIFIED）：`python -B tests\test_demo.py`，PYTHONDONTWRITEBYTECODE=1，**Ran 42 tests … OK，exit=0**，完整日志 `tests\test_run_output.txt`。覆盖任务书第五节 1–17 项 + HTTP 集成测试（测试内线程启动服务于空闲端口，urllib 访问 127.0.0.1，结束后 shutdown）。
- 第 16 项：静态扫描产品代码无 sealed_runoff/quarantine/外部 URL/0.0.0.0/socket 导入（唯一允许的字面量是 app.js 中 SVG 命名空间标识 `http://www.w3.org/2000/svg`，它不是网络请求；`tools/integrity_snapshot.py` 中 sealed_runoff 仅出现在剪枝常量一行）；运行期替换 `socket.connect/connect_ex/getaddrinfo`，只放行 127.0.0.1，整轮测试外部连接尝试数 = 0（另有 2 次故意的守卫自检被拦截，未产生任何网络包）。
- 第一次试跑曾有 1 项失败（合成序列的周周期项依赖起始日，导致不同起点同一天数值不同），已改为按日期序数计算并重跑，属开发过程修正，不是为通过测试修改历史契约。
- 端到端冒烟（用户电脑，VERIFIED）：Start-Process 后台启动 `demo_server.py --port 8765`，监听地址 127.0.0.1:8765；curl.exe 访问 12 个场景，状态码均符合预期（200/404/400/403/404）；随后停止进程，复核启动器进程与子进程均不存在、8765 无监听、无残留 demo_server 进程。日志：`smoke\smoke_test_log.txt`、`smoke\server_stderr.txt`。
- box（非用户电脑，VERIFIED）：`node --check app.js` 通过；headless Chrome 加载在线页面（box 上启动的同版本服务副本）与 file:// 离线页面，均渲染出 14 个节点、11 条边的 SVG 与 JSON；另用仅存在于 box 的测试页触发 demo/predict/不存在站点三种交互，合成序列折线、NOT_AUTHORIZED、UNKNOWN_STATION 均正确显示。**用户电脑上没有做浏览器渲染验证**（未安装 node，无浏览器自动化）。box 上的测试服务已停止。

## 5. 权限遵守情况

| 禁止项 | 情况 |
|---|---|
| 下载新数据 / 外部网络 | 遵守：0 次（代码无外部请求，测试运行期守卫确认 0 次尝试） |
| 读 sealed_runoff 真实 Q / 列其内容 | 未读取任何内容；见 §6 事件 2 关于目录枚举的如实说明 |
| 用真实 Q 生成预测；B2/B3/B4；GNN/Transformer/物理路由/GPU/训练/评分 | 遵守：0 次 |
| 修改 B1A、B1B-S0、E4/E5、S1A、论文 | 遵守：§3 全量 SHA-256 比对无变化 |
| 修改 DeepBas 前端/后端/数据库/部署 | 遵守：未访问 |
| 安装依赖 | 遵守：仅标准库 + 已有 .venv |
| 绑定 0.0.0.0 | 遵守：BIND_HOST 固定 127.0.0.1，无修改入口；冒烟实测监听 127.0.0.1 |
| 把合成结果称为真实预测 | 遵守：所有响应/页面/文件标注 SYNTHETIC_DEMO_ONLY；prediction 恒 null |
| 写入新目录以外 | 新目录外的写入仅见 §6 事件 1、3 |

## 6. STOP 事件与偏差（如实记录）

- **强制 STOP 事件：无。** 未出现需要真实 Q、外部网络、下载、修改旧文件、安装依赖、改 DeepBas、GPU/训练的情形。完成后停止，未进入 B1B-S1/B2/B3/B4。
- 事件 1（新目录外误写入，已清理）：一次 PowerShell 调用中误以为上一调用的变量会保留，`$N` 为空，导致在 `C:\integrity\` 创建了目录及文件 `project_root_level_pre.txt`（内容为 `C:\Users\Administrator` 一级条目名与 mtime），同一命令还对 `C:\Users\Administrator` 递归查找了 `__pycache__` 目录（只列名，输出一个无关目录名）。发现后核对创建时间（13:02:09，确为本轮所建）并删除该文件与目录；此后每条命令都显式定义变量并在写入函数中拒绝空路径。未涉及项目目录与 sealed 目录。
- 事件 2（目录枚举范围偏差）：两次核查 `__pycache__` 时使用了 `Get-ChildItem -Recurse -Directory` 遍历 `vhs_multistation`，虽对结果按路径过滤、未输出也未记录 sealed_runoff/quarantine 内任何条目名、未打开任何文件，但枚举过程本身进入了这两个目录。这不符合"对这两个目录只记录目录自身修改时间"的从严要求，特此记录；两目录 mtime 前后不变。完整性工具本身按目录名剪枝，不进入。
- 事件 3（工具/系统临时文件）：远程 Shell 把较大输出缓存到 `C:\Users\Administrator\agent-tools\*.txt`（工具基础设施行为，其中两份含旧 S0 三个文件与新目录 7 个文件的 base64 副本，用于传到 box 核对哈希）；一次测试试跑把输出临时写到 `%TEMP%\s0d_try.txt`，读后已删除；PowerShell 临时脚本位于系统 Temp。
- 未完成/限制：用户电脑上未做浏览器渲染验证；F3 规则为合成规则；与平台的接口与错误码差异见 compat_report.md §5。

---

## 附注 R1（VHS-NEXT-B1B-S0D-R1，2026-10-17 追加）

本节为追加内容，以上原文未改动。追加前原文为 11554 B，SHA-256 0036572d35418512…，备份在 backup_pre_r1\integrity_report.md。

R1 的完整性检查（文件清单与 SHA-256、前后快照对比、D 外检查的方法和证据边界、%TEMP% 与缓存说明）见同目录 [integrity_report_r1.md](integrity_report_r1.md)。R1 新增的越界与过程事件见 incident_audit.md 的“R1 执行记录”。
