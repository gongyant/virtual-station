# 原主站中的组件与路由映射

沿用原 `host/static/index.html` 的品牌、五项一级导航、`#view`/`#side`、页面路由、卡片、表格和状态管理。没有 iframe、R1 首页复制或第二套站点选择状态。

- 研究概览 `#/overview?dataset=LAMAH_CE_PUBLIC_V1`：原概览位置显示公开成果概况和所选站点曲线。
- 模型层 `#/model?...`：54个V2保存模型及站点、版本、训练截止、参数哈希；动态执行仍走原403门禁。
- 结果层 `#/results?...`：V1/V2/人工遮蔽曲线，选定站点原V1评分与逐年结果。日期范围仅过滤曲线，不把整期评分冒称筛选期评分。
- 模型评价 `#/results/evaluation?...`：27行对照，25站有真实V1评分，611/688为N/A。
- 空间层 `#/layers?...` 或原结果层空间子页：官方EPSG:3035站点点图、V1误差/区间诊断、选定类别和月份的Qsim。点位纵横采用相同投影比例；无河段值。
- 科研报告 `#/results/report?...`：原结果层报告子页展示P4/P5报告、模型卡和许可署名。
- 数据层 `#/data?...`：三种结果来源的精确快照和发布身份。

`static/view_public_results.js` 是原 `VHS.views` 的数据集分派扩展。SYRDARYA与旧LAMAHCE仍使用原视图；候选未挂载教师源时显示明确说明。站点、模型、类别、起止月、地图模式和报告ID由同一个 `VHS.state` 与hash路由控制。

`r2_public.py` 导入冻结R1 `PublicResultsBridge` 与 `V06PublicResultsHook`。本地候选只读接口为 `/api/v6/candidate-public/catalog` 及 `/results/{station,evaluation,spatial,report}`；必须显式带 `--candidate-public-preview`，不是生产授权。正式 `/api/v6/public/*` 继续由无审批回调的原hook返回403。旧 `/api/v6/*`、`/api/vhs/*` 不由公开适配器接管。

身份为 dataset + exact snapshot + model release + station + model + prediction kind + year/month。V1评价只接受V1快照，V2应用不能送入独立评价入口。数据集切换立即清除缓存、曲线、侧栏和地图，异步响应按token和dataset双重检查后才缓存和渲染。
