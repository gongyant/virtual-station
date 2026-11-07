# DeepBas-VHS-GT Lite

面向新疆—哈萨克斯坦跨境流域的虚拟水文站最小可运行工程。项目主线是：

1. 将水文站吸附到 HydroRIVERS 河网；
2. 用 `HYRIV_ID -> NEXT_DOWN` 建立有向站点图；
3. 对齐实测流量、ERA5-Land 和 WaterGAP 2.2e；
4. 使用轻量有向时空 GNN 重建整站缺测流量；
5. 按时间外推与整站留出评估 NSE、KGE、RMSE、MAE 和 PBIAS。

当前版本不包含强化学习。大山口等水库下泄站通过 `reservoir_flag` 标记；严格水量平衡损失暂不施加，只预留后续软约束扩展位置。

## 为什么普通电脑能运行

默认模型只有一个 GRU、两层有向图消息传递和一个小型解码器，不依赖 PyTorch Geometric。几十个站点、日尺度、30 天历史窗口通常只有几十万参数。CPU 可以跑演示；RTX 3050/4070 足以训练真实站点级模型。空间数据预处理通常比模型训练更耗时。

## 目录

```text
virtual_hydro_station/
├── configs/
│   ├── demo.yaml
│   └── real_data.example.yaml
├── data/
│   ├── raw/                 # 用户原始文件，不提交
│   └── processed/           # 标准化 CSV/NPZ
├── scripts/
│   ├── inspect_inputs.py    # 检查 Excel/KMZ/NetCDF 字段
│   ├── prepare_graph.py     # KMZ + HydroRIVERS + HydroBASINS -> 图
│   ├── prepare_timeseries.py# Excel + NetCDF -> 标准长表
│   └── run_demo.py          # 一键合成数据训练
├── src/vhs/
│   ├── data.py
│   ├── graph.py
│   ├── io.py
│   ├── metrics.py
│   ├── model.py
│   ├── synthetic.py
│   └── train.py
└── tests/
```

## 安装

建议在 WSL/Ubuntu 中建立单独环境：

```bash
conda create -n virtual-hydro python=3.11 -y
conda activate virtual-hydro

# 先按你的 CUDA 版本安装 PyTorch；CPU 也可以
pip install torch
pip install -e .
```

空间预处理需要额外依赖：

```bash
pip install -e ".[geo]"
```

安装后先检查电脑和显卡是否被正确识别：

```bash
python scripts/check_environment.py
```

若是 RTX 3050，先用 `batch_size: 8` 或 `16`；RTX 4070/4080 可从 `32` 开始。这个项目不要求高端显卡，模型内存主要由“站点数 × 历史窗口 × batch size”决定。

## 先跑通演示

```bash
python scripts/run_demo.py --config configs/demo.yaml
```

演示会自动生成一个 8 节点有向河网，将 `S05` 整站流量全部从输入和训练标签中遮蔽，再利用上游站、气象和 WaterGAP 先验重建它。输出位于 `outputs/demo/`。

## 真实数据应放在哪里

将数据解压或复制到 `data/raw/`，推荐结构：

```text
data/raw/
├── stations/
│   ├── 新疆基本水文站.kmz
│   └── 前苏联水文站点.kmz
├── runoff/
│   ├── Q-新疆.xls
│   ├── Q-dsk-byblk.xlsx
│   └── BYBLK-DSK日数据.xlsx
├── hydrorivers/HydroRIVERS_v10_as.shp  # 同目录保留 dbf/shx/prj
├── hydrobasins/hybas_as_lev12_v1c.shp
├── watergap/*.nc
├── era5_land/*.nc
└── static/                              # DEM、土地利用、土壤（后续）
```

不要直接让程序读取整个亚洲压缩包反复训练。第一次预处理时先用研究区包围盒裁剪河网，生成 `nodes.csv` 与 `edges.csv`，训练阶段只读取小型处理结果。

## 第一步：检查真实文件

```bash
python scripts/inspect_inputs.py data/raw/runoff/Q-新疆.xls
python scripts/inspect_inputs.py data/raw/stations/新疆基本水文站.kmz
python scripts/inspect_inputs.py data/raw/watergap/某个文件.nc
```

它会输出：

- Excel 工作表名、行列数、表头和前几行；
- KMZ 站名、坐标和属性字段；
- NetCDF 变量名、维度、时间范围、经纬度名称和单位。

## 第二步：构建有向站点图

修改 `configs/real_data.example.yaml` 中的路径与研究区包围盒，然后运行：

```bash
python scripts/prepare_graph.py --config configs/real_data.example.yaml
```

输出：

- `data/processed/nodes.csv`：站点、经纬度、吸附河段、子流域、静态属性；
- `data/processed/edges.csv`：上游站、下游站、累计河长等；
- `data/processed/station_river_matches.csv`：站点吸附质检表。

必须人工检查大山口、巴音布鲁克等关键站点。不能只按几何最近河流匹配，还要核对 `UPLAND_SKM` 与站点集水面积。

## 第三步：标准化时间序列

真实数据统一为一张长表：

```text
date,station_id,obs_q,wg_dis,wg_qtot,wg_qg,era5_tp,era5_t2m,...
2001-01-01,S001,35.2,31.7,0.00012,0.00003,1.6,268.1,...
```

运行：

```bash
python scripts/prepare_timeseries.py --config configs/real_data.example.yaml
```

由于老师的三个 Excel 表头尚未在当前环境成功读取，需要在配置中的 `flow_sources` 明确指定：

- `sheet`：工作表；
- `date_column`：日期列；
- `station_column`：站点列（长表时）；
- `value_column`：流量列；
- `wide_station_columns`：宽表中“列名 -> station_id”的映射。

WaterGAP 的使用原则：

- `dis`：取站点/子流域出口所在网格，不能对整个上游流域求和；
- `qtot`、`qg`：局地产流，可按子流域面积加权；Lite 版本先提供最近网格提取；
- 优先 `obsclim_histsoc_default`；
- `1901soc`、`2015soc` 只做反事实对照，不作为主数据。

## 第四步：训练真实模型

准备好 `nodes.csv`、`edges.csv` 与 `timeseries.csv` 后：

```bash
python -m vhs.train --config configs/real_data.example.yaml
```

推荐的第一轮实验顺序：

1. LSTM/无图基线（将 `graph_layers: 0`）；
2. 有向时空 GNN；
3. 加 WaterGAP `dis` 偏差订正；
4. 整站留出；
5. 中国训练—哈萨克斯坦测试；
6. 最后再扩展 HydroBASINS 多尺度超图或异构图。

## 防止数据泄漏

- 按日期连续切分训练/验证/测试，不随机打乱全时段；
- 虚拟目标站的 `obs_q` 在所有输入窗口中都被遮蔽；
- 目标站标签不能进入训练损失；
- 标准化统计量只使用训练期；
- 如果偏差订正产品使用过目标站观测，不得把它作为该站独立测试输入。

## 现阶段限制

- `prepare_graph.py` 建的是站点级图，尚未实现完整 Level 7/9/10 嵌套超图；
- WaterGAP/ERA5 默认使用最近网格提取，论文正式实验应升级为子流域面积加权；
- 没有水库调度动作，不能识别真实放水策略；
- 圣维南方程所需断面、粗糙度和水位数据不足，本版本只预留软物理约束接口；
- 真实 Excel 的最终字段映射必须依据实际可读文件完成。

## 上下游物理情景库（质量守恒 + 能量守恒）

`vhs.hydraulics` 提供了一个不依赖神经网络的物理参考层。它把上游和下游
实测的水位、河宽、平均水深、断面面积逐一交叉穷举，并按以下条件求解每个
情景：

- 稳态连续方程：无区间来水和蓄变量资料时，先采用 `Q_up = Q_down`；
- 能量方程：共同高程基准下的水面落差等于 Manning 摩阻损失与流速水头变化；
- 只保留非负、能量残差闭合的解，同时输出流速、弗劳德数和坡度诊断；
- `HydraulicScenarioInterpolator` 只做情景域内的近邻插值，禁止域外外推。

用现有 2011 测流断面构建 BYBLK→DSK 诊断情景库：

```powershell
python scripts/build_hydraulic_scenario_library.py --allow-missing-dem
```

当前仓库的 `dem_reach_slopes_2011.csv` 明确记录为
`blocked_no_dem_raster`，并没有可用的 DEM 栅格坡降值。因此上面的命令必须
显式允许缺失 DEM，输出状态也会保持为诊断用途，不能直接作为流量标签。
DEM 沿河坡降真正落盘后，去掉 `--allow-missing-dem`，脚本才会把情景库标记为
物理参考候选。相对水位不能跨站直接相减；脚本使用已审计的黄海基面水位基准
将两站水位转换到共同高程系统。

当日尺度数据同时具备上下游水位、宽度和水深时，可用
`add_hydraulic_lookup_features` 增加 `hydraulic_reference_q_m3s`、上下游流速、
查表距离和可用性标志。现有训练器已经支持把该列配置为
`physics_reference_feature`；缺测或超出情景域的日期不会生成物理参考量。

### 2011物理增量诊断

阶段D9保持D4B冻结K10不变，用1月11日至5月10日拟合物理残差，并在原固定
主窗口（5月11日至8月31日）评分：

```powershell
python scripts/run_stage_d9_physics_increment.py
```

固定 `n=0.04` 的物理残差未通过增量门槛。阶段D9B在结果揭示后另开根因分析，
只用开发窗比较预列出的糙率与边坡组合：

```powershell
python scripts/run_stage_d9b_hydraulic_sensitivity.py
```

D9B选择 `n=0.02`、边坡系数1.0后，主窗口NSE从冻结K10的0.138提高到
0.309，RMSE改善10.44%；但糙率触及网格下界，且晚期窗口残差修正退化，因而
不得晋级为稳定物理参数或正式模型。该结果说明水力状态有增量信息，同时说明
当前“有效糙率”仍在吸收闸门控制、区间来水、断面变化和缺失DEM坡降。

水位单变量对照在主窗口达到很高分数，仅用于暴露2011日Q可能来自H-Q整编曲线
的标签循环风险，不得表述为独立恢复真实流量。

### D10上游日水位电子化与替代实验

巴音布鲁克逐日平均水位表可运行以下脚本生成365天第一轮视觉复核数据，并按
表底月均进行闭合：

```powershell
python scripts/prepare_stage_d10_byblk_stage.py
python scripts/run_stage_d10_observed_upstream_stage.py
```

11个月月均闭合；12月逐格重建均值为3.9919 m，原表打印4.00 m，差异保留且
需要第二位复核。D10冻结D9B全部参数，只把上游几何索引由Q代理替换成实测H；
该迁移未通过主窗口增量门槛，因此日水位数据只能用于诊断，不能据此晋级模型。

D10失败后的根因检查发现，全年共用一条水位—断面关系会混合冷季与开敞水期：
相近水位可能对应明显不同的断面面积。以下脚本沿用项目既有的4至10月开敞水期、
11至3月冷季划分，分别建立水位—断面查表关系；D9B的糙率、边坡和残差参数保持
冻结：

```powershell
python scripts/run_stage_d10b_regime_aware_geometry.py
```

D10B主窗口物理覆盖率为98.23%，冻结残差模型相对M0的NSE由0.138提高到0.336，
RMSE由45.57降至39.99 m³/s（改善12.24%）。但该实验是在D10结果揭示后发起，
且上游日水位仍待第二人复核，所以只支持“分状态断面关系值得独立验证”，不得
作为预注册主检验或正式模型晋级证据。

### D11断面关系整月留出验证

D11先冻结协议，再将巴音布鲁克每个有断面观测的月份整体留出，直接预测留出月
的断面面积、宽度和平均水深。它不读取日流量标签或D9B残差参数：

```powershell
python scripts/run_stage_d11_geometry_cross_validation.py
```

共同插值域内，分状态模型的面积MAE由9.62降至1.59 m²，RMSE由13.28降至
2.39 m²；宽度和平均水深误差也同步下降。但共同覆盖仅12/24（50%），低于冻结
的60%门槛，故D11正式判定为未通过，不能事后放宽门槛。域外样本主要来自整月
留出4月或5月后开敞水期极值范围缺失，说明下一步应增加独立断面状态的覆盖，
而不是允许无约束外推。

### D12A支持域与数据完整性审计

D12A不修改模型或D11门槛，只盘点BYBLK水位/断面资料并逐条解释域外记录：

```powershell
python scripts/run_stage_d12a_support_audit.py
```

全仓库审计后，没有额外资料同时满足测站ID、同断面映射、水尺基准、单位和河床
稳定性要求，因此可合法加入的辅助几何记录为0，coverage仍为12/24。2011年
9月21日H=3.85 m的大断面若未来完成垂直基准确认和完整几何复算，理论上可使
coverage达到16/24；在完成这些核验前必须保持排除。D12A明确停止于数据诊断，
不会自动启动D12B。

### D12A.1大断面基准与稳定性复核

D12A.1只核查2011年5月21日和9月21日巴音布鲁克大断面的测时水位、垂直
基准和断面身份，不修改D11或启动D12B：

```powershell
python scripts/run_stage_d12a1_verification.py
```

原始表证明9月21日3.85m为断面测时水位、3.87m为逐日平均水位；但没有直接
证明28个床面高程与水尺零点/黄海基面共用垂直基准，也没有充分的断面复占控制
资料。因此完整几何和河床变化计算保持blocked，9月断面不得进入训练池，D11
实际coverage仍为12/24。16/24仅是未来完成基准核验后的条件覆盖情景。

### RS-W0两站Landsat下载与可用性审计

RS-W0按BYBLK和DSK的2011年实测H/Q/A/W/D/V日期检索Landsat 5/7 Collection 2
Level-2，并只范围读取站点附近5 km窗口：

```powershell
$env:PYTHONPATH='.codex_tmp\rs_w0_env'
python scripts/run_stage_rs_w0_landsat_audit.py
```

脚本保存Blue/Green/Red/NIR/SWIR1/QA_PIXEL原始像元、STAC元数据、SHA-256和完成
标记，按同日、±1、±3、±5、±8天顺序匹配并执行目标点局部QA。RS-W0只形成数据
和可用性审计，不拟合河宽阈值或流量，不启动RS-W1。

## 严格留出基线与无图消融

DSK 严格整站留出实验必须与不使用 DSK 训练标签的简单基线比较：

```bash
python scripts/evaluate_strict_baselines.py
```

结果写入 `outputs/strict_baselines/`，同时提供日尺度和完整月尺度指标。基线包括
WaterGAP、上游站滞后一日流量、面积比例缩放以及仅在上游供体站拟合后迁移到 DSK
的岭回归。它们都只在评分阶段读取 DSK 实测值。

完成无图消融后，可将其加入同一张对照表：

```bash
python scripts/evaluate_strict_baselines.py \
  --extra-prediction nograph_gru=outputs/holdout_dsk_nograph/test_predictions.csv
```

无图 GRU 消融实验使用与有向 GNN 相同的数据、划分和训练参数：

```bash
python -m vhs.train --config configs/holdout_dsk_nograph.yaml
```

该实验用于判断河网消息传播是否真正优于纯时间模型。

WaterGAP 站点邻域诊断：

```bash
python scripts/diagnose_watergap_cells.py
```

脚本同时输出距离、流量量级、零值比例以及仅用于诊断的实测相关性。候选像元的
`mainstem_score` 不使用站点实测流量，避免利用目标标签挑选输入。

若要评估“拥有一段 DSK 历史记录”能够带来多大改善，可单独运行历史校准协议：

```bash
python scripts/evaluate_calibrated_residual.py
```

该结果会写入 `outputs/calibrated_residual/`。它使用了 DSK 训练期观测，只能作为
可达上限和误差来源诊断，不能与严格零样本虚拟站结果混为一谈。
