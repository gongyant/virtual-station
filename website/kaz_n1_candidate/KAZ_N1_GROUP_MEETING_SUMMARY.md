# KAZ-N1组会核心结论

截至2026年11月3日核验的Kazhydromet官方页面，现行网络列示442个水文监测点，其中河流394、湖泊38、海洋7测点加3站；这不是394条已取得的Q训练序列，也不是2024年的377站口径。

本轮真实GIS生成1230个部分覆盖的几何初筛点，但通过完整现行站点去重及正式选址准入的候选为0个，可预测和研究准入虚拟站均为0个，全国潜在可选总量仍尚无法评估。

哈萨克斯坦无资料站NSE/KGE尚未验证；本轮欧洲24站PUB开发实验，在1983–2013供体训练、2014–2017目标站遮蔽评价下，最近邻迁移的留一站中位NSE=0.216、KGE=0.415（15/24站NSE>0），整片水系区域遮蔽则为NSE=-0.512、KGE=0.152，不能称为哈萨克斯坦精度或全新盲测。

按固定面积2,724,900 km²，全国全部监测点密度为0.000162207787个/km²（1.622077874个/万km²），河流基线为0.000144592462个/km²（1.445924621个/万km²）；本轮正式候选、可预测及研究准入增量均为0，因此对应实际等效河流密度仍为0.000144592462个/km²，没有已证实的监测密度提升。

## 真正完成的工作
官方页面与固定面积核验；既有GIS逐文件读取与哈希；新获取NaturalEarth国界；真实流向、25km距离/最小面积/重复点/边界缓冲筛选；1230个真实但未准入几何点。亚洲L12覆盖示意国界48.59%，不能称全国河网齐备。
欧洲PUB真实完成126次回归拟合、48个供体季节基线估计、9216条预测。24站每方案1152个唯一评价站月；两种遮蔽方案不当作48个独立流域。目标Q所有日期从该目标任务的训练/模板/标准化中移除，目标MET的早期气候态可使用，无目标Q；供体只用<=2013Q，评分2014–2017Q后连接。预测角色96次拒绝测试通过。

## 全部方法结果（不挑选高分）
- LEAVE_MACRO_REGION_OUT / DONOR_CLIMATOLOGY_BASELINE：中位NSE -1.669，中位KGE -0.057，NSE>0站数6/24，站点等权MSE技能+0.00%。
- LEAVE_MACRO_REGION_OUT / GEOGRAPHIC_DONOR_TRANSFER：中位NSE -0.512，中位KGE 0.152，NSE>0站数9/24，站点等权MSE技能+6.57%。
- LEAVE_MACRO_REGION_OUT / REGIONAL_SHARED_RIDGE：中位NSE -10.849，中位KGE -1.650，NSE>0站数1/24，站点等权MSE技能-380.03%。
- LEAVE_MACRO_REGION_OUT / STATIC_CLIMATE_SIMILARITY_TRANSFER：中位NSE -0.449，中位KGE 0.202，NSE>0站数7/24，站点等权MSE技能-20.07%。
- LEAVE_ONE_GAUGE_OUT_REMOVE_NESTED_DONORS / DONOR_CLIMATOLOGY_BASELINE：中位NSE -0.545，中位KGE 0.091，NSE>0站数7/24，站点等权MSE技能+0.00%。
- LEAVE_ONE_GAUGE_OUT_REMOVE_NESTED_DONORS / GEOGRAPHIC_DONOR_TRANSFER：中位NSE 0.216，中位KGE 0.415，NSE>0站数15/24，站点等权MSE技能+29.88%。
- LEAVE_ONE_GAUGE_OUT_REMOVE_NESTED_DONORS / REGIONAL_SHARED_RIDGE：中位NSE -0.780，中位KGE 0.203，NSE>0站数10/24，站点等权MSE技能-2.73%。
- LEAVE_ONE_GAUGE_OUT_REMOVE_NESTED_DONORS / STATIC_CLIMATE_SIMILARITY_TRANSFER：中位NSE 0.138，中位KGE 0.411，NSE>0站数15/24，站点等权MSE技能+22.19%。

区域共享模型出现严重负结果，水系区域遮蔽整体明显退化；没有依据这些分数重调alpha、换模型、删站。NSE/KGE不能换成笼统“准确率百分比”。对目标独立站点校准的P7-MEM属于A；本轮移除站点标签属于B但仍是已暴露历史时期开发；真正新位置C目前无哈萨克斯坦实测验证。

## 下一步最小数据需求
优先取得可核对ID/坐标/启停日期的现行394河流监测点目录及合法展示范围；补齐全国HydroRIVERS/HydroBASINS瓦片与官方八大流域边界；获取小规模经许可、带单位/QC/日期口径的哈萨克斯坦Q及同质驱动，再冻结未用于设计的站点/时期开展本国PUB。不是先扩大模型数量。
