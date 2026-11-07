# P6B数据准入实录

原27站逐一调查：24AUT、2DEU、1CHE。最初准入冻结表P6B_STATION_CROSSWALK.csv绑定不可变run；最终补充表P6B_STATION_CROSSWALK_FINAL.csv更新德国访问和2020驱动状态，原冻结表不改。

## 实际新增

24个奥地利站各取得官方eHYD日均Q文件及原站资料，2018、2019、2020年各12完整月，三年1096天/站。奥地利24站2020这些Q尚不评分，因未为它们恢复同口径气象；818的2020另见下文。2018–2019复用原快照全流域ERA5L日资料，576站月通过共同支持，1152预测已完成。

站点匹配使用HZB码、河名/站名、面积和BMN坐标。24站坐标差0.14–49.91m，未以名称相同直接匹配。初次实现误用了无假东距的GK CRS，导致全部拒绝；纠正为BEV定义BMN31257/58/59后重算，原失败记录保留，没有改变500m或5%面积阈值，也没有先看分数挑站。

## 质量

官方文件必须为Abfluss,I,Mit,T和[m³/s]，每日00:00全日数且无Lücke或重复。文件编号5已实查；编号3等为水位/极值，未作标签。数值Q仅在预测封存后进入评分。未自动延续“上一个有效日”跨缺档。

逐日QC列及UTC日界未获独立认证，所以主样本为描述性官方归档，非逐日质量认证。广义排除Q备注敏感性258个月，16站有值、11站>=12月；备注也包含人工影响背景，因此不得解释成完全等价的严格QC样本。见P6B_SOURCE_Q_FOOTNOTES.csv。

## 德国与瑞士

611=10035801 Dillingen/Donau，688=16602303 Stegen/Amper，沿用P6A官方坐标/面积证据；本轮再次真实请求。GKD自定义三年请求返回“需要有效邮箱”，未发邮件；官方完整归档选项两个站均Request Rejected，收到即停止。最新服务错误见external/GKD_NEW_ATTEMPTS_*.json。未用EStreams2018-01/2020-02零散月拼成连续Q。

818=FOEN2304，原27站中唯一瑞士站。CAMELS-CH observation_based日Q与P6A保持同源；2020有366天已取得，未当作simulation_based。2018–2019已在P6A评分，本轮不重复计入新增；2020经四格点原小时链60月验收后，新增12月、24预测，独立run已评分。

## 来源/许可

- 官方eHYD https://ehyd.gv.at/ ：现行网站Impressum注明非商业用途可在署名且无特别限制时转载，不是CC-BY通用商业再发布许可；本地科研处理保留BMLUK/Hydrographischer Dienst署名，不发布原始Qobs批量数据。官网JS原文、来源URL和SHA已保留。
- 官方年鉴 https://wasser.gv.at/hydjb/ ：公开年鉴和多年CSV访问路径；没有代替本人发送资料申请。
- CAMELS-CH v0.9 https://zenodo.org/records/15025258 ：原P6A记录与测站2304实测文件哈希继续有效，未再次下载或替换。
- ECMWF CDS ERA5-Land https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land ：真实凭据获取，私钥/令牌未复制到交付。具体输入和任务身份见driver下请求/结果记录。

FINAL表德国完整月数null表示未知未取得；原冻结表0仅为当次取得并核实完整月计数，不表示官方不存在记录。
