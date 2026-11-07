# VHS-NEXT-B1B-S0｜07 下一阶段决策

日期：2026-10-17（Asia/Singapore）。**本轮 S0 完成后停止，不自动进入任何下一步。**

## 1. 本轮判定

- 科研：`NO_GO_CURRENT_MULTISYSTEM_BENCHMARK` 维持（VERIFIED，01/06）；“通过补元数据在 LamaH-CE 内构建更多跨水系样本”**不可行**，因为独立目标组受真实结构限制（INFERRED，01 §5）。新数据源中存在值得核验的候选，但没有一个被证明合格（VERIFIED，02）。
- 工程：VHS 功能规格、候选契约、合成测试完成（VERIFIED，08）；平台集成未开始，需平台组协议（UNKNOWN）。
- B2/B3/B4、训练、评分、GPU：未启动，也不建议在当前证据下启动。

## 2. 唯一建议的最小可验收新任务（PROPOSED，需用户明确批准）

**VHS-NEXT-B1B-S1：CAMELS-FR v3.2 拓扑元数据只读核验**

- 目的：回答“CAMELS-FR 是否提供 ≥2 个与 LamaH-CE 无依赖关系、且各自含合格连通目标对的独立评价单元”。
- **需要用户批准的操作**：
  1. 从官方 Recherche Data Gouv（doi:10.57745/WH7FJR）下载**仅** `CAMELS_FR_geography.zip`（1,447,477 bytes）与 `CAMELS_FR_attributes.zip`（9,882,622 bytes）两个小文件；**不下载** `CAMELS_FR_time_series.zip`（361 MB）；
  2. 在新目录（例如 `research_next\vhs_multistation\b1b_s1_camels_fr_meta\`）内写入；
  3. 解压后**只打开**嵌套信息文件（`CAMELS_FR_catchment_nestedness_information.csv`）、站点位置/面积/流域边界文件；对其余属性文件只读表头，凡属水文签名/流量派生的文件整表列入黑名单、不读数值。
- 验收标准：输出独立自然系统数、人工依赖组数（标注调水信息缺失为 UNKNOWN）、含连通目标对的系统数、不连通对照共同支持的元数据级估计；每项标证据等级；许可冲突（CC BY vs CC BY-SA）原样记录为 CONDITIONAL；0 次 Q 读取。
- 不包括：任何流量数值、训练、评分、联系维护者。

## 3. 需用户自行决定、本轮不代办的事项

- 是否发送 B1A 已起草的维护者邮件（`b1a_provider_email_draft.md`，本轮只读、未发送）。
- 是否请 DeepBas 平台组回答 04 §8 的问题。
