# -*- coding: utf-8 -*-
"""有机形状层：花瓣、叶片、花苞按三维位置和朝向贴到画面上。

这一层不建三维曲面。每个形状是二维轮廓，先算出它所在平面的屏幕
仿射，再把轮廓整体贴上去。朝向决定了它被压窄多少，位置决定了遮挡
顺序。花按整朵处理，五片花瓣共用一个平面，侧视超过阈值时自动
收成一个扁椭圆，避免花瓣尖拉出长刺。
"""
from __future__ import annotations

import math

from .commands import Pen
from .mesh import camera_from_dict

PETAL = [
    (0.00, 0.00), (-0.15, 0.08), (-0.29, 0.28), (-0.34, 0.55),
    (-0.30, 0.80), (-0.18, 0.93), (0.00, 0.96),
    (0.18, 0.93), (0.30, 0.80), (0.34, 0.55),
    (0.29, 0.28), (0.15, 0.08),
]
LEAF = [
    (0.00, 0.00), (-0.22, 0.12), (-0.40, 0.36), (-0.34, 0.62),
    (-0.14, 0.84), (0.00, 0.90), (0.14, 0.84), (0.34, 0.62),
    (0.40, 0.36), (0.22, 0.12),
]
BUD = [
    (0.00, 1.00), (-0.40, 0.72), (-0.78, 0.34), (-0.95, -0.02),
    (-0.84, -0.46), (-0.50, -0.80), (0.00, -0.95),
    (0.50, -0.80), (0.84, -0.46), (0.95, -0.02),
    (0.78, 0.34), (0.40, 0.72),
]
SHAPES = {"petal": PETAL, "leaf": LEAF, "bud": BUD}
CENTRED = {"bud"}
NOTCH = 0.10


def _unit(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _smooth(points):
    knots = []
    total = len(points)
    for index, point in enumerate(points):
        prev = points[(index - 1) % total]
        nxt = points[(index + 1) % total]
        tx, ty = nxt[0] - prev[0], nxt[1] - prev[1]
        norm = math.hypot(tx, ty) or 1.0
        tx, ty = tx / norm, ty / norm
        span = 0.20 * (math.dist(point, nxt) + math.dist(point, prev)) * 0.5
        knots.append({
            "anchor": [point[0], point[1]],
            "in": [point[0] - tx * span, point[1] - ty * span],
            "out": [point[0] + tx * span, point[1] + ty * span],
        })
    return knots


def _affine(camera, origin, x_axis, y_axis):
    o = camera.project(origin)
    px = camera.project(_add(origin, x_axis))
    py = camera.project(_add(origin, y_axis))
    ex = (px.x - o.x, px.y - o.y)
    ey = (py.x - o.x, py.y - o.y)
    return lambda x, y: (o.x + ex[0] * x + ey[0] * y,
                         o.y + ex[1] * x + ey[1] * y), (o.x, o.y)


def _plane(center, facing, radial):
    facing = _unit(facing)
    radial = _unit(radial)
    tangent = _unit(_cross(facing, radial))
    tilted = _unit(_add(_mul(radial, 0.42), _mul(facing, 0.90)))
    return tangent, tilted


def _sprite(pen, camera, item):
    shape = str(item.get("shape", "petal"))
    if shape not in SHAPES:
        raise ValueError("不认识的形状 %s，只能取 %s" % (shape, "、".join(SHAPES)))
    points = SHAPES[shape]
    center = tuple(float(v) for v in item["center"])
    facing = item.get("facing", (0.0, 0.0, -1.0))
    radial = item.get("radial", (0.0, 1.0, 0.0))
    size = float(item["size"])
    width = float(item.get("width", size * 0.5))
    spin = math.radians(float(item.get("spin", 0.0)))
    color = str(item.get("color", "#E8B3C2"))

    # 花苞是近似对称的体块，平面直接朝观众，只保留生长方向
    normal = _unit((0.0, 0.0, -1.0)) if shape == "bud" else _unit(facing)
    grow = _unit(radial)
    dot = sum(grow[i] * normal[i] for i in range(3))
    grow = _unit(tuple(grow[i] - normal[i] * dot for i in range(3)))
    side = _unit(_cross(normal, grow))
    to_screen, _ = _affine(camera, center, _mul(side, width), _mul(grow, size))
    ca, sa = math.cos(spin), math.sin(spin)
    mapped = []
    for index, (x, y) in enumerate(points):
        if shape == "petal" and index == 6:
            y -= NOTCH
        rx = x * ca - y * sa
        ry = x * sa + y * ca
        mapped.append(to_screen(rx, ry))
    stroke = item.get("stroke")
    pen.path([{"closed": True, "knots": _smooth(mapped)}], fill=color,
             stroke_width=float(item.get("stroke_width", 1.0)) if stroke else None,
             stroke=stroke, name=item.get("name", shape))


def _blossom(pen, camera, item):
    center = tuple(float(v) for v in item["center"])
    facing = _unit(item.get("facing", (0.0, 0.0, -1.0)))
    helper = (0.0, 1.0, 0.0) if abs(facing[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _unit(_cross(helper, facing))
    v = _unit(_cross(facing, u))
    size = float(item["size"])
    count = int(item.get("petals", 5))
    color = str(item.get("color", "#F2C0CE"))
    spin = float(item.get("spin", 0.0))
    to_screen, origin = _affine(camera, center, _mul(u, size), _mul(v, size))

    for index in range(count):
        angle = math.radians(360.0 / count * index + math.degrees(spin))
        ca, sa = math.cos(angle), math.sin(angle)
        mapped = []
        for point_index, (x, y) in enumerate(PETAL):
            if point_index == 6:
                y -= NOTCH
            rx = x * ca - (y - 0.05) * sa
            ry = x * sa + (y - 0.05) * ca + 0.05
            mapped.append(to_screen(rx * 0.92, ry * 0.92))
        pen.path([{"closed": True, "knots": _smooth(mapped)}], fill=color,
                 stroke_width=float(item.get("stroke_width", 1.0)),
                 stroke=item.get("stroke", "#DE9DB2"),
                 name="%s·瓣%d" % (item.get("name", "花"), index + 1))
    if item.get("heart", True):
        radius = size * 0.085 * camera.focal / max(0.05, _distance(camera, center))
        pen.ellipse(origin[0], origin[1], radius, radius * 0.92,
                    fill=item.get("heart_color", "#E9C25C"),
                    stroke=None, name="%s·心" % item.get("name", "花"))


def _distance(camera, point):
    return math.dist(camera.position, point)


def build(params: dict, pen: Pen) -> dict:
    """组件入口：一组有机形状贴到画面上，远的先画。"""
    items = params.get("items")
    if not isinstance(items, (list, tuple)) or not items:
        raise ValueError("有机层需要 items：一组花瓣、叶片或花")
    camera = camera_from_dict(params.get("camera"), pen)
    ordered = sorted(items, key=lambda item: -_distance(camera, tuple(item["center"])))
    drawn = 0
    for item in ordered:
        if not isinstance(item, dict) or "center" not in item or "size" not in item:
            raise ValueError("每个有机形状都要写 center 和 size")
        if item.get("petals"):
            _blossom(pen, camera, item)
        else:
            _sprite(pen, camera, item)
        drawn += 1
    return {"items": drawn, "commands": len(pen.commands)}


COMPONENTS = {
    "organic_layer": {
        "name": "有机形状层",
        "description": "花瓣、叶片、花苞按三维位置和朝向贴到画面，朝向决定压窄程度",
        "params": {
            "camera": "{position, target, up, focal, frame, projection}，必填",
            "items": "形状数组，每项含 shape（petal/leaf/bud）、center、size，"
                     "可选 facing、radial、width、color、spin、petals",
        },
        "build": build,
    },
}

__all__ = ["build", "COMPONENTS"]
