# 复核方法

使用既有环境 `E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe`，始终`-B`。历史路径只读。先验证根SHA256SUMS.txt，随后运行：

```powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p6c_2020_validation\code\verify.py'
```

verify只复核已有固定预测和评分，不fit。它会重写P6C复核证据；如需严格只读核验，直接按SHA清单计算即可。driver.py representatives/all复算小时链，不读取Q；不应覆盖已交付封存文件，应先复制整个P6C到新目录并相应设置p6c_common.R。run_fixed.py predict、score各有禁止覆盖目录检查，分别先封存预测、后读取Q。不要删除已存在run以刷成绩。CDS脚本仅用本机已有配置，凭据不在交付包内；所有已取得数据可离线重算。

原始数据和模型哈希记录于P6C_ADMISSION_FROZEN.json、预测COMMITMENT.json、driver下载回执；许可复用P6B/SOURCE_LICENSE_AND_DOWNLOADS.md，ERA5-Land新增产品为CC-BY、DOI10.24381/ee82e357。保留Copernicus/ECMWF、LamaH-CE与eHYD/BMLUK署名，不批量导出日/月Qobs。
