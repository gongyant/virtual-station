# VHS-NEXT-B0｜文献定位矩阵

核查日：2026-10-11。小范围定向核查，不是系统综述；正式标题/DOI由出版社页面与Crossref元数据交叉核对。9条Crossref JSON在 `../evidence/crossref_records.json`；2024会议论文及2026论文由官方出版页核验。文献题名中的性能判断是原作者题名，不是本项目结论。没有使用第三方摘要推导未核实实验细节。

## 已有工作、支持范围与本项目增量

1. **PUB定位** — Sivapalan et al. (2003), *IAHS Decade on Predictions in Ungauged Basins (PUB), 2003–2012: Shaping an exciting future for the hydrological sciences*. DOI [10.1623/hysj.48.6.857.51421](https://doi.org/10.1623/hysj.48.6.857.51421)。来源：Hydrological Sciences Journal，Crossref正式元数据；出版社抓取403，未假称阅读全文。支持：无资料流域预测已有长期研究议程。不能支持：我们的C1优于C2。增量定位：具体信息条件与完整系统外推证据，不声称首创水文信息迁移。

2. **Regionalization综述** — Guo, Zhang, Zhang & Wang (2021; online 2020), *Regionalization of hydrological modeling for predicting streamflow in ungauged catchments: A comprehensive review*. DOI [10.1002/wat2.1487](https://doi.org/10.1002/wat2.1487)。[正式来源](https://wires.onlinelibrary.wiley.com/doi/abs/10.1002/wat2.1487)。已有：相似性、回归和水文签名区域化研究。边界：目标Q派生签名不适用于本协议的目标无标签描述符。增量：仅训练域学习季节/气象基线，再区分连通Q与区域邻站Q信息。

3. **无资料连续预测** — Arsenault et al. (2023), *Continuous streamflow prediction in ungauged basins: long short-term memory neural networks clearly outperform traditional hydrological models*. DOI [10.5194/hess-27-139-2023](https://doi.org/10.5194/hess-27-139-2023)。[HESS](https://hess.copernicus.org/articles/27/139/2023/)。已有：148流域LOOCV区域化比较，共享学习可用于pseudo-ungauged站。边界：逐流域留一不自动保证完整河流系统隔离；不把其模型优势转为真实上游信息必有增益。增量：显式完整系统分组、严格目标隔离与C0/C1/C2同预算对照。

4. **水文图学习先例** — Sun, Jiang, Mudunuru & Chen (2021), *Explore Spatio-Temporal Learning of Large Sample Hydrology Using Graph Neural Networks*. DOI [10.1029/2021WR030394](https://doi.org/10.1029/2021WR030394)。[WRR](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2021WR030394)。已有：大样本水文的图时空学习与连接定义研究。本文存在不能证明本任务中真实上下游必优于区域相关邻站，也不能仅凭模型名认定严格无资料。协议细节未全面复刻，保留核查边界。增量：先做可审计信息对照，再考虑GNN。

5. **拓扑效用与负结果** — Kirschstein & Sun (2024), *The Merit of River Network Topology for Neural Flood Forecasting*. [ICML/PMLR 235:24713–24725正式出版页](https://proceedings.mlr.press/v235/kirschstein24a.html)。预印本DOI [10.48550/arXiv.2405.19836](https://doi.org/10.48550/arXiv.2405.19836)，此为仓库DOI，不伪装期刊DOI；正式PMLR页未列DOI。已有：比较邻接定义，报告其设置中河网拓扑未带来增益。边界：不等于所有图模型无效，也不是本任务的完整系统strict zero-shot证明；PDF抓取因content-type失败，未假称核实其中所有置换试验。增量：明确记录失败/负迁移比例，预设计matched C2与受限置换，拒绝预设GNN优势。

6. **最新路由先例** — Mosaffa et al. (2026), *A GNN routing module is all you need for LSTM Rainfall–Runoff models*. DOI [10.5194/hess-30-2079-2026](https://doi.org/10.5194/hess-30-2079-2026)。[HESS正式来源](https://hess.copernicus.org/articles/30/2079/2026/)。已有：LamaH-CE上多子流域的LSTM与GNN路由组合，报告其研究内改进。正文§2.2以气象/静态资料作输入、历史Q作学习标签；§2.3说明时间样本划分，§4明确没有专门检验完全无资料流域。边界：输入没有历史Q不等于目标标签从未参与学习；该研究内成功不能直接支持跨完整系统、目标完全无监督、matched不连通Q的比较。没有复核全部补充材料，不声称它完全没有其他控制。增量：研究信息预算和可迁移条件，不将LSTM+GNN+LamaH组合本身包装成创新。

7. **空间/层级验证** — Roberts et al. (2017), *Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure*. DOI [10.1111/ecog.02881](https://doi.org/10.1111/ecog.02881)。[Ecography](https://nsojournals.onlinelibrary.wiley.com/doi/10.1111/ecog.02881)。已有：随机CV可低估结构依赖数据预测误差，分块需与外推目标一致。边界：文章不直接给出本数据的缓冲距离或最少系统数。增量：完整系统为独立单位，层级区间、组大小敏感性与时间自相关处理，避免将日样本当重复。

8. **真实河网基础** — Lehner & Grill (2013), *Global river hydrography and network routing: baseline data and new approaches to study the world's large river systems*. DOI [10.1002/hyp.9740](https://doi.org/10.1002/hyp.9740)。来源：Hydrological Processes；[官方产品说明](https://www.hydrosheds.org/products/hydrorivers)。已有：可追踪的有向河网产品。边界：衍生河网不自动证明站点snap、正式身份和人工渠系。增量：保存路径证据并要求独立station-to-reach核对。

9. **嵌套数据候选** — Klingler, Schulz & Herrnegger (2021), *LamaH-CE: LArge-SaMple DAta for Hydrology and Environmental Sciences for Central Europe*. DOI [10.5194/essd-13-4529-2021](https://doi.org/10.5194/essd-13-4529-2021)。[ESSD](https://essd.copernicus.org/articles/13/4529/2021/)。已有：真实观测产品、河网层级和不同集水区划分。边界：丰富子流域不等于丰富完整独立系统；目标Q派生属性与已率定模型不能直接作无资料输入。增量：逐对准入和完整系统级计数，许可审查见独立报告。

10. **多区域备选** — Helgason & Nijssen (2024), *LamaH-Ice: LArge-SaMple DAta for Hydrology and Environmental Sciences for Iceland*. DOI [10.5194/essd-16-2741-2024](https://doi.org/10.5194/essd-16-2741-2024)。[ESSD](https://essd.copernicus.org/articles/16/2741/2024/)。已有：寒区水文大样本产品。边界：本轮未枚举真实嵌套对，v1.5的分项限制与旧论文版本不能混用。增量：可能补充独立水系和寒区失效条件，需先过元数据门槛。

11. **大样本不等于嵌套图** — Addor, Newman, Mizukami & Clark (2017), *The CAMELS data set: catchment attributes and meteorology for large-sample studies*. DOI [10.5194/hess-21-5293-2017](https://doi.org/10.5194/hess-21-5293-2017)。[HESS](https://hess.copernicus.org/articles/21/5293/2017/)。已有：区域化所需多类流域属性；包括streamflow属性。边界：不能因站点多而认定多对真实嵌套，Q派生属性要排除。增量：法律与来源允许时作为训练域背景候选，不当作已确认拓扑benchmark。

## 证据空缺与可检验贡献

- 水文信息迁移、区域化、河网GNN、路由和拓扑负结果都已有工作；不宣称“首次”。此次小样本文献核查也不足证明所有既有研究均缺少我们的对照。
- 本项目可以新增的证据组合：目标Q完全隔离、连通Q对matched不连通Q的公平信息控制、完整未见系统外推、描述符解释增益与失败、预声明负结果与层级不确定性。
- **负迁移**以预定Δ性能小于零操作性定义；不把一篇拓扑负结果扩展为整个领域的普遍规律。专门负迁移理论/完整系统置换检验文献本轮未完成穷尽核查，标记LIMITED；需要下一次小范围补查，不能虚构DOI。
- **网络置换**目前是本项目的预设计控制，不声称被上述论文逐项验证有效。若可交换性或独立系统数量不足，仅作诊断，不能生成因果证明。

本轮使用nature-academic-search的窄范围多源核查思路；学术专用检索接口不可用时用正式出版页、仓库与Crossref。可核实事实与拟议实验分开记录，未下载数据集或打开任何新目标站Q。
