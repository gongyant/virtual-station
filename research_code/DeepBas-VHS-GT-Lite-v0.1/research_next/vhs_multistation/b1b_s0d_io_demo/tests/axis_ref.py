# -*- coding: utf-8 -*-
"""geo_map.js 的 Python 复现（同一公式；仅供测试做一致性对照）。SYNTHETIC / PROPOSED。
x <- 经度（向东增大）；y <- 纬度（翻转：北在上，SVG y 轴向下）。"""
DEFAULT_BOX = {"left": 50, "top": 40, "width": 660, "height": 300}


def make_projector(points, box=None):
    b = box or DEFAULT_BOX
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    min_lat, max_lat, min_lon, max_lon = min(lats), max(lats), min(lons), max(lons)

    def project(lat, lon):
        x = b["left"] + (b["width"] / 2 if max_lon == min_lon else (lon - min_lon) / (max_lon - min_lon) * b["width"])
        y = b["top"] + (b["height"] / 2 if max_lat == min_lat else (max_lat - lat) / (max_lat - min_lat) * b["height"])
        return [x, y]
    return project
