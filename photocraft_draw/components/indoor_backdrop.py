# -*- coding: utf-8 -*-
"""室内背景：墙面、地面、天顶和两侧帷幔。"""
from __future__ import annotations

from ..commands import Pen


def build(params: dict, pen: Pen) -> None:
    wall = params.get("wall")
    if not wall or len(wall) != 4:
        raise ValueError("室内背景需要 wall：[x, y, 宽, 高]")
    colors = params.get("colors") or {}
    wall_color = colors.get("wall", "bg")
    floor_color = colors.get("floor", "muted")
    ceiling_color = colors.get("ceiling", "surface")
    tapestry_color = colors.get("tapestry", "deep")
    fold_color = colors.get("fold", "ink")

    x, y, w, h = wall
    pen.rect(x, y, w, h, fill=wall_color)

    floor = params.get("floor")
    if floor:
        fx, fy, fw, fh = floor
        pen.rect(fx, fy, fw, fh, fill=floor_color)
        pen.line(fx, fy, fx + fw, fy, width=2, color="line", name="地平线")

    ceiling = params.get("ceiling")
    if ceiling:
        cx, cy, cw, ch = ceiling
        pen.rect(cx, cy, cw, ch, fill=ceiling_color)
        lines = int(params.get("ceiling_lines", 5))
        for index in range(lines):
            ly = cy + ch * (index + 1) / (lines + 1)
            pen.line(cx, ly, cx + cw, ly, width=1, color="line", name="天顶横线")

    for index, item in enumerate(params.get("tapestries") or []):
        if len(item) != 4:
            raise ValueError("tapestries 里每一项都要是 [x, y, 宽, 高]")
        tx, ty, tw, th = item
        pen.rect(tx, ty, tw, th, fill=tapestry_color, stroke_width=1, stroke="line", name=f"帷幔 {index + 1}")
        for step in (0.25, 0.5, 0.75):
            fx = tx + tw * step
            pen.line(fx, ty + th * 0.06, fx, ty + th * 0.94, width=1, color=fold_color, name="帷幔褶")
