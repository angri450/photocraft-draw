# -*- coding: utf-8 -*-
"""现代题材组件：饮料瓶、苹果、苹果树、货车、货台、握持的手。

两次连环画创作里反复手写的形状，抽成可复用组件。坐标都是参考系里的
绝对像素，调用时给位置和尺寸；同一件物体的各个面归成一个组，组内不查
色差。需要的颜色可以写进 colors 字典，也可以写在顶层，前者优先。
"""
from __future__ import annotations

import math

from ..commands import Pen


def _poly(points, closed=True):
    return {"closed": closed,
            "knots": [[round(x, 1), round(y, 1)] for x, y in points]}


def _rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _ellipse(cx, cy, rx, ry, n=20):
    return [(cx + rx * math.cos(2 * math.pi * i / n),
             cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _rotate(points, deg, cx, cy):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s,
             cy + (x - cx) * s + (y - cy) * c) for x, y in points]


def _leaf(cx, cy, length, width, angle=0):
    upper, lower = [], []
    for i in range(13):
        t = i / 12
        x = -length / 2 + t * length
        w = width * math.sin(math.pi * t) / 2
        upper.append((x, -w))
        lower.append((x, w))
    points = _rotate(upper + list(reversed(lower)), angle, 0, 0)
    return [(cx + x, cy + y) for x, y in points]


def _path(pen, points, fill, name, tilt=0, pivot=None):
    if tilt and pivot:
        points = _rotate(points, tilt, *pivot)
    pen.path([_poly(points)], fill=fill, name=name)


def _colour(params, key, default):
    return (params.get("colors") or {}).get(key) or params.get(key, default)


def _require_point(params, key, hint):
    value = params.get(key)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("%s 需要 %s：[x, y]" % (hint, key))
    return float(value[0]), float(value[1])


def _bottle_body(cx, by, h, w, nw):
    return [
        (cx - w / 2, by), (cx - w / 2, by - h * 0.66),
        (cx - nw / 2, by - h * 0.79), (cx - nw / 2, by - h * 0.91),
        (cx - nw * 0.47, by - h * 0.93), (cx - nw * 0.47, by - h),
        (cx + nw * 0.47, by - h), (cx + nw * 0.47, by - h * 0.93),
        (cx + nw / 2, by - h * 0.91), (cx + nw / 2, by - h * 0.79),
        (cx + w / 2, by - h * 0.66), (cx + w / 2, by),
    ]


def build_bottle(params: dict, pen: Pen) -> None:
    cx, by = _require_point(params, "base", "饮料瓶")
    h = float(params.get("height", 300))
    w = float(params.get("width") or h * 0.30)
    nw = w * 0.54
    tag = str(params.get("name") or "饮料瓶")
    tilt = float(params.get("tilt", 0))
    pivot = (cx, by - h * 0.5)
    with pen.group(tag):
        _path(pen, _bottle_body(cx, by, h, w, nw),
              _colour(params, "body", "#B4694F"), tag + " 瓶身", tilt, pivot)
        _path(pen, _rect(cx - w * 0.38, by - h * 0.63, w * 0.13, h * 0.56),
              _colour(params, "highlight", "#C8834F"), tag + " 高光", tilt, pivot)
        _path(pen, _rect(cx - w / 2, by - h * 0.26, w, h * 0.26),
              _colour(params, "tea", "#9A4E2C"), tag + " 茶液", tilt, pivot)
        ly, lh = by - h * 0.60, h * 0.28
        _path(pen, _rect(cx - w * 0.53, ly, w * 1.06, lh),
              _colour(params, "label", "#B23A48"), tag + " 标签", tilt, pivot)
        _path(pen, _ellipse(cx, ly + lh * 0.5, w * 0.20, lh * 0.28),
              _colour(params, "badge", "#E8C25A"), tag + " 圆标", tilt, pivot)
        _path(pen, _rect(cx - nw * 0.58, by - h * 1.025, nw * 1.16, h * 0.052),
              _colour(params, "cap", "#D9A253"), tag + " 瓶盖", tilt, pivot)


def _apple_body(cx, cy, r):
    return [
        (cx, cy - r * 0.76), (cx + r * 0.30, cy - r * 0.92),
        (cx + r * 0.64, cy - r * 0.86), (cx + r * 0.93, cy - r * 0.44),
        (cx + r, cy), (cx + r * 0.88, cy + r * 0.55),
        (cx + r * 0.46, cy + r * 0.90), (cx, cy + r * 0.96),
        (cx - r * 0.46, cy + r * 0.90), (cx - r * 0.88, cy + r * 0.55),
        (cx - r, cy), (cx - r * 0.93, cy - r * 0.44),
        (cx - r * 0.64, cy - r * 0.86), (cx - r * 0.30, cy - r * 0.92),
    ]


def _bite(cx, cy, r):
    """右上被咬出的缺口，外边沿着苹果轮廓，描边才会重合，外侧不会多出一圈线。"""
    return [
        (cx + r * 0.30, cy - r * 0.92), (cx + r * 0.64, cy - r * 0.86),
        (cx + r * 0.93, cy - r * 0.44), (cx + r, cy),
        (cx + r * 0.76, cy + r * 0.10), (cx + r * 0.58, cy - r * 0.14),
        (cx + r * 0.46, cy - r * 0.44), (cx + r * 0.38, cy - r * 0.72),
    ]


def build_apple(params: dict, pen: Pen) -> None:
    cx, cy = _require_point(params, "center", "苹果")
    r = float(params.get("radius", 100))
    tag = str(params.get("name") or "苹果")
    tilt = float(params.get("tilt", 0))
    pivot = (cx, cy)
    with pen.group(tag):
        _path(pen, _apple_body(cx, cy, r),
              _colour(params, "body", "#B23A48"), tag + " 果身", tilt, pivot)
        _path(pen, _ellipse(cx - r * 0.38, cy - r * 0.32, r * 0.18, r * 0.28),
              _colour(params, "highlight", "#E5A79A"), tag + " 高光", tilt, pivot)
        _path(pen, _rect(cx - r * 0.06, cy - r * 1.06, r * 0.12, r * 0.32),
              _colour(params, "stem", "#6B4226"), tag + " 果柄", tilt, pivot)
        _path(pen, _leaf(cx + r * 0.34, cy - r * 1.04, r * 0.66, r * 0.26, -26),
              _colour(params, "leaf", "#4E7440"), tag + " 叶", tilt, pivot)
        if bool(params.get("bite", False)):
            _path(pen, _bite(cx, cy, r),
                  _colour(params, "bite_color", "surface"),
                  tag + " 缺口", tilt, pivot)


_TREE_DOTS = [(-0.52, -0.18), (-0.20, -0.44), (0.16, -0.30),
              (0.48, -0.08), (-0.36, 0.22), (0.10, 0.26),
              (0.42, 0.30), (0.00, 0.04)]


def build_apple_tree(params: dict, pen: Pen) -> None:
    cx, gy = _require_point(params, "root", "苹果树")
    h = float(params.get("height", 350))
    tw, cr = h * 0.10, h * 0.30
    cy = gy - h * 0.62
    tag = str(params.get("name") or "苹果树")
    with pen.group(tag):
        _path(pen, _rect(cx - tw / 2, gy - h * 0.62, tw, h * 0.62),
              _colour(params, "trunk", "#6B4226"), tag + " 树干")
        _path(pen, _ellipse(cx, cy, cr, cr * 0.78),
              _colour(params, "crown", "#5C7A45"), tag + " 树冠后")
        _path(pen, _ellipse(cx - cr * 0.44, cy + cr * 0.20, cr * 0.66, cr * 0.50),
              _colour(params, "crown_light", "#7C9A5E"), tag + " 树冠左")
        _path(pen, _ellipse(cx + cr * 0.44, cy + cr * 0.18, cr * 0.66, cr * 0.50),
              _colour(params, "crown_light", "#7C9A5E"), tag + " 树冠右")
        fruit = bool(params.get("fruit", False))
        blossom = bool(params.get("blossom", False))
        if fruit or blossom:
            dots = [_poly(_ellipse(cx + dx * cr, cy + dy * cr,
                                   h * 0.028, h * 0.028))
                    for dx, dy in _TREE_DOTS]
            pen.path(dots,
                     fill=_colour(params,
                                  "fruit_color" if fruit else "blossom_color",
                                  "#B23A48" if fruit else "#E8D5D8"),
                     name=tag + (" 果子" if fruit else " 花"))


def build_truck(params: dict, pen: Pen) -> None:
    ox, oy = _require_point(params, "origin", "货车")
    k = float(params.get("scale", 1.0))
    tag = str(params.get("name") or "货车")

    def place(points):
        return [(ox + x * k, oy + y * k) for x, y in points]

    with pen.group(tag):
        _path(pen, place(_rect(0, 0, 525, 300)),
              _colour(params, "bed", "#9AA0A6"), tag + " 车厢")
        _path(pen, place([(525, 80), (670, 80), (750, 180),
                          (750, 300), (525, 300)]),
              _colour(params, "cab", "#8E2F3A"), tag + " 驾驶室")
        _path(pen, place(_rect(560, 110, 135, 90)),
              _colour(params, "window", "#CFE0E6"), tag + " 车窗")
        for label, wx in (("左轮", 130), ("右轮", 625)):
            _path(pen, place(_ellipse(wx, 307, 58, 58)),
                  _colour(params, "wheel", "#38271C"), tag + " " + label)
            _path(pen, place(_ellipse(wx, 307, 24, 24)),
                  _colour(params, "hub", "#9AA0A6"), tag + " " + label + " 轮毂")


def build_display_stand(params: dict, pen: Pen) -> None:
    frame = params.get("frame")
    if not isinstance(frame, (list, tuple)) or len(frame) != 4:
        raise ValueError("货台需要 frame：[x, y, 宽, 高]")
    x, y, w, h = (float(item) for item in frame)
    rows = int(params.get("rows", 3))
    per_row = int(params.get("per_row", 6))
    tag = str(params.get("name") or "货台")
    with pen.group(tag):
        _path(pen, [(x, y), (x + w, y), (x + w * 0.94, y + h),
                    (x + w * 0.06, y + h)],
              _colour(params, "stand", "#6A7078"), tag + " 台身")
        _path(pen, _rect(x - w * 0.02, y - 22, w * 1.04, 22),
              _colour(params, "rim", "#9AA0A6"), tag + " 台沿")
        if bool(params.get("apples", True)) and rows > 0:
            step = w * 0.80 / max(per_row, 1)
            rad = min(step * 0.38, 40)
            dots = []
            for row in range(rows):
                for col in range(max(1, per_row - row)):
                    px = x + w * 0.10 + col * step + row * step * 0.5
                    py = y - 30 - row * 58
                    dots.append(_poly(_ellipse(px, py, rad, rad)))
            pen.path(dots, fill=_colour(params, "apple", "#B23A48"),
                     name=tag + " 果堆")


def build_holding_hand(params: dict, pen: Pen) -> None:
    cx, cy = _require_point(params, "center", "握持的手")
    k = float(params.get("scale", 1.0))
    skin = _colour(params, "skin", "#D8B58C")
    tag = str(params.get("name") or "手")
    with pen.group(tag):
        pen.ellipse(cx, cy, 105 * k, 62 * k, fill=skin, name=tag + " 手掌")
        fingers = [_poly(_ellipse(cx + dx * k, cy + dy * k, 26 * k, 41 * k))
                   for dx, dy in ((-72, -40), (-32, -56), (10, -58))]
        pen.path(fingers, fill=skin, name=tag + " 手指")


COMPONENTS = {
    "bottle": {
        "name": "饮料瓶",
        "description": "细长瓶身、红色标签、金色瓶盖的冰红茶瓶，可整体倾斜",
        "params": {
            "base": "[中心x, 瓶底y]，必填",
            "height": "瓶高像素，默认 300",
            "width": "瓶身宽，默认瓶高的 0.30 倍",
            "tilt": "倾斜角度，默认 0",
            "name": "组名与部件名前缀，可选",
            "colors": "{body, highlight, tea, label, badge, cap}，可选",
        },
        "build": build_bottle,
    },
    "apple": {
        "name": "苹果",
        "description": "带果柄和一片叶子的红苹果，右上可咬出缺口",
        "params": {
            "center": "[中心x, 中心y]，必填",
            "radius": "半径像素，默认 100",
            "tilt": "倾斜角度，默认 0",
            "bite": "是否咬掉右上缺口，默认 false",
            "bite_color": "缺口颜色，写成背景色才透得出来，默认 surface",
            "name": "组名与部件名前缀，可选",
            "colors": "{body, highlight, stem, leaf}，可选",
        },
        "build": build_apple,
    },
    "apple_tree": {
        "name": "苹果树",
        "description": "树干加三层树冠，可挂果或开花",
        "params": {
            "root": "[中心x, 地面y]，必填",
            "height": "树高像素，默认 350",
            "fruit": "是否挂红果，默认 false",
            "blossom": "是否开浅粉白花，默认 false",
            "name": "组名与部件名前缀，可选",
            "colors": "{trunk, crown, crown_light, fruit_color, blossom_color}，可选",
        },
        "build": build_apple_tree,
    },
    "truck": {
        "name": "厢式货车",
        "description": "侧视货车，车厢、驾驶室、车窗、两只轮子",
        "params": {
            "origin": "[车厢左上角x, y]，必填",
            "scale": "整体缩放，默认 1.0",
            "name": "组名与部件名前缀，可选",
            "colors": "{bed, cab, window, wheel, hub}，可选",
        },
        "build": build_truck,
    },
    "display_stand": {
        "name": "梯形货台",
        "description": "超市水果堆头，可自动码放几层苹果",
        "params": {
            "frame": "[x, y, 宽, 高]，必填",
            "rows": "果堆层数，默认 3",
            "per_row": "每层个数，默认 6",
            "apples": "是否码放果堆，默认 true",
            "name": "组名与部件名前缀，可选",
            "colors": "{stand, rim, apple}，可选",
        },
        "build": build_display_stand,
    },
    "holding_hand": {
        "name": "握持的手",
        "description": "托住物体的手掌加三根并拢的手指",
        "params": {
            "center": "[中心x, 中心y]，必填",
            "scale": "整体缩放，默认 1.0",
            "name": "组名与部件名前缀，可选",
            "colors": "{skin}，可选",
        },
        "build": build_holding_hand,
    },
}
