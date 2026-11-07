# P5命令
    $py='E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
    $cli='E:\VHS_Public_Baseline_Lab\p5_robustness_and_external_validation\code\p5_cli.py'
    & $py -B $cli verify-release
    & $py -B $cli predict --station 2 --model P2-L1 --start 2016-01 --end 2016-12 --met E:\VHS_Public_Baseline_Lab\p5_robustness_and_external_validation\runs\P5_A_SAVED_MODEL_APPLICATION\MET_2.json --precip-unit mm/month --temp-unit degC --output "$env:TEMP\P5_ID2_predictions.csv"
单位需如实声明，不能从数值猜单位。输入不得包含Q。2016为V2应用示例，不是新OOF。
demo真实实现54进程批次，但本次目录独占创建，勿覆盖封存。重跑请使用新独立根/run身份。
SHRINK入口freeze.py→shrink.py；完整验证verify_p5.py，均会写记录，交付后在新目录运行，不覆写此封存。
诊断diagnose.py只作历史再分析；最终绘图plot_demo.py。外部只取得目录，不存在外部评分文件。
