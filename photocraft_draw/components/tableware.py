# -*- coding: utf-8 -*-
"""桌面器物：盘子、面包、酒杯和桌布褶。

四件器物各自成组件，绘制方案里按位置摆放；一张桌子放 6 到 8 件就够，
不要铺满。坐标按 800 宽的参考画布写，颜色只写配色角色。
"""
from __future__ import annotations

from ..commands import Pen


def _positive(value, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{what}要大于 0")
    return float(value)


def _point(item, message: str) -> tuple[float, float]:
    if not isinstance(item, (list, tuple)) or len(item) != 2:
        raise ValueError(message)
    for value in item:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(message)
    return float(item[0]), float(item[1])


def build_dinner_plate(params: dict, pen: Pen) -> None:
    """盘子：扁椭圆，盘沿比盘面深一档，下面垫一层软阴影。"""
    cx, cy = _point(params.get("center"), "盘子需要 center：[中心x, 中心y]")
    size = _positive(params.get("size", 26), "盘子的 size ")
    colors = params.get("colors") or {}
    rim_color = params.get("rim") or colors.get("rim", "line")
    face_color = params.get("face") or colors.get("face", "accent")
    shade_color = colors.get("shadow", "muted")
    depth = _positive(params.get("depth", 0.24), "盘子的 depth ")
    if depth > 1:
        raise ValueError("盘子的 depth 是纵向半径与横向半径之比，要小于等于 1，盘子是扁的")
    shadow = bool(params.get("shadow", True))

    rx = size / 2
    ry = rx * depth
    if shadow:
        pen.ellipse(cx + 1.5, cy + ry * 0.55, rx * 1.04, ry * 1.05,
                    fill=shade_color, stroke_width=None, stroke=None, name="盘影")
    pen.ellipse(cx, cy, rx, ry, fill=rim_color, stroke_width=None, stroke=None, name="盘沿")
    pen.ellipse(cx, cy - ry * 0.12, rx * 0.76, ry * 0.66,
                fill=face_color, stroke_width=None, stroke=None, name="盘面")


def build_bread_loaf(params: dict, pen: Pen) -> None:
    """面包：小椭圆，顶上一块亮面，可加割口和切面。"""
    cx, cy = _point(params.get("center"), "面包需要 center：[中心x, 中心y]")
    size = _positive(params.get("size", 14), "面包的 size ")
    colors = params.get("colors") or {}
    crust_color = params.get("crust") or colors.get("crust", "mid")
    crumb_color = params.get("crumb") or colors.get("crumb", "soft")
    score_color = params.get("score") or colors.get("score", "muted")
    shade_color = colors.get("shadow", "muted")
    depth = _positive(params.get("depth", 0.52), "面包的 depth ")
    cut = bool(params.get("cut", False))

    rx = size / 2
    ry = rx * depth
    pen.ellipse(cx + 1, cy + ry * 0.5, rx * 1.02, ry * 0.95,
                fill=shade_color, stroke_width=None, stroke=None, name="面包影")
    pen.ellipse(cx, cy, rx, ry, fill=crust_color, stroke_width=None, stroke=None, name="面包")
    pen.ellipse(cx, cy - ry * 0.2, rx * 0.7, ry * 0.52,
                fill=crumb_color, stroke_width=None, stroke=None, name="面包顶")
    if cut:
        pen.ellipse(cx - rx * 0.16, cy - ry * 0.24, rx * 0.36, ry * 0.36,
                    fill=crumb_color, stroke_width=None, stroke=None, name="面包切面")
        pen.line(cx - rx * 0.4, cy - ry * 0.32, cx - rx * 0.16, cy - ry * 0.58,
                 width=1, color=score_color, name="面包割口")
        pen.line(cx + rx * 0.1, cy - ry * 0.26, cx + rx * 0.34, cy - ry * 0.52,
                 width=1, color=score_color, name="面包割口")
    else:
        pen.line(cx - rx * 0.24, cy - ry * 0.24, cx + rx * 0.02, cy - ry * 0.54,
                 width=1, color=score_color, name="面包割口")


def build_wine_goblet(params: dict, pen: Pen) -> None:
    """酒杯：细颈、圆杯身、小杯口，杯里可带一点酒。"""
    cx, base_y = _point(params.get("center"), "酒杯需要 center：[中心x, 杯底中心y]")
    height = _positive(params.get("height", 20), "酒杯的 height ")
    colors = params.get("colors") or {}
    glass_color = colors.get("glass", "soft")
    edge_color = colors.get("edge", "line")
    light_color = colors.get("light", "accent")
    wine_color = colors.get("wine", "deep")
    shade_color = colors.get("shadow", "muted")
    with_wine = bool(params.get("wine", True))
    glint = bool(params.get("glint", True))

    w = height * 0.5
    rx = w / 2
    foot_ry = w * 0.13
    bowl_ry = height * 0.26
    bowl_cy = base_y - height * 0.74
    stem_top = base_y - height * 0.56
    stem_bottom = base_y - foot_ry * 0.2

    pen.ellipse(cx + 1, base_y + foot_ry * 0.5, rx * 1.05, foot_ry * 0.9,
                fill=shade_color, stroke_width=None, stroke=None, name="杯影")
    pen.ellipse(cx, base_y, w * 0.46, foot_ry, fill=glass_color,
                stroke_width=1, stroke=edge_color, name="杯脚")
    pen.rect(cx - w * 0.055, stem_top, w * 0.11, stem_bottom - stem_top,
             fill=glass_color, stroke_width=None, stroke=None, name="杯颈")
    pen.ellipse(cx, bowl_cy, w * 0.5, bowl_ry, fill=glass_color,
                stroke_width=1, stroke=edge_color, name="杯身")
    if glint:
        pen.ellipse(cx - w * 0.2, bowl_cy + bowl_ry * 0.15, w * 0.12, bowl_ry * 0.42,
                    fill=light_color, stroke_width=None, stroke=None, name="杯光")
    pen.ellipse(cx, bowl_cy - bowl_ry * 0.62, w * 0.4, bowl_ry * 0.3,
                fill=light_color, stroke_width=1, stroke=edge_color, name="杯口")
    if with_wine:
        pen.ellipse(cx, bowl_cy - bowl_ry * 0.58, w * 0.3, bowl_ry * 0.2,
                    fill=wine_color, stroke_width=None, stroke=None, name="酒")


def build_table_cloth_folds(params: dict, pen: Pen) -> None:
    """桌布褶：浅色大块加几条竖向褶，褶只用同色系暗部，不描黑边。"""
    area = params.get("area")
    if not isinstance(area, (list, tuple)) or len(area) != 4:
        raise ValueError("桌布褶需要 area：[x, y, 宽, 高]，指前垂区域")
    for value in area:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("area 要是 [x, y, 宽, 高]，四个数字")
    x, y, w, h = (float(value) for value in area)
    if w <= 0 or h <= 0:
        raise ValueError("桌布的宽和高要大于 0")

    colors = params.get("colors") or {}
    cloth_color = colors.get("cloth", "soft")
    fold_color = colors.get("fold", "line")
    light_color = colors.get("light", "surface")
    fold_width = _positive(params.get("fold_width", 10), "桌布褶的 fold_width ")
    top_shade = bool(params.get("top_shade", True))
    hem = bool(params.get("hem", True))
    fractions = _fold_positions(params.get("folds", 3))

    pen.rect(x, y, w, h, fill=cloth_color, stroke_width=None, stroke=None, name="桌布")
    if top_shade:
        pen.rect(x, y, w, max(2, h * 0.1), fill=fold_color, stroke_width=None, stroke=None,
                 name="桌沿阴影")
    for index, value in enumerate(fractions, 1):
        cx = x + w * value
        pen.ellipse(cx, y + h * 0.5, fold_width * 0.5, h * 0.47,
                    fill=fold_color, stroke_width=None, stroke=None, name=f"布褶 {index}")
        pen.ellipse(cx + fold_width * 0.2, y + h * 0.5, fold_width * 0.16, h * 0.4,
                    fill=light_color, stroke_width=None, stroke=None, name=f"布褶亮边 {index}")
    if hem:
        pen.line(x, y + h - 1.5, x + w, y + h - 1.5, width=2, color=fold_color, name="布边")


def _fold_positions(value) -> list[float]:
    """折数给整数，按等距排；给数组，按占宽的比例排。"""
    if isinstance(value, bool):
        raise ValueError("folds 要给折数，或给占宽比例的数组")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("桌布褶的折数要大于 0")
        return [(index + 1) / (value + 1) for index in range(value)]
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("folds 要给折数，或给占宽比例的数组")
    positions = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not 0.02 <= item <= 0.98:
            raise ValueError("folds 数组里每一项要是 0.02 到 0.98 之间的小数，表示占宽的比例")
        positions.append(float(item))
    return positions


COMPONENTS = {
    "dinner_plate": {
        "name": "盘子",
        "description": "扁椭圆盘子，盘沿比盘面深一档，下面带一层软阴影",
        "params": {
            "center": "[中心x, 中心y]，必填",
            "size": "盘的宽，默认 26",
            "depth": "纵向半径与横向半径之比，默认 0.24",
            "shadow": "是否画盘下软阴影，默认 true",
            "colors": "{rim, face, shadow}，可选",
        },
        "build": build_dinner_plate,
    },
    "bread_loaf": {
        "name": "面包",
        "description": "小椭圆面包，顶上一块亮面，可选切面和割口",
        "params": {
            "center": "[中心x, 中心y]，必填",
            "size": "面包的宽，默认 14",
            "depth": "高与宽之比，默认 0.52",
            "cut": "是否画切面和两道割口，默认 false",
            "colors": "{crust, crumb, score, shadow}，可选",
        },
        "build": build_bread_loaf,
    },
    "wine_goblet": {
        "name": "酒杯",
        "description": "细颈圆杯身的酒杯，小杯口，带一点酒和杯身反光",
        "params": {
            "center": "[中心x, 杯底中心y]，必填",
            "height": "杯高，默认 20",
            "wine": "是否画酒，默认 true",
            "glint": "是否画杯身反光，默认 true",
            "colors": "{glass, edge, light, wine, shadow}，可选",
        },
        "build": build_wine_goblet,
    },
    "table_cloth_folds": {
        "name": "桌布褶",
        "description": "桌布前垂的浅色大块、顶部阴影、竖向褶和布边，叠在长条餐桌上",
        "params": {
            "area": "[x, y, 宽, 高]，前垂区域，必填",
            "folds": "折数，默认 3；也可以给占宽比例的数组",
            "fold_width": "单条褶的宽，默认 10",
            "top_shade": "是否画桌沿下的阴影，默认 true",
            "hem": "是否画布边，默认 true",
            "colors": "{cloth, fold, light}，可选",
        },
        "build": build_table_cloth_folds,
    },
}


__all__ = [
    "build_dinner_plate",
    "build_bread_loaf",
    "build_wine_goblet",
    "build_table_cloth_folds",
    "COMPONENTS",
]
