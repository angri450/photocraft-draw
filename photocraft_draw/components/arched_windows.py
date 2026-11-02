# -*- coding: utf-8 -*-
"""拱形窗户：外框、窗光、竖棂和横档。"""
from __future__ import annotations

from ..commands import Pen


def build(params: dict, pen: Pen) -> None:
    windows = params.get("windows")
    if not windows:
        raise ValueError("拱形窗户需要 windows：[[x, y, 宽, 高], …]")
    colors = params.get("colors") or {}
    frame_color = colors.get("frame", "line")
    glass_color = colors.get("glass", "accent")
    light_color = colors.get("light", "surface")
    mullions = bool(params.get("mullions", True))

    pen.stage("拱形窗户")
    for index, item in enumerate(windows):
        if len(item) != 4:
            raise ValueError("windows 里每一项都要是 [x, y, 宽, 高]")
        x, y, w, h = item
        pen.rounded_rect(x, y, w, h, radius=[w / 2, w / 2, 0, 0], fill=glass_color,
                         stroke_width=3, stroke=frame_color, name=f"窗框 {index + 1}")
        inset = max(4, w * 0.1)
        inner_radius = (w - inset * 2) / 2
        pen.rounded_rect(x + inset, y + inset, w - inset * 2, h - inset,
                         radius=[inner_radius, inner_radius, 0, 0], fill=light_color,
                         stroke_width=1, stroke=frame_color, name="窗光")
        if mullions:
            pen.line(x + w / 2, y + inset, x + w / 2, y + h - inset * 0.4,
                     width=2, color=frame_color, name="竖棂")
            pen.line(x + inset, y + h * 0.62, x + w - inset, y + h * 0.62,
                     width=2, color=frame_color, name="横档")
