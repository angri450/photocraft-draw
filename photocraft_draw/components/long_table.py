# -*- coding: utf-8 -*-
"""长条餐桌：桌布、前垂、桌沿、盘子和面包。"""
from __future__ import annotations

from ..commands import Pen


def build(params: dict, pen: Pen) -> None:
    table = params.get("table")
    if not table or len(table) != 4:
        raise ValueError("长条餐桌需要 table：[x, y, 宽, 高]")
    colors = params.get("colors") or {}
    cloth_color = colors.get("cloth", "surface")
    front_color = colors.get("front", "soft")
    edge_color = colors.get("edge", "line")
    plate_color = colors.get("plate", "bg")
    bread_color = colors.get("bread", "mid")

    x, y, w, h = table
    front = float(params.get("front", 38))
    pen.rect(x, y, w, h, fill=cloth_color, name="桌面")
    pen.rect(x, y + h, w, front, fill=front_color, name="前垂")
    pen.line(x, y + h, x + w, y + h, width=3, color=edge_color, name="桌沿")

    plate_y = float(params.get("plate_y", y + h * 0.62))
    for index, px in enumerate(params.get("plates") or []):
        pen.ellipse(px, plate_y, max(6, h * 0.22), max(2.5, h * 0.09),
                    fill=plate_color, stroke_width=1, stroke=edge_color, name=f"盘子 {index + 1}")
        if index % 3 == 1:
            pen.ellipse(px, plate_y - h * 0.12, max(4, h * 0.12), max(2, h * 0.06),
                        fill=bread_color, stroke_width=None, stroke=None, name="面包")

    cup_x = params.get("cup_x")
    if cup_x is not None:
        pen.rounded_rect(cup_x - h * 0.1, plate_y - h * 0.55, h * 0.2, h * 0.3,
                         radius=h * 0.06, fill=plate_color,
                         stroke_width=1, stroke=edge_color, name="酒杯")
