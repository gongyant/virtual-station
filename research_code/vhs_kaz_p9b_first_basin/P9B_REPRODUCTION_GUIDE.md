# 复现及文件映射

数值/GIS环境：E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe，-B；无需安装。仅官方PDF读取/渲染使用现成bundled pypdf/pdfplumber/PDFium，未改变科研Python环境。

只读验证封存：
```powershell
& 'E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/.venv/Scripts/python.exe' -B 'E:/VHS_Public_Baseline_Lab/vhs_kaz_p9b_first_basin/code/verify_delivery.py'
```

数据生成依赖：acquire.py（初始保护/小文件）→必要时resume_download.py（只执行一次合法HTTP Range恢复）→gis.py→q_audit.py→bulletin_sources.py→extract_bulletin.py/render_bulletin.py（bundledPDF读取）→bulletin_admission.py→ca_key_audit.py→prepare_protocol.py→verify.py→reports.py→figures.py/figure_qa.py→人工查看→seal.py。仅在独立新目录设置VHS_P9B_OUTPUT后重算，不能覆盖已封存目录。GIS脚本会拒绝已存在的新GIS文件。当前来源皆本地，可复制已获快照及哈希后跳过网络；外部页面会变，重访须新快照。

注意bulletin_admission.py为人工原样转录矩阵，不是模型或合成数据；独立verify.py从PDF字词位置读数，校验所有252值与真实月份。Lepsy36冲突行保留不修改。CA时序仅公开KAZ16390被读取数值，其余按日期/分辨率统计，不访问任何教师文件。GeoPackage使用immutable只读，不能通过改WAL头解决警告。CA数据为CC-BY4.0，官方公报/QazSu完整再发布及训练范围未确认，交付仅本地研究，不自动上传网站。

GIS为P9B_FIRST_BASIN_GIS.gpkg，候选、首流域、49点、源集水区出口代理及CA其他本国流域分层。P9B_CATCHMENT_DELINEATION_STATUS是点位精度/面积/跨境限制；P9B_CANDIDATE_NETWORK_RELATIONSHIPS是有向关系和内河段距离；权重data/ERA5_LAND_PROXY_AREA_WEIGHTS是准备值，不是ERA5实测或重分析值本体。

P9B_AVAILABLE_Q_INVENTORY逐来源/站/分辨率列出本流域与流域外；统计时段不等同于已取得原始Q，N/A不改0。P10JSON/MD冻结设计而非已执行折。暴露台账单列2021–2024月值及整本公报，未来保管机制尚未具备。

所有实际命令、下载、恢复和质量问题见RUN_ATTEMPTS.jsonl、source各DOWNLOAD记录及evidence/FAILURE_RECOVERY_LOG.json；独立QA见P9B_INDEPENDENT_QA.json；软件检查与数据源6项算术失败分开报告。最终SHA256SUMS覆盖代码、来源、GIS、CSV、图、报告和证据（清单自身不自引用）。
