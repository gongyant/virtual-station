/* VHS-NEXT-B1B-S0D-R1 坐标映射纯函数（无 DOM 依赖；浏览器与 node 均可运行；SYNTHETIC_DEMO_ONLY；PROPOSED）。
   约定（决策 D7，见 interface_decisions.md）：
   - API 载荷 coordinate_reference_system.coordinates 按 EPSG:4326 权威轴序 [纬度, 经度]，
     并以 coordinate_axis_order_in_payload 显式声明；lon_lat 仅为 [经度, 纬度] 辅助字段。
   - SVG 绘图：x <- 经度（向东增大）；y <- 纬度，翻转（北在上；SVG 的 y 轴向下）。
   - 只接受 EPSG:4326 / degree；EPSG:3035 等投影坐标（米）或轴名不符一律拒绝，绝不混用。 */
(function (root) {
  "use strict";
  var DEFAULT_BOX = { left: 50, top: 40, width: 660, height: 300 };

  function latLonFromCrs(crs) {
    if (!crs || crs.epsg !== 4326 || crs.units !== "degree") {
      throw new Error("ONLY_EPSG_4326_DEGREE_SUPPORTED");
    }
    var order = crs.coordinate_axis_order_in_payload, c = crs.coordinates;
    if (!order || order.length !== 2 || !c || c.length !== 2) {
      throw new Error("AXIS_ORDER_OR_COORDINATES_MISSING");
    }
    var iLat = order.indexOf("latitude"), iLon = order.indexOf("longitude");
    if (iLat < 0 || iLon < 0 || iLat === iLon) {
      throw new Error("AXIS_NAMES_INVALID_FOR_EPSG_4326");
    }
    var lat = c[iLat], lon = c[iLon];
    if (typeof lat !== "number" || typeof lon !== "number" || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
      throw new Error("COORDINATE_OUT_OF_RANGE");
    }
    return { lat: lat, lon: lon };
  }

  function makeProjector(points, box) {
    var b = box || DEFAULT_BOX;
    var lats = points.map(function (p) { return p.lat; }), lons = points.map(function (p) { return p.lon; });
    var minLat = Math.min.apply(null, lats), maxLat = Math.max.apply(null, lats);
    var minLon = Math.min.apply(null, lons), maxLon = Math.max.apply(null, lons);
    return function (lat, lon) {
      var x = b.left + (maxLon === minLon ? b.width / 2 : (lon - minLon) / (maxLon - minLon) * b.width);
      var y = b.top + (maxLat === minLat ? b.height / 2 : (maxLat - lat) / (maxLat - minLat) * b.height);
      return [x, y];
    };
  }

  var api = {
    version: "S0D-R1",
    AXIS_CONVENTION: "payload [lat, lon] (EPSG:4326 authority order); SVG x <- lon, y <- lat (flipped, north up)",
    DEFAULT_BOX: DEFAULT_BOX,
    latLonFromCrs: latLonFromCrs,
    makeProjector: makeProjector
  };
  if (typeof module === "object" && module && module.exports) {
    module.exports = api;
  } else {
    root.VHSGeo = api;
  }
}(typeof window !== "undefined" ? window : this));
