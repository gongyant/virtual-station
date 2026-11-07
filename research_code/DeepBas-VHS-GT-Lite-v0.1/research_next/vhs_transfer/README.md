# VHS-NEXT-S0

本目录是独立新研究交付，历史文件只读。入口：reports/vhs_next_s0_validation_report.md。
详情：source_inventory / provenance_audit / leakage_audit / topology_audit / physics_baseline_inventory / research_protocol。
物理规范：physics/physics_baseline_specification.md。状态：reports/vhs_next_s0_status.txt。
哈希范围和逐值证据：data_audit/。合成测试：tests/。下一阶段仅设计：experiments/、evaluation/。

已执行命令（项目根，PowerShell）：
`.venv/Scripts/python.exe -B research_next/vhs_transfer/data_audit/integrity.py before`
`.venv/Scripts/python.exe -B research_next/vhs_transfer/data_audit/collect_evidence.py`
`.venv/Scripts/python.exe -B research_next/vhs_transfer/tests/run_synthetic_tests.py`
`.venv/Scripts/python.exe -B research_next/vhs_transfer/tests/check_synthetic_input_boundary.py`
`.venv/Scripts/python.exe -B research_next/vhs_transfer/data_audit/integrity.py after`
`.venv/Scripts/python.exe -B research_next/vhs_transfer/reports/build_s0_reports.py`

before基准脚本拒绝覆盖，勿当成可随意重置的状态。rerun仅限经批准的审计/合成核验，不能自动进入真实实验。
