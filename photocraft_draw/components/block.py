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
