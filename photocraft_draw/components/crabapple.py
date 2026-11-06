# -*- coding: utf-8 -*-
"""海棠花林：背景、单棵花树、按 z 前后摆位的小树林。

空间作图的做法：每棵树给 x（横向）、y（脚线）、z（离观众多远）三个坐标。
树林组件按 z 从大到小画，远的先画、近的后画，遮挡自动正确；同时按 z 算
近大远小、远淡近浓、脚线后退、向画面中心收，这四条就是把三维位置压成
二维画面时的透视。depth 管谁压谁，z 管谁离得远，两根轴分开。

所有色块都显式传 stroke=None。绘制服务给形状的默认描边是 line，不写
就会给每个椭圆描一圈边，白模会糊成一片泡泡和硬线。
"""
from __future__ import annotations

import math
import random

from ..commands import Pen

BG = "#FAF6EC"
TRUNK = "#6B3A2E"
CROWN_DEEP = "#C97E9C"
CROWN = "#E3AEC4"
CROWN_LIGHT = "#F6DCE6"
BLOSSOM = "#B4232A"
BLOSSOM_SOFT = "#D96A82"
BLOSSOM_PALE = "#F2C4D4"
LEAF = "#7A9A5B"
SHADOW = "#E4D6BC"
GROUND = "#EADFC6"
SKY = "#F6ECE4"
HAZE = "#E9DBD1"


def _rgb(value):
    v = str(value).lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def _hex(color):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c))) for c in color)


def _mix(a, b, t):
    ca, cb = _rgb(a), _rgb(b)
    return _hex([ca[i] + (cb[i] - ca[i]) * t for i in range(3)])


def _fade(color, t):
    """远处的树往纸白里淡，空气透视。"""
    return _mix(color, BG, max(0.0, min(1.0, t)))


def _blob(pen, cx, cy, rx, ry, color, name):
    """无描边椭圆色块。"""
    pen.ellipse(cx, cy, rx, ry, fill=color, stroke=None, name=name)


def _five_petal(pen, cx, cy, r, color, core, mid=None, heart=None):
    """一朵重瓣海棠：三层花瓣交错套叠，外浅内深，花心只留一点。

    观赏海棠的花多为重瓣，单层五瓣是错的。平涂色块没有描边，层次只能靠
    明度拉开，所以外层用最浅的花瓣色，中层深一档，内层最深，花心再深一档。
    """
    mid = mid or color
    heart = heart or core
    # 外层：五片大瓣
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5
        _blob(pen, cx + math.cos(a) * r, cy + math.sin(a) * r,
              r * 0.58, r * 0.58, color, "外瓣")
    # 中层：五片错开半个瓣位，缩小一圈
    for k in range(5):
        a = -math.pi / 2 + (k + 0.5) * 2 * math.pi / 5
        _blob(pen, cx + math.cos(a) * r * 0.60, cy + math.sin(a) * r * 0.60,
              r * 0.40, r * 0.40, mid, "内瓣")
    # 内层：再错开，收成一小团，把花心包住
    for k in range(5):
        a = -math.pi / 2 + (k + 0.25) * 2 * math.pi / 5
        _blob(pen, cx + math.cos(a) * r * 0.30, cy + math.sin(a) * r * 0.30,
              r * 0.22, r * 0.22, heart, "心瓣")
    _blob(pen, cx, cy, r * 0.14, r * 0.14, heart, "花心")


def build_backdrop(params, pen):
    """天光、远坡和地面，给花林打底。平涂，无色带、无云、无描边。"""
    w = float(params.get("width", 800))
    h = float(params.get("height", 1200))
    horizon = float(params.get("horizon", 0.70)) * h

    pen.rect(0, 0, w, horizon, fill=SKY, stroke=None, name="天光")
    rng = random.Random(int(params.get("seed", 7)))
    # 地平线上几团远树影，压得很淡，交代林子往远处去；全部收在画布内
    for i in range(11):
        cx = 70 + i * (w - 140) / 10 + rng.uniform(-10, 10)
        rh = rng.uniform(24, 56)
        _blob(pen, cx, horizon + 4, rng.uniform(26, 44), rh, HAZE, "远树影")
    pen.rect(0, horizon, w, h - horizon, fill=GROUND, stroke=None, name="地面")
    _blob(pen, w * 0.5, horizon + 2, w * 0.40, 13,
          _mix(GROUND, SKY, 0.45), "地面亮带")


def _tree(pen, root, height, seed, bloom, fade,
          crown=0.225, trunk=0.48):
    """一棵完整的海棠树：投影、主干、分枝、花冠、花、嫩叶、落花。

    crown 是树冠半径占树高的比例，trunk 是主干高度占树高的比例。近树把
    crown 调大、trunk 调小，冠就压得更低更团、树干更短，整棵显得粗壮；
    远树反过来，冠小杆细。默认值保持原来的形态不变。
    """
    x, y = root
    rng = random.Random(seed)
    h = float(height)
    th = h * trunk
    wb = h * 0.050
    wm = h * 0.034
    wt = h * 0.024
    lean = rng.uniform(-0.10, 0.10) * h

    trunk_c = _fade(TRUNK, fade)
    crown_deep_c = _fade(CROWN_DEEP, fade)
    crown_c = _fade(CROWN, fade)
    crown_light_c = _fade(CROWN_LIGHT, fade)
    blossom = _fade(BLOSSOM, fade)
    blossom_soft = _fade(BLOSSOM_SOFT, fade)
    blossom_pale = _fade(BLOSSOM_PALE, fade)
    leaf = _fade(LEAF, fade)
    shadow = _fade(SHADOW, fade)

    # 地面投影，把树按在地上
    _blob(pen, x + lean * 0.3, y + 2, h * 0.15, h * 0.028, shadow, "树影")

    # 主干：下粗上细，略带 S 弯，闭合多边形，无描边
    knots = [
        [x - wb, y],
        [x - wm + lean * 0.45, y - th * 0.52],
        [x - wt + lean, y - th],
        [x + wt + lean, y - th],
        [x + wm + lean * 0.45, y - th * 0.52],
        [x + wb, y],
    ]
    pen.path([{"closed": True, "knots": knots}], fill=trunk_c, stroke=None,
             name="主干")

    # 树冠中心与半径：冠紧接主干顶端，冠底略压过杆顶
    cr = h * crown
    cy = y - th - cr * 0.578

    # 女字形出枝：角度不等、长短不一、不对生
    for i, a0 in enumerate((-62, -24, 16, 54)):
        a = math.radians(a0 + rng.uniform(-8, 8))
        length = cr * rng.uniform(0.70, 0.98)
        ex = x + lean + math.sin(a) * length
        ey = cy - math.cos(a) * length * 0.55
        pen.line(x + lean * 0.62, y - th * 0.76, ex, ey,
                 width=h * 0.015, color=trunk_c, name="主枝")

    # 花冠：几团重叠的椭圆，先深后浅，靠明度分出体积；各团收在树冠半径内
    puffs = [(-0.42, 0.08), (0.42, 0.04), (-0.24, -0.28),
             (0.26, -0.30), (0.0, 0.30), (0.0, -0.02)]
    for dx, dy in puffs:
        cx = x + lean + dx * cr + rng.uniform(-4, 4)
        py = cy + dy * cr + rng.uniform(-4, 4)
        _blob(pen, cx, py, cr * 0.50, cr * 0.44, crown_deep_c, "花冠暗部")
    for dx, dy in puffs[:5]:
        cx = x + lean + dx * cr * 0.90
        py = cy + dy * cr * 0.90 - cr * 0.08
        _blob(pen, cx, py, cr * 0.40, cr * 0.34, crown_c, "花冠")
    for dx, dy in ((-0.24, -0.32), (0.22, -0.34), (0.0, -0.44)):
        cx = x + lean + dx * cr
        py = cy + dy * cr - cr * 0.10
        _blob(pen, cx, py, cr * 0.26, cr * 0.20, crown_light_c, "花冠亮部")

    # 花：近树点缀重瓣，远树用花点，疏密由 bloom 与随机数定
    count = int(26 * bloom)
    for i in range(count):
        a = rng.uniform(0, 2 * math.pi)
        r = math.sqrt(rng.uniform(0, 1))
        fx = x + lean + math.cos(a) * cr * r * 0.94
        fy = cy + math.sin(a) * cr * r * 0.72
        if fade < 0.28 and i % 3 == 0:
            _five_petal(pen, fx, fy, h * 0.018, blossom_pale, blossom,
                        mid=blossom_soft, heart=blossom)
        else:
            _blob(pen, fx, fy, h * 0.008, h * 0.008,
                  blossom if i % 2 else blossom_soft, "花点")

    # 少量嫩叶，先花后叶，不铺满
    for _ in range(int(8 * bloom)):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.55, 0.92)
        lx = x + lean + math.cos(a) * cr * r
        ly = cy + math.sin(a) * cr * r * 0.70
        _blob(pen, lx, ly, h * 0.011, h * 0.006, leaf, "嫩叶")

    # 落花：树下几点，交代花会落
    for _ in range(5):
        lx = x + rng.uniform(-h * 0.15, h * 0.15)
        ly = y + rng.uniform(-h * 0.012, h * 0.042)
        _blob(pen, lx, ly, h * 0.008, h * 0.004, blossom_soft, "落花")


def build_tree(params, pen):
    """单棵海棠树。"""
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("crabapple_tree 需要 root：[x, y]")
    _tree(pen, (float(root[0]), float(root[1])),
          float(params.get("height", 400)),
          int(params.get("seed", 1)),
          float(params.get("bloom", 1.0)),
          float(params.get("fade", 0.0)),
          float(params.get("crown", 0.225)),
          float(params.get("trunk", 0.48)))


def build_grove(params, pen):
    """小树林：一组树按 z 前后摆位，透视与遮挡都由 z 推出来。"""
    trees = params.get("trees")
    if not isinstance(trees, (list, tuple)) or not trees:
        raise ValueError("crabapple_grove 需要 trees：一组树的坐标")
    width = float(params.get("width", 800))
    zmax = float(params.get("z_max", 100)) or 100.0

    prepared = []
    for i, t in enumerate(trees):
        if not isinstance(t, dict):
            raise ValueError("trees 第 %d 项要是对象" % (i + 1))
        z = float(t.get("z", 0))
        k = max(0.0, min(1.0, z / zmax))
        cx = width / 2
        px = cx + (float(t["x"]) - cx) * (1 - 0.10 * k)
        py = float(t["y"]) - 26 * k
        prepared.append({
            "z": z,
            "x": px,
            "y": py,
            "h": float(t["height"]) * (1 - 0.20 * k),
            "fade": 0.60 * k,
            "seed": int(t.get("seed", i + 1)),
            "bloom": float(t.get("bloom", 1.0)) * (1 - 0.35 * k),
            "crown": float(t.get("crown", 0.225)),
            "trunk": float(t.get("trunk", 0.48)),
        })
    prepared.sort(key=lambda d: -d["z"])
    for d in prepared:
        _tree(pen, (d["x"], d["y"]), d["h"], d["seed"], d["bloom"], d["fade"],
              d["crown"], d["trunk"])


# ---------------------------------------------------------------- 花枝特写

SPRAY_BG = "#F4E9DC"
SPRAY_LEAF_DARK = "#3F5A34"
SPRAY_LEAF = "#55703F"
SPRAY_BRANCH = "#5A4A38"
SPRAY_PETAL_OUT = "#C8455F"
SPRAY_PETAL_EDGE = "#E88AA0"
SPRAY_PETAL_MID = "#B3324C"
SPRAY_PETAL_IN = "#8E2740"
SPRAY_BUD = "#9E2A44"
SPRAY_STAMEN = "#E8C24A"


def _bloom_big(pen, cx, cy, r, rng):
    """一朵重瓣海棠特写：三层花瓣加一圈花丝，瓣缘提亮一档。"""
    for k in range(6):
        a = -math.pi / 2 + k * math.pi / 3 + rng.uniform(-0.10, 0.10)
        d = r * rng.uniform(0.66, 0.86)
        _blob(pen, cx + math.cos(a) * d, cy + math.sin(a) * d,
              r * rng.uniform(0.40, 0.50), r * rng.uniform(0.36, 0.46), SPRAY_PETAL_OUT, "外瓣")
    for k in range(6):
        a = -math.pi / 2 + k * math.pi / 3 + rng.uniform(-0.06, 0.06)
        d = r * rng.uniform(0.58, 0.68)
        _blob(pen, cx + math.cos(a) * d, cy + math.sin(a) * d,
              r * 0.34, r * 0.30, SPRAY_PETAL_EDGE, "瓣缘")
    for k in range(6):
        a = -math.pi / 2 + (k + 0.5) * math.pi / 3 + rng.uniform(-0.06, 0.06)
        d = r * rng.uniform(0.42, 0.52)
        _blob(pen, cx + math.cos(a) * d, cy + math.sin(a) * d,
              r * 0.30, r * 0.28, SPRAY_PETAL_MID, "内瓣")
    for k in range(5):
        a = -math.pi / 2 + (k + 0.25) * 2 * math.pi / 5
        _blob(pen, cx + math.cos(a) * r * 0.20, cy + math.sin(a) * r * 0.20,
              r * 0.17, r * 0.16, SPRAY_PETAL_IN, "心瓣")
    _blob(pen, cx, cy, r * 0.09, r * 0.09, SPRAY_STAMEN, "花心")
    for k in range(10):
        a = k * math.pi / 5
        _blob(pen, cx + math.cos(a) * r * 0.13, cy + math.sin(a) * r * 0.13,
              r * 0.018, r * 0.018, SPRAY_STAMEN, "花丝")


def _leaf(pen, cx, cy, length, angle, color):
    """一片狭长叶：旋转椭圆用闭合折线近似。"""
    rx = length * 0.5
    ry = length * 0.16
    ca, sa = math.cos(angle), math.sin(angle)
    pts = []
    for k in range(28):
        t = 2 * math.pi * k / 28
        ex, ey = math.cos(t) * rx, math.sin(t) * ry
        pts.append([cx + ex * ca - ey * sa, cy + ex * sa + ey * ca])
    pen.path([{"closed": True, "knots": pts}], fill=color, stroke=None, name="叶")


def build_spray(params, pen):
    """海棠花枝特写：一簇重瓣花、狭长叶、深色枝条，背景虚化成色团。

    part 参数把一幅画拆成三层（bg / branch / bloom），逐层出图时每层只画
    自己那部分；不写 part 就整幅一次画出。
    """
    w = float(params.get("width", 900))
    h = float(params.get("height", 1200))
    seed = int(params.get("seed", 3))
    part = str(params.get("part", "all"))
    rng = random.Random(seed)

    if part in ("all", "bg"):
        pen.rect(0, 0, w, h, fill=SPRAY_BG, stroke=None, name="背景")
        for _ in range(16):
            cx = rng.uniform(-0.05, 1.05) * w
            cy = rng.uniform(-0.02, 1.02) * h
            rx = rng.uniform(0.05, 0.11) * w
            c = rng.choice(["#F0DDE2", "#EAD4DA", "#DFE6D2", "#EFE2D2", "#E8D9CC"])
            _blob(pen, cx, cy, rx, rx * rng.uniform(0.55, 0.90), c, "虚化团")

    if part in ("all", "branch"):
        pen.line(w * 0.88, h * 0.94, w * 0.18, h * 0.20,
                 width=w * 0.030, color=SPRAY_BRANCH, name="主枝")
        pen.line(w * 0.50, h * 0.60, w * 0.16, h * 0.76,
                 width=w * 0.018, color=SPRAY_BRANCH, name="侧枝一")
        pen.line(w * 0.58, h * 0.48, w * 0.90, h * 0.28,
                 width=w * 0.015, color=SPRAY_BRANCH, name="侧枝二")
        leaves = [
            (0.22, 0.22, 0.20, -1.0), (0.30, 0.58, 0.21, 0.7),
            (0.72, 0.20, 0.18, 1.2), (0.80, 0.54, 0.19, 0.4),
            (0.50, 0.70, 0.16, -0.5), (0.14, 0.42, 0.17, -0.1),
            (0.88, 0.34, 0.15, 0.9), (0.62, 0.66, 0.15, 0.2),
        ]
        for lx, ly, ln, ang in leaves:
            _leaf(pen, w * lx, h * ly, w * ln, ang,
                  SPRAY_LEAF if rng.random() > 0.4 else SPRAY_LEAF_DARK)

    if part in ("all", "bloom"):
        for bx, by, br in ((0.30, 0.70, 0.032), (0.66, 0.72, 0.028)):
            _blob(pen, w * bx, h * by, w * br, w * br * 1.2, SPRAY_BUD, "花苞")
        blooms = [
            (0.50, 0.38, 0.140), (0.36, 0.30, 0.105), (0.64, 0.31, 0.100),
            (0.43, 0.50, 0.096), (0.58, 0.49, 0.090), (0.29, 0.44, 0.072),
            (0.71, 0.42, 0.066),
        ]
        for bx, by, br in blooms:
            _bloom_big(pen, w * bx, h * by, w * br, rng)


def build_label(params, pen):
    """包装文字层：产品名、真实属性名、产品特点、净含量，都是原生文字。"""
    title = str(params.get("title", "冷晶苹香花萃粉"))
    subtitle = str(params.get("subtitle", "固体饮料"))
    features = list(params.get("features") or [])
    net = str(params.get("net", ""))
    color = params.get("color", "#6B2F24")
    sub_color = params.get("sub_color", "#8A6A3A")
    y_title = float(params.get("y_title", 150))
    y_feat = float(params.get("y_features", 1090))
    width = float(params.get("width", 800))

    pen.text(width / 2, y_title, title, size=54, color=color,
             align="center", weight=700, tracking=40, name="产品名")
    pen.text(width / 2, y_title + 46, subtitle, size=22, color=sub_color,
             align="center", tracking=60, name="真实属性名")
    for i, line in enumerate(features):
        pen.text(width / 2, y_feat + i * 34, str(line), size=20, color=color,
                 align="center", tracking=20, name="产品特点 %d" % (i + 1))
    if net:
        pen.text(width - 40, y_feat + len(features) * 34, net, size=16,
                 color=sub_color, align="right", name="净含量")


COMPONENTS = {
    "grove_backdrop": {
        "name": "花林背景",
        "description": "天光、地平线远树影和地面平涂，给海棠花林打底",
        "params": {
            "width": "画面宽，默认 800",
            "height": "画面高，默认 1200",
            "horizon": "地平线占画高比例，默认 0.70",
            "seed": "远树影随机种子，默认 7",
        },
        "build": build_backdrop,
    },
    "crabapple_tree": {
        "name": "海棠树",
        "description": "一棵完整的海棠花树：投影、主干、分枝、花冠、花、嫩叶、落花",
        "params": {
            "root": "[x, y] 树根脚点，必填",
            "height": "树高像素，默认 400",
            "seed": "形态随机种子，默认 1",
            "bloom": "花量 0 到 1，默认 1.0",
            "fade": "往纸白淡化 0 到 1，远处调大，默认 0",
            "crown": "树冠半径占树高的比例，默认 0.225；近树调大到 0.30 更团",
            "trunk": "主干高度占树高的比例，默认 0.48；近树调小到 0.36 更矮壮",
        },
        "build": build_tree,
    },
    "crabapple_grove": {
        "name": "海棠花林",
        "description": "一组树按 z 从远到近摆位，自动算近大远小、远淡近浓与遮挡",
        "params": {
            "trees": "[{x, y, z, height, seed, bloom}, …]，必填；z 越大越远",
            "width": "画面宽，默认 800",
            "z_max": "z 的最大值，用来换算透视，默认 100",
        },
        "build": build_grove,
    },
    "crabapple_spray": {
        "name": "海棠花枝特写",
        "description": "一簇重瓣海棠花、狭长叶与枝条，背景虚化色团，用作真实照片的转绘底稿",
        "params": {
            "width": "画面宽，默认 900",
            "height": "画面高，默认 1200",
            "seed": "随形态种子，默认 3",
            "part": "画哪一层：bg 背景 / branch 枝叶 / bloom 花簇 / all 整幅",
        },
        "build": build_spray,
    },
    "grove_label": {
        "name": "包装文字",
        "description": "产品名、真实属性名、产品特点、净含量，写成原生文字层",
        "params": {
            "title": "产品名，默认 冷晶苹香花萃粉",
            "subtitle": "真实属性名，默认 固体饮料",
            "features": "特点行数组",
            "net": "净含量文字",
            "color": "产品名字色，默认 #6B2F24",
            "sub_color": "副文字色，默认 #8A6A3A",
            "y_title": "产品名基线，默认 150",
            "y_features": "特点首行基线，默认 1090",
            "width": "画面宽，默认 800",
        },
        "build": build_label,
    },
}

__all__ = ["build_backdrop", "build_tree", "build_grove", "build_spray",
           "build_label", "COMPONENTS"]
