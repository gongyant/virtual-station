/* VHS v0.6 -- core: state, router, HTTP, formatting, charts */
(function () {
  'use strict';
  var VHS = window.VHS = window.VHS || {};
  VHS.version = '0.6.0';
  VHS.views = VHS.views || {};
  VHS.state = { dataset: 'SYRDARYA', station: null, layer: null, token: 0, publicKind:'TEMPORAL_HOLDOUT', publicModel:'P2-L1', publicStart:'2015-01', publicEnd:'2017-12', publicMapMode:'nse', publicReport:'p4_report' };
  VHS.cache = new Map();

  /* ---------------- formatting ---------------- */
  var ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
  VHS.esc = function (s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"]/g, function (c) { return ESC[c]; });
  };
  VHS.e = VHS.esc;
  VHS.num = function (v, d) {
    if (v === null || v === undefined || !isFinite(v)) return '—';
    d = (d === undefined) ? 1 : d;
    var a = Math.abs(v);
    if (a >= 10000) return whole(v);
    if (a >= 100) return v.toFixed(Math.min(d, 1));
    return v.toFixed(d);
  };
  function whole(v) {
    return String(Math.round(v)).replace(/(\d)(?=(\d{3})+$)/g, '$1,');
  }
  VHS.whole = whole;
  VHS.pct = function (v, d) {
    if (v === null || v === undefined || !isFinite(v)) return '—';
    d = (d === undefined) ? 1 : d;
    return (v * 100).toFixed(d) + '%';
  };
  VHS.bool = function (b) { return b ? '是' : '否'; };

  /* ---------------- pills / cards ---------------- */
  var KIND = {
    ok: ['OBSERVED', 'CONSISTENT', 'READY', 'AVAILABLE', 'GIS_DISPLAY_READY', 'HYDROLOGICALLY_CERTIFIED', 'OK', 'COMPLETE', 'PASS', 'ZERO'],
    warn: ['PARTIAL', 'SUSPECT', 'CONDITIONAL', 'GRAPH_TENTATIVE', 'UNKNOWN', 'W_MISSING_IN_SOURCE', 'W_INCONSISTENT', 'NOT_CHECKABLE_MISSING_MONTHS', 'W_UNIT_SCALE_SUSPECT', 'INTERFACE_ONLY', 'SYNTHETIC_PREVIEW_ONLY', 'METADATA_ONLY', 'NO_OBSERVATION', 'NO_RECORD_YEAR', 'MISSING', 'NOT_READ', 'NOT_REGISTERED'],
    bad: ['NOT_AUTHORIZED', 'BLOCKED', 'ERROR', 'GIS_DISPLAY_NOT_AVAILABLE', 'NOT_AVAILABLE', 'NO_AUTHORIZED_SERIES', 'PREDICTION_LAYER_NOT_AVAILABLE', 'OUT_OF_RANGE', 'FAIL'],
    info: ['DERIVED', 'INFO', 'DEFINED_ONLY', 'NOT_EVALUATED', 'NOT_RUN', 'NOT_IMPLEMENTED', 'NOT_GENERATED', 'NOT_STAGED', 'WARN']
  };
  VHS.kind = function (code) {
    var k;
    for (k in KIND) { if (KIND[k].indexOf(code) >= 0) return k; }
    return '';
  };
  VHS.pill = function (text, kind) {
    return '<span class="pill ' + (kind || '') + '">' + VHS.esc(text) + '</span>';
  };
  VHS.spill = function (code) {
    if (code === null || code === undefined || code === '') return VHS.pill('—');
    return VHS.pill(code, VHS.kind(code));
  };
  VHS.card = function (o) {
    var cls = 'card' + (o.tight ? ' tight' : '');
    var head = '';
    if (o.title) {
      head = '<h2>' + (o.num ? '<span class="num">' + VHS.esc(o.num) + '</span>' : '') +
        VHS.esc(o.title) + (o.badge || '') + '</h2>';
    }
    var lead = o.lead ? '<p class="lead">' + o.lead + '</p>' : '';
    return '<section class="' + cls + '"' + (o.id ? ' id="' + VHS.esc(o.id) + '"' : '') + '>' +
      head + lead + (o.body || '') + (o.foot || '') + '</section>';
  };
  VHS.kpi = function (label, value, sub, cls) {
    return '<div class="kpi ' + (cls || '') + '"><div class="k">' + VHS.esc(label) +
      '</div><div class="v">' + value + '</div><div class="s">' + (sub || '') + '</div></div>';
  };
  VHS.table = function (headers, rows, opt) {
    opt = opt || {};
    var h = '<div class="tblwrap"><table class="' + (opt.cls || '') + '"><thead><tr>';
    headers.forEach(function (x) {
      var label = (typeof x === 'string') ? x : x.label;
      var cls = (typeof x === 'object' && x.num) ? ' class="num"' : '';
      h += '<th' + cls + '>' + VHS.esc(label) + '</th>';
    });
    h += '</tr></thead><tbody>';
    rows.forEach(function (r) {
      h += '<tr>';
      r.forEach(function (c) {
        if (c && typeof c === 'object' && c.html !== undefined) {
          h += '<td' + (c.cls ? ' class="' + c.cls + '"' : '') + '>' + c.html + '</td>';
        } else {
          h += '<td>' + (c === null || c === undefined ? '—' : c) + '</td>';
        }
      });
      h += '</tr>';
    });
    h += '</tbody></table></div>';
    return h;
  };
  VHS.kv = function (pairs) {
    var h = '<dl class="kv">';
    pairs.forEach(function (p) {
      h += '<dt>' + VHS.esc(p[0]) + '</dt><dd>' + (p[2] === 'html' ? p[1] : VHS.esc(p[1])) + '</dd>';
    });
    return h + '</dl>';
  };
  VHS.banner = function (kind, title, body) {
    var icon = { info: 'i', warn: '!', bad: '×', ok: '✓' }[kind] || 'i';
    return '<div class="banner ' + kind + '"><span class="bicon">' + icon + '</span><div><b>' +
      title + '</b>' + (body ? '<br>' + body : '') + '</div></div>';
  };
  VHS.empty = function (msg) { return '<div class="empty">' + msg + '</div>'; };
  VHS.ul = function (items) {
    return '<ul class="ul">' + items.map(function (x) { return '<li>' + x + '</li>'; }).join('') + '</ul>';
  };

  /* ---------------- HTTP ---------------- */
  VHS.api = async function (path, opts) {
    var init = Object.assign({ credentials: 'same-origin' }, opts || {});
    var r = await fetch(path, init);
    var text = await r.text();
    var data;
    try { data = JSON.parse(text); } catch (e) { data = { raw: text }; }
    if (!r.ok) {
      var err = new Error((data && data.message) || ('HTTP ' + r.status));
      err.status = r.status;
      err.body = data;
      throw err;
    }
    return data;
  };
  VHS.get = async function (path) {
    if (VHS.cache.has(path)) return VHS.cache.get(path);
    var token=VHS.state.token, dataset=VHS.state.dataset;
    var d = await VHS.api(path);
    if(token!==VHS.state.token || dataset!==VHS.state.dataset){var stale=new Error('STALE_DATASET_RESPONSE');stale.stale=true;throw stale;}
    VHS.cache.set(path, d);
    return d;
  };
  VHS.clearCache = function () { VHS.cache.clear(); };

  /* ---------------- router ---------------- */
  var LAYERS = ['overview', 'layers', 'data', 'model', 'results', 'evidence'];
  VHS.parse = function () {
    var raw = location.hash.replace(/^#/, '');
    if (!raw) raw = '/overview';
    var parts = raw.split('?');
    var segs = parts[0].split('/').filter(function (s) { return s.length; });
    var q = {};
    if (parts[1]) {
      parts[1].split('&').forEach(function (kv) {
        if (!kv) return;
        var i = kv.indexOf('=');
        var k = i < 0 ? kv : kv.slice(0, i);
        var v = i < 0 ? '' : decodeURIComponent(kv.slice(i + 1));
        q[k] = v;
      });
    }
    var layer = segs[0] || 'overview';
    if (LAYERS.indexOf(layer) < 0) layer = 'overview';
    return { layer: layer, sub: segs[1] || null, extra: segs.slice(2), q: q };
  };
  VHS.href = function (layer, sub, params) {
    var q = Object.assign({ dataset: VHS.state.dataset }, params || {});
    if(VHS.state.dataset==='LAMAH_CE_PUBLIC_V1'){
      var pub={kind:VHS.state.publicKind,model:VHS.state.publicModel,start:VHS.state.publicStart,end:VHS.state.publicEnd,mapmode:VHS.state.publicMapMode,report:VHS.state.publicReport};
      q=Object.assign(pub,q);
    }
    if (q.station === undefined && VHS.state.station) q.station = VHS.state.station;
    var keys = Object.keys(q).filter(function (k) { return q[k] !== null && q[k] !== undefined && q[k] !== ''; });
    var qs = keys.map(function (k) { return k + '=' + encodeURIComponent(q[k]); }).join('&');
    return '#/' + layer + (sub ? '/' + sub : '') + (qs ? '?' + qs : '');
  };
  VHS.go = function (layer, sub, params) {
    location.hash = VHS.href(layer, sub, params);
  };

  VHS.setDataset = function (ds) {
    ++VHS.state.token; VHS.clearCache();
    VHS.state.dataset = ds;
    VHS.state.station = null;
    VHS.state.publicKind='TEMPORAL_HOLDOUT';VHS.state.publicModel='P2-L1';VHS.state.publicStart='2015-01';VHS.state.publicEnd='2017-12';VHS.state.publicMapMode='nse';VHS.state.publicReport='p4_report';
    document.getElementById('view').innerHTML=VHS.loading('切换数据集，已清除旧结果');
    document.getElementById('side').innerHTML='';
    var ctx = VHS.parse();
    location.hash = VHS.href(ctx.layer, ctx.sub, { station: null });
  };

  var NAV_LABEL = {
    overview: '研究概览', layers: '空间图层', data: '数据层',
    model: '模型层', results: '结果层'
  };
  function paintNav(layer) {
    var items = document.querySelectorAll('#nav a');
    Array.prototype.forEach.call(items, function (a) {
      var k = a.getAttribute('data-nav');
      if (k === layer) a.className += ' on';
      else a.className = a.className.replace(' on', '');
    });
    var dsb = document.querySelectorAll('#dsSwitch button');
    Array.prototype.forEach.call(dsb, function (b) {
      var on = b.getAttribute('data-ds') === VHS.state.dataset;
      if (on) b.className = 'on'; else b.className = '';
    });
    document.title = 'VHS v0.6 · ' + (NAV_LABEL[layer] || '') + ' · 虚拟水文站四层科研平台';
  }

  function loadingHtml(msg) {
    return '<div class="loading"><span class="spin"></span>' + VHS.esc(msg || '载入中…') + '</div>';
  }
  VHS.loading = loadingHtml;

  VHS.render = async function () {
    var ctx = VHS.parse();
    var incoming=ctx.q.dataset?ctx.q.dataset.toUpperCase():VHS.state.dataset;
    if(incoming!==VHS.state.dataset){++VHS.state.token;VHS.clearCache();VHS.state.station=null;VHS.state.publicKind='TEMPORAL_HOLDOUT';VHS.state.publicModel='P2-L1';VHS.state.publicStart='2015-01';VHS.state.publicEnd='2017-12';VHS.state.publicMapMode='nse';VHS.state.publicReport='p4_report';}
    VHS.state.dataset=incoming;
    if(incoming==='LAMAH_CE_PUBLIC_V1'){
      if(ctx.q.kind)VHS.state.publicKind=ctx.q.kind;
      if(ctx.q.model)VHS.state.publicModel=ctx.q.model;
      if(ctx.q.start)VHS.state.publicStart=ctx.q.start;
      if(ctx.q.end)VHS.state.publicEnd=ctx.q.end;
      if(ctx.q.mapmode)VHS.state.publicMapMode=ctx.q.mapmode;
      if(ctx.q.report)VHS.state.publicReport=ctx.q.report;
    }
    if (ctx.q.station !== undefined) VHS.state.station = ctx.q.station || null;
    VHS.state.layer = ctx.layer;
    paintNav(ctx.layer);
    var view = document.getElementById('view');
    var side = document.getElementById('side');
    view.innerHTML = loadingHtml();
    side.innerHTML = '';
    var token = ++VHS.state.token;
    try {
      var fn = VHS.views[ctx.layer] || VHS.views.overview;
      var out = await fn(ctx);
      if (token !== VHS.state.token) return;
      view.innerHTML = out.html;
      side.innerHTML = out.side || '';
      if (typeof out.mount === 'function') out.mount(view, ctx);
    } catch (e) {
      if (token !== VHS.state.token) return;
      view.innerHTML = '<div class="err"><b>载入失败</b><br>' + VHS.esc(e.message) +
        (e.status ? '（HTTP ' + e.status + '）' : '') + '</div>';
      side.innerHTML = '';
    }
    if (window.innerWidth < 900) { /* avoid jumpy scroll on narrow screens */ }
  };

  /* ---------------- series helpers ---------------- */
  VHS.monthIdx = function (t) {
    var p = String(t).split('-');
    return (+p[0]) * 12 + (+p[1]) - 1;
  };
  VHS.monthLabel = function (t) {
    var p = String(t).split('-');
    return p[0] + '-' + p[1];
  };

  function niceMax(v) {
    if (!v || v <= 0) return 1;
    var e = Math.pow(10, Math.floor(Math.log(v) / Math.LN10));
    var f = v / e;
    var n = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
    return n * e;
  }
  function ticks(min, max, n) {
    var out = [];
    for (var i = 0; i <= n; i++) out.push(min + (max - min) * i / n);
    return out;
  }

  /* generic line chart; null values are gaps, never zero */
  VHS.lineChart = function (o) {
    var W = 1000, H = o.height || 320;
    var padL = 58, padR = 20, padT = o.yLabel ? 26 : 14, padB = 40;
    var pts = o.points || [];
    var vals = [];
    pts.forEach(function (p) {
      if (p.value !== null && p.value !== undefined && isFinite(p.value) && !p.skip) vals.push(p.value);
    });
    var ymin = (o.ymin !== undefined) ? o.ymin : 0;
    var ymax = (o.ymax !== undefined) ? o.ymax : (vals.length ? niceMax(Math.max.apply(null, vals)) : 1);
    if (ymax === ymin) ymax = ymin + 1;
    var n = pts.length;
    function X(i) { return padL + (W - padL - padR) * (n <= 1 ? 0.5 : i / (n - 1)); }
    function Y(v) { return padT + (H - padT - padB) * (1 - (v - ymin) / (ymax - ymin)); }
    var s = '<div class="chart"><svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' +
      VHS.esc(o.aria || '时间序列图') + '">';
    /* no-record-year bands */
    if (o.bandStatus) {
      var start = -1;
      pts.forEach(function (p, i) {
        var bad = p.status === o.bandStatus;
        if (bad && start < 0) start = i;
        if (!bad && start >= 0) {
          s += band(start, i - 1);
          start = -1;
        }
      });
      if (start >= 0) s += band(start, n - 1);
    }
    function band(a, b) {
      var x0 = X(a) - 2, x1 = X(b) + 2;
      var w = Math.max(2, x1 - x0);
      return '<rect x="' + x0.toFixed(1) + '" y="' + padT + '" width="' + w.toFixed(1) +
        '" height="' + (H - padT - padB) + '" fill="#f7e9e9" opacity="0.62"></rect>';
    }
    /* grid + y labels */
    var yts = ticks(ymin, ymax, 4);
    yts.forEach(function (v) {
      var y = Y(v);
      s += '<line class="grid" x1="' + padL + '" y1="' + y.toFixed(1) + '" x2="' + (W - padR) +
        '" y2="' + y.toFixed(1) + '"></line>';
      s += '<text class="tick" x="' + (padL - 8) + '" y="' + (y + 3).toFixed(1) +
        '" text-anchor="end">' + VHS.num(v, 0) + '</text>';
    });
    s += '<line class="axis" x1="' + padL + '" y1="' + (H - padB) + '" x2="' + (W - padR) +
      '" y2="' + (H - padB) + '"></line>';
    s += '<line class="axis" x1="' + padL + '" y1="' + padT + '" x2="' + padL + '" y2="' +
      (H - padB) + '"></line>';
    /* x labels at January */
    var lastLabel = -99;
    pts.forEach(function (p, i) {
      if (p.month === 1 && (i - lastLabel) >= 12) {
        lastLabel = i;
        s += '<text class="tick" x="' + X(i).toFixed(1) + '" y="' + (H - padB + 15) +
          '" text-anchor="middle">' + p.year + '</text>';
        s += '<line class="grid" x1="' + X(i).toFixed(1) + '" y1="' + padT + '" x2="' +
          X(i).toFixed(1) + '" y2="' + (H - padB) + '"></line>';
      }
    });
    if (o.yLabel) {
      s += '<text class="lbl" x="' + padL + '" y="12" text-anchor="start">' + VHS.esc(o.yLabel) + '</text>';
    }
    s += '<text class="lbl" x="' + (W - padR) + '" y="' + (H - 6) + '" text-anchor="end">' +
      VHS.esc(o.xLabel || '时间（年-月）') + '</text>';
    /* observed polyline with gaps */
    var segs = [], cur = [];
    pts.forEach(function (p, i) {
      var ok = p.value !== null && p.value !== undefined && isFinite(p.value) && !p.skip;
      if (ok) cur.push([X(i), Y(p.value)]);
      else if (cur.length) { segs.push(cur); cur = []; }
    });
    if (cur.length) segs.push(cur);
    segs.forEach(function (seg) {
      if (seg.length === 1) {
        s += '<circle class="pt" cx="' + seg[0][0].toFixed(1) + '" cy="' + seg[0][1].toFixed(1) + '" r="2.2"></circle>';
        return;
      }
      var d = seg.map(function (q, k) { return (k ? 'L' : 'M') + q[0].toFixed(1) + ' ' + q[1].toFixed(1); }).join(' ');
      s += '<path class="obs" d="' + d + '"></path>';
    });
    /* suspect markers along the baseline (not drawn as values) */
    if (o.markSuspect) {
      pts.forEach(function (p, i) {
        if (p.status === 'SUSPECT') {
          s += '<line x1="' + X(i).toFixed(1) + '" y1="' + (H - padB) + '" x2="' + X(i).toFixed(1) +
            '" y2="' + (H - padB - 7) + '" stroke="#9a6400" stroke-width="2" opacity="0.55"></line>';
        }
      });
    }
    s += '</svg></div>';
    return s;
  };

  /* bar chart for meteorology (supports negative values) */
  VHS.barChart = function (o) {
    var W = 1000, H = o.height || 220;
    var padL = 54, padR = 18, padT = 12, padB = 34;
    var pts = o.points || [];
    var vals = pts.filter(function (p) { return p.value !== null && isFinite(p.value); })
      .map(function (p) { return p.value; });
    var lo = Math.min.apply(null, vals.concat([0]));
    var hi = Math.max.apply(null, vals.concat([0]));
    if (hi === lo) hi = lo + 1;
    var n = pts.length || 1;
    var bw = (W - padL - padR) / n;
    function Y(v) { return padT + (H - padT - padB) * (1 - (v - lo) / (hi - lo)); }
    var s = '<div class="chart"><svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' +
      VHS.esc(o.aria || '柱状图') + '">';
    ticks(lo, hi, 4).forEach(function (v) {
      var y = Y(v);
      s += '<line class="grid" x1="' + padL + '" y1="' + y.toFixed(1) + '" x2="' + (W - padR) +
        '" y2="' + y.toFixed(1) + '"></line>';
      s += '<text class="tick" x="' + (padL - 8) + '" y="' + (y + 3).toFixed(1) +
        '" text-anchor="end">' + VHS.num(v, 0) + '</text>';
    });
    var zy = Y(0);
    s += '<line class="axis" x1="' + padL + '" y1="' + zy.toFixed(1) + '" x2="' + (W - padR) +
      '" y2="' + zy.toFixed(1) + '"></line>';
    pts.forEach(function (p, i) {
      var x = padL + bw * i + bw * 0.18;
      var w = bw * 0.64;
      if (p.value === null || !isFinite(p.value)) {
        s += '<line x1="' + (x + w / 2).toFixed(1) + '" y1="' + (zy - 4).toFixed(1) + '" x2="' +
          (x + w / 2).toFixed(1) + '" y2="' + (zy + 4).toFixed(1) + '" stroke="#a83232" stroke-width="1.4"></line>';
        return;
      }
      var y = Y(p.value);
      var h = Math.abs(y - zy);
      var top = Math.min(y, zy);
      s += '<rect x="' + x.toFixed(1) + '" y="' + top.toFixed(1) + '" width="' + w.toFixed(1) +
        '" height="' + Math.max(1, h).toFixed(1) + '" fill="' + (o.color || '#1f5fa8') + '" opacity="0.75"></rect>';
      if (n <= 14) {
        s += '<text class="tick" x="' + (x + w / 2).toFixed(1) + '" y="' + (H - padB + 14) +
          '" text-anchor="middle">' + VHS.esc(p.label) + '</text>';
      }
    });
    s += '<text class="lbl" x="' + (padL - 40) + '" y="' + (padT + 8) +
      '" transform="rotate(-90 ' + (padL - 40) + ' ' + (padT + 8) + ')" text-anchor="end">' +
      VHS.esc(o.yLabel || '') + '</text>';
    s += '</svg></div>';
    return s;
  };

  /* station dot map in projected metres (never lat/lon degrees) */
  VHS.mapSvg = function (o) {
    var W = 1000, H = o.height || 520;
    var pts = o.points || [];
    var b = o.bounds;
    if (!b || !pts.length) return '';
    var pad = 18;
    var sx = (W - pad * 2) / Math.max(1, (b.xmax - b.xmin));
    var sy = (H - pad * 2) / Math.max(1, (b.ymax - b.ymin));
    var sc = Math.min(sx, sy);
    var ox = (W - (b.xmax - b.xmin) * sc) / 2;
    var oy = (H - (b.ymax - b.ymin) * sc) / 2;
    function X(x) { return ox + (x - b.xmin) * sc; }
    function Y(y) { return H - oy - (y - b.ymin) * sc; }
    var s = '<div class="chart"><svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' +
      VHS.esc(o.aria || '站点投影散点图') + '">';
    s += '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="none" stroke="#e3eaf2"></rect>';
    for (var gx = 0; gx <= 4; gx++) {
      var x = pad + (W - pad * 2) * gx / 4;
      s += '<line class="grid" x1="' + x + '" y1="' + pad + '" x2="' + x + '" y2="' + (H - pad) + '"></line>';
    }
    for (var gy = 0; gy <= 4; gy++) {
      var y = pad + (H - pad * 2) * gy / 4;
      s += '<line class="grid" x1="' + pad + '" y1="' + y + '" x2="' + (W - pad) + '" y2="' + y + '"></line>';
    }
    pts.forEach(function (p) {
      var cls = 'mapdot';
      if (o.target && String(p.id) === String(o.target)) cls += ' tgt';
      if (o.selected && String(p.id) === String(o.selected)) cls += ' sel';
      s += '<circle class="' + cls + '" data-id="' + p.id + '" cx="' + X(p.x).toFixed(1) + '" cy="' +
        Y(p.y).toFixed(1) + '" r="' + (o.r || 3.1) + '"><title>' + VHS.esc((p.uid || p.id) + ' ' +
          (p.name || '') + ' ' + (p.candidate_status || '')) + '</title></circle>';
    });
    s += '<text class="tick" x="' + pad + '" y="' + (H - 4) + '">x / y = EPSG:3035 投影米（不是经纬度）</text>';
    s += '</svg></div>';
    return s;
  };

  /* synthetic preview map (local 0-100 box); strictly separate from the real map */
  VHS.synthSvg = function (syn, o) {
    o = o || {};
    var W = 520, H = 380, pad = 20;
    var box = 100;
    function X(v) { return pad + (W - pad * 2) * (v / box); }
    function Y(v) { return H - pad - (H - pad * 2) * (v / box); }
    var s = '<div class="chart"><svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="合成预览（非真实地理）">';
    s += '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#fdfaf3" stroke="#eddcb8"></rect>';
    (syn.layers || []).forEach(function (L) {
      var gj = L.geojson || {};
      (gj.features || []).forEach(function (f) {
        var g = f.geometry || {};
        var coords = g.coordinates;
        if (!coords) return;
        if (g.type === 'LineString') {
          s += '<path class="synth" d="' + coords.map(function (c, i) {
            return (i ? 'L' : 'M') + X(c[0]).toFixed(1) + ' ' + Y(c[1]).toFixed(1);
          }).join(' ') + '"></path>';
        } else if (g.type === 'MultiLineString') {
          coords.forEach(function (line) {
            s += '<path class="synth" d="' + line.map(function (c, i) {
              return (i ? 'L' : 'M') + X(c[0]).toFixed(1) + ' ' + Y(c[1]).toFixed(1);
            }).join(' ') + '"></path>';
          });
        }
      });
    });
    (syn.stations || []).forEach(function (st) {
      s += '<circle cx="' + X(st.pos[0]).toFixed(1) + '" cy="' + Y(st.pos[1]).toFixed(1) +
        '" r="5" fill="#b06a2c" opacity="0.9"></circle>';
      s += '<text class="tick" x="' + (X(st.pos[0]) + 8).toFixed(1) + '" y="' + (Y(st.pos[1]) + 4).toFixed(1) +
        '" fill="#8a531f">' + VHS.esc(st.id + ' · ' + st.role) + '</text>';
    });
    s += '<text class="watermark" x="' + pad + '" y="' + (pad + 14) + '">SYNTHETIC PREVIEW · 非真实地理</text>';
    s += '</svg></div>';
    return s;
  };

  /* minimal markdown renderer for the generated report (headings, lists, tables) */
  VHS.md = function (text) {
    var lines = String(text || '').split(String.fromCharCode(10));
    var out = [], i = 0;
    while (i < lines.length) {
      var ln = lines[i];
      if (/^### /.test(ln)) { out.push('<h3>' + VHS.esc(ln.slice(4)) + '</h3>'); i++; continue; }
      if (/^## /.test(ln)) { out.push('<h2>' + VHS.esc(ln.slice(3)) + '</h2>'); i++; continue; }
      if (/^# /.test(ln)) { out.push('<h2>' + VHS.esc(ln.slice(2)) + '</h2>'); i++; continue; }
      if (/^\|/.test(ln)) {
        var rows = [];
        while (i < lines.length && /^\|/.test(lines[i])) { rows.push(lines[i]); i++; }
        var body = rows.filter(function (r) { return !/^\|[\s-|]+\|?$/.test(r); });
        out.push('<table>');
        body.forEach(function (r, k) {
          var cells = r.split('|').slice(1, -1).map(function (c) { return c.trim(); });
          out.push('<tr>' + cells.map(function (c) {
            return (k === 0 ? '<th>' : '<td>') + VHS.esc(c) + (k === 0 ? '</th>' : '</td>');
          }).join('') + '</tr>');
        });
        out.push('</table>');
        continue;
      }
      if (/^- /.test(ln)) {
        out.push('<ul>');
        while (i < lines.length && /^- /.test(lines[i])) {
          out.push('<li>' + VHS.esc(lines[i].slice(2)) + '</li>'); i++;
        }
        out.push('</ul>');
        continue;
      }
      if (ln.trim() === '') { i++; continue; }
      out.push('<p>' + VHS.esc(ln) + '</p>');
      i++;
    }
    return '<div class="report">' + out.join('') + '</div>';
  };

  /* ---------------- shared sidebar ---------------- */
  VHS.sideCards = function (opts) {
    var h = '';
    if (opts.dataset) {
      var dsInfo = opts.dataset;
      h += VHS.card({
        title: '当前数据集',
        tight: true,
        body: VHS.kv([
          ['数据集', dsInfo.id],
          ['名称', dsInfo.title],
          ['CRS', dsInfo.crs],
          ['授权模式', dsInfo.authorization || '—'],
          ['快照', opts.snapshotId || '—']
        ]) + '<p class="notice">' + VHS.esc(opts.snapshotNote || '') + '</p>'
      });
    }
    if (opts.permissions) {
      var p = opts.permissions;
      h += VHS.card({
        title: '权限域',
        tight: true,
        body: VHS.kv([
          ['历史观测展示', p.HISTORICAL_OBSERVATION_DISPLAY],
          ['未来模型输入', p.FUTURE_MODEL_INPUT],
          ['模型预测', p.PREDICTION],
          ['数据导岀'.replace('岀', '出'), p.DATA_EXPORT]
        ]) + '<p class="notice">展示历史观测不等于允许模型输入或预测。</p>'
      });
    }
    if (opts.model) {
      h += VHS.card({
        title: '模型状态',
        tight: true,
        body: VHS.kv([
          ['未实现', String(opts.model.implemented_models || 0)],
          ['未训练', String(opts.model.trained_models || 0)],
          ['已评估', String(opts.model.evaluated_models || 0)],
          ['注册基线', String(opts.model.registered_models || 0)]
        ]) + '<p class="notice">' + VHS.esc(opts.model.notice || '') + '</p>'
      });
    }
    if (opts.links && opts.links.length) {
      h += VHS.card({
        title: '快捷入口',
        tight: true,
        body: '<div class="chips">' + opts.links.map(function (l) {
          return '<a class="btn small" href="' + l.href + '">' + VHS.esc(l.label) + '</a>';
        }).join('') + '</div>'
      });
    }
    return h;
  };

  /* ---------------- shared ui pieces ---------------- */
  VHS.subnav = function (layer, items, active) {
    return '<nav class="subnav">' + items.map(function (it) {
      var on = it.key === active ? ' class="on"' : '';
      return '<a href="' + VHS.href(layer, it.key === 'index' ? null : it.key, it.params || {}) + '"' + on + '>' +
        VHS.esc(it.label) + '</a>';
    }).join('') + '</nav>';
  };
  VHS.stationSelect = function (id, stations, selected) {
    var h = '<select id="' + id + '">';
    stations.forEach(function (s) {
      var uid = s.uid || ('SYRDARYA:' + s.code);
      var label = uid + (s.name ? ' · ' + s.name : '') + (s.years ? '（' + s.years.length + ' 年）' : '');
      h += '<option value="' + VHS.esc(uid) + '"' + (uid === selected ? ' selected' : '') + '>' +
        VHS.esc(label) + '</option>';
    });
    return h + '</select>';
  };
  VHS.select = function (id, options, selected) {
    var h = '<select id="' + id + '">';
    options.forEach(function (o) {
      var v = (typeof o === 'object') ? o.value : o;
      var t = (typeof o === 'object') ? o.label : o;
      h += '<option value="' + VHS.esc(v) + '"' + (String(v) === String(selected) ? ' selected' : '') + '>' +
        VHS.esc(t) + '</option>';
    });
    return h + '</select>';
  };
  VHS.onChange = function (root, id, fn) {
    var el = root.querySelector('#' + id);
    if (el) el.addEventListener('change', function () { fn(el.value); });
    return el;
  };

  /* ---------------- boot ---------------- */
  async function boot() {
    var dsb = document.querySelectorAll('#dsSwitch button');
    Array.prototype.forEach.call(dsb, function (b) {
      b.addEventListener('click', function () {
        var ds = b.getAttribute('data-ds');
        if (ds !== VHS.state.dataset) VHS.setDataset(ds);
      });
    });
    window.addEventListener('hashchange', function () { VHS.render(); });
    try {
      var h = await VHS.get('/api/vhs/health');
      var el = document.getElementById('topStatus');
      var ok = h.status === 'ok';
      el.innerHTML = '<span class="dot ' + (ok ? '' : 'bad') + '"></span>' +
        'v' + VHS.esc(h.app_version || '') + ' · 快照 ' +
        VHS.esc((h.syrdarya_snapshot && h.syrdarya_snapshot.snapshot_id) || '—');
      var badge = document.getElementById('verBadge');
      if (badge) badge.textContent = 'v' + (h.app_version || '0.6.0');
    } catch (e) {
      document.getElementById('topStatus').innerHTML = '<span class="dot bad"></span>服务不可用';
    }
    if (!location.hash) location.hash = '#/overview';
    VHS.render();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else { boot(); }
})();
