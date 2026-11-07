# VHS-NEXT-B0｜元数据与许可

审查日期：2026-10-11（Asia/Singapore）。仅数据结构、允许的元数据、河网属性与文献。新目标 Q 数值不进入本轮分析；不训练、不评分、不启动 GPU。


## 本地：UNVERIFIED

新疆及前苏联KMZ提供地理目录，不附可核实逐站原始观测供数合同；三个流量工作簿只证明文件存在。来源机构、原始单位打印、观测还是模拟、整编/补缺、迁站、日界、使用/公开再发布许可均不能由文件名或OQ标记推断。Q-dsk-byblk月序列不能自动称独立官方观测。不要再发布这些原始Q或把来源不明MQ作为输入。

34节点加工图、NPZ训练张量、WaterGAP采样和未知MQ均不能替代原始水文站观测。B0保存哈希及目录结构，不复制原始流量内容。

## 公开：产品逐项核验

1. **LamaH-CE**：仓库v1.0描述明确CC BY-SA 4.0，需作者/论文、版本、Info内各来源署名及改动说明、适用共享条件。捷克径流另列禁止用于运行性预警系统的条件；德国来源可能事后修订。正式用前获取Info和源部门条件，并审核兼容性；本轮未获得包内Info，故公开再发布整合benchmark仍CONDITIONAL。[仓库](https://zenodo.org/records/5153305)。不能把论文CC BY 4.0当数据许可。
2. **LamaH-Ice**：v1.5仓库正文将径流设为CC BY-NC 4.0，其他资料CC BY 4.0；通用页面又显示CC BY，必须按分项限制审查，不能套用通用标签开放商业使用。原始供数IMO/NPC可追溯修订；下载与版本文件可取性未实际测试。[v1.5](https://www.hydroshare.org/resource/705d69c0f77c48538d83cf383f8c63d6/)。不复制数据、不代用户接受下载许可。
3. **HydroRIVERS/HydroBASINS v1**：官网允许科学、教育及商业使用，采用HydroSHEDS v1协议。该协议Appendix A §2.1.2限制独立原材料再分发，衍生产品仍受条款约束；不能改标通用CC BY。B0只发布项目审查及少量路径证据；完整原图层不重新打包。[河网](https://www.hydrosheds.org/products/hydrorivers)、[集水区](https://www.hydrosheds.org/products/hydrobasins)、[协议Appendix A](https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf)。本地原始下载凭据/当时版本条款仍需归档。
4. HydroATLAS与以上产品许可不能混同；若后续使用其属性需另审。尤其长期平均流量、径流签名、目标Q率定产物不能因出现在“静态属性”表而成为无资料描述符。
5. CAMELS-US：文献标题/DOI已查，数据仓库细项授权及真实嵌套关系此次UNVERIFIED；不作为已审核许可来源。

## 时间制度与泄漏防线

LamaH-CE日流量为m³/s；奥/德/瑞日值按GMT 00:00–23:59整合，捷克制度须单独核验；数据论文说明1981–2017研究窗口。观测缺测标记−999、质量标记及插补信息需保留；不得按0流量解读缺测。[论文](https://essd.copernicus.org/articles/13/4529/2021/)

归档中的观测日期不是发布时间。只允许供数方给出的 `interval_start/end/timezone/release_time/QC_revision_time`在发行时点前可用输入；暂无release_time时仅能设计retrospective reconstruction，不能称实时预报。ERA5再分析也要采用其真实可用时刻；没有实时气象供给证明时只作回顾性信息重建。

只允许读取日期覆盖/QC缺测掩码、站点属性与许可；不允许目标Q均值、季节统计、FDC、runoff ratio、由Q反推area或率定参数。公开库中的hydrological signatures、COSERO已校准输出、未知MQ和目标依赖gap filling都需排除或单独封存审查。模型训练期可使用训练系统Q，测试系统任何站的Q不参与参数学习。
