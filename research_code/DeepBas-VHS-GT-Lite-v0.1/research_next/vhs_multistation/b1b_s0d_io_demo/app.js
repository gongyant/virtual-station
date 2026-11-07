/* VHS-NEXT-B1B-S0D 前端逻辑（无框架、无外链；SYNTHETIC_DEMO_ONLY；PROPOSED：非 DeepBas 官方协议，未完成正式集成）
   R1：坐标映射改用 geo_map.js 中的纯函数 VHSGeo（x <- 经度，y <- 纬度翻转）；显示 operation / data_mode /
   science_stage / admission_status / certification_status；s0d_status 仅作兼容别名显示。 */
"use strict";
(function () {
  var SNAP = window.VHS_OFFLINE_SNAPSHOT || null;
  var GEO = window.VHSGeo;
  var SVGNS = "http://www.w3.org/2000/svg"; // XML 命名空间标识符，不发起网络请求
  var state = { online: false };
  var FORCE_OFFLINE = /[?&]offline=1/.test(window.location.search) || window.location.protocol === "file:";
  var ROLE_COLORS = {
    TARGET: "#111111", TARGET_IN_CYCLE: "#111111", UPSTREAM_PASS: "#2d6a4f", UPSTREAM_CONDITIONAL: "#e07a00",
    UPSTREAM_BLOCKED: "#b00020", DOWNSTREAM: "#4361ee", SAME_SYSTEM_NOT_UPSTREAM: "#9aa0a6",
    NONCONNECTED_CONTROL: "#00a6d6", CYCLE: "#d00000", OTHER: "#cccccc"
  };
  var ROLE_LABELS = {
    TARGET: "目标站", UPSTREAM_PASS: "上游(路径确定)", UPSTREAM_CONDITIONAL: "上游(路径含不确定边)",
    UPSTREAM_BLOCKED: "上游(拓扑阻断)", DOWNSTREAM: "下游(非上游)", SAME_SYSTEM_NOT_UPSTREAM: "同水系非上游",
    NONCONNECTED_CONTROL: "不连通对照候选", CYCLE: "环路节点"
  };

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, text) {
    var n = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (text !== undefined) { n.textContent = text; }
    return n;
  }
  function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } }
  function h(tag, text, cls) {
    var n = document.createElement(tag);
    if (text !== undefined) { n.textContent = text; }
    if (cls) { n.className = cls; }
    return n;
  }

  function setMode(online, why) {
    state.online = online;
    var b = $("modeBanner");
    b.className = online ? "online" : "offline";
    b.textContent = online
      ? "在线模式：已连接本地 Python 服务（" + window.location.host + "），所有结果由服务实时计算 · SYNTHETIC_DEMO_ONLY"
      : "离线预览：未连接本地服务（" + why + "），显示由程序预先生成的内嵌合成快照 offline_snapshot.js · SYNTHETIC_DEMO_ONLY";
  }

  function stationList() {
    if (SNAP && SNAP.stations) { return SNAP.stations; }
    return [{ station_id: "DEMO_TARGET_A", station_name: "SYNTHETIC 目标断面 A", role: "TARGET" }];
  }

  function apiUrl(fn, sid, start, end) {
    var e = encodeURIComponent(sid);
    if (fn === "station") { return "/api/vhs/stations/" + e; }
    if (fn === "network") { return "/api/vhs/stations/" + e + "/network"; }
    if (fn === "audit") { return "/api/vhs/stations/" + e + "/audit"; }
    return "/api/vhs/synthetic-demo?station_id=" + e + "&start=" + encodeURIComponent(start) +
      "&end=" + encodeURIComponent(end);
  }

  function callOnline(fn, sid, start, end, extra) {
    var req;
    if (fn === "predict") {
      var body = { target_station_id: sid };
      if (start) { body.start = start; }
      if (end) { body.end = end; }
      Object.keys(extra || {}).forEach(function (k) { if (!(k in body)) { body[k] = extra[k]; } });
      req = fetch("/api/vhs/predict", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) });
    } else {
      req = fetch(apiUrl(fn, sid, start, end));
    }
    return req.then(function (r) {
      return r.json().then(function (j) { return { http: r.status, body: j, source: "online" }; });
    });
  }

  function callOffline(fn, sid, start, end) {
    var key = fn + "|" + sid;
    var hit = SNAP && SNAP.responses ? SNAP.responses[key] : null;
    if (!hit) {
      return Promise.resolve({ http: 0, source: "offline", body: { offline_note:
        "离线预览快照中没有该条目（" + key + "）。请启动本地服务以实时计算。", data_class: "SYNTHETIC_DEMO_ONLY",
        prediction: null } });
    }
    var out = { http: hit[0], body: hit[1], source: "offline" };
    if (fn === "demo" && SNAP.default_range && (start !== SNAP.default_range[0] || end !== SNAP.default_range[1])) {
      out.note = "离线快照只含默认时间范围 " + SNAP.default_range.join(" ~ ") + "，已显示默认范围结果";
    }
    return Promise.resolve(out);
  }

  function call(fn, sid, start, end, extra) {
    return state.online ? callOnline(fn, sid, start, end, extra) : callOffline(fn, sid, start, end);
  }

  function badge(status) {
    var s = String(status || "UNKNOWN");
    var cls = ["PASS", "CONDITIONAL", "BLOCKED", "UNKNOWN", "NOT_AUTHORIZED"].indexOf(s) >= 0 ? s
      : (s === "SYNTHETIC_DEMO_ONLY" ? "SYN" : "ERR");
    return h("span", s, "status " + cls);
  }

  function list(title, items) {
    var d = h("div");
    d.appendChild(h("b", title));
    var ul = h("ul");
    (items || []).forEach(function (t) { ul.appendChild(h("li", String(t))); });
    if (!items || !items.length) { ul.appendChild(h("li", "（无）")); }
    d.appendChild(ul);
    return d;
  }

  function renderMessages(res) {
    var box = $("msgBody");
    clear(box);
    var b = res.body || {};
    var top = h("div");
    top.appendChild(h("span", "HTTP " + (res.http || "-") + " · 来源：" + (res.source === "online" ? "本地服务" : "离线快照") + " · s0d_status（兼容别名，计划废弃）："));
    top.appendChild(badge(b.s0d_status || (b.error ? b.error.alias : "UNKNOWN")));
    top.appendChild(h("span", "  prediction = " + JSON.stringify(b.prediction === undefined ? null : b.prediction)));
    box.appendChild(top);
    var fields = h("div", "", "small");
    fields.id = "fieldLine";
    fields.textContent = "interface_status=" + (b.interface_status || "-") + " · operation=" + (b.operation || "-") +
      " · data_mode=" + (b.data_mode || "-") + " · science_stage=" + (b.science_stage || "-") +
      " · admission_status=" + (b.admission_status ? b.admission_status.status : "-") +
      " · certification_status=" + (b.certification_status || "-");
    box.appendChild(fields);
    if (b.interface_notice) { box.appendChild(h("p", b.interface_notice, "small")); }
    if (b.certification_note) { box.appendChild(h("p", b.certification_note, "small")); }
    if (b.coordinate_reference_system && GEO) {
      var cp = h("p", "", "small");
      cp.id = "coordLine";
      try {
        var ll = GEO.latLonFromCrs(b.coordinate_reference_system);
        cp.textContent = "目标站坐标（SYNTHETIC）：EPSG:4326，载荷轴序 [" +
          b.coordinate_reference_system.coordinate_axis_order_in_payload.join(", ") + "] = [" +
          b.coordinate_reference_system.coordinates.join(", ") + "] → 纬度 " + ll.lat + "°，经度 " + ll.lon +
          "°；示意图 x←经度（东→），y←纬度（北↑）";
      } catch (e) {
        cp.textContent = "坐标被拒绝：" + e.message + "（只接受 EPSG:4326 度、纬度/经度轴）";
      }
      box.appendChild(cp);
    }
    if (b.prediction_authorization_note) { box.appendChild(h("p", b.prediction_authorization_note, "small")); }
    if (res.note) { box.appendChild(h("p", res.note)); }
    if (b.offline_note) { box.appendChild(h("p", b.offline_note)); }
    if (b.error) {
      box.appendChild(list("错误", [b.error.alias + " → 旧契约码 " + b.error.code + "（" + b.error.name + "）",
        "reason_code: " + b.error.reason_code, "detail: " + b.error.detail]));
    }
    if (b.prediction_authorized) {
      box.appendChild(list("预测授权", [b.prediction_authorized.status + "：" + (b.prediction_authorized.reason || "")]));
    }
    if (b.admission_status) { box.appendChild(list("科学准入（合成规则）：" + b.admission_status.status, b.admission_status.reasons)); }
    if (b.topology_status) { box.appendChild(list("拓扑状态：" + b.topology_status.status, b.topology_status.reasons)); }
    if (b.s0d && b.s0d.predict) { box.appendChild(list("预测请求被拒绝的原因", b.s0d.predict.reasons.concat(
      ["已忽略的越权字段：" + (b.s0d.predict.override_attempts_ignored.join(", ") || "无")]))); }
    if (b.synthetic_display_data) { box.appendChild(h("p", b.synthetic_display_data.banner)); }
  }

  function drawLegend() {
    var lg = $("legend");
    clear(lg);
    Object.keys(ROLE_LABELS).forEach(function (k) {
      var s = h("span");
      var d = h("span", "", "dot");
      d.style.background = ROLE_COLORS[k];
      s.appendChild(d);
      s.appendChild(document.createTextNode(ROLE_LABELS[k]));
      lg.appendChild(s);
    });
  }

  function drawNetwork(net) {
    var svg = $("netSvg");
    clear(svg);
    var defs = el("defs");
    var mk = el("marker", { id: "arrow", viewBox: "0 0 10 10", refX: "19", refY: "5", markerWidth: "10",
      markerHeight: "10", markerUnits: "userSpaceOnUse", orient: "auto-start-reverse" });
    mk.appendChild(el("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#555" }));
    defs.appendChild(mk);
    svg.appendChild(defs);
    svg.appendChild(el("text", { x: "380", y: "200", "text-anchor": "middle", "font-size": "46", fill: "#000",
      "fill-opacity": "0.06", transform: "rotate(-12 380 200)" }, "SYNTHETIC_DEMO_ONLY"));
    if (!net || !net.graph_for_display) {
      svg.appendChild(el("text", { x: "20", y: "30", "font-size": "14" }, "无可显示的合成河网（错误响应或离线快照缺条目）"));
      return;
    }
    var g = net.graph_for_display, roles = net.display_roles || {};
    var project = GEO.makeProjector(g.nodes, GEO.DEFAULT_BOX);   // x <- 经度，y <- 纬度（翻转，北在上）
    var pos = {};
    g.nodes.forEach(function (n) { pos[n.id] = project(n.lat, n.lon); });
    var pathEdges = {};
    (net.upstream_nodes || []).forEach(function (u) { u.path_edge_ids.forEach(function (e) { pathEdges[e] = true; }); });
    g.edges.forEach(function (e) {
      var a = pos[e.from], b = pos[e.to];
      var color = e.kind === "artificial_transfer" ? "#7b2cbf" : "#555";
      var attrs = { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: color,
        "stroke-width": pathEdges[e.id] ? "4" : "1.5", "marker-end": "url(#arrow)" };
      if (e.snap_status !== "CERTIFIED") { attrs["stroke-dasharray"] = "6 4"; }
      if (e.kind === "artificial_transfer") { attrs["stroke-dasharray"] = "2 3"; }
      svg.appendChild(el("line", attrs));
      svg.appendChild(el("text", { x: (a[0] + b[0]) / 2 + 3, y: (a[1] + b[1]) / 2 - 3, "font-size": "10", fill: color }, e.id));
    });
    g.nodes.forEach(function (n) {
      var role = roles[n.id] || "OTHER";
      var p = pos[n.id];
      var c = el("circle", { cx: p[0], cy: p[1], r: role.indexOf("TARGET") === 0 ? 10 : 7,
        fill: ROLE_COLORS[role] || ROLE_COLORS.OTHER, stroke: role === "TARGET_IN_CYCLE" ? "#d00000" : "#fff",
        "stroke-width": role === "TARGET_IN_CYCLE" ? "3" : "1.5" });
      c.appendChild(el("title", {}, n.id + " · " + (ROLE_LABELS[role] || role)));
      svg.appendChild(c);
      svg.appendChild(el("text", { x: p[0] + 9, y: p[1] + 4, "font-size": "11", fill: "#222" }, n.id));
    });
    svg.appendChild(el("line", { x1: "735", y1: "60", x2: "735", y2: "22", stroke: "#333", "stroke-width": "2",
      "marker-end": "url(#arrow)" }));
    svg.appendChild(el("text", { x: "735", y: "74", "text-anchor": "middle", "font-size": "12", fill: "#333" }, "N"));
    svg.appendChild(el("text", { id: "axisLabel", x: "752", y: "356", "text-anchor": "end", "font-size": "10", fill: "#333" },
      "EPSG:4326 · x←经度（东→） · y←纬度（北↑） · 载荷轴序 [纬度, 经度]"));
    svg.appendChild(el("text", { x: "8", y: "372", "font-size": "11", fill: "#b00020" },
      "SYNTHETIC_DEMO_ONLY · " + g.graph_id + " · connection_status=" + net.connection_status +
      " · topology=" + (net.topology ? net.topology.status : "-")));
  }

  function drawSeries(sdd) {
    var svg = $("tsSvg");
    clear(svg);
    svg.appendChild(el("text", { x: "380", y: "130", "text-anchor": "middle", "font-size": "40", fill: "#000",
      "fill-opacity": "0.07" }, "SYNTHETIC_DEMO_ONLY"));
    if (!sdd || !sdd.values || !sdd.values.length) {
      svg.appendChild(el("text", { x: "20", y: "30", "font-size": "14" }, "无合成序列（仅 demo 功能返回 synthetic_display_data）"));
      $("tsNote").textContent = "prediction 字段恒为 null；本图只显示 synthetic_display_data。";
      return;
    }
    var v = sdd.values, n = v.length;
    var lo = Math.min.apply(null, v), hi = Math.max.apply(null, v);
    if (hi === lo) { hi = lo + 1; }
    function X(i) { return 60 + (n === 1 ? 320 : i / (n - 1) * 670); }
    function Y(y) { return 200 - (y - lo) / (hi - lo) * 170; }
    svg.appendChild(el("line", { x1: 60, y1: 200, x2: 735, y2: 200, stroke: "#888" }));
    svg.appendChild(el("line", { x1: 60, y1: 25, x2: 60, y2: 200, stroke: "#888" }));
    svg.appendChild(el("text", { x: "4", y: "30", "font-size": "10" }, hi.toFixed(1)));
    svg.appendChild(el("text", { x: "4", y: "200", "font-size": "10" }, lo.toFixed(1)));
    svg.appendChild(el("text", { x: "60", y: "218", "font-size": "10" }, sdd.time_index[0]));
    svg.appendChild(el("text", { x: "735", y: "218", "font-size": "10", "text-anchor": "end" }, sdd.time_index[n - 1]));
    var pts = v.map(function (y, i) { return X(i).toFixed(1) + "," + Y(y).toFixed(1); }).join(" ");
    svg.appendChild(el("polyline", { points: pts, fill: "none", stroke: "#8d6e00", "stroke-width": "2" }));
    v.forEach(function (y, i) { svg.appendChild(el("circle", { cx: X(i), cy: Y(y), r: 2.5, fill: "#8d6e00" })); });
    svg.appendChild(el("text", { x: "60", y: "236", "font-size": "11", fill: "#b00020" },
      "单位：" + sdd.unit + "（" + sdd.unit_note + "）· " + sdd.series_kind));
    $("tsNote").textContent = sdd.banner;
  }

  function run() {
    var sid = $("stationTxt").value.trim() || $("stationSel").value;
    var fn = $("funcSel").value, start = $("startDate").value, end = $("endDate").value;
    var extra = {};
    if (fn === "predict") {
      try { extra = JSON.parse($("predExtra").value || "{}"); } catch (e) { extra = { _unparsable_extra: true }; }
    }
    var startArg = (fn === "demo" || fn === "predict") ? start : null, endArg = (fn === "demo" || fn === "predict") ? end : null;
    return call(fn, sid, startArg, endArg, extra).then(function (res) {
      $("jsonOut").textContent = JSON.stringify(res.body, null, 1);
      renderMessages(res);
      drawSeries(res.body && res.body.synthetic_display_data);
      if (res.body && res.body.s0d && res.body.s0d.network) { drawNetwork(res.body.s0d.network); return; }
      return call("network", sid, null, null, {}).then(function (r2) {
        drawNetwork(r2.body && r2.body.s0d ? r2.body.s0d.network : null);
      });
    }).catch(function (err) {
      $("msgBody").textContent = "请求失败：" + err + "（若服务已停止，请刷新页面进入离线预览）";
    });
  }

  function init() {
    var sel = $("stationSel");
    stationList().forEach(function (s) {
      var o = document.createElement("option");
      o.value = s.station_id;
      o.textContent = s.station_id + " · " + s.station_name;
      sel.appendChild(o);
    });
    drawLegend();
    drawNetwork(null);
    drawSeries(null);
    $("runBtn").addEventListener("click", run);
    if (FORCE_OFFLINE || typeof fetch !== "function") {
      setMode(false, FORCE_OFFLINE ? "页面以 file:// 或 ?offline=1 打开" : "浏览器不支持 fetch");
      return run();
    }
    var ctl = typeof AbortController === "function" ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctl) { ctl.abort(); } }, 2500);
    fetch("/api/vhs/stations/DEMO_TARGET_A", ctl ? { signal: ctl.signal } : {}).then(function (r) {
      return r.json();
    }).then(function (j) {
      clearTimeout(timer);
      setMode(j && j.data_class === "SYNTHETIC_DEMO_ONLY", "服务响应异常");
      return run();
    }).catch(function () {
      clearTimeout(timer);
      setMode(false, "本地服务不可用");
      return run();
    });
  }

  if (typeof document !== "undefined") { document.addEventListener("DOMContentLoaded", init); }
}());
