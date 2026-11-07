/* VHS v0.6 -- spatial layers: layer tree + map + station summary */
(function () {
  'use strict';
  var V = window.VHS;

  function layerRow(l) {
    var st = l.display_status === 'GIS_DISPLAY_READY' ? 'ready'
      : (l.hydrologic_status === 'GRAPH_TENTATIVE' ? 'tent' : 'na');
    return '<div class="lrow" data-layer="' + V.esc(l.id) + '">' +
      '<span class="st ' + st + '"></span><span class="nm"><b>' + V.esc(l.title) + '</b>' +
      '<span>' + V.esc(l.display_status) + ' · ' + V.esc(l.geometry) + '</span></span></div>';
  }

  function tree(groups) {
    return '<div class="tree">' + groups.map(function (g) {
      return '<div class="grp" data-group="' + V.esc(g.key) + '">' +
        '<div class="grph"><span class="chev">▾</span>' + V.esc(g.title) +
        ' <span class="pill">' + g.layers.length + '</span></div>' +
        '<div class="layers">' + g.layers.map(layerRow).join('') + '</div></div>';
    }).join('') + '</div>';
  }

  function detail(l) {
    if (!l) return '<div class="empty">在左侧图层树中选择一个图层查看说明与状态。</div>';
    var rows = [
      ['显示状态', V.spill(l.display_status) + ' <span class="muted small">' + V.esc(l.display_status_zh) + '</span>'],
      ['水文认证', V.spill(l.hydrologic_status) + ' <span class="muted small">' + V.esc(l.hydrologic_status_zh) + '</span>'],
      ['几何类型', V.esc(l.geometry)],
      ['要素数', l.feature_count === null || l.feature_count === undefined ? '—' : V.esc(l.feature_count)],
      ['CRS', V.esc(l.crs || '—')],
      ['来源', V.esc(l.source)],
      ['证据', V.esc(l.evidence)],
      ['说明', V.esc(l.notes)]
    ];
    var h = '<h3 style="margin-bottom:8px">' + V.esc(l.title) + '</h3>' + V.kv(rows);
    h += '<div style="margin-top:10px">' + V.banner('info', '两种状态必须分开看',
      'GIS_DISPLAY_READY 只表示真实空间数据可以绘制；HYDROLOGICALLY_CERTIFIED 表示水文物理关系已审核。' +
      '本图层当前：' + V.esc(l.display_status) + ' / ' + V.esc(l.hydrologic_status) + '。') + '</div>';
    return h;
  }

  V.views.layers = async function (ctx) {
    var ds = V.state.dataset;
    var isSyr = ds === 'SYRDARYA';
    var L = await V.get('/api/v6/layers?dataset=' + ds);
    var s = L.summary;
    var fe = null, pts = [];
    if (!isSyr) {
      fe = await V.get('/api/v6/layers/features?dataset=LAMAHCE&layer=hs_gauges');
      pts = (fe.collection.features || []).map(function (f) {
        return { id: f.properties.id, uid: f.properties.uid, x: f.geometry.coordinates[0],
          y: f.geometry.coordinates[1], name: f.properties.name,
          candidate_status: f.properties.candidate_status };
      });
    }

    var head = V.card({
      title: '图层管理器 · ' + (isSyr ? 'Syr Darya 锡尔河下游' : 'LamaH-CE 欧洲河网'),
      lead: '五类图层：河网 / DEM / 水文站点 / 气象站点 / 行政区域。左侧图层树、中央地图、右侧站点摘要。',
      body: '<div class="kpis">' +
        V.kpi('图层总数', s.layers_total, '五类分组') +
        V.kpi('可绘制', s.display_ready, 'GIS_DISPLAY_READY') +
        V.kpi('已认证', s.hydrologically_certified, 'HYDROLOGICALLY_CERTIFIED', 'na') +
        V.kpi('图级暂定', s.tentative, 'GRAPH_TENTATIVE') +
        V.kpi('不可用', s.not_available, '不绘制假几何') +
        '</div>' +
        '<div style="margin-top:10px">' + V.banner('warn', '约束', V.esc(L.rule_note)) + '</div>'
    });

    var mapBody;
    if (isSyr) {
      mapBody = '<div class="mapbox" style="min-height:470px"><div class="mapempty">' +
        '<b>无经核验的真实空间数据</b>' +
        '<span>Syr Darya 缺少 CRS 已核验的站点坐标、河段几何与 DEM。为避免错误地图，' +
        '本页只呈现图层接口与状态；真实数据到达后同一接口即可渲染。</span>' +
        '<div class="tagline">' + V.pill('GIS_PENDING', 'bad') + V.pill('HYDROLOGICALLY_CERTIFIED = 0', 'warn') + '</div>' +
        '</div><div class="mapnote">不套用 LamaH-CE 的 EPSG:3035；不编造站点位置、河流形状或 DEM。</div></div>';
    } else {
      mapBody = '<div class="mapbox" style="min-height:470px">' +
        V.mapSvg({ points: pts, bounds: fe.bounds, height: 470, selected: (V.state.station || '').split(':')[1] }) +
        '<div class="mapnote">' + V.esc(fe.note) + '　共 ' + pts.length + ' 个投影点。点击任一点进入该站结果层。</div></div>';
    }

    var treeCard = '<div class="layergrid">' +
      '<div>' + V.subnav('layers', [{ key: 'index', label: '图层总览' }], 'index') +
      '<div style="margin-top:10px">' + tree(L.groups) + '</div>' +
      '<p class="notice">圆点：绿=可绘制，橙=图级暂定关系，灰=不可用。</p></div>' +
      '<div>' + mapBody +
      '<div id="stSummary" class="card tight" style="margin-top:12px">' +
      V.empty('点击地图上的站点，显示站点摘要并可直接跳转到数据层 / 结果层。') + '</div>' +
      '<div id="layerDetail" class="card tight" style="margin-top:12px">' + detail(null) + '</div></div></div>';

    var auth = V.card({
      title: '真实 GIS 接入所需授权清单',
      lead: '本轮未读取任何未授权的 GIS 文件；以下为最小接入清单',
      body: V.table(['数据项', '需要核验的内容', '用途'],
        (L.authorization_required || []).map(function (a) {
          return [V.esc(a.item), V.esc(a.need), V.esc(a.purpose)];
        })) +
        '<p class="notice">另一路径：先提供 ' + V.esc(isSyr ? 'Syr Darya' : 'LamaH-CE') +
        ' 的 CRS 与要素计数，再逐层暂存并校验；任一层缺失都不影响其他图层单独显示。</p>'
    });

    var synth = V.card({
      title: '合成预览（SYNTHETIC_PREVIEW_ONLY）',
      lead: '与真实地图彻底分开：仅用于演示接口形状，不携带任何真实地理坐标',
      id: 'synthCard',
      body: '<div id="synthBody">' + V.empty('点击下方按钮载入合成预览（离线、本地合成，不代表真实河流）。') + '</div>' +
        '<div class="chips" style="margin-top:10px"><button class="btn small" id="synthBtn">载入合成预览</button>' +
        '<span class="pill warn">SYNTHETIC_PREVIEW_ONLY</span></div>'
    });

    var side = V.sideCards({
      dataset: { id: ds, title: isSyr ? 'Syr Darya 锡尔河下游' : 'LamaH-CE 欧洲河网',
        crs: L.crs, authorization: isSyr ? 'TEACHER_CSV_READ_ONLY' : 'OPEN_METADATA_ONLY' },
      snapshotId: (L.snapshot || {}).snapshot_id,
      permissions: L.permissions,
      links: [
        { href: V.href('data'), label: '转向数据层' },
        { href: V.href('results'), label: '转向结果层' }
      ]
    }) + V.card({
      title: '状态图例', tight: true,
      body: '<div class="small">' + Object.keys(L.display_status_legend).map(function (k) {
        return '<div style="margin:3px 0">' + V.spill(k) + ' ' + V.esc(L.display_status_legend[k]) + '</div>';
      }).join('') + '<div class="hr"></div>' +
        Object.keys(L.hydrologic_status_legend).map(function (k) {
          return '<div style="margin:3px 0">' + V.spill(k) + ' ' + V.esc(L.hydrologic_status_legend[k]) + '</div>';
        }).join('') + '</div>'
    });

    var html = [head, V.card({ title: '图层树 · 地图 · 图层说明', body: treeCard }), auth, synth].join('');

    return {
      html: html, side: side,
      mount: function (root) {
        var byId = {};
        L.groups.forEach(function (g) { g.layers.forEach(function (l) { byId[l.id] = l; }); });

        function select(id) {
          var rows = root.querySelectorAll('.lrow');
          Array.prototype.forEach.call(rows, function (r) {
            r.className = r.getAttribute('data-layer') === id ? 'lrow on' : 'lrow';
          });
          var box = root.querySelector('#layerDetail');
          if (box) box.innerHTML = detail(byId[id]);
        }
        Array.prototype.forEach.call(root.querySelectorAll('.lrow'), function (r) {
          r.addEventListener('click', function () { select(r.getAttribute('data-layer')); });
        });
        Array.prototype.forEach.call(root.querySelectorAll('.grph'), function (h) {
          h.addEventListener('click', function () {
            var layers = h.parentNode.querySelector('.layers');
            var chev = h.querySelector('.chev');
            if (!layers) return;
            var hidden = layers.style.display === 'none';
            layers.style.display = hidden ? '' : 'none';
            chev.textContent = hidden ? '▾' : '▸';
          });
        });
        var svg = root.querySelector('.mapbox svg');
        if (svg) {
          svg.addEventListener('click', async function (ev) {
            var t = ev.target;
            if (!t || !t.getAttribute || !t.getAttribute('data-id')) return;
            var id = t.getAttribute('data-id');
            var box = root.querySelector('#stSummary');
            box.innerHTML = '<div class="loading"><span class="spin"></span>读取站点 ' + V.esc(id) + '…</div>';
            try {
              var st = await V.get('/api/vhs/stations/' + id);
              var net = await V.get('/api/vhs/stations/' + id + '/network?depth=1');
              var uid = 'LAMAHCE:' + id;
              box.innerHTML = '<div class="tagline" style="margin-bottom:8px">' + V.pill(uid, 'info') +
                V.pill(st.audit_state || 'UNKNOWN') + '</div>' +
                '<h3>' + V.esc(st.name || '（无名称）') + '</h3>' +
                '<div class="kv" style="margin-top:6px">' +
                '<dt>河流</dt><dd>' + V.esc(st.river || '—') + '</dd>' +
                '<dt>区域</dt><dd>' + V.esc(st.region || '—') + '</dd>' +
                '<dt>面积 km²</dt><dd>' + V.num(st.area_gov_km2, 1) + '</dd>' +
                '<dt>观测期</dt><dd>' + V.esc(st.obsbeg_day || '—') + ' → ' + V.esc(st.obsend_day || '未标注') + '</dd>' +
                '<dt>上游 / 下游</dt><dd>' + V.esc(st.n_upstream) + ' / ' + V.esc(st.n_downstream) + '</dd>' +
                '<dt>候选状态</dt><dd>' + V.esc(st.candidate_status || '—') + '</dd>' +
                '<dt>坐标</dt><dd class="mono-s">' + V.num(st.x_epsg3035, 0) + ', ' + V.num(st.y_epsg3035, 0) + '（EPSG:3035 米）</dd>' +
                '</div>' +
                '<p class="notice">上下游关系为图级暂定（' + V.esc(st.candidate_status || 'UNKNOWN') + '），不是物理认证。</p>' +
                '<div class="chips" style="margin-top:8px">' +
                '<a class="btn small" href="' + V.href('data', 'history', { station: uid }) + '">数据层</a>' +
                '<a class="btn small primary" href="' + V.href('results', 'station', { station: uid }) + '">结果层</a>' +
                '<a class="btn small" href="' + V.href('layers', null, { station: uid }) + '">设为当前浏览测站</a>' +
                '</div>';
            } catch (e) {
              box.innerHTML = '<div class="err">' + V.esc(e.message) + '</div>';
            }
          });
        }
        var btn = root.querySelector('#synthBtn');
        if (btn) {
          btn.addEventListener('click', async function () {
            btn.disabled = true;
            btn.textContent = '载入中…';
            try {
              var syn = await V.get('/api/vhs/gis/synthetic');
              var body = root.querySelector('#synthBody');
              body.innerHTML = V.banner('warn', '这不是地图',
                '合成预览使用 LOCAL_SYNTHETIC_BOX_0_100 局部坐标，只演示接口形状；' +
                '禁止作为研究成果或真实地理引用。') +
                '<div class="split" style="margin-top:10px">' + V.synthSvg(syn) +
                '<div>' + V.kv([
                  ['坐标系', syn.crs],
                  ['图层数', String(syn.layers.length)],
                  ['来源', 'SYNTHETIC'],
                  ['T/W/U 路径', Object.keys(syn.reach_paths || {}).join(', ')],
                  ['汇流节点', String(syn.confluence_node)]
                ]) + '<p class="notice">' + V.esc(syn.note) + '</p></div></div>';
            } catch (e) {
              root.querySelector('#synthBody').innerHTML = '<div class="err">' + V.esc(e.message) + '</div>';
            }
            btn.textContent = '重新载入';
            btn.disabled = false;
          });
        }
      }
    };
  };
})();
