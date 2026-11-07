# P2 冻结新增流域的外部验证

新18站在任何P2成绩之前冻结。ID清单、候选排除、逐日完整性、官方属性、河网路径和协议哈希见P2_NEW_BASINS_FROZEN.json。站点不是按分数筛选。

与原九站分开报告。每个站仍使用自己的其他年份Q训练；这不是无资料站/跨站零标签预测。共同支持完整，没有模型专属删月。

## 总体增量

- CONSECUTIVE_10Y P2-L1：均值/中位技能 7.35%/5.70%，改善18/18，逐年jackknife全正17/18。

- CONSECUTIVE_10Y P2-SNOW：均值/中位技能 4.45%/4.17%，改善15/18，逐年jackknife全正14/18。

- SPARSE_10Y_PUBLIC_SUBSAMPLING P2-L1：均值/中位技能 9.07%/7.04%，改善18/18，逐年jackknife全正18/18。

- SPARSE_10Y_PUBLIC_SUBSAMPLING P2-SNOW：均值/中位技能 -9.34%/4.96%，改善16/18，逐年jackknife全正15/18。

## 全部新站连续方案（顺序：C0+PT / P2-L1 / P2-SNOW）

- ID22 Mellau，Rhine/Rhine，面积227.613km²，高程1464m，frac_snow=0.30；NSE 0.56473 / 0.60129 / 0.60517；KGE 0.65790 / 0.67705 / 0.68258。

- ID10 Laterns，Rhine/Rhine，面积33.373km²，高程1471m，frac_snow=0.23；NSE 0.31657 / 0.35346 / 0.32860；KGE 0.44507 / 0.46861 / 0.45533。

- ID377 Leopoldschlag，Elbe/Vltava，面积94.116km²，高程831m，frac_snow=0.13；NSE 0.11003 / 0.13073 / 0.14856；KGE 0.17377 / 0.19841 / 0.22284。

- ID103 Kitzbuehel (Bahnhofsbruecke)，Danube/Inn above Salzach，面积153.221km²，高程1407m，frac_snow=0.30；NSE 0.57418 / 0.59971 / 0.60884；KGE 0.68827 / 0.70496 / 0.71484。

- ID142 Viehhofen，Danube/Salzach，面积150.925km²，高程1534m，frac_snow=0.29；NSE 0.59472 / 0.61022 / 0.63444；KGE 0.70979 / 0.72049 / 0.74094。

- ID270 Teichlbruecke，Danube/Enns，面积148.553km²，高程1038m，frac_snow=0.24；NSE 0.41406 / 0.45533 / 0.43705；KGE 0.52001 / 0.55121 / 0.53523。

- ID230 Gruenau，Danube/Traun，面积170.218km²，高程1010m，frac_snow=0.26；NSE 0.47353 / 0.56275 / 0.48031；KGE 0.54748 / 0.70740 / 0.59201。

- ID545 Mallnitz，Danube/Drava，面积85.852km²，高程2042m，frac_snow=0.39；NSE 0.74841 / 0.75529 / 0.77323；KGE 0.82767 / 0.83249 / 0.83933。

- ID480 Madling，Danube/Mur，面积86.463km²，高程1652m，frac_snow=0.28；NSE 0.45344 / 0.46470 / 0.50710；KGE 0.59601 / 0.60526 / 0.62902。

- ID512 Guendorf，Danube/Mur，面积205.320km²，高程491m，frac_snow=0.07；NSE 0.19042 / 0.25431 / 0.28475；KGE 0.22828 / 0.29475 / 0.42298。

- ID401 Schwarzau im Gebirge (Bundesstrasse)，Danube/Leitha，面积128.551km²，高程844m，frac_snow=0.17；NSE 0.16372 / 0.24329 / 0.22562；KGE 0.23209 / 0.30775 / 0.29053。

- ID383 Schwarzenau (Sued)，Danube/Morava，面积173.852km²，高程581m，frac_snow=0.10；NSE 0.09699 / 0.12542 / 0.13025；KGE 0.16103 / 0.19188 / 0.21703。

- ID428 Piringsdorf (Pfarrbruecke)，Danube/Rabnitz，面积118.604km²，高程561m，frac_snow=0.09；NSE 0.01643 / 0.07682 / -0.11222；KGE -0.01521 / 0.06978 / 0.09522。

- ID455 Neudorf bei Ilz，Danube/Raab，面积189.097km²，高程397m，frac_snow=0.07；NSE 0.08212 / 0.12963 / 0.11897；KGE 0.06637 / 0.13897 / 0.11266。

- ID171 Haging，Danube/Inn under Salzach，面积162.706km²，高程515m，frac_snow=0.08；NSE 0.47969 / 0.49535 / 0.47746；KGE 0.61503 / 0.64855 / 0.61287。

- ID343 Imbach，Danube/Danube between Enns and Morava，面积305.775km²，高程685m，frac_snow=0.11；NSE 0.06025 / 0.07198 / 0.06237；KGE 0.10797 / 0.12278 / 0.13128。

- ID185 Hartmannsdorf，Danube/Danube between Inn and Traun，面积138.094km²，高程758m，frac_snow=0.12；NSE 0.30242 / 0.38004 / 0.36427；KGE 0.40854 / 0.46600 / 0.45971。

- ID688 Stegen_Amper，Danube/Danube above Inn，面积1001.468km²，高程776m，frac_snow=0.12；NSE 0.17702 / 0.42611 / 0.17298；KGE 0.22482 / 0.44838 / 0.22947。

稀疏全部结果及逐年结果见reports/EXTERNAL_FROZEN_NEW。ID383稀疏SNOW失败必须保留：NSE−2.118442、MSE技能−270.21%；真实日历和Ridge数学核验通过，295.6训练SD的代理外推是可直接观察的失效证据，未更改样本/公式。

## 空间依赖和结论边界

宏观分布Rhine2/Elbe1/Danube15；官方路径中无新站嵌套，但共享多瑙河网络/气候并不独立。只有三个不平衡水系，水系bootstrap及删除水系结果仅描述性。两个时间方案不能视为36个独立流域。

L1提供了比原九站开发结果更有价值的外部重复证据，足以优先推进未评分时段验证；仍不宣布确认性普适改进。SNOW为站点/季节依赖且尾部不稳健，不能作为通用最终模型。

P2_REGION_SUMMARY.csv逐水系和官方区域列出均值/中位技能；P2_COHORT_SUMMARY.csv保存所有组权重、区间和敏感性口径。