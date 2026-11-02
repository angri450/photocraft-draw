# -*- coding: utf-8 -*-
"""三维盒子投影：先建三维，再压成二维。

工程制图的做法：每个部件先定 x、y、z 三个坐标和长宽深三个尺寸，压到平面上
时按 z 从大到小画，远的先画、近的后画，遮挡关系就自动对了。不用再靠手调
绘制顺序。

z 越大表示离观众越远。侧视图投影时给一点斜度，把 z 映射成画面上的偏移，
看起来有一点立体感，但零件本身还是矩形。
"""
from __future__ import annotations

from ..commands import Pen

DEFAULTS = {"skew_x": 0.45, "skew_y": 0.28}


def _box(item, message):
    if not isinstance(item, (dict, list, tuple)):
        raise ValueError(message)
    if isinstance(item, dict):
        try:
            return (float(item["x"]), float(item["y"]), float(item["z"]),
                    float(item["w"]), float(item["h"]), float(item.get("d", 1)))
        except (KeyError, TypeError, ValueError):
            raise ValueError(message) from None
    if len(item) < 6:
        raise ValueError(message)
    return tuple(float(value) for value in item[:6])


def build_box3d_scene(params: dict, pen: Pen) -> None:
    """按三维坐标摆盒子，投影成二维后按 z 排序绘制。

    参数：
        boxes   [[x, y, z, 宽, 高, 深], …] 或 [{x,y,z,w,h,d,color,name}, …]，必填
                坐标以左侧中点为原点，y 向下为正，z 越大越远
        skew_x  z 每单位的横向偏移，默认 0.45
        skew_y  z 每单位的纵向偏移，默认 0.28
        colors  按索引给颜色，不给就用 single
        single  默认颜色，默认 mid
    """
    boxes = params.get("boxes")
    if not isinstance(boxes, (list, tuple)) or not boxes:
        raise ValueError("三维场景需要 boxes：一组坐标")
    skew_x = float(params.get("skew_x", DEFAULTS["skew_x"]))
    skew_y = float(params.get("skew_y", DEFAULTS["skew_y"]))
    single = params.get("single", "mid")
    colors = params.get("colors") or []

    prepared = []
    for index, raw in enumerate(boxes):
        x, y, z, w, h, d = _box(raw, f"第 {index + 1} 个盒子要写 [x, y, z, 宽, 高, 深]")
        color = raw.get("color") if isinstance(raw, dict) else None
        name = raw.get("name") if isinstance(raw, dict) else None
        if color is None and colors:
            color = colors[index % len(colors)]
        prepared.append({
            "x": x, "y": y, "z": z, "w": w, "h": h, "d": d,
            "color": color or single,
            "name": name or f"盒 {index + 1}",
        })

    # 远的先画，近的后画；同深度按原始顺序
    prepared.sort(key=lambda item: -item["z"])

    for item in prepared:
        px = item["x"] + item["z"] * skew_x
        py = item["y"] - item["z"] * skew_y
        pen.rect(px, py, item["w"], item["h"], fill=item["color"],
                 stroke_width=None, stroke=None, name=item["name"])


COMPONENTS = {
    "box3d_scene": {
        "name": "三维盒子",
        "description": "按三维坐标摆盒子，按 z 从远到近投影，遮挡自动正确",
        "params": {
            "boxes": "[[x, y, z, 宽, 高, 深], …]，必填；z 越大越远",
            "skew_x": "z 的横向偏移，默认 0.45",
            "skew_y": "z 的纵向偏移，默认 0.28",
            "colors": "按索引循环的颜色",
            "single": "默认颜色",
        },
        "build": build_box3d_scene,
    },
}

__all__ = ["build_box3d_scene", "COMPONENTS"]
