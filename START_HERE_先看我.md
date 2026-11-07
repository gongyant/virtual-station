# DeepBas-VHS 全项目交接包 — 先看我

**状态以 `HANDOFF_ACCEPTANCE.json` 为准。** 本包基于原 8795（哈国候选）真实前后端，并保留/可对照 8794（P6/P7 科研）源码；已挂入 P8–P9C **已封存**只读结果页。

## 郑为：五分钟理解

1. **什么时候做的？** 见 `项目时间线与研究范围.md`（按阶段+证据，非仅靠 mtime）。
2. **用了什么数据？** 见 `项目用了哪些数据与模型.md`。
3. **岭回归还是 LSTM？** 见 `与锡尔河_岭回归_LSTM的关系.md`：**有 Ridge/正则化回归实据；LSTM 在平台里是 NOT_IMPLEMENTED 占位，主线未证明已训练使用。**
4. **和锡尔河一样吗？** 不一样：锡尔河是历史/受限支线；欧洲24站是公开方法开发；哈国工程首流域是 Balkhash–Alakol；正式已验证新增 VHS=0。
5. **网站能干什么？** 查询与展示历史重建/封存结果；**不是未来水情预报产品。**

## 启动（Windows）

```powershell
cd <解压后的本目录>
powershell -ExecutionPolicy Bypass -File .\scripts\check_prereqs.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1
```

默认：`http://127.0.0.1:8805/`（仅本机）。停止：`.\scripts\stop_windows.ps1`

## 建议浏览路径

- 首页 / 站点与模型（原界面）
- `#/p8` 全国河网 · `#/p9a` 站点链长 · `#/p9b` 30候选 · `#/p9c` 有效E2结果 · `#/withdrawn` 已撤回错误口径

## 压缩包

- `VHS_FULL_SOURCE_AND_DEMO.zip` — 源码+网站+可分享演示/结果摘要
- `VHS_RESEARCH_RESULTS.zip` — 派生成果/GIS/证明
- `VHS_INTERNAL_ONLY_MANIFEST.md` — 受限索引（无敏感字节）

受限教师 Q / 密钥 **不在包内**。详见 `MISSING_AND_PERMISSION_BLOCKERS.md`。
