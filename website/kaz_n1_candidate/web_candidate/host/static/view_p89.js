/* P8–P9C sealed research evidence views — readonly, no live fitting. */
'use strict';
(function () {
  var V = window.VHS;
  if (!V || !V.views) return;
  var API = '/api/v6/p89/';

  function get(leaf) {
    return V.get(API + leaf);
  }

  function n(x, d) {
    if (x === null || x === undefined || x === '') return 'N/A';
    var v = Number(x);
    if (!isFinite(v)) return String(x);
    return v.toFixed(d == null ? 3 : d);
  }

  function banner() {
    return V.card({
      title: '口径声明（必读）',
      tight: true,
      body: V.kv([
        ['展示性质', '已封存科研结果只读展示'],
        ['不是什么', '未来水位/流量预报；正式哈国无资料站PUB；认证新增VHS'],
        ['正式已验证新增VHS', '0'],
        ['欧洲P6/P7成绩', '≠ 哈萨克斯坦精度'],
        ['在线拟合/预测', '403 NOT_AUTHORIZED']
      ])
    });
  }

  V.views.p8 = function () {
    return get('p8').then(function (d) {
      var rows = (d.basins || []).map(function (r) {
        return [V.e(r.basin_name || r.scope), n(r.all_orders_km, 3), n(r.class1_km, 1), n(r.class2_km, 1), n(r.class3_km, 1)];
      });
      var html = banner();
      html += V.card({
        title: 'P8 全国河网统计',
        lead: 'HydroRIVERS国家裁剪；八管理流域；ORD_CLAS / ORD_STRA 分别统计。总长以封存状态为准。',
        body: V.kv([
          ['全国河段数', d.national_reaches],
          ['全国总长 km', n(d.national_length_km, 3)],
          ['期望核对值', '659769.848 km'],
          ['未分配残差 km', n(d.unassigned_length_km, 3)],
          ['QazSu坐标记录', (d.gauge_catalog && d.gauge_catalog.QazSu_valid_coordinate_records) || 'N/A'],
          ['临时几何匹配', (d.gauge_catalog && d.gauge_catalog.geometric_500m_provisional_matches) || 'N/A']
        ])
      });
      html += V.card({
        title: '八流域 / 国家口径长度',
        body: V.table(['范围/流域', '总长km', '1级', '2级', '3级'], rows)
      });
      html += V.card({ title: '等级字段说明', body: '<p>' + V.e(d.ORD_CLAS_ORD_STRA_note_zh || '') + '</p>' });
      return html;
    });
  };

  V.views.p9a = function () {
    return get('p9a').then(function (d) {
      var html = banner();
      html += V.card({
        title: 'P9A 站点链长与候选筛查',
        lead: V.e(d.not_certified_note_zh || ''),
        body: V.kv([
          ['QazSu目录', d.QazSu_records],
          ['临时吸附站', d.provisional_gauges],
          ['几何拓扑合格候选', d.topology_geometry_qualified],
          ['身份认证官方站', d.official_gauges_identity_certified],
          ['首流域试点', d.pilot_basin_name],
          ['期望核对', '334 / 237 / 519']
        ])
      });
      var orows = (d.order_1_to_7 || []).map(function (r) {
        return Object.keys(r).slice(0, 6).map(function (k) { return V.e(r[k]); });
      });
      if (orows.length) {
        var oh = Object.keys(d.order_1_to_7[0] || {}).slice(0, 6);
        html += V.card({ title: '河网1–7级摘要', body: V.table(oh, orows) });
      }
      return html;
    });
  };

  V.views.p9b = function () {
    return get('p9b').then(function (d) {
      var html = banner();
      html += V.card({
        title: 'P9B 巴尔喀什—阿拉湖工程候选',
        lead: '20主链 + 10支流工程候选；出口代理与冲突标志见源表。正式VHS仍为0。',
        body: V.kv([
          ['流域', d.basin],
          ['主链工程候选', d.original_engineering_candidates],
          ['支流交替候选', d.alternate_engineering_candidates],
          ['出口代理记录', d.outlet_proxy_records],
          ['正式VHS', d.formal_VHS],
          ['P10', d.P10_status],
          ['期望核对', '20 + 10 = 30']
        ])
      });
      var arows = (d.alternate_sample || []).slice(0, 12).map(function (r) {
        var keys = Object.keys(r).slice(0, 5);
        return keys.map(function (k) { return V.e(r[k]); });
      });
      if (arows.length) {
        html += V.card({
          title: '候选表示例（截断）',
          body: V.table(Object.keys(d.alternate_sample[0] || {}).slice(0, 5), arows)
        });
      }
      return html;
    });
  };

  V.views.p9c = function () {
    return get('p9c').then(function (d) {
      var html = banner();
      html += V.card({
        title: 'P9C 修正后有效结果（E2）',
        lead: V.e(d.estimand_zh || ''),
        body: V.kv([
          ['目标站数(WB)', d.new_WB_target_stations],
          ['完整站月', d.numeric_complete_station_months],
          ['C0 NSE / KGE', n(d.E2_C0_NSE, 6) + ' / ' + n(d.E2_C0_KGE, 6)],
          ['C0+PT NSE / KGE', n(d.E2_C0PT_NSE, 6) + ' / ' + n(d.E2_C0PT_KGE, 6)],
          ['C0+PT MSE技能', n(d.E2_C0PT_MSE_skill, 6) + '（约 -1.053%）'],
          ['Tauturgen', V.e(d.Tauturgen_note_zh || '')],
          ['期望核对', '4站 / 705站月；C0 NSE 0.695836']
        ])
      });
      var mrows = (d.metrics || []).filter(function (r) {
        return String(r.variant || '') === 'RAW';
      }).map(function (r) {
        return [V.e(r.model_id), V.e(r.year), V.e(r.n), n(r.NSE, 6), n(r.KGE, 6), n(r.MSE_skill_vs_C0, 6)];
      });
      html += V.card({
        title: '时间验证指标（RAW）',
        body: V.table(['模型', '年', 'n', 'NSE', 'KGE', 'MSE_skill'], mrows)
      });
      html += V.card({
        title: '已撤回错误结果',
        body: '<p>作废口径（655站月/40站年/120预测等）已撤回；详见 <code>#/withdrawn</code>。rejected_schema_predictions=' +
          V.e(d.rejected_schema_predictions) + '</p>'
      });
      return html;
    });
  };

  V.views.withdrawn = function () {
    return get('withdrawn').then(function (d) {
      return banner() + V.card({
        title: d.title_zh || '已撤回',
        body: '<p><strong>状态：' + V.e(d.status) + '</strong></p><p>' + V.e(d.body_zh || '') + '</p><p>目录：' + V.e(d.location || '') + '</p>'
      });
    });
  };
})();
