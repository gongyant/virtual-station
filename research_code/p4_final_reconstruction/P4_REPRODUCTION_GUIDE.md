# 加载、推理与复核
推理不重新训练，使用现有Python/NumPy。PowerShell：
    $py='E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
    $p='E:\VHS_Public_Baseline_Lab\p4_final_reconstruction'
    & $py -B "$p\release\P4_PUBLIC_V2\runtime\inference.py" --model "$p\release\P4_PUBLIC_V2\models\ID_2\P2-L1" --met "$p\release\P4_PUBLIC_V2\example_MET_ID2.json" --start 2016-01 --end 2016-12 --output "$env:TEMP\P4_ID2_new_inference.csv"
此V2示例日期已经参与最终训练，不可重新评分宣称独立验证。排除2016标签的真正人工缺档模型在runs/PUBLIC_DATA_FINAL_P4_MASKED_DEMO/P2-L1。
加载API：将runtime加入sys.path，再from inference import load_model,predict_month,predict_range。缺测/单位错/跨站/目标Q字段拒绝，真实L1日历对齐。示例输入仅气象。
可移植ZIP应与release/P4_PUBLIC_V2_ATTRIBUTION.txt一并使用/分发，不依赖原始Q或冻结P2/P3源码。模型.json绝对路径只是历史来源记录，推理不打开这些数据。
入口顺序：prepare.py→train.py freeze→train.py V1→validate_models.py→score_v1.py→train.py V2→apply.py→export_models.py→verify.py→report.py。
训练/评分入口采用独占创建及已评分拒绝，勿在封存目录重复执行。若要完整复现实验，使用新独立目录/新run身份，保持原协议与来源哈希，common.py指向新根，不能覆写本次封存。
verify.py复算已冻结数值不做训练/选择，但会写新核验记录；若在交付后执行，应改为新的核验输出目录。只读复核本次SHA256SUMS可直接逐行计算哈希。
证据链：T0_FREEZE→模型/区间/预测COMMITMENT→REAL_MODEL_ACCEPTANCE/FRESH_PROCESS→TEST_Q_RELEASE_RECEIPT→唯一V1评分→新V2快照/参数→新进程应用。
