# 日界证据与限制

直接证据：24份eHYD file5归档表头定义日均Abfluss、m³/s、每日00:00日期，并说明区间值持续到下一时间戳或缺口；表头未列UTC偏移。P6B身份和来源归档只读复用。

本轮核查官方 https://wasser.gv.at/hydjb/index.xhtml （2026-11-02）：提供eHYD长期站点元数据与CSV入口、法定公开来源说明；未发现24份file5具体UTC日界认证。官方eHYD旧PDF https://ehyd.gv.at/assets/eHYD/pdf/Aktuelle_Daten.pdf 当前404，记录为失败来源；不能用搜索缓存冒充已取得证据。

官方MEZ/MEZ夏令时通用说明及其他参数的观测规则不能直接证明本批流量归档的时区。也不能借用瑞士BAFU说明认证奥地利eHYD。故保持PROVIDER_CALENDAR_DAY / UTC_NOT_CERTIFIED。

协议在评分前固定±1日敏感性：保持原预测，分别用每天标注日期-1/0/+1天的源Q求月均；仅为月边界鲁棒性诊断，既不等于精确±1小时时区换算，也不将得分最佳偏移替换主结果。源日序列没有小时变化，无法精确还原UTC月均。
