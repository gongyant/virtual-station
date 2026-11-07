# 精确发布差异

基线：E:\VHS_WorkBuddy_S1T_Sandbox\output\sprint_w2_vhs_query_app\v0.6_four_layer_platform

候选：E:\VHS_Public_Baseline_Lab\vhs_web_r2_host_integration\host

修改的原文件（仅候选副本）：

- `run_vhs.ps1`
- `server.py`
- `static/app.js`
- `static/index.html`
- `static/styles.css`
- `stop_vhs.ps1`

新增主站文件：

- `r2_public.py`
- `static/view_public_results.js`


原始视图、平台API、教师适配器、旧权限策略均没有改写。server只增加公开模块分派与候选安全启动、教师源不挂载处理；app只扩展公开选择状态和缓存隔离；index增加第三数据集按钮与模块脚本；CSS仅加模块布局。原启动/停止脚本在候选中改为安全8792包装。

冻结R1为只读外部依赖，未复制其首页或启动8791。P4/P5代码与参数不变。补丁详见 evidence/HOST_SOURCE_DIFF.patch。

正式部署步骤：先完成R2_PRODUCTION_PERMISSION_REQUIREMENTS.md中的实际审批与生产目录确认；在独立正式版本中使用真实受信任display回调和正式API前缀，禁用候选命名空间；执行相同来源、身份与UI验收；最后由实际负责人切换正式发布指针。当前没有替生产填写回调或启动8775。
