/* VHS v0.6 -- results layer: station series, evaluation, spatial, report */
(function () {
  'use strict';
  var V = window.VHS;
  var SUB = [
    { key: 'index', label: '站点结果' },
    { key: 'evaluation', label: '模型评估' },
    { key: 'spatial', label: '空间结果' },
    { key: 'report', label: '科研报告' }
  ];
  function subnav(active) {
    return V.subnav('results', SUB, active || 'index');
  }

  function stationView(ctx) {
    var ds = V.state.dataset;
    var params = 'dataset=' + ds + (V.state.station ? '&station=' + encodeURIComponent(V.state.station) : '');
    return Promise.all([
      V.get('/api/v6/results/station?' + params),
      ds === 'SYRDARYA' ? V.get('/api/vhs/datasets/SYRDARYA/stations') : Promise.resolve({ stations: [] })
    ]).then(function (arr) {
      var d = arr[0], stl = arr[1];
      var sel = '';
      if (ds === 'SYRDARYA') {
        sel = '<div class="formgrid" style="margin-bottom:10px"><div class="field"><label>当前测站</label>' +
          V.stationSelect('resSt', stl.stations || [], d.station) + '</div></div>';
      }
      if (d.status === 'NO_AUTHORIZED_SERIES') {
        var html0 = subnav('index') + V.card({
          title: '站点结果 · ' + (d.station || ds),
          body: V.banner('warn', '无经授权的水文序列', V.esc(d.notice)) +
            '<div class="hr"></div>' + V.empty('没有 Qobs，也没有 Qsim。结果层不会生成占位曲线。') +
            '<div class="chips" style="margin-top:10px"><a class="btn" href="' + V.href('layers') +
            '">查看站点位置</a><a class="btn" href="' + V.href('data', 'history') + '">数据层</a></div>'
        });
        return { html: html0, side: sideResults(ds, d, null) };
      }
      var pts = d.observations || [];
      var chart = V.lineChart({
        points: pts, height: 400, yLabel: 'Q（单位 UNKNOWN）', xLabel: '时间（年-月）',
        markSuspect: true, bandStatus: 'NO_RECORD_YEAR', aria: '观测与模拟水文过程线'
      });
      var roleLabel = { CASE_REACH_DOWNSTREAM: '固定河段下游站 T', CASE_REACH_UPSTREAM: '固定河段上游站 U', OBSERVED_GAUGE: '观测站' }[d.role] || d.role;
      var kpis = '<div class="kpis">' +
        V.kpi('Qobs 有值月', d.qobs.n_defined, '实测记录') +
        V.kpi('缺测月', d.qobs.n_missing, '不插值') +
        V.kpi('序号嫌疑月', d.qobs.n_suspect, '保留原值、不绘制') +
        V.kpi('观测年份', (d.years || []).length, (d.years || []).join(','), 'na') +
        V.kpi('Qsim', '<span class="c-mut">null</span>', '未生成', 'na') +
        V.kpi('NSE / KGE', 'N/A', 'NOT_EVALUATED', 'na') +
        '</div>';
      var annualRows = (d.annual || []).map(function (a) {
        return [String(a.year), V.num(a.W_source, 1), V.num(a.W_from_Q, 1),
          a.rel_diff === null || a.rel_diff === undefined ? '—' : V.pct(a.rel_diff, 2),
          { html: V.spill(a.status) }];
      });
      var html = subnav('index') +
        V.card({ title: '当前研究任务', lead: '固定河段 16037 -> 16039 · 268 km（老师案例），与当前浏览测站分开',
          body: '<div class="grid2"><div>' + V.kv([
            ['研究区域', ds + ' · ' + (ds === 'SYRDARYA' ? '锡尔河下游' : 'LamaH-CE 欧洲河网')],
            ['固定研究河段', '16037 -> 16039（268 km）'],
            ['当前测站', d.station + ' ' + (d.name || '')],
            ['角色', roleLabel]
          ]) + '</div><div>' + V.kv([
            ['时间尺度', d.time_scale],
            ['单位', d.unit],
            ['单位状态', d.unit_status],
            ['快照', (d.snapshot || {}).snapshot_id || '—']
          ]) + '</div></div>' }) +
        V.card({ title: '观测与模拟水文过程线', lead: '第一屏优先展示过程线：Qobs 为真实观测；Qsim 与预测区间未生成',
          body: sel + '<div style="margin-top:4px">' + chart + '</div>' +
            '<div class="legend"><span><i style="border-color:#1f5fa8"></i>Qobs 实测月平均（源表原值）</span>' +
            '<span><i style="border-color:#b06a2c;border-top-style:dashed"></i>Qsim 模拟（未生成）</span>' +
            '<span><i style="border-color:#a83232;border-top-style:dashed"></i>红底 = 该年无记录</span>' +
            '<span><i style="border-color:#9a6400"></i>底部竖线 = 序号占位嫌疑</span></div>' +
            V.banner('bad', '模拟结果尚未生成', V.esc(d.notice)) +
            '<p class="notice">' + V.esc(d.qsim_status) + '；prediction_interval = null。' +
            '缺测月份留空，不补零、不插值。</p>' }) +
        V.card({ title: '观测摘要', body: kpis }) +
        V.card({ title: '年径流：源值与派生值并列', lead: '源值永不覆盖；W_from_Q 为 DERIVED',
          body: annualRows.length ? V.table(['年份', { label: 'W 源值', num: 1 }, { label: 'W_from_Q', num: 1 },
            { label: '相对差', num: 1 }, '状态'], annualRows) : V.empty('无年径流记录') }) +
        V.card({ title: '下一步', body: '<div class="chips">' +
          '<a class="btn" href="' + V.href('results', 'evaluation', { station: d.station }) + '">模型评估</a>' +
          '<a class="btn" href="' + V.href('results', 'spatial') + '">空间结果</a>' +
          '<a class="btn primary" href="' + V.href('results', 'report', { station: d.station }) + '">生成科研报告</a>' +
          '</div>' });

      return {
        html: html, side: sideResults(ds, d, null),
        mount: function (root) {
          if (ds === 'SYRDARYA') {
            V.onChange(root, 'resSt', function (v) {
              location.hash = V.href('results', 'station', { station: v });
            });
          }
        }
      };
    });
  }

  function sideResults(ds, d, extra) {
    return V.sideCards({
      dataset: { id: ds, title: ds === 'SYRDARYA' ? 'Syr Darya 锡尔河下游' : 'LamaH-CE 欧洲河网',
        crs: ds === 'SYRDARYA' ? 'GIS_PENDING' : 'EPSG:3035',
        authorization: ds === 'SYRDARYA' ? 'TEACHER_CSV_READ_ONLY' : 'OPEN_METADATA_ONLY' },
      snapshotId: (d.snapshot || {}).snapshot_id,
      permissions: d.permissions,
      links: [
        { href: V.href('results', 'evaluation'), label: '模型评估' },
        { href: V.href('results', 'report'), label: '科研报告' },
        { href: V.href('data', 'quality'), label: '质量证据' }
      ]
    }) + V.card({ title: '结果层口径', tight: true,
      body: V.kv([['Qobs', 'AUTHORIZED'], ['Qsim', 'null / NOT_GENERATED'],
        ['评估', 'NOT_EVALUATED'], ['空间预测', 'PREDICTION_LAYER_NOT_AVAILABLE']]) });
  }

  function evaluationView(ctx) {
    var ds = V.state.dataset;
    return V.get('/api/v6/results/evaluation?dataset=' + ds + (V.state.station ? '&station=' + encodeURIComponent(V.state.station) : ''))
      .then(function (d) {
        var metrics = d.metrics.map(function (m) {
          return '<div class="kpi na"><div class="k">' + V.esc(m.key) + '</div>' +
            '<div class="v">N/A</div><div class="s">' + V.spill(m.status) + ' · 单位 ' + V.esc(m.unit) + '</div></div>';
        }).join('');
        var prov = d.provenance_requirements;
        var html = subnav('evaluation') +
          V.card({ title: '模型评估', lead: '核心指标组件已就绪；当前无模型运行 → 全部 N/A',
            body: V.banner('bad', 'NOT_EVALUATED', V.esc(d.empty_state)) +
              '<div class="kpis" style="margin-top:12px">' + metrics + '</div>' +
              '<div class="kpis" style="margin-top:10px">' +
              V.kpi('评价样本数', 'N/A', '无共同样本', 'na') +
              V.kpi('评价区间', 'N/A', '未定义', 'na') +
              V.kpi('模型版本', 'N/A', '未训练', 'na') +
              '</div>' }) +
          V.card({ title: '指标必须携带的溯源信息', lead: '任何未来指标都必须同时给出以下四项，否则不得写入结果层',
            body: V.table(['字段', '当前值'], [
              ['model_version', V.esc(String(prov.model_version))],
              ['dataset_version', V.esc(prov.dataset_version)],
              ['period', V.esc(String(prov.period))],
              ['common_sample_ids', V.esc(String(prov.common_sample_ids))],
              ['snapshot_id', V.esc(prov.snapshot_id || '—')]
            ]) + '<p class="notice">' + V.esc(d.required_for_each_metric.join(' / ')) + '</p>' }) +
          V.card({ title: '后续可增加的评估视图（已规划，未实现）',
            body: V.ul(d.planned_views.map(function (x) { return V.esc(x); })) +
              '<p class="notice">这些视图需要真实观测-模拟配对样本，目前不存在。</p>' });
        return { html: html, side: sideResults(ds, d, null) };
      });
  }

  function spatialView(ctx) {
    var ds = V.state.dataset;
    return V.get('/api/v6/results/spatial?dataset=' + ds).then(function (d) {
      var planned = V.table(['空间结果图层', '状态', '前置条件'], d.planned_layers.map(function (l) {
        return [V.esc(l.title), { html: V.spill(l.status) }, V.esc(l.requires)];
      }));
      var html = subnav('spatial') +
        V.card({ title: '空间结果', lead: '统一接口已定义；真实模拟结果尚未产生',
          body: V.banner('bad', d.status_zh, V.esc(d.notice) +
            '<div style="margin-top:6px">状态码 <span class="mono-s">' + V.esc(d.status) + '</span></div>') +
            '<div style="margin-top:10px">' + planned + '</div>' }) +
        V.card({ title: '未来空间图层的字段契约',
          body: V.kv([['几何', d.contract.geometry], ['CRS', d.contract.crs],
            ['属性', d.contract.properties.join(', ')], ['禁止', d.contract.prohibited]]) }) +
        V.card({ title: '当前合法空间数据',
          body: (d.base_layers || []).length ?
            V.kv(d.base_layers.map(function (b) { return [b.title, b.note]; })) +
            '<div class="chips" style="margin-top:10px"><a class="btn" href="' + V.href('layers') + '">打开空间图层</a></div>' :
            V.empty('本数据集没有可用的空间图层（GIS_PENDING）。') });
      return { html: html, side: sideResults(ds, d, null) };
    });
  }

  function reportView(ctx) {
    var ds = V.state.dataset;
    var params = 'dataset=' + ds + (V.state.station ? '&station=' + encodeURIComponent(V.state.station) : '');
    return V.get('/api/v6/results/report?' + params).then(function (d) {
      var body = '<div class="chips" style="margin-bottom:10px">' +
        '<button class="btn" id="rptCopy">复制 Markdown</button>' +
        '<button class="btn" id="rptDl">下载 .md</button>' +
        '<span class="pill">executed: ' + V.esc(d.executed_sections.join(', ')) + '</span>' +
        '<span class="pill bad">not executed: ' + V.esc(d.not_executed_sections.join(', ')) + '</span></div>' +
        V.md(d.markdown);
      var html = subnav('report') +
        V.card({ title: '科研报告 · ' + (d.station || ''), lead: '仅包含已有真实观测与诊断；未运行部分逐项标记未执行',
          body: body });
      return {
        html: html, side: sideResults(ds, d, null),
        mount: function (root) {
          var cp = root.querySelector('#rptCopy');
          if (cp) cp.addEventListener('click', function () {
            if (navigator.clipboard) navigator.clipboard.writeText(d.markdown);
            cp.textContent = '已复制';
          });
          var dl = root.querySelector('#rptDl');
          if (dl) dl.addEventListener('click', function () {
            var blob = new Blob([d.markdown], { type: 'text/markdown;charset=utf-8' });
            var a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'VHS_v06_report_' + (d.station || ds).replace(':', '_') + '.md';
            document.body.appendChild(a);
            a.click();
            setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
          });
        }
      };
    });
  }

  V.views.results = async function (ctx) {
    if (!ctx.sub) return stationView(ctx);
    if (ctx.sub === 'evaluation') return evaluationView(ctx);
    if (ctx.sub === 'spatial') return spatialView(ctx);
    if (ctx.sub === 'report') return reportView(ctx);
    return stationView(ctx);
  };
})();
