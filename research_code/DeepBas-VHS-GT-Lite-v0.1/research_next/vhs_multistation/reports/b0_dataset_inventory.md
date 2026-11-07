# VHS-NEXT-B0｜候选数据清单

审查日期：2026-10-11（Asia/Singapore）。仅数据结构、允许的元数据、河网属性与文献。新目标 Q 数值不进入本轮分析；不训练、不评分、不启动 GPU。


## 本地资源及证据边界

1. `data/raw/stations/新疆基本水文站.kmz`：130 个 Placemark；`前苏联水文站点.kmz`：1382 个。它们是地理站点目录，不能当作1512条流量序列。B0读取站名、坐标、白名单身份字段；正式供数者、有效期和再发布权仍未核实。目录证据见 `../evidence/station_catalogs.json` 及两个 inventory JSON。
2. `data/raw/runoff/`仅见三个工作簿。`BYBLK-DSK日数据.xlsx`：Sheet1，声明范围 A1:C16803；`Q-dsk-byblk.xlsx`：BYBLK、DSK、Sheet3，声明范围 A1:B246、A1:H253、A1；`Q-新疆.xls`：12个工作表，包括2000/2005支流、2005干流及SB/RS标记表。只读sheet目录和XML dimension，未读取工作表Q单元格。范围不等于有效记录数；sheet年份不构成精确日期覆盖证明。SHA-256和完整sheet目录见 `../evidence/workbook_structures.json`。
3. 已冻结S0来源审查记录两站1978-01-01至1983-12-31、2191日；B0只引用历史元数据，不重新打开数值，不把旧开发站转成独立盲测站。单位打印、日界、整编史、正式供数身份仍缺证明。
4. 早期五站2005资产：BYBLK/DSK各184日（05-01..10-31），ALAR/XQM/AQK各300日（01-02..10-28）；全五站共同窗口181日。日期/计数来自已有覆盖元数据，不重新验证原始数值。TARIM_*是项目别名；不是已核实官方ID。旧bundle包含OQ和来源不明MQ，禁止直接用作strict zero-shot基准。两个塔里木边仅为历史文献顺序/折叠边。
5. 早期34节点资产：`data/processed/nodes.csv`34站、`edges.csv`19边；NPZ头为2191×34×2，不能据shape认定34站都有观测。历史S0区分实际两站obs_q与WaterGAP等加工输入；WaterGAP不是测站原始Q，率定独立性也未核实。B0仅读NPY头，所有数组payload均未加载。
6. 本地 `data/raw/hydrorivers/HydroRIVERS_v10_as.*` 与 `data/raw/hydrobasins/hybas_as_lev12_v1c.*`是地形衍生河网/集水区，不是观测序列。B0从区域bbox内217163个河段的HYRIV_ID/NEXT_DOWN/MAIN_RIV/LENGTH_KM/UPLAND_SKM复核19条路径。节点UP_AREA为项目HydroBASINS匹配字段，不能冒充官方测站集水面积。没有重算全体集水区多边形，也没有证明官方下载链。
7. 本地有ERA5-Land、WaterGAP、静态/DEM/SWORD目录。现有已审查气象覆盖服务旧BYBLK–DSK域；不能证明34站或前苏联目录具备逐站气象覆盖。WaterGAP、MQ、已率定物理输出均不自动成为合法无资料输入。其他原始Q文件在本轮有界 `data/raw/runoff` 清单中未发现；不宣称全磁盘不存在。

## 公开候选及可访问性

- **LamaH-CE，首选元数据获取对象**：正式说明区分859个集水区与882条站点径流序列，提供日/小时资料及有向关系字段；数量均不是嵌套对数。[数据论文](https://essd.copernicus.org/articles/13/4529/2021/)。真实合格对数和完整独立系统数尚未枚举。
- [Zenodo v1.0](https://zenodo.org/records/5153305)可公开查看；概念记录4525244跳转到5153305，版本DOI为10.5281/zenodo.5153305。页面列daily包约1.5GB、daily/hourly约14.8GB；未下载。数据描述有CC BY-SA 4.0及来源附加条件，详见许可报告。[来源](https://zenodo.org/records/5153305)
- **LamaH-Ice，补充候选**：论文描述107流域及日/小时资料。[论文](https://essd.copernicus.org/articles/16/2741/2024/)。当前公开v1.5页面已核实存在；旧资源被新版本替代。未枚举该版本站点表、嵌套对或独立系统；不能把论文107流域无条件转为v1.5合格对数。[资源](https://www.hydroshare.org/resource/705d69c0f77c48538d83cf383f8c63d6/)
- **CAMELS-US，区域化参考候选**：正式数据说明已核对DOI10.5194/hess-21-5293-2017；不能由其流域数推断嵌套站点对。此次未核验其逐站拓扑及仓库许可，故不作为已确认拓扑样本或已授权完整下载来源。

本轮公开数据访问为论文、仓库目录与许可说明，没有下载流量归档。原始测站观测、资料编整后的观测产品、模拟输出和项目训练张量在以上条目中分别列明；哈希只证明文件一致性，不证明科学真实性或许可。
