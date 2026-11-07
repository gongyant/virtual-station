# P6新数据准入与身份核查

本轮日期：2026-11-02（Asia/Singapore）。协议在新模型评分前冻结，哈希 `21ac3b087c19f57c4a4a575e10d84f0a0aae0273c5eec4d0328584e028ea7740`。没有重新训练或修改alpha。

三站的原始LamaH-CE ERA5-Land文件均已存在，并逐日覆盖至2019-12-31。按原P4代码同样规则得到2018–2019每站24个完整月：prec以日值mm累计、2m_temp_mean以°C日均值取月均；每月必须有完整且唯一的日历日。2017-12聚合与原P4月表逐值相同，L1取真实前一自然月。未使用E-OBS，未下载11.3GB气象包，未取得同处理口径2020气象，因此2020不评分。

## 已取得的真实Q与身份

- ID818：瑞士FOEN/BAFU官方2304站，Ova dal Fuorn / Zernez-Punt la Drossa；通过CAMELS-CH v0.9正式发布的observation_based文件取得实测discharge_vol(m3/s)，没有读取simulation_based模型Q。文件覆盖1981–2020，2018/2019/2020分别有365/365/366个日记录。集水面积55.3km²一致。CAMELS/EStreams两位小数坐标导致542.4米表观差异；FOEN原始EPSG:2056坐标2810564/1170779转WGS84后与LamaH点相距12.22米，支持同一站点身份。未获得历史迁站事件记录，不能声称整个历史从未迁站。
- ID611：德国Dillingen / Donau，官方10035801，EStreams DEBY0480；站码、11378.7km²面积一致，坐标差3.92米。已取得EStreams月均Q索引，官方已检查日均Q下载未成功（实际网络/DNS失败记录已保留）。月索引没有逐月有效日数，不能伪装成完整日均资料。
- ID688：德国Stegen / Amper，官方16602303，EStreams DEBY0802；站码、993.4km²面积一致，坐标差4.63米。EStreams名称写成Landsberg am Lech，与官方Stegen不一致；官方HND/GKD主站记录、站码和坐标支持这是区县名称混入，而非仅凭名称判定。官方Q任务已提交，但未获得文件，后续实际页面出现Request Rejected；未绕过该拒绝。月索引同样缺有效日数和逐日QC。

EStreams月索引文件的实际非空覆盖与目录并不相同：818在2018–2020有36个月；611/688分别只有2/2个月，而不是目录终止日期所暗示的连续覆盖。精确月份见P6_ESTREAMS_MONTHLY_AVAILABILITY.csv。原始月索引成员已通过ZIP CRC32核验并记录SHA256。仅定向下载约57.9MB压缩成员，没有下载2.3GB整个索引包。它们没有进入本轮主评分；不要把“下载到了月索引”误写成“完成严格Q准入”。

## 质量分层与许可

CAMELS-CH正式发布没有逐日checked/suspect标志；本轮仅在完整日历月、数值有限非负的条件下，按预冻结协议允许**有质量限制的描述性P6验证**。它不等价于旧LamaH ckhs=1，不是业务认证，也不是QC完全无疑的确认性测试。FOEN站页的当前冬季结冰警告只支持需要核查历史QC这一风险，不能断言2018/2019误差由结冰导致。

CAMELS-CH 15025258/v0.9 API声明CC BY 4.0（原始来源FOEN/BAFU）；EStreams 17598150/v1.4 API声明CC BY-NC 4.0，其气象为E-OBS，本轮没有使用；原LamaH-CE和ERA5-Land继续沿用冻结来源与署名记录。不同许可没有互相覆盖，新增源文件不经网页批量导出。

官方依据：[CAMELS-CH发布](https://zenodo.org/records/15025258)、[EStreams v1.4](https://zenodo.org/records/17598150)、[FOEN2304](https://www.hydrodaten.admin.ch/de/seen-und-fluesse/stationen-und-daten/2304)、[官方Stegen站](https://www.hnd.bayern.de/pegel/isar/stegen-16602303/stammdaten)。精确文件/字节范围/CRC/SHA256在external的下载回执与目录记录中。整个大归档MD5未通过局部下载重新验证，不能声称验证了完整归档。
