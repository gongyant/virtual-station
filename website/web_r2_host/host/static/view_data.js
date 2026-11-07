/* VHS v0.6 -- data layer: catalog, coverage matrix, station history, remote sensing, yearbook, literature, quality */
(function () {
  'use strict';
  var V = window.VHS;
  var SUB = [
    { key: 'index', label: '数据目录' },
    { key: 'history', label: '站点历史数据' },
    { key: 'remote', label: '遥感数据' },
    { key: 'yearbook', label: '统计年鉴' },
    { key: 'literature', label: '文献材料' },
    { key: 'quality', label: '质量与科研证据' }
  ];
  var S = '/api/vhs/datasets/SYRDARYA';

  function subnav(active) { return V.subnav('data', SUB, active || 'index'); }

  function coverageCard(cv) {
    if (!cv.available) {
      return V.card({ title: '时间覆盖矩阵', body: V.empty(V.esc(cv.reason)) });
    }
    var years = cv.years;
    function matrix(rows) {
      var h = '<div class="scrollx"><table class="matrix"><thead><tr><th class="rowlabel">序列</th>';
      years.forEach(function (y) { h += '<th>' + y.year + '</th>'; });
      h += '<th>说明</th></tr></thead><tbody>';
      rows.forEach(function (r) {
        h += '<tr><td class="rowlabel">' + V.esc(r.label) + (r.name ? ' <span class="muted tiny">' +
          V.esc(r.name) + '</span>' : '') + '</td>';
        r.cells.forEach(function (c) {
          var t = c.year + '：' + (c.present === undefined ? c.status : (c.present + '/' + c.total + ' 月 · ' + c.status));
          h += '<td><span class="cell c-' + V.esc(c.status) + '" title="' + V.esc(t) + '"></span></td>';
        });
        h += '<td class="tiny muted">' + V.esc(r.kind || '') + '</td></tr>';
      });
      return h + '</tbody></table></div>';
    }
    return V.card({
      title: '时间覆盖矩阵',
      lead: '哪些年份/月份有真实记录；空格不是零值。' + V.esc(cv.note_zh || ''),
      body: '<h4 style="margin:2px 0 6px">测站 × 年份（月平均 Q 的有效月份数 / 12）</h4>' +
        matrix(cv.station_rows) +
        '<div class="hr"></div><h4 style="margin:2px 0 6px">变量 × 年份</h4>' + matrix(cv.variable_rows) +
        '<div class="legend">' + Object.keys(cv.legend).map(function (k) {
          return '<span><i class="sw c-' + k + '" style="background:' + colorOf(k) + '"></i>' + V.esc(k + '：' + cv.legend[k]) + '</span>';
        }).join('') + '</div>' +
        '<p class="notice">气象：' + V.esc((cv.met_note || {}).range ? (cv.met_note.range[0] + ' ~ ' + cv.met_note.range[1]) : '') +
        '；缺测日 ' + V.esc((cv.met_note || {}).missing_days) + ' 天。矩阵共用年份列，但分母不同，不能合并成一个“完整率”。</p>'
    });
  }
  function colorOf(k) {
    return { OBSERVED: '#2f7d55', PARTIAL: '#c8a13a', SUSPECT: '#b06a2c', MISSING: '#c07373',
      NO_RECORD_YEAR: '#e4e9ef', OUT_OF_RANGE: '#e3e9f0' }[k] || '#eef2f7';
  }

  async function catalogView(ctx) {
    var ds = V.state.dataset;
    var cat = await V.get('/api/v6/data/catalog?dataset=' + ds);
    var cv = ds === 'SYRDARYA' ? await V.get('/api/v6/data/coverage?dataset=' + ds) : { available: false,
      reason: '该数据集仅开放元数据，无时间序列可做覆盖矩阵' };
    var mods = cat.modules.map(function (m) {
      var rec = m.records || {};
      var recTxt = Object.keys(rec).map(function (k) {
        var v = rec[k];
        if (Array.isArray(v)) v = v.join(', ');
        return k + '=' + v;
      }).join('；');
      return V.card({
        title: m.title,
        badge: V.spill(m.status),
        body: '<div class="kv"><dt>记录</dt><dd class="mono-s">' + V.esc(recTxt || '—') + '</dd>' +
          '<dt>原始 / 派生</dt><dd>' + V.esc((m.origin || '') + (m.derived && m.derived.length ? '；派生：' + m.derived.join('；') : '')) + '</dd>' +
          '<dt>缺测口径</dt><dd>' + V.esc(m.missing_policy) + '</dd></div>' +
          (m.kinds ? '<div class="chips" style="margin-top:8px">' + m.kinds.map(function (k) {
            return '<span class="pill">' + V.esc(k) + '</span>';
          }).join('') + '</div>' : '') +
          '<div style="margin-top:9px"><a class="btn small" href="' + m.href + '">打开模块</a></div>'
      });
    }).join('');
    var html = [
      V.card({ title: '数据层 · 可检索 / 可理解 / 可追溯', lead: '四个子模块共用同一套来源、快照与缺测口径。',
        body: V.banner('info', '数据边界', '历史观测只读展示已授权；模型输入、预测与批量导出均 NOT_AUTHORIZED。') }),
      '<div class="grid2">' + mods + '</div>',
      coverageCard(cv),
      V.card({ title: '质量与科研证据', lead: '完整 QC 错误列表、字段哈希与单位说明放在二级页面',
        body: '<p class="small muted">首页只给出状态与计数；' + V.esc((cat.quality_page || {}).title || '') + '</p>' +
          '<div class="chips" style="margin-top:8px"><a class="btn primary" href="' +
          V.href('data', 'quality') + '">打开数据质量与科研证据</a></div>' })
    ].join('');
    return { html: html, side: sideBase(ds, cat) };
  }

  function sideBase(ds, cat) {
    return V.sideCards({
      dataset: { id: ds, title: cat.dataset_info ? cat.dataset_info.title : (ds === 'SYRDARYA' ? 'Syr Darya 锡尔河下游' : 'LamaH-CE 欧洲河网'),
        crs: cat.dataset_info ? cat.dataset_info.crs : '', authorization: cat.dataset_info ? cat.dataset_info.authorization : '' },
      snapshotId: (cat.snapshot || {}).snapshot_id,
      permissions: cat.permissions,
      links: [
        { href: V.href('data', 'history'), label: '站点历史' },
        { href: V.href('data', 'remote'), label: '遥感' },
        { href: V.href('data', 'quality'), label: '质量证据' }
      ]
    });
  }

  async function stationsList() {
    var s = await V.get(S + '/stations');
    return s.stations || [];
  }

  async function historyView(ctx) {
    var ds = V.state.dataset;
    var tab = ctx.q.tab || 'flow';
    if (ds !== 'SYRDARYA') {
      return { html: V.card({ title: '站点历史数据 · LamaH-CE',
        body: '<div class="grid2">' + V.banner('warn', '仅开放元数据',
          'LamaH-CE 的径流序列位于 sealed_runoff，未授权读取；可用的是站点属性与审计状态。') +
          V.ul(['站点名称 / 编号 / 河段号 / 面积 / 观测起止',
            '审计状态与供数候选关系（图级暂定）', '无流量、无气象、无水量平衡序列']) +
          '<div class="chips" style="margin-top:10px">' +
          '<a class="btn" href="' + V.href('layers') + '">在空间图层中查看站点</a>' +
          '<a class="btn" href="' + V.href('data', 'quality') + '">质量与证据</a></div></div>' }),
        side: V.sideCards({ dataset: { id: ds, title: 'LamaH-CE 欧洲河网', crs: 'EPSG:3035', authorization: 'OPEN_METADATA_ONLY' },
          permissions: (await V.get('/api/v6/data/catalog?dataset=' + ds)).permissions }) };
    }
    var stations = await stationsList();
    var uid = V.state.station || 'SYRDARYA:16037';
    var st = null;
    stations.forEach(function (x) { if (x.uid === uid) st = x; });
    if (!st) st = stations[0], uid = st.uid;
    var years = st.years || [];
    var year = parseInt(ctx.q.year, 10) || years[years.length - 1];
    if (years.indexOf(year) < 0) year = years[years.length - 1];

    var tabs = '<div class="subnav" style="margin-bottom:10px">' +
      [['flow', '月流量 / 年径流'], ['met', '气象（降水/气温）'], ['wb', '水量平衡 α 情景']].map(function (t) {
        var on = t[0] === tab ? ' class="on"' : '';
        return '<a href="' + V.href('data', 'history', { tab: t[0], year: year }) + '"' + on + '>' + t[1] + '</a>';
      }).join('') + '</div>';

    var selectors =
      '<div class="formgrid" style="margin-bottom:10px">' +
      '<div class="field"><label>研究区</label><div>' + V.pill('SYRDARYA', 'info') + '</div></div>' +
      '<div class="field"><label>测站</label>' + V.stationSelect('stSel', stations, uid) + '</div>' +
      '<div class="field"><label>年份</label>' + V.select('yrSel', years, year) + '</div>' +
      '</div>';

    var body = '', chartNote = '';
    if (tab === 'flow') {
      var d = await V.get(S + '/discharge?station=' + encodeURIComponent(uid) + '&year=' + year);
      var ann = await V.get(S + '/discharge?station=' + encodeURIComponent(uid) + '&view=annual');
      var rows = d.months.map(function (m) {
        function cell(st) {
          if (m[st] === null || m[st] === undefined) {
            return { html: '<span class="c-mut">MISSING</span>', cls: 'num' };
          }
          var cls = 'num' + (m[st + '_flags'] && m[st + '_flags'].length ? ' c-warn' : '');
          return { html: V.num(m[st], 1) + (m[st + '_flags'] && m[st + '_flags'].length ?
            ' <span class="pill warn" title="序号占位嫌疑">S</span>' : ''), cls: cls };
        }
        return [String(m.month), cell('mean'), cell('max'), cell('min')];
      });
      var obs = d.months.filter(function (m) { return m.mean !== null && m.mean !== undefined; });
      body = V.card({
        title: year + ' 年 ' + uid + ' 月流量（源表原值）',
        lead: '统计量逐月给出：月平均 / 月最大 / 月最小。缺测 = MISSING，不插值、不补零。',
        body: V.table(['月', { label: '月平均', num: 1 }, { label: '月最大', num: 1 }, { label: '月最小', num: 1 }], rows) +
          '<p class="notice">单位：<b>' + V.esc(d.unit) + '</b>（' + V.esc(d.unit_status) + '）。' +
          '本年度有值月份 ' + obs.length + ' / 12。</p>'
      }) + V.card({
        title: '年度径流：源值 vs 派生值',
        lead: '源值永不覆盖；W_from_Q 是由月流量派生的对比量（标注 DERIVED）',
        body: (d.annual ? V.kv([
          ['W 源值（10^6 m3）', V.num(d.annual.W_source, 2)],
          ['W_from_Q（派生）', V.num(d.annual.W_from_Q, 2)],
          ['相对差（分母=源 W）', d.annual.rel_diff === null ? '—' : V.pct(d.annual.rel_diff, 2)],
          ['一致性判定', ({ html: V.spill(d.annual.status) }), 'html'],
          ['有值月数', String(d.annual.months_present)]
        ]) : V.empty('该年无年径流记录行')) +
          '<div class="hr"></div><h4>全部年份</h4>' +
          V.table(['年份', { label: 'W 源值', num: 1 }, { label: 'W_from_Q', num: 1 },
            { label: '相对差', num: 1 }, '状态'],
            (ann.years || []).map(function (y) {
              return [String(y.year), V.num(y.W_source, 1), V.num(y.W_from_Q, 1),
                y.rel_diff === null || y.rel_diff === undefined ? '—' : V.pct(y.rel_diff, 2),
                { html: V.spill(y.status) }];
            })) +
          '<p class="notice">' + V.esc(d.target_q_notice || '') + '</p>'
      }) + V.card({
        title: '该年逐月过程（观测）',
        body: V.lineChart({
          points: d.months.map(function (m) {
            return { year: year, month: m.month, t: year + '-' + (m.month < 10 ? '0' : '') + m.month,
              value: m.mean, status: (m.mean_flags && m.mean_flags.length) ? 'SUSPECT' : (m.mean === null ? 'MISSING' : 'OBSERVED') };
          }),
          height: 240, yLabel: 'Q（单位 UNKNOWN）', xLabel: '月', markSuspect: true,
          aria: year + ' 年月流量过程线'
        }) + '<p class="notice">仅观测值；无模拟线。</p>'
      });
      chartNote = '单位未确认：轴标题写 UNKNOWN，不擅自标 m³/s。';
    } else if (tab === 'met') {
      var met = await V.get(S + '/meteorology?year=' + year);
      var mrows = met.months.map(function (m) {
        return [String(m.month), m.P_sum === null ? { html: '<span class="c-mut">—</span>', cls: 'num' } : V.num(m.P_sum, 1),
          m.T_mean === null ? { html: '<span class="c-mut">—</span>', cls: 'num' } : V.num(m.T_mean, 2),
          m.days_with_P + '/' + m.days_in_month, m.days_with_T + '/' + m.days_in_month,
          { html: m.complete ? V.spill('COMPLETE') : V.spill('PARTIAL') }];
      });
      body = V.card({
        title: year + ' 年逐日气象（月聚合）',
        lead: '只有整月逐日齐全才给出月聚合值；否则显示 —（缺测不等于 0）。',
        body: V.barChart({ points: met.months.map(function (m) {
          return { label: m.month + '月', value: m.P_sum };
        }), height: 200, yLabel: 'P 月合计（单位 UNKNOWN）', color: '#2e7d6b', aria: '月降水合计' }) +
          V.barChart({ points: met.months.map(function (m) {
            return { label: m.month + '月', value: m.T_mean };
          }), height: 200, yLabel: 'T 月平均（单位 UNKNOWN）', color: '#1f5fa8', aria: '月平均气温' }) +
          V.table(['月', { label: 'P 月合计', num: 1 }, { label: 'T 月平均', num: 2 },
            'P 日数', 'T 日数', '完整'], mrows) +
          '<p class="notice">单位：P=' + V.esc(met.units.P) + '，T=' + V.esc(met.units.T) +
          '（源表表头未标注）。横轴为月份，纵轴单位保留 UNKNOWN，不做换算。</p>'
      });
    } else {
      var alpha = ctx.q.alpha || '0.75';
      var width = ctx.q.width || '3.0';
      var wb = await V.get(S + '/water-balance?year=' + year + '&alpha=' + alpha + '&width_km=' + width);
      var b = wb.balance, ck = wb.checks, res = wb.residuals;
      body = V.card({
        title: year + ' 年河段水量平衡（268 km 案例）',
        lead: 'W 上/下、dW、P/ET 体积、引水与残余并列；源文件公式与标准平衡诊断分开。',
        body: '<div class="formgrid" style="margin-bottom:10px">' +
          '<div class="field"><label>半宽 km</label>' + V.select('wsSel', [3.0, 5.0, 8.0], parseFloat(width)) + '</div>' +
          '<div class="field"><label>引水情景 α</label>' + V.select('alSel', ['0.60', '0.75', '0.90'], alpha) + '</div>' +
          '</div>' +
          V.table(['项', '值', '单位/状态'], [
            ['W 上游', V.num(b.W_up, 4), V.esc(b.units.W_up)],
            ['W 下游', V.num(b.W_down, 4), V.esc(b.units.W_down)],
            ['dW = 上-下', V.num(b.dW, 4), V.esc(b.units.dW)],
            ['P 体积', V.num(b.P_vol, 4), V.esc(b.units.P_vol)],
            ['ET 体积', V.num(b.ET_vol, 4), V.esc(b.units.ET_vol)],
            ['引水（源记录）', V.num(b.W_intake, 4), V.esc(b.units.W_intake)],
            ['残余（源文件公式）', V.num(b.residual_file, 4), V.esc(b.units.residual)]
          ], { cls: 'mono-s' }) +
          '<div class="hr"></div><h4>一致性核对（复算）</h4>' +
          V.table(['检查', '结果'], [
            ['W 上游 / 16037 源 W', V.num(ck.W_up_vs_disch_W, 5)],
            ['W 下游 / 16039 源 W', V.num(ck.W_down_vs_disch_W, 5)],
            ['dW 闭合', { html: ck.dW_ok ? V.pill('闭合', 'ok') : V.pill('不闭合', 'bad') }],
            ['P_vol 闭合', { html: ck.P_vol_ok ? V.pill('闭合', 'ok') : V.pill('不闭合', 'bad') }],
            ['ET_vol 闭合', { html: ck.ET_vol_ok ? V.pill('闭合', 'ok') : V.pill('不闭合', 'bad') }],
            ['残余符合源公式', { html: ck.residual_matches_file_convention ? V.pill('一致', 'ok') : V.pill('不一致', 'bad') }],
            ['源公式残余', V.num(ck.residual_recomputed_file_convention, 4)],
            ['标准平衡诊断残余', V.num(ck.residual_recomputed_standard_balance, 4)]
          ]) +
          '<div class="hr"></div><h4>α 情景：固定源残余 vs 所选情景残余</h4>' +
          V.table(['口径', '值', '说明'], [
            ['固定源记录引水', V.num(res.fixed_source_record.W_intake_source, 4),
              V.esc(res.fixed_source_record.residual_file_formula)],
            ['固定源残余', V.num(res.fixed_source_record.residual_file_value, 4), '不随 α 变化'],
            ['标准平衡诊断', V.num(res.fixed_source_record.residual_control_volume_diagnostic, 4),
              V.esc(res.control_volume_definition)],
            ['所选 α=' + alpha + ' 引水', V.num(res.selected_scenario.W_intake_alpha, 4),
              '情景代数（同单位假设），非实测'],
            ['所选 α 残余（源公式口径）', V.num(res.selected_scenario.residual_file_formula_with_selected_intake, 4), '—'],
            ['所选 α 残余（标准平衡）', V.num(res.selected_scenario.residual_control_volume_diagnostic, 4), '—']
          ]) +
          '<p class="notice">' + V.esc(wb.disclaimer) + '</p>' +
          '<p class="notice">' + V.esc(wb.units_note) + '</p>'
      }) + V.card({
        title: 'α 情景表',
        body: V.table(['α', '引水值', '置信度', '是实测吗', '方法'],
          (wb.intake_scenarios || []).map(function (s) {
            return [String(s.alpha), V.num(s.value, 4), V.esc(s.confidence),
              { html: s.is_measurement ? V.pill('实测', 'ok') : V.pill('反演情景', 'warn') }, V.esc(s.method)];
          }))
      });
    }

    var html = subnav('history') + V.card({ title: '站点历史数据', lead: '来源、快照与缺测口径对四个模块一致',
      body: selectors + tabs + '<div id="dataPanel">' + body + '</div>' + (chartNote ? '<p class="notice">' + chartNote + '</p>' : '') });

    return {
      html: html,
      side: V.sideCards({
        dataset: { id: 'SYRDARYA', title: 'Syr Darya 锡尔河下游', crs: 'GIS_PENDING', authorization: 'TEACHER_CSV_READ_ONLY' },
        snapshotId: 'syr-snap（见数据目录）',
        links: [
          { href: V.href('data', 'coverage'), label: '覆盖矩阵' },
          { href: V.href('results', 'station', { station: uid }), label: '该站结果层' },
          { href: V.href('data', 'quality'), label: '质量证据' }
        ]
      }) + V.card({ title: '当前选择', tight: true,
        body: V.kv([['测站', uid], ['年份', String(year)], ['页签', tab]]) }),
      mount: function (root) {
        V.onChange(root, 'stSel', function (v) {
          location.hash = V.href('data', 'history', { station: v, year: year, tab: tab });
        });
        V.onChange(root, 'yrSel', function (v) {
          location.hash = V.href('data', 'history', { station: uid, year: v, tab: tab });
        });
        V.onChange(root, 'wsSel', function (v) {
          location.hash = V.href('data', 'history', { year: year, tab: 'wb', width: v, alpha: ctx.q.alpha || '0.75' });
        });
        V.onChange(root, 'alSel', function (v) {
          location.hash = V.href('data', 'history', { year: year, tab: 'wb', width: ctx.q.width || '3.0', alpha: v });
        });
      }
    };
  }

  async function remoteView(ctx) {
    var ds = V.state.dataset;
    var year = parseInt(ctx.q.year, 10) || 2010;
    if (ds !== 'SYRDARYA') {
      return { html: subnav('remote') + V.card({ title: '遥感数据', body: V.empty('LamaH-CE 无授权遥感产品。') }) };
    }
    var rs = await V.get('/api/v6/data/remote-sensing?dataset=SYRDARYA&year=' + year);
    var rows = rs.circles.map(function (c) {
      return ['圆区 ' + c.site, c.months_with_value + '/12',
        c.first === null ? '—' : c.first, c.last === null ? '—' : c.last,
        c.missing_months.length ? V.esc(c.missing_months.join(',')) : '无',
        c.values_km2.filter(function (x) { return x.value !== null; }).length ?
          V.num(c.values_km2.filter(function (x) { return x.value !== null; })
            .map(function (x) { return x.value; }).reduce(function (a, b) { return a + b; }, 0), 1) : '—'];
    });
    var html = subnav('remote') + V.card({
      title: '遥感数据 · ' + year + ' 年',
      lead: '数据来源、有效观测时间、观测数量与缺失状态；NO_OBSERVATION 不是 0。',
      body: '<div class="formgrid" style="margin-bottom:10px"><div class="field"><label>年份</label>' +
        V.select('rySel', [2003, 2005, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024], year) + '</div></div>' +
        V.table(['产品', '来源', '空间范围', '单位'], rs.products.map(function (p) {
          return [V.esc(p.id + ' · ' + p.title), V.esc(p.source), V.esc(p.spatial_extent), V.esc(p.unit)];
        })) +
        '<div class="hr"></div>' +
        V.table(['圆区', '有值月数', '首月', '末月', '缺失月份', { label: '面积合计 km2', num: 1 }], rows) +
        '<p class="notice">' + V.esc(rs.missing_policy) + '</p>' +
        '<div class="hr"></div><h4>KZDAM KC/KD/KS/KU</h4>' +
        (rs.kzdam.rows.length ? V.table(['月', '站点', { label: '值', num: 1 }, '状态'],
          rs.kzdam.rows.map(function (k) { return [String(k.month), k.site, V.num(k.value, 2), V.spill(k.status)]; })) :
          V.empty('该年无 KZDAM 记录行')) +
        '<p class="notice">KZDAM 单位 UNKNOWN（源表未标注，且不是 km2）；' + V.esc(rs.overlap_note) + '</p>'
    });
    return {
      html: html,
      side: V.sideCards({ dataset: { id: ds, title: 'Syr Darya 锡尔河下游', crs: 'GIS_PENDING', authorization: 'TEACHER_CSV_READ_ONLY' },
        permissions: rs.permissions,
        links: [{ href: V.href('data', 'history'), label: '站点历史' }, { href: V.href('data', 'quality'), label: '质量证据' }] }),
      mount: function (root) {
        V.onChange(root, 'rySel', function (v) {
          location.hash = V.href('data', 'remote', { year: v });
        });
      }
    };
  }

  async function docView(ctx, kind) {
    var ds = V.state.dataset;
    var d = await V.get('/api/v6/data/' + kind + '?dataset=' + ds);
    var title = kind === 'yearbooks' ? '统计年鉴' : '文献材料';
    var body = V.banner('warn', '本轮未读取，目录为空是真实状态',
      V.esc(d.reason || d.policy)) +
      '<div class="hr"></div><h4>数据契约（界面已就绪）</h4>' +
      V.table(['字段', '说明'], (d.required_fields || []).map(function (f) {
        return [V.esc(f), '必填；缺失即不登记'];
      })) +
      '<div class="hr"></div><h4>登记规则</h4>' +
      V.ul([
        '只读打开 + SHA-256 校验后才登记元数据',
        '不得以估算值填充缺失数据',
        '不生成无法核实的论文条目',
        '接入前需老师/管理员授权'
      ]) +
      (d.authorization_needed ? '<div class="hr"></div><h4>需要授权的路径</h4>' +
        V.kv([['路径', d.authorization_needed.path], ['申请', d.authorization_needed.ask]]) : '') +
      (d.ingestion_contract ? V.kv([['接口', d.ingestion_contract.endpoint],
        ['模式', d.ingestion_contract.mode], ['禁止', d.ingestion_contract.forbidden]]) : '');
    return {
      html: subnav(kind === 'yearbooks' ? 'yearbook' : 'literature') +
        V.card({ title: title, lead: '文档目录与来源索引', body: body }) +
        V.card({ title: '当前登记条目', body: V.empty('0 条（未授权 / 未核验 → 如实为空）') }),
      side: V.sideCards({ dataset: { id: ds, title: ds === 'SYRDARYA' ? 'Syr Darya 锡尔河下游' : 'LamaH-CE 欧洲河网',
        crs: ds === 'SYRDARYA' ? 'GIS_PENDING' : 'EPSG:3035', authorization: 'READ_ONLY' }, permissions: d.permissions })
    };
  }

  async function qualityView(ctx) {
    var ds = V.state.dataset;
    var code = ctx.q.code || '';
    var sev = ctx.q.severity || '';
    var page = parseInt(ctx.q.page, 10) || 0;
    var qs = 'dataset=' + ds + '&page=' + page + '&size=25' + (code ? '&code=' + encodeURIComponent(code) : '') +
      (sev ? '&severity=' + encodeURIComponent(sev) : '');
    var d = await V.get('/api/v6/evidence?' + qs);
    if (ds !== 'SYRDARYA') {
      return { html: subnav('quality') + V.card({ title: '数据质量与科研证据', body: V.empty(d.note) }) };
    }
    var codeOpts = [{ value: '', label: '全部错误码' }];
    Object.keys(d.flag_counts || {}).sort().forEach(function (k) {
      codeOpts.push({ value: k, label: k + '（' + d.flag_counts[k] + '）' });
    });
    var rows = (d.flags || []).map(function (f) {
      return [{ html: V.spill(f.severity) }, V.esc(f.code), V.esc(f.scope), V.esc(f.message), V.esc(f.source_file)];
    });
    var totalPages = Math.max(1, Math.ceil(d.total / (d.size || 25)));
    var html = subnav('quality') + V.card({
      title: '数据质量与科研证据（二级页面）',
      lead: '首页不铺开诊断；这里可过滤、分页并查看来源文件哈希。',
      body: '<div class="formgrid" style="margin-bottom:10px">' +
        '<div class="field"><label>错误码</label>' + V.select('qcCode', codeOpts, code) + '</div>' +
        '<div class="field"><label>严重度</label>' + V.select('qcSev', [{ value: '', label: '全部' },
          { value: 'ERROR', label: 'ERROR' }, { value: 'WARN', label: 'WARN' }, { value: 'INFO', label: 'INFO' }], sev) + '</div>' +
        '</div>' +
        V.table(['严重度', '错误码', '作用域', '说明', '来源文件'], rows) +
        '<div class="chips" style="margin-top:10px">' +
        (page > 0 ? '<a class="btn small" href="' + V.href('data', 'quality', { page: page - 1, code: code, severity: sev }) + '">上一页</a>' : '') +
        '<span class="pill">第 ' + (page + 1) + ' / ' + totalPages + ' 页 · 共 ' + d.total + ' 条</span>' +
        (page + 1 < totalPages ? '<a class="btn small" href="' + V.href('data', 'quality', { page: page + 1, code: code, severity: sev }) + '">下一页</a>' : '') +
        '</div>'
    }) + V.card({
      title: '来源文件与 SHA-256（加载时校验）',
      body: V.table(['文件', { label: '字节', num: 1 }, { label: '记录', num: 1 }, '编码', 'SHA-256'],
        (d.files || []).map(function (f) {
          return [V.esc(f.file), V.whole(f.bytes || 0), V.esc(f.records), V.esc(f.encoding),
            { html: '<span class="mono-s">' + V.esc((f.sha256 || '').slice(0, 32)) + '…</span>' }];
        }))
    }) + V.card({
      title: '单位状态（未确认的保持 UNKNOWN）',
      body: V.table(['字段', '单位'], (d.units || []).map(function (u) {
        return [V.esc(u.field), V.spill(u.unit)];
      })) + '<p class="notice">' + V.esc(d.note) + '</p>'
    });
    return {
      html: html,
      side: V.sideCards({ dataset: { id: ds, title: 'Syr Darya 锡尔河下游', crs: 'GIS_PENDING', authorization: 'TEACHER_CSV_READ_ONLY' },
        snapshotId: (d.snapshot || {}).snapshot_id,
        permissions: d.permissions,
        links: [{ href: V.href('data'), label: '数据目录' }, { href: V.href('results', 'report'), label: '科研报告' }] }) +
        V.card({ title: '严重度计数', tight: true,
          body: V.kv(Object.keys(d.severity_counts || {}).map(function (k) {
            return [k, String(d.severity_counts[k])];
          })) }),
      mount: function (root) {
        V.onChange(root, 'qcCode', function (val) {
          location.hash = V.href('data', 'quality', { code: val, severity: sev, page: 0 });
        });
        V.onChange(root, 'qcSev', function (val) {
          location.hash = V.href('data', 'quality', { code: code, severity: val, page: 0 });
        });
      }
    };
  }

  V.views.data = async function (ctx) {
    if (!ctx.sub) return catalogView(ctx);
    if (ctx.sub === 'history') return historyView(ctx);
    if (ctx.sub === 'remote') return remoteView(ctx);
    if (ctx.sub === 'yearbook') return docView(ctx, 'yearbooks');
    if (ctx.sub === 'literature') return docView(ctx, 'literature');
    if (ctx.sub === 'quality') return qualityView(ctx);
    if (ctx.sub === 'coverage') {
      var cv = await V.get('/api/v6/data/coverage?dataset=' + V.state.dataset);
      return { html: subnav('index') + coverageCard(cv), side: '' };
    }
    return catalogView(ctx);
  };
})();
