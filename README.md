# DeepBas-VHS 虚拟水文站 — 完整 DEMO 交接快照

**仓库：** 公开交接快照（2026-11-05 打包 / 2026-11-07 推送）。  
**状态：** `HANDOFF_PARTIAL`（真网站 + 可分享代码/结果可独立启动；受限教师 Q 与原始大数据未收录）。

本仓库基于原 **8794 / 8795** 真实前后端，并挂入 **P8–P9C 已封存**只读结果；**不是**重新生成的空模板网站。

## 五分钟理解

1. **时间线：** 多阶段（欧洲公开原型 → 哈国全国河网 → P9A/B 选址 → P9C 首流域实验）。详见 `项目时间线与研究范围.md`。
2. **数据：** LamaH-CE、HydroRIVERS 派生、QazSu/公开气象等。详见 `项目用了哪些数据与模型.md`。本仓含 **公开 LamaH 日表副本**；教师/锡尔河受限 Q **不在仓内**（见 `VHS_INTERNAL_ONLY_MANIFEST.md`）。
3. **模型：** 有 **Ridge / 正则化回归** 实据；平台内 **LSTM = NOT_IMPLEMENTED 占位**，主线未证明已训练。详见 `与锡尔河_岭回归_LSTM的关系.md`。
4. **锡尔河 vs 巴尔喀什—阿拉湖：** 不同阶段；工程首流域为 Balkhash–Alakol。
5. **能做什么：** 历史流量重建与封存结果展示；**不是**未来水位/流量预报产品。

## 顶层结构

| 路径 | 内容 |
|------|------|
| `website/` | 可启动前后端（含 `#/p8` `#/p9a` `#/p9b` `#/p9c`） |
| `research_code/` | 各阶段研究代码 + 公开日表副本 |
| `scripts/` | Windows 启动 / 停止 / 前置检查 |
| `demo_data/` `results/` `provenance/` | 可分享演示与封存摘要 |
| `config/.env.example` | 环境变量模板（无真密钥） |
| `PUSH_EXCLUSIONS.md` | 推送排除清单与安全扫描记录 |

## 启动（Windows）

需要本机 Python 3（建议 3.10+）。**不要**依赖原开发机上的 8794/8795 服务或旧 E: 路径。

```powershell
cd <本仓库根目录>
powershell -ExecutionPolicy Bypass -File .\scripts\check_prereqs.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1
```

默认：`http://127.0.0.1:8805/`（仅本机 loopback）。停止：`.\scripts\stop_windows.ps1`

更细说明：`START_HERE_先看我.md`、`RECEIVER_SETUP_WINDOWS.md`、`REPRODUCE.md`。

## 安全与许可

- **Public 仓库提醒：** 内容为可分享源码与公开数据副本；请勿向本仓追加教师 Q、账号密钥或未授权微数据。
- 缺项与权限阻断：`MISSING_AND_PERMISSION_BLOCKERS.md`
- 推送排除：`PUSH_EXCLUSIONS.md`

## 许可 / 归属

研究代码与文档按原项目约定由仓库所有者维护；第三方公开数据（如 LamaH-CE、Natural Earth）保留其各自许可与出处说明。