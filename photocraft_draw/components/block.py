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
HORSE_LEG_WIDTH = 0.09


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


# 人物比例照搬 Minecraft：头 8、身体 12、腿 12，总高 32
PERSON_POSES = {
    "stand": {"arm_l": 94, "arm_r": 86, "leg_l": 92, "leg_r": 88},
    "walk": {"arm_l": 100, "arm_r": 80, "leg_l": 101, "leg_r": 79},
    "run": {"arm_l": 116, "arm_r": 64, "leg_l": 114, "leg_r": 66},
    "point": {"arm_l": 94, "arm_r": -38, "leg_l": 92, "leg_r": 88},
    "sit": {"arm_l": 86, "arm_r": 94, "leg_l": 4, "leg_r": 14},
}


def build_rig_person(params: dict, pen: Pen) -> None:
    """方块人：六个长方体，照 Minecraft 的比例。

    头 8、身体 12、腿 12，总高 32。手臂和腿从肩、髋两个枢轴旋转，
    躯干和头不转。全部是矩形，没有曲线。

    参数：
        root    [x, y]，肩部位置，必填
        height  总身高像素，必填
        pose    stand / walk / run / point / sit
        body    身体颜色，默认 mid
        skin    头和手的颜色，默认 soft
        flip    是否左右翻转，默认 false
    """
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("方块人需要 root：[x, y]，肩部位置")
    total = params.get("height")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or total <= 0:
        raise ValueError("方块人需要 height，大于 0 的总身高像素")
    pose = str(params.get("pose", "stand"))
    if pose not in PERSON_POSES:
        raise ValueError(f"方块人 pose 只能是 {'、'.join(PERSON_POSES)}，收到 {pose}")
    body = params.get("body", "mid")
    skin = params.get("skin", "soft")
    flip = bool(params.get("flip", False))

    sx, sy = float(root[0]), float(root[1])
    u = float(total) / 32.0
    angles = PERSON_POSES[pose]

    head_w, head_h = 8 * u, 8 * u
    torso_w, torso_h = 8 * u, 12 * u
    arm_w, arm_h = 4 * u, 12 * u
    leg_w, leg_h = 4 * u, 12 * u

    # 头：方块压在肩上
    pen.rect(sx - head_w / 2, sy - head_h, head_w, head_h,
             fill=skin, stroke_width=None, stroke=None, name="头")
    # 躯干：从肩往下 12
    pen.rect(sx - torso_w / 2, sy, torso_w, torso_h,
             fill=body, stroke_width=None, stroke=None, name="躯干")

    # 手臂：从肩旋转
    for side, key in ((-1, "arm_l"), (1, "arm_r")):
        angle = angles[key] if not flip else angles["arm_r" if key == "arm_l" else "arm_l"]
        _segment(pen, sx + side * torso_w / 2, sy + arm_w * 0.2,
                 angle, arm_h, arm_w, body, "左臂" if side < 0 else "右臂", taper=1.0)

    # 腿：从髋旋转
    for side, key in ((-1, "leg_l"), (1, "leg_r")):
        angle = angles[key] if not flip else angles["leg_r" if key == "leg_l" else "leg_l"]
        _segment(pen, sx + side * torso_w * 0.25, sy + torso_h,
                 angle, leg_h, leg_w, body, "左腿" if side < 0 else "右腿", taper=1.0)


COMPONENTS["rig_person"] = {
    "name": "方块人",
    "description": "六个长方体的方块人，照 Minecraft 比例，手臂腿可摆动",
    "params": {
        "root": "[x, y]，肩部位置，必填",
        "height": "总身高像素，必填",
        "pose": "stand / walk / run / point / sit",
        "body": "身体颜色，默认 mid",
        "skin": "头部颜色，默认 soft",
        "flip": "是否左右翻转，默认 false",
    },
    "build": build_rig_person,
}

__all__ = ["build_block_figure", "build_block_horse", "build_custom_shape", "build_ascii_art",
           "build_rig_horse", "build_rig_person", "POSES", "HORSE_POSES", "PERSON_POSES",
           "ORDER", "COMPONENTS"]


def build_scatter_shape(params: dict, pen: Pen) -> None:
    """撒点填充：在轮廓里随机撒方块，一条指令出一片。

    参数：
        outline  person / horse，用哪套轮廓
        box      [x, y, 宽, 高]，轮廓落进这个框，必填
        count    方块数量，默认 40
        seed     随机种子，同一个种子出同一张图
        size     方块边长占框宽的比例，[最小, 最大]，默认 [0.06, 0.16]
        tones    三档颜色，默认 surface / muted / line
    """
    from ..scatter import scatter_blocks, scatter_grid

    box = params.get("box")
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise ValueError("撒点填充需要 box：[x, y, 宽, 高]")
    outline = str(params.get("outline", "person"))
    count = int(params.get("count", 40))
    if count <= 0:
        raise ValueError("撒点填充的 count 要大于 0")
    size = params.get("size") or [0.06, 0.16]
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        raise ValueError("size 要写成 [最小, 最大]")
    tones = params.get("tones") or ["surface", "muted", "line"]
    if not isinstance(tones, (list, tuple)) or len(tones) != 3:
        raise ValueError("tones 要给三档颜色")

    mode = str(params.get("mode", "grid"))
    if mode == "grid":
        blocks = scatter_grid(outline, box, cell=float(params.get("cell", 16)),
                              fill=float(params.get("fill", 0.92)),
                              jitter=float(params.get("jitter", 0.0)),
                              seed=int(params.get("seed", 0)))
    else:
        blocks = scatter_blocks(outline, box, count=count,
                                min_size=float(size[0]), max_size=float(size[1]),
                                seed=int(params.get("seed", 0)))
    for index, block in enumerate(blocks):
        tone = block["tone"]
        color = tones[0] if tone < 0.35 else (tones[1] if tone < 0.7 else tones[2])
        x, y, w, h = block["rect"]
        pen.rect(x, y, w, h, fill=color, stroke_width=None, stroke=None,
                 name=f"方块 {index + 1}")


COMPONENTS["scatter_shape"] = {
    "name": "撒点填充",
    "description": "在人形或马形轮廓里随机撒方块，一条指令出一片",
    "params": {
        "outline": "person / horse，默认 person",
        "box": "[x, y, 宽, 高]，必填",
        "count": "方块数量，只在 mode=random 时用",
        "mode": "grid 铺格子 / random 随机撒，默认 grid",
        "cell": "grid 模式的格子大小，默认 16",
        "fill": "方块占格子的比例，默认 0.92",
        "jitter": "每块随机偏移，0 到 0.5，默认 0",
        "seed": "随机种子，同一个种子出同一张图",
        "size": "[最小, 最大]，占框宽比例，默认 [0.06, 0.16]",
        "tones": "三档颜色，默认 surface / muted / line",
    },
    "build": build_scatter_shape,
}

__all__ = ["build_block_figure", "build_block_horse", "build_custom_shape", "build_ascii_art",
           "build_rig_horse", "build_rig_person", "build_scatter_shape",
           "POSES", "HORSE_POSES", "PERSON_POSES", "ORDER", "COMPONENTS"]


def build_pixel_person(params: dict, pen: Pen) -> None:
    """像素人：按 Minecraft 比例把六个部位切成小方块。

    轮廓由比例决定，不用手写曲线。每个部位切成 cell 大小的格子，
    格子有概率跳过，形成斑驳感。

    参数：
        root    [x, y]，肩部位置，必填
        height  总身高像素，必填
        cell    一个格子的像素，默认 12
        gap     格子之间留的缝，默认 1
        skip    跳过格子的概率，0 到 0.9，默认 0
        tones   三档颜色，默认 surface / muted / line
        seed    随机种子
    """
    import random as _random

    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("像素人需要 root：[x, y]，肩部位置")
    total = params.get("height")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or total <= 0:
        raise ValueError("像素人需要 height，大于 0 的总身高像素")
    cell = float(params.get("cell", 12))
    if cell <= 0:
        raise ValueError("像素人的 cell 要大于 0")
    gap = float(params.get("gap", 1))
    skip = float(params.get("skip", 0))
    if not 0 <= skip < 1:
        raise ValueError("skip 要在 0 到 1 之间")
    tones = params.get("tones") or ["surface", "muted", "line"]
    rng = _random.Random(int(params.get("seed", 0)))

    sx, sy = float(root[0]), float(root[1])
    u = float(total) / 32.0
    # 每个部位：左上角、宽、高（单位是 Minecraft 像素）
    blocks = {
        "头": (sx - 4 * u, sy - 8 * u, 8 * u, 8 * u),
        "躯干": (sx - 4 * u, sy, 8 * u, 12 * u),
        "左臂": (sx - 6 * u, sy, 4 * u, 12 * u),
        "右臂": (sx + 2 * u, sy, 4 * u, 12 * u),
        "左腿": (sx - 2 * u, sy + 12 * u, 4 * u, 12 * u),
        "右腿": (sx + 2 * u, sy + 12 * u, 4 * u, 12 * u),
    }

    index = 0
    for name, (bx, by, bw, bh) in blocks.items():
        cols = max(1, int(round(bw / cell)))
        rows = max(1, int(round(bh / cell)))
        cw = bw / cols
        ch = bh / rows
        for row in range(rows):
            for col in range(cols):
                if rng.random() < skip:
                    continue
                index += 1
                # 颜色按上下分档，下面深
                depth = (by + row * ch - (sy - 8 * u)) / (32 * u)
                color = tones[0] if depth < 0.4 else (tones[1] if depth < 0.75 else tones[2])
                pen.rect(bx + col * cw + gap / 2, by + row * ch + gap / 2,
                         cw - gap, ch - gap, fill=color, stroke_width=None, stroke=None,
                         name=f"{name} {row + 1}-{col + 1}")


COMPONENTS["pixel_person"] = {
    "name": "像素人",
    "description": "按 Minecraft 比例切成一格一格的小方块，轮廓由比例定，不靠手画曲线",
    "params": {
        "root": "[x, y]，肩部位置，必填",
        "height": "总身高像素，必填",
        "cell": "格子大小，默认 12",
        "gap": "格子缝隙，默认 1",
        "skip": "跳过格子的概率，0 到 0.9，默认 0",
        "tones": "三档颜色，默认 surface / muted / line",
        "seed": "随机种子",
    },
    "build": build_pixel_person,
}

__all__ = ["build_block_figure", "build_block_horse", "build_custom_shape", "build_ascii_art",
           "build_rig_horse", "build_rig_person", "build_scatter_shape", "build_pixel_person",
           "POSES", "HORSE_POSES", "PERSON_POSES", "ORDER", "COMPONENTS"]


def _capsule(pen: Pen, x1: float, y1: float, x2: float, y2: float,
             width: float, color: str, name: str) -> None:
    """胶囊：一段矩形加两端各一个圆，接头是圆的，不会有方角。"""
    _segment(pen, x1, y1, _math.degrees(_math.atan2(y2 - y1, x2 - x1)),
             _math.hypot(x2 - x1, y2 - y1), width, color, name, taper=1.0)
    radius = width / 2
    for suffix, (cx, cy) in ((" 头", (x1, y1)), (" 尾", (x2, y2))):
        pen.ellipse(cx, cy, radius, radius, fill=color, stroke_width=None, stroke=None,
                    name=name + suffix)


def build_capsule_person(params: dict, pen: Pen) -> None:
    """胶囊人：四肢用胶囊，躯干用圆角矩形，头用圆。

    SDF 那套做法在不能算距离场的画笔上做不到，但可以把"圆角"这一层
    补上：四肢两端是圆的，关节处自然融在一起，不会有方角戳出来。

    参数：
        root    [x, y]，肩部位置，必填
        height  总身高像素，必填
        pose    stand / walk / run / point
        body    身体颜色，默认 surface
    """
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("胶囊人需要 root：[x, y]，肩部位置")
    total = params.get("height")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or total <= 0:
        raise ValueError("胶囊人需要 height，大于 0 的总身高像素")
    pose = str(params.get("pose", "stand"))
    if pose not in PERSON_POSES:
        raise ValueError(f"胶囊人 pose 只能是 {'、'.join(PERSON_POSES)}，收到 {pose}")
    body = params.get("body", "surface")
    skin = params.get("skin", "body")

    sx, sy = float(root[0]), float(root[1])
    u = float(total) / 32.0
    angles = PERSON_POSES[pose]

    # 头：圆，直径 8
    pen.ellipse(sx, sy - 4 * u, 4 * u, 4 * u, fill=skin if skin != "body" else body,
                stroke_width=None, stroke=None, name="头")
    # 躯干：圆角矩形
    pen.rounded_rect(sx - 4 * u, sy, 8 * u, 12 * u, radius=2.4 * u,
                     fill=body, stroke_width=None, stroke=None, name="躯干")

    def limb(bx, by, angle, length, width, label):
        a = _math.radians(angle)
        ex = bx + _math.cos(a) * length
        ey = by + _math.sin(a) * length
        _capsule(pen, bx, by, ex, ey, width, body, label)

    for side, key, label in ((-1, "arm_l", "左臂"), (1, "arm_r", "右臂")):
        limb(sx + side * 4 * u, sy + 1.2 * u, angles[key], 12 * u, 4 * u, label)
    for side, key, label in ((-1, "leg_l", "左腿"), (1, "leg_r", "右腿")):
        limb(sx + side * 2 * u, sy + 12 * u, angles[key], 12 * u, 4 * u, label)


COMPONENTS["capsule_person"] = {
    "name": "胶囊人",
    "description": "四肢用胶囊、躯干用圆角矩形、头用圆，关节处没有方角",
    "params": {
        "root": "[x, y]，肩部位置，必填",
        "height": "总身高像素，必填",
        "pose": "stand / walk / run / point",
        "body": "身体颜色，默认 surface",
    },
    "build": build_capsule_person,
}

__all__ = ["build_block_figure", "build_block_horse", "build_custom_shape", "build_ascii_art",
           "build_rig_horse", "build_rig_person", "build_scatter_shape", "build_pixel_person",
           "build_capsule_person", "POSES", "HORSE_POSES", "PERSON_POSES", "ORDER", "COMPONENTS"]


def build_capsule_horse(params: dict, pen: Pen) -> None:
    """胶囊马：身体圆角矩形，颈、腿、尾巴都是胶囊。

    参数：
        root    [x, y]，肩部位置，必填
        length  肩高像素，必填
        pose    stand / walk / gallop
        body    马身颜色，默认 muted
        dark    鬃毛和蹄的颜色，默认 line
    """
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("胶囊马需要 root：[x, y]，肩部位置")
    height = params.get("length")
    if isinstance(height, bool) or not isinstance(height, (int, float)) or height <= 0:
        raise ValueError("胶囊马需要 length，大于 0 的肩高像素")
    pose = str(params.get("pose", "stand"))
    if pose not in ("stand", "walk", "gallop"):
        raise ValueError("胶囊马 pose 只能是 stand、walk、gallop")
    body = params.get("body", "muted")
    dark = params.get("dark", "line")

    sx, sy = float(root[0]), float(root[1])
    u = float(height)

    # 身体：一个大圆角矩形，从肩向后
    pen.rounded_rect(sx - u * 0.56, sy - u * 0.13, u * 0.58, u * 0.26, radius=u * 0.11,
                     fill=body, stroke_width=None, stroke=None, name="躯干")

    # 颈：两段胶囊，下段陡上段缓
    def capsule(x1, y1, x2, y2, width, color, label):
        _capsule(pen, x1, y1, x2, y2, width, color, label)
        return x2, y2

    nx, ny = capsule(sx + u * 0.01, sy - u * 0.06, sx + u * 0.12, sy - u * 0.26,
                     u * 0.13, body, "颈下段")
    nx, ny = capsule(nx, ny, nx + u * 0.12, ny - u * 0.13, u * 0.105, body, "颈上段")
    # 头：略向下垂的胶囊
    capsule(nx, ny, nx + u * 0.22, ny + u * 0.08, u * 0.135, body, "头")
    # 耳：一个小胶囊竖着
    capsule(nx + u * 0.02, ny - u * 0.02, nx + u * 0.02, ny - u * 0.09, u * 0.05, body, "耳")
    # 鬃毛：沿颈背两段深色
    capsule(sx + u * 0.03, sy - u * 0.13, sx + u * 0.14, sy - u * 0.31,
            u * 0.045, dark, "鬃毛下")
    capsule(sx + u * 0.14, sy - u * 0.31, sx + u * 0.24, sy - u * 0.42,
            u * 0.04, dark, "鬃毛上")

    # 尾巴：三段胶囊往下后甩
    tx, ty = sx - u * 0.52, sy - u * 0.06
    for index, angle in enumerate((118, 136, 152)):
        a = _math.radians(angle)
        ex = tx + _math.cos(a) * u * 0.15
        ey = ty + _math.sin(a) * u * 0.15
        capsule(tx, ty, ex, ey, u * 0.055, dark, f"尾 {index + 1}")
        tx, ty = ex, ey

    # 四条腿：三段胶囊
    for key, spec in HORSE_LEGS.items():
        bx = sx + spec["root"][0] * u
        by = sy + spec["root"][1] * u
        angles = spec[pose]
        x, y = bx, by
        for index, (angle, length) in enumerate(zip(angles, HORSE_LEG_LENGTHS)):
            a = _math.radians(angle)
            ex = x + _math.cos(a) * length * u
            ey = y + _math.sin(a) * length * u
            capsule(x, y, ex, ey, HORSE_LEG_WIDTH * u * (1.4 if index == 2 else 1.2),
                    dark if index == 2 else body, f"腿 {key} 段 {index + 1}")
            x, y = ex, ey


COMPONENTS["capsule_horse"] = {
    "name": "胶囊马",
    "description": "身体圆角矩形，颈腿尾巴都是胶囊，关节处圆润",
    "params": {
        "root": "[x, y]，肩部位置，必填",
        "length": "肩高像素，必填",
        "pose": "stand / walk / gallop",
        "body": "马身颜色，默认 muted",
        "dark": "鬃毛和蹄的颜色，默认 line",
    },
    "build": build_capsule_horse,
}

__all__ = ["build_block_figure", "build_block_horse", "build_custom_shape", "build_ascii_art",
           "build_rig_horse", "build_rig_person", "build_scatter_shape", "build_pixel_person",
           "build_capsule_person", "build_capsule_horse",
           "POSES", "HORSE_POSES", "PERSON_POSES", "ORDER", "COMPONENTS"]


def build_capsule_rider(params: dict, pen: Pen) -> None:
    """骑手：马和人在一个组件里，按前后关系逐层画。

    顺序是：马后腿 → 马身 → 颈头尾 → 人 → 人的腿 → 马前腿。
    这样人的腿压在马身上，马的前腿又压在人的腿前面，
    前后关系一眼能看出来。

    参数：
        root    [x, y]，马肩位置，必填
        length  肩高像素，必填
        horse   马的颜色，默认 mid
        rider   人的颜色，默认 deep
        skin    人的头部颜色，默认 soft
        pose    stand / walk / gallop，马的步态
    """
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("骑手需要 root：[x, y]，马肩位置")
    height = params.get("length")
    if isinstance(height, bool) or not isinstance(height, (int, float)) or height <= 0:
        raise ValueError("骑手需要 length，大于 0 的肩高像素")
    pose = str(params.get("pose", "stand"))
    if pose not in ("stand", "walk", "gallop"):
        raise ValueError("骑手 pose 只能是 stand、walk、gallop")
    horse = params.get("horse", "mid")
    rider = params.get("rider", "deep")
    skin = params.get("skin", "soft")

    sx, sy = float(root[0]), float(root[1])
    u = float(height)
    angles = HORSE_LEGS

    def capsule(x1, y1, x2, y2, width, color, label):
        _capsule(pen, x1, y1, x2, y2, width, color, label)
        return x2, y2

    def leg(key, index_range, width_scale=1.2):
        spec = angles[key]
        x = sx + spec["root"][0] * u
        y = sy + spec["root"][1] * u
        for index in index_range:
            angle = spec[pose][index]
            length = HORSE_LEG_LENGTHS[index]
            a = _math.radians(angle)
            ex = x + _math.cos(a) * length * u
            ey = y + _math.sin(a) * length * u
            _segment(pen, x, y, angle, HORSE_LEG_LENGTHS[index] * u,
                     HORSE_LEG_WIDTH * u * (1.5 if index == 2 else 1.3),
                     "ink" if index == 2 else horse, f"{key} 腿 {index + 1}", taper=1.0)
            x, y = ex, ey

    # 1. 后腿和尾巴：最靠后
    leg("bl", (0, 1, 2))
    leg("br", (0, 1, 2))
    tx, ty = sx - u * 0.52, sy - u * 0.06
    for index, angle in enumerate((118, 136, 152)):
        a = _math.radians(angle)
        ex = tx + _math.cos(a) * u * 0.15
        ey = ty + _math.sin(a) * u * 0.15
        capsule(tx, ty, ex, ey, u * 0.055, "line", f"尾 {index + 1}")
        tx, ty = ex, ey

    # 2. 远侧腿：先画，等会儿被马身盖掉大半，只露蹄子
    hip_x, hip_y = sx - u * 0.3, sy - u * 0.14
    far_x = hip_x - u * 0.08
    capsule(far_x, hip_y, far_x - u * 0.04, hip_y + u * 0.16, u * 0.09, rider, "远侧大腿")
    capsule(far_x - u * 0.04, hip_y + u * 0.16, far_x - u * 0.04, hip_y + u * 0.4,
            u * 0.07, rider, "远侧小腿")
    capsule(far_x - u * 0.04, hip_y + u * 0.4, far_x - u * 0.04, hip_y + u * 0.46,
            u * 0.075, "ink", "远侧靴")

    # 3. 马身：盖住大腿根，露出的只有膝盖以下
    pen.rounded_rect(sx - u * 0.56, sy - u * 0.13, u * 0.58, u * 0.26, radius=u * 0.11,
                     fill=horse, stroke_width=None, stroke=None, name="马身")

    # 3. 颈、头、鬃毛
    nx, ny = capsule(sx + u * 0.01, sy - u * 0.06, sx + u * 0.12, sy - u * 0.26,
                     u * 0.13, horse, "马颈下")
    nx, ny = capsule(nx, ny, nx + u * 0.12, ny - u * 0.13, u * 0.105, horse, "马颈上")
    capsule(nx, ny, nx + u * 0.22, ny + u * 0.08, u * 0.135, horse, "马头")
    capsule(sx + u * 0.03, sy - u * 0.13, sx + u * 0.14, sy - u * 0.31, u * 0.045, "line", "鬃毛下")
    capsule(sx + u * 0.14, sy - u * 0.31, sx + u * 0.24, sy - u * 0.42, u * 0.04, "line", "鬃毛上")

    # 3.5 近侧腿：后画，压在马身上，整条可见
    near_x = hip_x + u * 0.1
    capsule(near_x, hip_y, near_x + u * 0.03, hip_y + u * 0.16, u * 0.095, rider, "近侧大腿")
    capsule(near_x + u * 0.03, hip_y + u * 0.16, near_x + u * 0.03, hip_y + u * 0.46,
            u * 0.08, rider, "近侧小腿")
    capsule(near_x + u * 0.03, hip_y + u * 0.46, near_x + u * 0.03, hip_y + u * 0.52,
            u * 0.085, "ink", "近侧靴")

    # 4. 骑手：躯干压在马上
    body_w, body_h = u * 0.24, u * 0.36
    # 手臂先画，躯干后画，手臂根部被躯干盖住，不会在胸口留一条斜线
    capsule(hip_x + u * 0.08, hip_y - body_h + u * 0.08, hip_x + u * 0.24, hip_y - body_h - u * 0.12,
            u * 0.075, rider, "举起的手臂")
    capsule(hip_x - u * 0.06, hip_y - body_h + u * 0.14, hip_x + u * 0.1, hip_y - u * 0.02,
            u * 0.07, rider, "握缰绳的手臂")
    pen.rounded_rect(hip_x - body_w / 2, hip_y - body_h, body_w, body_h, radius=u * 0.07,
                     fill=rider, stroke_width=None, stroke=None, name="躯干")
    pen.ellipse(hip_x, hip_y - body_h - u * 0.11, u * 0.1, u * 0.11,
                fill=skin, stroke_width=None, stroke=None, name="头")
    # 斗篷：身后一块
    capsule(hip_x - u * 0.1, hip_y - body_h + u * 0.04, hip_x - u * 0.3, hip_y - u * 0.16,
            u * 0.12, rider, "斗篷")

    # 6. 前腿：最前
    leg("fl", (0, 1, 2))
    leg("fr", (0, 1, 2))


COMPONENTS["capsule_rider"] = {
    "name": "骑手",
    "description": "马和人在一个组件里按前后关系画：后腿、马身、颈头、人、人的腿、前腿",
    "params": {
        "root": "[x, y]，马肩位置，必填",
        "length": "肩高像素，必填",
        "horse": "马的颜色，默认 mid",
        "rider": "人的颜色，默认 deep",
        "skin": "头部颜色，默认 soft",
        "pose": "stand / walk / gallop",
    },
    "build": build_capsule_rider,
}

__all__ = ["build_block_figure", "build_block_horse", "build_custom_shape", "build_ascii_art",
           "build_rig_horse", "build_rig_person", "build_scatter_shape", "build_pixel_person",
           "build_capsule_person", "build_capsule_horse", "build_capsule_rider",
           "POSES", "HORSE_POSES", "PERSON_POSES", "ORDER", "COMPONENTS"]
