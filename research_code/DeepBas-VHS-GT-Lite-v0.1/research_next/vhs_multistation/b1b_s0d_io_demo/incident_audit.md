# VHS-NEXT-B1B-S0D 越界事件审计（R1 正式记录）

> 记录对象：上一轮（S0D 09 号任务）中发生的三项越界/偏差事件。本文件只记录事实与限制，不修改、不删除任何历史文件。
> 证据等级：**VERIFIED**（有可复核证据）/ **INFERRED**（由间接证据推断）/ **UNKNOWN**（无法确定）。
> 原始陈述见 `integrity_report.md` §6（原文保留，R1 只在其末尾追加附注）。

## INC-1 误写 `C:\integrity\`　状态：**已清理**

| 项 | 内容 |
|---|---|
| 原因 | 一次 PowerShell 调用误以为上一调用中的变量 `$N` 会保留；`$N` 为空，相对路径落到了 `C:\` 根，创建了 `C:\integrity\` 目录及文件 `project_root_level_pre.txt`。同一命令还对 `C:\Users\Administrator` 递归查找了 `__pycache__` 目录名。 |
| 实际影响 | 在授权目录外新建 1 个目录 + 1 个文本文件（内容：`C:\Users\Administrator` 一级条目名与 mtime，无项目数据、无 Q 数值）；对 `C:\Users\Administrator` 进行了一次只列目录名的递归枚举（输出 1 个无关目录名）。随后核对创建时间（13:02:09，确为本轮所建）后删除该文件与目录。 |
| 证据等级 | 创建、内容、删除：**VERIFIED**（上轮命令输出，记录于 integrity_report.md §6）。删除后 `C:\` 根是否有其他残留：**UNKNOWN**——R1 按用户要求"不再访问 C:\ 下任何路径"，未复查。递归枚举 `C:\Users\Administrator` 是否触及其它敏感目录内容：只列名、未打开文件（**VERIFIED** 依据命令本身）；枚举过程本身会读取目录项（**VERIFIED**，不可撤销）。 |
| 残余未知风险 | ① `C:\integrity\` 删除后的状态未在 R1 复核（UNKNOWN，低）；② 文件系统/杀毒/索引服务是否记录了这次写入与枚举（UNKNOWN）；③ `C:\Users\Administrator` 下目录项的访问时间可能被更新（INFERRED）。 |
| 防止措施 | R1 起每条命令内显式定义全部变量；写入函数 `Assert-InD` 拒绝空路径、相对路径与 D 之外的路径；Python 写入工具 `_safe_out()` 只允许写入 D；R1 未对 C:\ 做任何访问。 |

## INC-2 递归枚举进入封存目录　状态：**无法撤销，只能记录**

| 项 | 内容 |
|---|---|
| 原因 | 两次核查 `__pycache__` 时对 `vhs_multistation` 使用了 `Get-ChildItem -Recurse -Directory`，该命令会下探到 `b1a\sealed_runoff` 与 `b1a\quarantine`。 |
| 实际影响 | 枚举过程读取了两个目录（及其子目录）的目录项；结果按路径过滤，**未输出、未记录**其中任何条目名，未打开任何文件，未读取任何 Q 数值。两目录自身 mtime 前后不变。 |
| 证据等级 | 枚举发生：**VERIFIED**（命令本身）。未输出条目名、未打开文件：**VERIFIED**（命令管道只输出过滤后的 `__pycache__` 路径）。工具输出缓存中是否含其条目名：**INFERRED 不含**（过滤发生在远端 PowerShell 内，输出只有过滤后结果），但缓存文件 R1 未重新读取，最终 **UNKNOWN**。目录访问时间是否被更新：**UNKNOWN**（取决于 NTFS 设置）。 |
| 残余未知风险 | 目录项已被读取这一事实无法撤销；若封存协议以"目录从未被枚举"为前提，该前提已被破坏（应由项目持有人判断是否需重新封存或备案）。R1 记录：b1a/sealed_runoff mtime_ns=1792123375343036500，b1a/quarantine mtime_ns=1792123381802710800（只对目录自身取值）。 |
| 防止措施 | R1 起禁止对 vhs_multistation 上层/项目根使用 `-Recurse`；`__pycache__` 只在 D 内递归查找；完整性快照工具 `tools\integrity_snapshot_r1.py` 使用自写遍历 `walk_pruned`，目录名匹配 `(?i)sealed|quarantin` 时**不调用 scandir 进入**，只记录目录自身 mtime；测试 R1-SEAL-01（假文件系统证明剪枝）、R1-SEAL-03（运行期 open/scandir/listdir/stat 守卫，0 次触及）。 |

## INC-3 工具输出缓存与临时文件　状态：**未清理，待用户决定**

| 项 | 内容 |
|---|---|
| 原因 | 远程 Shell 工具在输出较大时把输出缓存到 `C:\Users\Administrator\agent-tools\*.txt`（工具基础设施行为，不是项目代码写入）。上一轮其中两份缓存含旧 S0 三个文件与新目录 7 个文件的 base64 副本（为传到 box 核对哈希）。另有一次测试试跑输出写到 `%TEMP%\s0d_try.txt`，读后已删除；PowerShell 自身的临时脚本位于系统 Temp。 |
| 实际影响 | 授权目录外存在项目文件的外部副本（旧 S0 契约文件为只读公开代码/文档，不含真实 Q 数值；新目录文件为合成原型）。 |
| 证据等级 | agent-tools 缓存存在：**VERIFIED**（上轮报告）。缓存的当前数量/内容：**UNKNOWN**——按用户要求 R1 **未重新读取该目录，待用户授权**。`%TEMP%\s0d_try.txt` 已删：**VERIFIED**（上轮）。系统 Temp 中 PowerShell 临时脚本：**INFERRED** 存在且由系统管理，R1 未访问。R1 本轮 Shell 输出是否也被缓存：**UNKNOWN**（R1 尽量缩小单次输出，但无法核实）。 |
| 残余未知风险 | ① 缓存副本会一直保留直到用户清理；② R1 的部分输出（测试日志摘要、哈希、文档片段）也可能被缓存；③ 缓存中不应含真实 Q 数值（全程未读取），INFERRED。 |
| 防止措施 | R1 不访问、不清理 agent-tools（需用户授权）；R1 未在 %TEMP% 主动创建文件（测试日志直接写入 D\tests、D\smoke）；文件传输改为 box 打包、PC 端经 `Assert-InD` 解包并逐个 SHA-256 核对。**建议用户决定**：是否授权列出/清理 `C:\Users\Administrator\agent-tools\` 中本项目相关的缓存。 |

## R1 本轮新增事件
见 `integrity_report_r1.md` §STOP / 偏差。

---

## R1 执行记录（2026-10-17 追加，时间均为 Asia/Singapore UTC+8）

本节如实记录 R1 执行过程中出现的中断、失误与过程异常。以上 INC-1/2/3 原文未改动。

### E-1 执行中断（用户于 17:33 指出）

| 项 | 内容 |
|---|---|
| 发生时间 | 约 17:32:20 – 17:33 之间。PC 上最后一次写入是 smoke\smoke_test_log_r1.txt，时间 17:32:20，文件含收尾行 `# stopped ...` |
| 中断时正在做的操作 | 在盒子（box，非用户 PC）上只读查看 demo_core.handle_predict 的 403 响应结构，用于核对 smoke 日志中 prediction_authorized 一栏的显示。此时 PC 上没有进行中的写操作，也没有运行中的服务进程 |
| 可能的半写文件 | 逐一核对后未发现。核对方法：17:33 后对 D 根目录及 backup_pre_r1、schema_draft、tests、tests\js、tests\fixtures、smoke、integrity、_r1_transfer、tools、synthetic_data 各做一次非递归列举，记录长度、修改时间和 SHA-256 前 16 位。test_run_output_r1.txt 有 `# exit_code: 0` 和 `# finished` 尾行；smoke_test_log_r1.txt 有 `# summary: 20/20 PASS` 和 `# stopped` 行；io_examples_r1.json 可完整解析为 JSON；由 _r1_transfer 下 7 个分块合并解码出的 19 个文件，SHA-256 与盒子侧一致 |
| 中断时已完成 | 传输包落盘；README.md 与 compat_report.md 追加完成（原文前缀与 backup_pre_r1 的 SHA 一致）；build_artifacts；gen_io_examples_r1；PC 测试（第 2 次）；PC 冒烟测试（第 2 次） |
| 中断时未完成（之后续做） | 盒子 headless Chrome 页面检查；本执行记录；integrity_report.md 的 R1 附注；post 快照与对比；integrity_report_r1.md |
| 残余风险 | 低。所有文件都在 D 内，且已用哈希核对。中断本身不涉及 D 外写入 |

### E-2（INC-4）PowerShell 别名冲突导致错误输出刷屏，输出落到 C 盘工具缓存

| 项 | 内容 |
|---|---|
| 起因 | 追加 README/compat 时，自定义的哈希函数取名为 `H`。PowerShell 5.1 中 `H` 是 Get-History 的内置别名，别名优先于函数，于是每个字节都被当作历史 ID 去调用 Get-History，产生大量报错 |
| 影响一：校验失效 | 首次输出的 `same_as_backup=True`、`prefix_matches_backup=True` 是空值相等造成的假阳性，不能作为证据。随后改用不冲突的函数名 Get-ShaHexR1 重新校验：README.md 与 compat_report.md 的原文前缀 SHA 等于 backup_pre_r1 中的 SHA（a097656d… / b26a7f52…）；分隔符为 `\n\n`；追加部分与片段文件 SHA 一致；均无 BOM。追加操作本身正确 |
| 影响二：D 外文件 | 该命令运行超过 30 秒后被工具转入后台，约 1.1 MB 的输出被远程 Shell 工具机制写入 `C:\Users\Administrator\terminals\708052.txt`（C 盘，D 外）。这不是我的命令主动写入的，但是由我的命令引发，按越界事件记录。内容只有 PowerShell 报错文本，其中含 README/compat 字节的十进制值（即两份文档本身的内容），不含 Q 数值、凭据或封存目录信息 |
| 处置 | 按“不访问 C:”和“不自动删除”的要求，未读取、未删除该文件，等待用户决定。之后的命令都控制在 30 秒内或小输出，避免再次转入后台 |
| 证据等级 | 文件路径和大小来自工具返回信息（output_length=1135008），未在 PC 上直接核验 |
| 残余风险 | 该目录下可能还有其他工具缓存文件（与 INC-3 同一机制），本轮无法证明不存在 |
| 防止措施 | PowerShell 自定义函数一律用“动词-名词”加 R1 后缀的命名，避开内置别名；所有校验输出必须打印实际哈希值，不只打印布尔值 |

### E-3 PC 第 1 次测试：1 个 ERROR（测试自身的跨平台缺陷）

R1_SEAL_NoSealedAccess.test_SEAL_01 的假文件系统以 POSIX 路径 `/r` 为键。walk_pruned 内部调用 os.path.abspath，在 Windows 上把 `/r` 变成 `E:\r`，查不到键，抛出 KeyError。

修正只针对测试中的 _FakeFS.scandir：去掉盘符、统一分隔符后再查键，记录的也是规范化后的键。断言一条未改，被测代码未改。

test_r1.py 的 SHA 由 b0f8ccb4… 变为 40ed0a89…（56030 B）。第 1 次日志保留为 tests\test_run_output_r1_attempt1.txt，未覆盖。

### E-4 PC 第 1 次冒烟测试：19 项中 1 项不符（测试脚本缺陷）

- 用例 05 请求 synthetic-demo 时没有带 start/end 参数，服务正确返回 400 TIME_RANGE_MISSING。脚本错在把这一项预期写成了 200。
- 日志中提取错误码字段的正则写错了键名。
- 只停止了 Start-Process 返回的启动器 PID。.venv 的 python.exe 是启动器，真正监听端口的是它的子进程。事后核实：该子进程（PID 38752）已不存在，8765 端口无监听。

第 1 次日志与对应的 server 输出已改名为 *_attempt1.txt 保留。第 2 次冒烟测试 20/20 PASS，启动器和监听进程都已停止，停止后端口无监听。

### E-5 冒烟日志中 403 一行 `prediction_authorized=-` 的含义

这是日志解析脚本的局限，不是字段缺失：403 响应中 prediction_authorized 是对象 `{"status":"NOT_AUTHORIZED","authorization_ref":null,...}`，解析脚本只提取标量值。该字段的存在和取值由测试 R1_D6/R1_PR 断言覆盖。4xx 错误响应（400/404/405/413/414）按 D6 规定不含 prediction_authorized。

### E-6 传输分块校验值的说明

chunk_06 在 PC 上为 8876 B，比盒子上的 8877 B 少一个结尾换行，因此其分块哈希与计划值 4eeedbff… 不同。完整性改为以解码后逐文件 SHA-256 为准，19 个文件全部一致。

_r1_transfer\ 下的 7 个分块和 2 个追加片段属于中转文件，按“不自动删除”的要求保留，是否清理由用户决定。
