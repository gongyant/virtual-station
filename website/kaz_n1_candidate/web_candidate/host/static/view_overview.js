/* VHS v0.6 -- research overview (first screen: area -> task -> target -> space -> hydrograph -> model -> entries) */
(function () {
  'use strict';
  var V = window.VHS;

  function quickFacts(s, isSyr) {
    if (isSyr) {
      return V.kpi('测站', s.n_stations, '有流量记录') +
        V.kpi('记年', (s.discharge_years || []).length, '离散年份，不插值') +
        V.kpi('遥感月', s.circle_months, '圆区 A-G 有值') +
        V.kpi('KZ 月', s.kzdam_months, 'KC/KD/KS/KU') +
        V.kpi('QC 标记', (s.qc || {}).flags_total, '详见质量证据页');
    }
    return V.kpi('站点', s.stations_total, '开放元数据') +
      V.kpi('图内站点', s.stations_in_graph, '有向边') +
      V.kpi('有向边', s.directed_edges, '图级') +
      V.kpi('供数候选目标', s.targets_with_candidates, 'GRAPH_TENTATIVE') +
      V.kpi('几何认证', s.geometry_verified, 'GEOMETRY_VERIFIED', 'na');
  }

  function tiles(entries) {
    return '<div class="tiles">' + entries.map(function (en) {
      return '<a class="tile" href="' + en.href + '"><span class="tk">' + V.esc(en.key) + '</span><b>' +
        V.esc(en.title) + '</b><span>' + V.esc(en.sub) + '</span></a>';
    }).join('') + '</div>';
  }

  V.views.overview = async function (ctx) {
    var ds = V.state.dataset;
    var params = { dataset: ds };
    if (V.state.station) params.station = V.state.station;
    var qs = Object.keys(params).map(function (k) { return k + '=' + encodeURIComponent(params[k]); }).join('&');
    var d = await V.get('/api/v6/overview?' + qs);
    var r = d.research, b = d.browse, sp = d.spatial, hg = d.hydrograph, m = d.model, dsun = d.data_summary;
    var isSyr = ds === 'SYRDARYA';

    /* 1. research area + task */
    var area = V.card({
      num: '1', title: '研究区域与研究任务',
      body: '<div class="grid2">' +
        '<div>' +
        '<div class="tagline" style="margin-bottom:6px">' + V.pill(ds, 'info') +
        V.pill(isSyr ? 'GIS_PENDING' : 'EPSG:3035') + V.pill(isSyr ? 'TEACHER_CSV_READ_ONLY' : 'OPEN_METADATA_ONLY') + '</div>' +
        '<h3>' + V.esc(r.title) + '</h3>' +
        '<p class="notice">' + V.esc(r.task) + '</p>' +
        '<div class="kpis" style="margin-top:10px">' + quickFacts(dsun, isSyr) + '</div>' +
        '</div>' +
        '<div>' +
        '<h4>研究任务类型</h4>' + V.ul((r.task_types || []).map(function (t) { return V.esc(t); })) +
        '<p class="notice">固定研究河段与当前浏览测站是两个不同的对象，分开显示。</p>' +
        '</div></div>'
    });

    /* 2. fixed reach + browsed station */
    var reach = r.case_reach || {};
    var reachHtml = V.card({
      num: '2', title: '固定研究河段',
      body: '<div class="tagline" style="margin-bottom:8px">' +
        V.pill(reach.role || '', '') + V.spill(reach.hydrologic_status) + '</div>' +
        '<div class="kv" style="font-size:13px"><dt>河段</dt><dd class="strong">' + V.esc(reach.label || '—') + '</dd>' +
        '<dt>上游 U</dt><dd>' + V.esc(reach.upstream || '—') + '</dd>' +
        '<dt>下游 T</dt><dd>' + V.esc(reach.downstream || '—') + '</dd>' +
        '<dt>认证状态</dt><dd>' + V.spill(reach.hydrologic_status) + '</dd></div>' +
        '<p class="notice">' + (isSyr
          ? '老师提供的 16037 -> 16039 案例；河段几何与坐标未授权，不绘制。'
          : '无老师指定河段；本任务为全站网图级关系筛查。') + '</p>'
    });
    var stationHtml = V.card({
      num: '3', title: '当前浏览测站',
      body: (b.station ? '<div class="tagline" style="margin-bottom:8px">' + V.pill(b.station, 'info') +
        V.spill('OBSERVED_GAUGE') + '</div>' : V.empty('未选择测站')) +
        '<div class="kv" style="font-size:13px"><dt>名称</dt><dd>' + V.esc(b.name || '—') + '</dd>' +
        '<dt>角色</dt><dd>' + V.esc(b.role || '') + '</dd>' +
        '<dt>观测年份</dt><dd>' + (b.years ? V.esc(b.years.join(', ')) : '—') + '</dd>' +
        '<dt>坐标状态</dt><dd>' + V.esc(b.coordinate_status || '—') + '</dd></div>' +
        (isSyr ? '<p class="notice">切换浏览测站不会改变固定研究河段。</p>' : '')
    });

    /* 3. spatial overview */
    var spatialBody;
    if (isSyr) {
      spatialBody = '<div class="mapbox" style="min-height:250px"><div class="mapempty">' +
        '<b>无经核验的空间数据，不绘制地图</b>' +
        '<span>Syr Darya 的站点/河段/DEM 坐标尚未授权，CRS = GIS_PENDING。' +
        '把欧洲 EPSG:3035 套用到锡尔河会产生错误地图，因此这里显示状态而不是假图。</span>' +
        V.pill('GIS_DISPLAY_NOT_AVAILABLE', 'bad') +
        '</div><div class="mapnote">图层接口已就绪：河网 / DEM / 水文站 / 气象站 / 行政区 五类；' +
        '真实数据到达后即可渲染。</div></div>';
    } else {
      var fe = await V.get('/api/v6/layers/features?dataset=LAMAHCE&layer=hs_gauges');
      var pts = (fe.collection.features || []).map(function (f) {
        return { id: f.properties.id, uid: f.properties.uid, x: f.geometry.coordinates[0],
          y: f.geometry.coordinates[1], name: f.properties.name,
          candidate_status: f.properties.candidate_status };
      });
      spatialBody = '<div class="mapbox" style="min-height:250px">' +
        V.mapSvg({ points: pts, bounds: fe.bounds, height: 250, selected: (b.station || '').split(':')[1], r: 2.4 }) +
        '<div class="mapnote">' + V.esc(fe.note) + '　共 ' + pts.length + ' 点。</div></div>';
    }

    /* 4. core hydrograph */
    var hydroBody, hydroLegend = '';
    if (isSyr) {
      hydroBody = V.lineChart({
        points: hg.points || [], height: 300, yLabel: 'Q（单位 UNKNOWN）',
        xLabel: '时间（年-月）', markSuspect: true, bandStatus: 'NO_RECORD_YEAR',
        aria: '核心水文过程线：实测月平均流量'
      }) +
        '<div class="legend"><span><i style="border-color:#1f5fa8"></i>Qobs 实测月平均（' + V.esc(hg.station) + '）</span>' +
        '<span><i style="border-color:#b06a2c;border-top-style:dashed"></i>Qsim 模拟（未生成）</span>' +
        '<span><i style="border-color:#a83232;border-top-style:dashed"></i>红底=该年无记录（不插值）</span>' +
        '<span><i style="border-color:#9a6400"></i>底部短竖线=序号占位嫌疑（不绘制）</span></div>' +
        '<p class="notice">' + V.esc(hg.notice) + '　有值 ' + hg.n_observed + ' 个月 / 缺测 ' +
        hg.n_missing_cell + ' / 无记录年 ' + hg.n_no_record_year + ' 个月（共 ' + hg.n_points + ' 个月槽位）。</p>';
    } else {
      hydroBody = V.empty('LamaH-CE 仅开放元数据，径流序列位于 sealed_runoff，未授权读取。<br>' +
        '因此本站网没有可展示的观测曲线，也不生成模拟曲线。');
    }

    /* 5. model status */
    var modelBody =
      '<div class="kpis">' +
      V.kpi('模型执行', '<span class="c-bad">NOT_AUTHORIZED</span>', 'prediction = null') +
      V.kpi('注册基线', m.registered_models, 'SYR-B0 / B1 / B2 仅定义') +
      V.kpi('已实现', m.implemented_models, '可运行模型数') +
      V.kpi('已训练', m.trained_models, '训练结果数') +
      V.kpi('已评估', m.evaluated_models, '评估记录数', 'na') +
      V.kpi('Qsim', '<span class="c-mut">null</span>', '未生成', 'na') +
      '</div>' +
      '<div style="margin-top:11px">' + V.banner('info', '当前没有真实评估结果',
        V.esc(m.notice) + '　因此结果层的 NSE / KGE / RMSE / MAE / PBIAS 一律显示 N/A，' +
        '不使用示例数字。') + '</div>' +
      '<div class="chips" style="margin-top:10px">' +
      '<a class="btn" href="' + V.href('model', null) + '">查看模型架构</a>' +
      '<a class="btn" href="' + V.href('results', 'evaluation') + '">查看模型评估</a>' +
      '<a class="btn primary" href="' + V.href('results', 'station') + '">打开结果层 · 站点结果</a>' +
      '</div>';

    var html = [
      area,
      '<div class="split">' + reachHtml + stationHtml + '</div>',
      V.card({ num: '4', title: '空间概览', lead: isSyr
        ? 'Syr Darya：无授权坐标 → 用状态说明代替地图'
        : 'LamaH-CE：真实 EPSG:3035 投影站点散点（无底图、无河段几何）', body: spatialBody }),
      V.card({ num: '5', title: '核心水文过程线', lead: isSyr
        ? '实测月平均流量（观测为唯一真实曲线；模拟曲线留空）'
        : '本站网无授权观测序列', body: hydroBody }),
      V.card({ num: '6', title: '模型运行状态与真实评估结果', body: modelBody }),
      V.card({ num: '7', title: '进入四层功能', lead: '按“研究区域 → 数据 → 模型 → 结果”的科研叙事组织',
        body: tiles(d.entries || []) })
    ].join('');

    var side = V.sideCards({
      dataset: { id: ds, title: isSyr ? 'Syr Darya 锡尔河下游' : 'LamaH-CE 欧洲河网',
        crs: sp.dataset_crs, authorization: isSyr ? 'TEACHER_CSV_READ_ONLY' : 'OPEN_METADATA_ONLY' },
      snapshotId: (d.snapshot || {}).snapshot_id,
      snapshotNote: isSyr ? '六文件不可变快照；哈希在加载时校验' : '开放元数据静态清单',
      permissions: d.permissions,
      model: m,
      links: [
        { href: V.href('layers'), label: '空间图层' },
        { href: V.href('data'), label: '数据层' },
        { href: V.href('data', 'quality'), label: '质量与证据' },
        { href: V.href('results', 'report'), label: '科研报告' }
      ]
    });

    return {
      html: html, side: side,
      mount: function (root) {
        if (!isSyr) {
          var svg = root.querySelector('.mapbox svg');
          if (svg) {
            svg.addEventListener('click', function (ev) {
              var t = ev.target;
              if (t && t.getAttribute && t.getAttribute('data-id')) {
                var uid = 'LAMAHCE:' + t.getAttribute('data-id');
                location.hash = V.href('results', 'station', { station: uid });
              }
            });
          }
        }
      }
    };
  };
})();
