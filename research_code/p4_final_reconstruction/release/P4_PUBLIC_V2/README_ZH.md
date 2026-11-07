# P4公开流域月径流重建模型
只需Python与NumPy，无需P2/P3源码、原始Q或训练过程。LamaH-CE v1.0，DOI 10.5281/zenodo.5153305。依据原来源说明遵守CC BY-SA 4.0归属与共享条件，ERA5-Land流域气象；不得称为锡尔河成绩。
先按SHA256SUMS.txt核验发布包。模型.json内绝对路径仅为历史来源证据，推理不会打开它们。
输入为date、gauge_id、P(mm/月)、T(°C)，L1模型必须含前一自然月P。未提供、非有限、单位错、跨站及目标Q字段均拒绝。
示例（在此目录执行）：
python -B runtime/inference.py --model models/ID_2/P2-L1 --met example_MET_ID2.json --start 2016-01 --end 2016-12 --output example_predictions.csv
该例仅演示V2磁盘推理，V2已经使用这些年份标签，绝不可将示例预测作为新的样本外成绩。独立遮蔽精度请见P4主目录MASKED_DEMO产物。
API: 将runtime目录加入sys.path，from inference import load_model,predict_month,predict_range。
每月输出风险及资格；DEFAULT仅在气象完整、区间有效、非HIGH_EXTRAPOLATION时适用，不保证单站提升或严格区间覆盖。
