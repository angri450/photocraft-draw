# -*- coding: utf-8 -*-
"""兵器按深度分段。

一件兵器从头到尾常常不是一个深度。棒尾甩在人的身后，棒头压在对手身前，
这两头跟中间不在同一个深度上。白模按层排序画，一层画不出这种前后关系，
所以一件兵器要拆成几段，每段一个深度，切点由本项目的几何代码计算。

方案里一件兵器这样写：

    {
      "name": "golden cudgel",
      "holder": "wukong",
      "segments": [
        {"from": 0.0, "to": 0.66, "depth": 3.5, "z": 80, "name": "棒身"},
        {"from": 0.66, "to": 1.0, "depth": 0.0, "z": -60, "name": "棒头"}
      ],
      "components": [...]
    }

from 和 to 是兵器主轴上的位置比例，0 是尾端，1 是头端。切分按主轴垂直的
方向切开多边形，切出来的每一段单独占一层，深度由这一段自己的 depth 决定。
"""
from __future__ import annotations

import math


def shape_points(params: dict) -> list[tuple[float, float]]:
    """一件形状里所有控制点的位置。"""
    points: list[tuple[float, float]] = []
    for subpath in params.get("subpaths") or []:
        for knot in subpath.get("knots") or []:
            if isinstance(knot, dict):
                anchor = knot.get("anchor") or [0, 0]
                points.append((float(anchor[0]), float(anchor[1])))
            else:
                points.append((float(knot[0]), float(knot[1])))
    return points


def axis_of(components: list[dict], declared=None):
    """兵器的主轴。

    方案里写了 axis 就照方案写的来，没写就从控制点里找距离最远的一对。
    """
    if declared:
        first, second = declared[0], declared[1]
        return (float(first[0]), float(first[1])), (float(second[0]), float(second[1]))
    points: list[tuple[float, float]] = []
    for item in components:
        if item.get("component") != "custom_shape":
            continue
        points.extend(shape_points(item.get("params") or {}))
    if len(points) < 2:
        return None
    best = (0.0, points[0], points[1])
    for index, first in enumerate(points):
        for other in points[index + 1:]:
            span = math.dist(first, other)
            if span > best[0]:
                best = (span, first, other)
    return best[1], best[2]


def lerp_point(axis, ratio: float) -> tuple[float, float]:
    (x1, y1), (x2, y2) = axis
    return (x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio)


def axis_vector(axis) -> tuple[float, float]:
    dx = axis[1][0] - axis[0][0]
    dy = axis[1][1] - axis[0][1]
    length = math.hypot(dx, dy) or 1.0
    return dx / length, dy / length


def clip_polygon(points, cut, axis_vec, keep_head: bool):
    """把多边形按垂直于主轴的直线切开，keep_head 决定留哪一半。"""
    out = []
    count = len(points)
    for index in range(count):
        cur = points[index]
        nxt = points[(index + 1) % count]
        d_cur = ((cur[0] - cut[0]) * axis_vec[0]
                 + (cur[1] - cut[1]) * axis_vec[1])
        d_nxt = ((nxt[0] - cut[0]) * axis_vec[0]
                 + (nxt[1] - cut[1]) * axis_vec[1])
        inside_cur = d_cur >= 0 if keep_head else d_cur <= 0
        inside_nxt = d_nxt >= 0 if keep_head else d_nxt <= 0
        if inside_cur:
            out.append(cur)
        if inside_cur != inside_nxt:
            ratio = d_cur / (d_cur - d_nxt)
            out.append((cur[0] + ratio * (nxt[0] - cur[0]),
                        cur[1] + ratio * (nxt[1] - cur[1])))
    return out


def slice_shape(params: dict, axis, low: float, high: float) -> dict:
    """把一件形状切成主轴上 low 到 high 那一段。"""
    axis_vec = axis_vector(axis)
    cut_low = lerp_point(axis, low)
    cut_high = lerp_point(axis, high)
    subpaths = []
    for subpath in params.get("subpaths") or []:
        knots = subpath.get("knots") or []
        points = []
        for knot in knots:
            if isinstance(knot, dict):
                anchor = knot.get("anchor") or [0, 0]
                points.append((float(anchor[0]), float(anchor[1])))
            else:
                points.append((float(knot[0]), float(knot[1])))
        if len(points) < 3:
            continue
        piece = clip_polygon(points, cut_low, axis_vec, True)
        piece = clip_polygon(piece, cut_high, axis_vec, False)
        if len(piece) < 3:
            continue
        smooth = len(piece) == len(knots) and all(
            isinstance(knot, dict) for knot in knots)
        if smooth:
            new_knots = []
            for knot, point in zip(knots, piece):
                anchor = knot.get("anchor") or [0, 0]
                new_knots.append({
                    "anchor": [point[0], point[1]],
                    "out": knot.get("out"),
                    "in": knot.get("in"),
                })
        else:
            new_knots = [[point[0], point[1]] for point in piece]
        subpaths.append({"closed": subpath.get("closed", True), "knots": new_knots})
    out = dict(params)
    out["subpaths"] = subpaths
    return out
