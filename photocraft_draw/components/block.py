# -*- coding: utf-8 -*-
"""积木人：十个形状拼一个人。

一个头、一个躯干、两条手臂、两条腿、两只脚，全是轴对齐的长方形和椭圆，
顺序固定：先头，再躯干，再四肢，最后脚。同一套部件表换坐标就是另一个
姿态，不用每次重新想怎么画。

坐标以髋部为原点，身高 1.0 归一，调用时给像素高度。
"""
from __future__ import annotations

from ..commands import Pen

# 每个姿态一张部件表：[x, y, 宽, 高]，相对髋部，y 向下为正
POSES: dict[str, dict[str, tuple[float, float, float, float]]] = {
    "stand": {
        "head": (-0.085, -0.53, 0.17, 0.18),
        "torso": (-0.1, -0.35, 0.2, 0.37),
        "arm_l": (-0.17, -0.33, 0.065, 0.28),
        "arm_r": (0.105, -0.33, 0.065, 0.28),
        "leg_l": (-0.095, 0.02, 0.08, 0.4),
        "leg_r": (0.015, 0.02, 0.08, 0.4),
        "foot_l": (-0.115, 0.42, 0.12, 0.055),
        "foot_r": (-0.005, 0.42, 0.12, 0.055),
    },
    "walk": {
        "head": (-0.075, -0.53, 0.17, 0.18),
        "torso": (-0.09, -0.35, 0.2, 0.37),
        "arm_l": (-0.2, -0.33, 0.065, 0.26),
        "arm_r": (0.13, -0.33, 0.065, 0.26),
        "leg_l": (-0.15, 0.02, 0.08, 0.38),
        "leg_r": (0.07, 0.02, 0.08, 0.38),
        "foot_l": (-0.19, 0.4, 0.13, 0.055),
        "foot_r": (0.06, 0.4, 0.13, 0.055),
    },
    "point": {
        "head": (-0.085, -0.53, 0.17, 0.18),
        "torso": (-0.1, -0.35, 0.2, 0.37),
        "arm_l": (-0.17, -0.33, 0.065, 0.28),
        "arm_r": (0.105, -0.36, 0.3, 0.07),
        "leg_l": (-0.095, 0.02, 0.08, 0.4),
        "leg_r": (0.015, 0.02, 0.08, 0.4),
        "foot_l": (-0.115, 0.42, 0.12, 0.055),
        "foot_r": (-0.005, 0.42, 0.12, 0.055),
    },
    "sit": {
        "head": (-0.085, -0.53, 0.17, 0.18),
        "torso": (-0.1, -0.35, 0.2, 0.37),
        "arm_l": (-0.17, -0.33, 0.065, 0.26),
        "arm_r": (0.105, -0.33, 0.065, 0.26),
        "leg_l": (-0.3, 0.02, 0.21, 0.085),
        "leg_r": (0.09, 0.02, 0.21, 0.085),
        "foot_l": (-0.32, 0.1, 0.06, 0.14),
        "foot_r": (0.26, 0.1, 0.06, 0.14),
    },
    "ride": {
        "head": (-0.085, -0.55, 0.17, 0.18),
        "torso": (-0.1, -0.37, 0.2, 0.37),
        "arm_l": (-0.2, -0.52, 0.065, 0.3),
        "arm_r": (0.135, -0.36, 0.065, 0.2),
        "leg_l": (-0.28, 0.0, 0.09, 0.28),
        "leg_r": (0.19, 0.0, 0.09, 0.28),
        "foot_l": (-0.31, 0.27, 0.12, 0.06),
        "foot_r": (0.2, 0.27, 0.12, 0.06),
    },
}

# 画图顺序：头、躯干、手臂、腿、脚
ORDER = ("head", "torso", "arm_l", "arm_r", "leg_l", "leg_r", "foot_l", "foot_r")

# 每个部件的形状和名字
SHAPES = {
    "head": ("ellipse", "头"),
    "torso": ("rect", "躯干"),
    "arm_l": ("rect", "左臂"),
    "arm_r": ("rect", "右臂"),
    "leg_l": ("rect", "左腿"),
    "leg_r": ("rect", "右腿"),
    "foot_l": ("rect", "左脚"),
    "foot_r": ("rect", "右脚"),
}


def _table(value) -> dict[str, tuple[float, float, float, float]]:
    if isinstance(value, str):
        if value not in POSES:
            raise ValueError(f"pose 只能是 {'、'.join(POSES)}，收到 {value}")
        return POSES[value]
    if isinstance(value, dict):
        missing = [name for name in ORDER if name not in value]
        if missing:
            raise ValueError(f"自定义姿态缺少部件：{'、'.join(missing)}")
        table = {}
        for name in ORDER:
            box = value[name]
            if not isinstance(box, (list, tuple)) or len(box) != 4:
                raise ValueError(f"部件 {name} 要写成 [x, y, 宽, 高]")
            table[name] = tuple(float(item) for item in box)
        return table
    raise ValueError("pose 给姿态名，或者直接给一张部件表")


def build_block_figure(params: dict, pen: Pen) -> None:
    """积木人：八个部件，先头再躯干再四肢。

    参数：
        root    [x, y]，髋部位置，必填
        height  身高像素，必填
        pose    stand / walk / point / sit / ride，也可以直接给部件表
        body    身体颜色，默认 surface
        skin    头和手的颜色，默认 body
        flip    是否左右翻转，默认 false
    """
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("积木人需要 root：[x, y]，髋部位置")
    height = params.get("height")
    if isinstance(height, bool) or not isinstance(height, (int, float)) or height <= 0:
        raise ValueError("积木人需要 height，大于 0 的像素高度")

    table = _table(params.get("pose", "stand"))
    body = params.get("body", "surface")
    skin = params.get("skin", body)
    flip = bool(params.get("flip", False))
    if flip:
        table = {name: (-(x + w), y, w, h) for name, (x, y, w, h) in table.items()}

    ox, oy = float(root[0]), float(root[1])
    for name in ORDER:
        x, y, w, h = table[name]
        kind, label = SHAPES[name]
        color = skin if name == "head" else body
        left = ox + x * height
        top = oy + y * height
        width = w * height
        height_px = h * height
        if kind == "ellipse":
            pen.ellipse(left + width / 2, top + height_px / 2, width / 2, height_px / 2,
                        fill=color, stroke_width=None, stroke=None, name=label)
        else:
            pen.rect(left, top, width, height_px,
                     fill=color, stroke_width=None, stroke=None, name=label)


COMPONENTS = {
    "block_figure": {
        "name": "积木人",
        "description": "八个长方形和椭圆拼的人，头、躯干、两臂、两腿、两脚，五种姿态",
        "params": {
            "root": "[x, y]，髋部位置，必填",
            "height": "身高像素，必填",
            "pose": "stand / walk / point / sit / ride，也可以直接给部件表",
            "body": "身体颜色，默认 surface",
            "skin": "头部颜色，默认同身体",
            "flip": "是否左右翻转，默认 false",
        },
        "build": build_block_figure,
    },
}


__all__ = ["build_block_figure", "POSES", "ORDER", "COMPONENTS"]


# 马的部件表：身体、颈、头、四条腿、尾、耳、眼，相对马身中心，体长 1.0 归一
HORSE_POSES = {
    "stand": {
        "body": (-0.5, -0.11, 1.0, 0.26),
        "neck": (0.3, -0.34, 0.20, 0.28),
        "head": (0.42, -0.4, 0.26, 0.13),
        "ear": (0.5, -0.47, 0.05, 0.07),
        "leg_fl": (0.3, 0.13, 0.08, 0.33),
        "leg_fr": (0.42, 0.13, 0.08, 0.33),
        "leg_bl": (-0.42, 0.13, 0.08, 0.33),
        "leg_br": (-0.3, 0.13, 0.08, 0.33),
        "tail": (-0.58, -0.08, 0.1, 0.3),
        "eye": (0.56, -0.36, 0.04, 0.04),
    },
    "rear": {
        "body": (-0.5, -0.13, 1.0, 0.26),
        "neck": (0.3, -0.42, 0.2, 0.3),
        "head": (0.42, -0.5, 0.26, 0.13),
        "ear": (0.5, -0.57, 0.05, 0.07),
        "leg_fl": (0.32, 0.11, 0.08, 0.2),
        "leg_fr": (0.44, 0.11, 0.08, 0.2),
        "leg_bl": (-0.44, 0.11, 0.08, 0.35),
        "leg_br": (-0.32, 0.11, 0.08, 0.35),
        "tail": (-0.6, -0.14, 0.1, 0.34),
        "eye": (0.56, -0.46, 0.04, 0.04),
    },
}

HORSE_ORDER = ("body", "neck", "head", "ear", "leg_fl", "leg_fr", "leg_bl", "leg_br", "tail", "eye")

HORSE_SHAPES = {
    "body": ("rect", "马身"),
    "neck": ("rect", "马颈"),
    "head": ("rect", "马头"),
    "ear": ("rect", "马耳"),
    "leg_fl": ("rect", "前左腿"),
    "leg_fr": ("rect", "前右腿"),
    "leg_bl": ("rect", "后左腿"),
    "leg_br": ("rect", "后右腿"),
    "tail": ("ellipse", "马尾"),
    "eye": ("ellipse", "马眼"),
}


def build_block_horse(params: dict, pen: Pen) -> None:
    """积木马：十个部件，身体横块加四条竖腿。

    参数：
        root    [x, y]，马身中心，必填
        length  体长像素，必填
        pose    stand / rear，前腿抬起用 rear
        body    马身颜色，默认 muted
        dark    蹄、耳、眼的颜色，默认 line
    """
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("积木马需要 root：[x, y]，马身中心")
    length = params.get("length")
    if isinstance(length, bool) or not isinstance(length, (int, float)) or length <= 0:
        raise ValueError("积木马需要 length，大于 0 的像素体长")
    pose = str(params.get("pose", "stand"))
    if pose not in HORSE_POSES:
        raise ValueError(f"马 pose 只能是 {'、'.join(HORSE_POSES)}，收到 {pose}")
    body = params.get("body", "muted")
    dark = params.get("dark", "line")

    table = HORSE_POSES[pose]
    ox, oy = float(root[0]), float(root[1])
    for name in HORSE_ORDER:
        x, y, w, h = table[name]
        kind, label = HORSE_SHAPES[name]
        color = dark if name in ("ear", "eye", "tail") else body
        left = ox + x * length
        top = oy + y * length
        width = w * length
        height_px = h * length
        if kind == "ellipse":
            pen.ellipse(left + width / 2, top + height_px / 2, width / 2, height_px / 2,
                        fill=color, stroke_width=None, stroke=None, name=label)
        else:
            pen.rect(left, top, width, height_px,
                     fill=color, stroke_width=None, stroke=None, name=label)


def build_custom_shape(params: dict, pen: Pen) -> None:
    """自定义路径：把一组路径点直接交给画笔。

    参数：
        subpaths  路径列表，每项 {"closed": 是否闭合, "knots": [...]}，必填
        fill      填充色，默认 surface
        stroke    描边色，给了才描边
        stroke_width 描边宽度
    """
    subpaths = params.get("subpaths")
    if not isinstance(subpaths, (list, tuple)) or not subpaths:
        raise ValueError("自定义路径需要 subpaths：一个非空的路径列表")
    fill = params.get("fill", "surface")
    stroke = params.get("stroke")
    width = params.get("stroke_width")
    pen.path(subpaths, fill=fill, stroke_width=width, stroke=stroke or "line",
             name=params.get("name") or "自定义路径")


COMPONENTS["custom_shape"] = {
    "name": "自定义路径",
    "description": "直接给路径点，支持贝塞尔控制点，画任意形状",
    "params": {
        "subpaths": "路径列表，每项 {closed, knots}，必填",
        "fill": "填充色，默认 surface",
        "stroke": "描边色，可选",
        "stroke_width": "描边宽度，可选",
    },
    "build": build_custom_shape,
}

def build_ascii_art(params: dict, pen: Pen) -> None:
    """字符画：把终端里的字符网格转成矩形。

    每一行从左到右扫，连续的实心字符合并成一个矩形，空白字符跳过。
    所以一条 40 列的字符画，每行大概出两到四段，不是一列一个矩形。

    参数：
        art    多行字符串，空格和点算空，其他字符算实心，必填
        cell   一个字符占多少像素，默认 10
        origin [x, y]，左上角起点，默认 [0, 0]
        color  填充色，默认 line
    """
    art = params.get("art")
    if not isinstance(art, str) or not art.strip():
        raise ValueError("字符画需要 art：一段多行字符串")
    cell = float(params.get("cell", 10))
    if cell <= 0:
        raise ValueError("字符画的 cell 要大于 0")
    origin = params.get("origin") or [0, 0]
    if not isinstance(origin, (list, tuple)) or len(origin) != 2:
        raise ValueError("字符画的 origin 要写成 [x, y]")
    color = params.get("color", "line")
    empty = set(params.get("empty", " ."))

    lines = art.strip("\n").split("\n")
    ox, oy = float(origin[0]), float(origin[1])
    for row, line in enumerate(lines):
        col = 0
        while col < len(line):
            if line[col] in empty:
                col += 1
                continue
            start = col
            while col < len(line) and line[col] not in empty:
                col += 1
            pen.rect(ox + start * cell, oy + row * cell, (col - start) * cell, cell,
                     fill=color, stroke_width=None, stroke=None, name=f"字符段 {row + 1}-{start + 1}")


COMPONENTS["ascii_art"] = {
    "name": "字符画",
    "description": "把多行字符画转成矩形，连续字符合并成一段",
    "params": {
        "art": "多行字符串，必填",
        "cell": "一个字符的像素大小，默认 10",
        "origin": "[x, y]，左上角，默认 [0, 0]",
        "color": "填充色，默认 line",
    },
    "build": build_ascii_art,
}

COMPONENTS["block_horse"] = {
    "name": "积木马",
    "description": "十个长方形和椭圆拼的马，身体、颈、头、四条腿、尾、耳、眼",
    "params": {
        "root": "[x, y]，马身中心，必填",
        "length": "体长像素，必填",
        "pose": "stand / rear，默认 stand",
        "body": "马身颜色，默认 muted",
        "dark": "蹄、耳、眼的颜色，默认 line",
    },
    "build": build_block_horse,
}

__all__ = ["build_block_figure", "build_block_horse", "build_custom_shape", "build_ascii_art",
           "POSES", "HORSE_POSES", "ORDER", "COMPONENTS"]


import math as _math

# 马的四条腿：每条腿三段，角度是绝对角度（0 向右，90 向下）
HORSE_LEGS = {
    "fl": {"root": (0.02, 0.10), "stand": (86, 90, 72), "walk": (70, 100, 62), "gallop": (62, 112, 46)},
    "fr": {"root": (-0.06, 0.10), "stand": (92, 94, 76), "walk": (98, 84, 86), "gallop": (28, 132, 24)},
    "bl": {"root": (-0.46, 0.10), "stand": (94, 88, 74), "walk": (108, 78, 80), "gallop": (120, 70, 60)},
    "br": {"root": (-0.38, 0.10), "stand": (90, 86, 70), "walk": (84, 94, 70), "gallop": (110, 78, 52)},
}

HORSE_LEG_LENGTHS = (0.17, 0.17, 0.06)
HORSE_LEG_WIDTH = 0.055


def _segment(pen: Pen, x: float, y: float, angle: float, length: float,
             width: float, color: str, name: str,
             taper: float = 0.72) -> tuple[float, float]:
    """从 (x, y) 按角度画一段骨头，返回末端点。

    骨段画成梯形：起点宽 width，末端宽 width * taper。taper 给 1 就是矩形。
    四肢从根到梢本来就应该变细，梯形比矩形自然。
    """
    a = _math.radians(angle)
    dx, dy = _math.cos(a), _math.sin(a)
    nx, ny = -dy, dx
    x2, y2 = x + dx * length, y + dy * length
    w1 = width / 2
    w2 = width * taper / 2
    knots = [[x + nx * w1, y + ny * w1], [x2 + nx * w2, y2 + ny * w2],
             [x2 - nx * w2, y2 - ny * w2], [x - nx * w1, y - ny * w1]]
    pen.path([{"closed": True, "knots": knots}], fill=color, name=name)
    return x2, y2


def _profile(pen: Pen, x: float, y: float, angle: float, points,
             color: str, name: str) -> None:
    """在一个沿角度旋转的局部坐标系里画多边形。

    points 每项是 (u, v)：u 沿朝向，v 垂直于朝向。
    """
    a = _math.radians(angle)
    dx, dy = _math.cos(a), _math.sin(a)
    nx, ny = -dy, dx
    knots = [[x + dx * u + nx * v, y + dy * u + ny * v] for u, v in points]
    pen.path([{"closed": True, "knots": knots}], fill=color, name=name)


def build_rig_horse(params: dict, pen: Pen) -> None:
    """关节马：每段骨头是一个可旋转的四边形，腿不会直挺挺。

    参数：
        root    [x, y]，肩部位置，必填
        length  肩高像素，必填
        pose    stand / walk / gallop
        body    马身颜色，默认 mid
        dark    蹄和鬃毛的颜色，默认 line
    """
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("关节马需要 root：[x, y]，肩部位置")
    height = params.get("length")
    if isinstance(height, bool) or not isinstance(height, (int, float)) or height <= 0:
        raise ValueError("关节马需要 length，大于 0 的肩高像素")
    pose = str(params.get("pose", "stand"))
    if pose not in ("stand", "walk", "gallop"):
        raise ValueError("关节马 pose 只能是 stand、walk、gallop")
    body_color = params.get("body", "mid")
    dark = params.get("dark", "line")

    sx, sy = float(root[0]), float(root[1])
    u = float(height)

    # 躯干：从肩往后一段斜的厚矩形
    _segment(pen, sx, sy, 180, u * 0.55, u * 0.25, body_color, "躯干", taper=0.86)
    # 颈分两段，下段陡、上段缓，侧面才有一条弧，不是直筒
    nx, ny = _segment(pen, sx + u * 0.03, sy - u * 0.05, -62, u * 0.17, u * 0.18,
                      body_color, "颈下段", taper=0.84)
    nx, ny = _segment(pen, nx, ny, -48, u * 0.2, u * 0.145, body_color, "颈上段", taper=0.76)
    # 头：后脑高、鼻口窄、下颌斜，用五个点收出马脸
    head_len = u * 0.3
    head_w = u * 0.14
    _profile(pen, nx, ny, 32, [
        (0, -head_w * 0.3), (head_len * 0.62, -head_w * 0.46),
        (head_len, -head_w * 0.18), (head_len, head_w * 0.14),
        (head_len * 0.5, head_w * 0.46), (0, head_w * 0.62),
    ], body_color, "头")
    # 耳：头后上方一个小三角
    _profile(pen, nx, ny, 32, [
        (u * 0.04, -head_w * 0.5), (u * 0.1, -head_w * 0.88), (u * 0.13, -head_w * 0.5),
    ], body_color, "耳")
    # 臀：躯干后端加一块圆的肌肉，直角变成弧
    pen.ellipse(sx - u * 0.46, sy - u * 0.015, u * 0.16, u * 0.135,
                fill=body_color, stroke_width=None, stroke=None, name="臀")
    # 胸：前端加一块，肩膀不是切平的
    pen.ellipse(sx + u * 0.01, sy + u * 0.015, u * 0.13, u * 0.125,
                fill=body_color, stroke_width=None, stroke=None, name="胸")
    # 鬃毛：一条连续的锯齿带，沿颈背从颈根到颈顶
    mane = []
    for index in range(7):
        t = index / 6.0
        ang = -62 + 16 * t
        cx = sx + u * (0.03 + 0.17 * t)
        cy = sy - u * (0.05 + 0.21 * t)
        a = _math.radians(ang)
        nx, ny = _math.sin(a), -_math.cos(a)
        base_x = cx + nx * u * 0.075
        base_y = cy + ny * u * 0.075
        if index % 2 == 0:
            mane.append([base_x, base_y])
        else:
            mane.append([base_x + nx * u * 0.055, base_y + ny * u * 0.055])
    pen.path([{"closed": True, "knots": mane}], fill=dark, name="鬃毛")

    # 尾巴：三段往下后甩
    tx, ty = sx - u * 0.46, sy - u * 0.06
    for index, angle in enumerate((120, 134, 148, 160)):
        tx, ty = _segment(pen, tx, ty, angle, u * 0.14, u * 0.06,
                          dark, f"尾 {index + 1}", taper=0.55)

    # 四条腿，每条三段
    for key, spec in HORSE_LEGS.items():
        bx = sx + spec["root"][0] * u
        by = sy + spec["root"][1] * u
        angles = spec[pose]
        x, y = bx, by
        for index, (angle, length) in enumerate(zip(angles, HORSE_LEG_LENGTHS)):
            x, y = _segment(pen, x, y, angle, length * u,
                            HORSE_LEG_WIDTH * u * (1.0 if index < 2 else 1.3),
                            body_color if index < 2 else dark,
                            f"腿 {key} 段 {index + 1}",
                            taper=0.78 if index < 2 else 1.0)


COMPONENTS["rig_horse"] = {
    "name": "关节马",
    "description": "每段骨头可旋转的马，三段腿，站立走路奔跑三种步态",
    "params": {
        "root": "[x, y]，肩部位置，必填",
        "length": "肩高像素，必填",
        "pose": "stand / walk / gallop，默认 stand",
        "body": "马身颜色，默认 mid",
        "dark": "蹄和鬃毛颜色，默认 line",
    },
    "build": build_rig_horse,
}

__all__ = ["build_block_figure", "build_block_horse", "build_custom_shape", "build_ascii_art",
           "build_rig_horse", "POSES", "HORSE_POSES", "ORDER", "COMPONENTS"]
