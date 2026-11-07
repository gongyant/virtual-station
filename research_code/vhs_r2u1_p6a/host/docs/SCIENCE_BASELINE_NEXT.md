# 后续水文科研基线：最小具体任务（VHS v0.6 之后）

> 目标不是“先上大模型”，而是先把**一条可复现、可评价、可证伪**的基线跑通。
> 每一步都给出：输入、产出、验收标准、需要的授权。当前所有模型执行均为 NOT_AUTHORIZED。

## 任务 S1：把“数据资格”变成可执行的样本表（1–2 天，无新增授权）

- 输入：research_ready/（task_eligibility.json、samples.csv、qc_station_year.csv、continuous_intervals.json）
- 动作：对 16037→16039 的每个可用年-月，标记
  - 是否 SEQUENCE_INDEX_SUSPECT（占位嫌疑，剔除）
  - 是否缺测（剔除，不插值）
  - 是否有年径流一致性结论（CONSISTENT / W_INCONSISTENT 仅作记录，不改值）
- 产出：samples_baseline.csv（列：t、Q_up、Q_down、P、T、circle_area_A_G、usable、exclude_reason）
- 验收：样本数、剔除数、剔除原因分布可复现；与现有 QC 计数一致（不许静默改口径）
- 授权：无（仅使用已授权历史观测的只读派生）

## 任务 S2：跑通 SYR-B0 线性基线（需 2 项授权）

- 模型：Q_down(t) ≈ a + b·Q_up(t)（无滞后；滞后版本作为对照）
- 输入：samples_baseline.csv 中 usable=True 的行
- 切分：时间切分（例如 2003–2019 训练 / 2020–2024 测试），**不得随机切分**
- 评价：NSE、KGE、RMSE、MAE、PBIAS + 评价样本数 n；指标必须带 model_version、dataset_version、period、common_sample_ids
- 产出：metrics.json + 散点图 + 残差图 + 逐年误差表
- 验收：脚本可一键重跑；指标与服务端 /api/v6/results/evaluation 的契约一致；预测只写 results 产物，不回写观测
- 需要的授权：① FUTURE_MODEL_INPUT（允许把历史 Q 作为模型输入/标签）；② MODEL_EXECUTION（允许训练与推理）

## 任务 S3：SYR-B1 / B2 增量对照（依赖 S2）

- B1：+P_monthly_sum、T_daily；B2：+circle_area_A_G（KZDAM 单位未确认前不得进入）
- 做消融：B0 → B1 → B2，报告指标变化与不确定性
- 泄露检查：沿用 research/feature_dag.py 的递归谱系 + 三类任务规则；零目标 Q 任务下禁用任何含目标站 Q 的谱系
- 验收：同一份 samples_baseline.csv、同一时间切分、同一评价函数

## 任务 S4：把结果写回四层平台（依赖 S2）

- 新增只读产物目录 results_runs/<run_id>/（metrics.json、series.csv、report.md、manifest.json 带哈希）
- 平台侧：/api/v6/results/* 增加 run 维度（当前契约已预留 qsim/qsim_status/model_version/uncertainty）
- 验收：结果层出现真实 Qsim 曲线与指标；未运行状态仍可回退到当前空状态

## 任务 S5：GIS 与空间结果（依赖授权，可与 S2 并行）

- 按 docs/DATA_AND_AUTHORIZATION_REQUEST.md 接入河网/站点坐标/reach268
- 先做点位与河段显示（GIS_DISPLAY_READY），再做“按河段汇总的模拟流量”图层的渲染契约
- HYDROLOGICALLY_CERTIFIED 仍需单独的上下游关系复核，不能因为画出河就自动认证

## 建议的推进顺序与里程碑

1. 第 1 周：S1 完成（无授权门槛）→ 用 S1 的结果检验“数据够不够训练”。
2. 第 2 周：取得两项授权后做 S2，先只做 B0，指标如实报告（哪怕不好）。
3. 第 3 周：S3 消融 + S4 写回；同时准备 S5 的 GIS 授权材料。
4. 任何阶段：结果层不得出现没有 run_id 的数字。

## 现在就能给的“最小可交付承诺”

- 一个能一键重跑的基线脚本 + 一份 metrics.json + 一张过程线/散点图 + 一段诚实的限制说明。
- 明确写出：单位未确认、年份离散、占位嫌疑剔除规则、样本量、时间切分边界。
