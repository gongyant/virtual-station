# P6D复现与文件映射

实际运行环境：E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe。工作目录：E:\VHS_Public_Baseline_Lab\vhs_p6d_failure_diagnostics。所有历史输入只读。未联网、未下载数据、未安装依赖。

实际运行的计算命令（均已执行，不是计划）：

```powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p6d_failure_diagnostics\code\extract.py'
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p6d_failure_diagnostics\code\analyze.py'
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p6d_failure_diagnostics\code\verify.py'
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p6d_failure_diagnostics\code\figures.py'
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p6d_failure_diagnostics\code\figure_qa.py'
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p6d_failure_diagnostics\code\report.py'
```

不要在已封存P6D上重新执行写出命令。重新计算时先复制P6D到一个新研究目录，设置`$env:VHS_P6D_OUTPUT='新目录绝对路径'`，然后按上列顺序运行新目录code中的脚本；该变量只改变输出位置，P4/P6B/P6C输入不变。verify也写新目录核验结果。若只要只读验收，按根SHA256SUMS.txt逐文件核对，不运行生成器。fit/partial_fit等在提取进程内被拒绝，未导入原训练入口。

文件映射：P6D_MONTHLY_PAIRED_ERRORS.csv=864个主配对月；P6D_STATION_YEAR_FAILURES.csv=年度/24月/36月、主与严格子集；P6D_PREDICTION_DECOMPOSITION.csv=1728模型月真实项；P6D_SEASONAL_AND_DRIFT.csv=季节和训练参照；P6D_INTERVAL_AND_QC_DIAGNOSTICS.csv=冻结区间与QC；P6D_EVIDENCE_GRADE.csv=分级结论。额外表保留预测差各项、模板/峰值、支持状态、Rhine4月、固定日期敏感性和归一化月份损失。

四类图：F1_MONTHLY_PREDICTIONS（用户指定8案例的36月曲线）、F2_ERROR_CONTRIBUTION（455/171逐月与累计贡献）、F3_SEASONAL_SKILL_AND_FAILURE（24站相对/绝对季节失败）、F4_FEATURE_CONTRIBUTIONS（455/171原模型项与差值项）。每图有PDF/SVG/300dpi PNG，源数据在figure_source_data，脚本为code/figures.py，输入/脚本/图哈希在P6D_FIGURE_PROVENANCE.json。图只表达原始点或描述性配对量，不包含置信区间/显著性主张。

质量限制：没有逐日QC和UTC认证；STRICT不是业务认证；季节n=2/3指标不稳定；网络站点相关；已有标签暴露必须记账。自动PDF碰撞审查依赖PyMuPDF，本环境缺失，NOT_AUDITABLE不能算PASS。图渲染、PDF字形及对齐采用现有Python；不使用R或AI生成数值/图片替代。

来源：LamaH-CE v1.0（Klingler, Schulz, Herrnegger 2021，DOI10.5281/zenodo.5153305，CC BY-SA4.0），Copernicus/ECMWF ERA5-Land（新小时来源DOI10.24381/ee82e357，CC-BY），Hydrographie Österreichs/BMLUK/eHYD归档。许可与署名继续沿用P6B/P6C来源说明，Qobs输出限本地研究。教师数据与SYRDARYA分支没有参与。
