# -*- coding: utf-8 -*-
"""有机形状层：花瓣、叶片、花苞按三维位置和朝向贴到画面上。

这一层不建三维曲面。每个形状是二维轮廓，先算出它所在平面的屏幕
仿射，再把轮廓整体贴上去。朝向决定了它被压窄多少，位置决定了遮挡
顺序。花按整朵处理，两层花瓣共用一个平面，内层错开半格、压暗一档；
花心是一圈放射状花丝加一个小圆盘。
"""
from __future__ import annotations

import math

from .commands import Pen
from .mesh import camera_from_dict
from .palette import color_of

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


def _darken(color, amount):
    """把 #rrggbb 压暗一档，色相不变；不是十六进制就原样返回。"""
    text = str(color)
    if len(text) != 7 or not text.startswith("#"):
        return text
    try:
        channels = [int(text[index:index + 2], 16) for index in (1, 3, 5)]
    except ValueError:
        return text
    factor = max(0.0, 1.0 - float(amount))
    return "#%02x%02x%02x" % tuple(
        max(0, min(255, int(round(channel * factor)))) for channel in channels
    )


def _petal_layer(pen, to_screen, count, spin, scale, fill, stroke,
                 stroke_width, name, suffix, offset):
    """铺一层花瓣。scale 是这一层的直径比例，offset 是整层的旋转角。"""
    for index in range(count):
        angle = math.radians(360.0 / count * index + math.degrees(spin) + offset)
        ca, sa = math.cos(angle), math.sin(angle)
        mapped = []
        for point_index, (x, y) in enumerate(PETAL):
            if point_index == 6:
                y -= NOTCH
            rx = x * ca - (y - 0.05) * sa
            ry = x * sa + (y - 0.05) * ca + 0.05
            mapped.append(to_screen(rx * 0.92 * scale, ry * 0.92 * scale))
        pen.path([{"closed": True, "knots": _smooth(mapped)}], fill=fill,
                 stroke_width=stroke_width, stroke=stroke,
                 name="%s·%s%d" % (name, suffix, index + 1))


def _dot(pen, to_screen, cx, cy, radius, fill, name, sides=12):
    """在花朵平面里画一个小圆点，跟着平面一起压扁。"""
    points = [
        to_screen(cx + radius * math.cos(2.0 * math.pi * index / sides),
                  cy + radius * math.sin(2.0 * math.pi * index / sides))
        for index in range(sides)
    ]
    pen.path([{"closed": True, "knots": points}], fill=fill, stroke_width=None,
             stroke=None, name=name)


def _heart(pen, to_screen, item, name):
    """一圈花丝加一个小圆盘，长度按花径的一成算，随花朵平面一起压扁。"""
    color = str(item.get("heart_color", "#E9C25C"))
    count = int(item.get("stamens", 9))
    if not 8 <= count <= 10:
        raise ValueError("stamens 要在 8 到 10 之间")
    length = 0.18
    scale = math.dist(to_screen(0.0, 0.0), to_screen(1.0, 0.0))
    width = max(1.0, scale * 0.0075)
    for index in range(count):
        angle = 2.0 * math.pi * index / count + math.radians(12.0)
        dx, dy = math.cos(angle), math.sin(angle)
        start = length * 0.34
        pen.line(*to_screen(dx * start, dy * start),
                 *to_screen(dx * length, dy * length),
                 width=width, color=color, name="%s·花丝%d" % (name, index + 1))
        _dot(pen, to_screen, dx * length, dy * length, 0.018, color,
             "%s·蕊头%d" % (name, index + 1))
    _dot(pen, to_screen, 0.0, 0.0, 0.045,
         _darken(color_of(pen.palette, color), 0.12), "%s·心盘" % name, sides=16)


def _blossom(pen, camera, item):
    center = tuple(float(v) for v in item["center"])
    facing = _unit(item.get("facing", (0.0, 0.0, -1.0)))
    helper = (0.0, 1.0, 0.0) if abs(facing[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _unit(_cross(helper, facing))
    v = _unit(_cross(facing, u))
    size = float(item["size"])
    count = int(item.get("petals", 5))
    layers = max(1, int(item.get("layers", 2)))
    color = str(item.get("color", "#F2C0CE"))
    spin = float(item.get("spin", 0.0))
    name = item.get("name", "花")
    to_screen, _ = _affine(camera, center, _mul(u, size), _mul(v, size))
    stroke = item.get("stroke", "#DE9DB2")
    stroke_width = float(item.get("stroke_width", 1.0))

    # 外层五瓣
    _petal_layer(pen, to_screen, count, spin, 1.0, color, stroke,
                 stroke_width, name, "瓣", 0.0)

    # 内层错开半格，直径 0.58，填充和描边都压暗一档
    if layers >= 2:
        inner_fill = _darken(color_of(pen.palette, color), 0.10)
        inner_stroke = _darken(inner_fill, 0.16)
        _petal_layer(pen, to_screen, count, spin, 0.58, inner_fill, inner_stroke,
                     stroke_width, name, "内瓣", 180.0 / count)

    if item.get("heart", True):
        _heart(pen, to_screen, item, name)


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
                     "可选 facing、radial、width、color、spin、petals；"
                     "花另有 layers（默认 2）、stamens（8 到 10，默认 9）、heart",
        },
        "build": build,
    },
}

__all__ = ["build", "COMPONENTS"]
