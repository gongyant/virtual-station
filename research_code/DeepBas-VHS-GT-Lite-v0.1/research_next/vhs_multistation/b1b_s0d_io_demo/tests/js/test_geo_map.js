/* R1（D7）坐标轴序一致性测试（node；无第三方依赖）。SYNTHETIC / PROPOSED。
   用法：node tests/js/test_geo_map.js
   对 geo_map.js（前端实际加载的纯函数）运行 tests/fixtures/axis_cases.json 中由 Python 生成的同一批用例，
   并静态核对 app.js 绘图确实调用 VHSGeo.makeProjector。 */
"use strict";
var fs = require("fs"), path = require("path");
var ROOT = path.join(__dirname, "..", "..");
var geo = require(path.join(ROOT, "geo_map.js"));
var fx = JSON.parse(fs.readFileSync(path.join(ROOT, "tests", "fixtures", "axis_cases.json"), "utf8"));
var passed = 0, failed = [];
function check(name, cond) { if (cond) { passed += 1; } else { failed.push(name); } }
function close(a, b) { return Math.abs(a - b) < 1e-9; }

check("default_box_equal", JSON.stringify(geo.DEFAULT_BOX) === JSON.stringify(fx.box));
fx.projector_cases.forEach(function (c) {
  var p = geo.makeProjector(c.points, fx.box);
  c.points.forEach(function (q, i) {
    var xy = p(q.lat, q.lon);
    check(c.name + "[" + i + "]", close(xy[0], c.expected[i][0]) && close(xy[1], c.expected[i][1]));
  });
});
var card = fx.projector_cases[0], pc = geo.makeProjector(card.points, fx.box);
var O = pc(card.points[0].lat, card.points[0].lon), E = pc(card.points[1].lat, card.points[1].lon);
var N = pc(card.points[2].lat, card.points[2].lon);
check("east_has_larger_x", E[0] > O[0]);
check("east_same_y", close(E[1], O[1]));
check("north_has_smaller_svg_y", N[1] < O[1]);
check("north_same_x", close(N[0], O[0]));
fx.crs_accept.forEach(function (c) {
  var ll = geo.latLonFromCrs(c.crs);
  check("accept_" + c.name, ll.lat === c.lat && ll.lon === c.lon);
});
// API 载荷 -> 前端映射：AX_E 在 AX_O 正东，AX_N 在 AX_O 正北
var pts = fx.crs_accept.slice(0, 3).map(function (c) { return geo.latLonFromCrs(c.crs); });
var pa = geo.makeProjector(pts, fx.box);
var o = pa(pts[0].lat, pts[0].lon), e = pa(pts[1].lat, pts[1].lon), n = pa(pts[2].lat, pts[2].lon);
check("api_east", e[0] > o[0] && close(e[1], o[1]));
check("api_north", n[1] < o[1] && close(n[0], o[0]));
fx.crs_reject.forEach(function (c) {
  var msg = null;
  try { geo.latLonFromCrs(c.crs); } catch (err) { msg = err.message; }
  check("reject_" + c.name, msg === c.error);
});
var app = fs.readFileSync(path.join(ROOT, "app.js"), "utf8");
check("app_uses_makeProjector", app.indexOf("GEO.makeProjector(g.nodes, GEO.DEFAULT_BOX)") >= 0);
check("app_projects_lat_lon", app.indexOf("project(n.lat, n.lon)") >= 0);
check("app_no_local_lon_mapping", app.indexOf("function X(lon)") < 0);
var html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
check("html_loads_geo_before_app", html.indexOf('src="geo_map.js"') >= 0 &&
  html.indexOf('src="geo_map.js"') < html.indexOf('src="app.js"'));
console.log(JSON.stringify({ suite: "test_geo_map.js", node: process.version, passed: passed, failed: failed }));
process.exit(failed.length ? 1 : 0);
