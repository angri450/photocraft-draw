# -*- coding: utf-8 -*-
"""绘图笔：把参考坐标换算成画布坐标，并生成绘制指令。"""
from __future__ import annotations

from .palette import color_of


class Pen:
    """按参考宽度绘制，输出时统一放大到画布尺寸。

    构图组件只关心参考坐标（默认 800 宽），不用考虑最终画布多大。
    """

    def __init__(self, width: int, height: int, ref_width: float = 800, palette: dict | None = None,
                 base_layer: str = "Background"):
        if width <= 0 or height <= 0:
            raise ValueError("画布宽高必须大于 0")
        if ref_width <= 0:
            raise ValueError("参考宽度必须大于 0")
        self.width = int(width)
        self.height = int(height)
        self.ref_width = float(ref_width)
        self.k = self.width / self.ref_width
        self.palette = palette or {}
        self.base_layer = str(base_layer)
        self.commands: list[dict] = []
        self._has_stage = False

    @property
    def ref_height(self) -> float:
        return self.height / self.k

    def _x(self, value: float) -> int:
        return int(round(value * self.k))

    def _size(self, value: float) -> int:
        return max(1, int(round(value * self.k)))

    def _rect(self, x: float, y: float, w: float, h: float) -> list[int]:
        return [self._x(x), self._x(y), self._size(w), self._size(h)]

    def _stroke(self, width: float | None, color) -> dict | None:
        if width is None and color is None:
            return None
        return {
            "width": self._size(width or 1),
            "color": color_of(self.palette, color or "line"),
            "align": "center",
        }

    def stage(self, name: str, nested: bool = False) -> None:
        """开一个图层组。

        顶层的组先选回背景层，保证和上一个组同级；组件组用 nested=True，
        直接落在当前组里面。
        """
        if not nested and self._has_stage:
            self.commands.append({"command": "layer.select", "params": {"name": self.base_layer}})
        command = {"command": "layer.new.group", "params": {"name": str(name)}}
        if nested:
            command["_nested"] = True
        self.commands.append(command)
        self._has_stage = True

    def rect(self, x, y, w, h, fill="surface", stroke_width=None, stroke="line", name=None) -> None:
        self.commands.append({
            "command": "shape.create",
            "params": {
                "kind": "rect",
                "rect": self._rect(x, y, w, h),
                "fill": color_of(self.palette, fill),
                "stroke": self._stroke(stroke_width, stroke),
                **({"name": str(name)} if name else {}),
            },
        })

    def _radii(self, value):
        if isinstance(value, (list, tuple)):
            if len(value) != 4:
                raise ValueError("圆角给四个角时必须写 [左上, 右上, 右下, 左下]")
            return [self._size(item) for item in value]
        return self._size(value)

    def rounded_rect(self, x, y, w, h, radius=12, fill="surface", stroke_width=None, stroke="line", name=None) -> None:
        self.commands.append({
            "command": "shape.create",
            "params": {
                "kind": "roundedRect",
                "rect": self._rect(x, y, w, h),
                "radii": self._radii(radius),
                "fill": color_of(self.palette, fill),
                "stroke": self._stroke(stroke_width, stroke),
                **({"name": str(name)} if name else {}),
            },
        })

    def ellipse(self, cx, cy, rx, ry, fill="surface", stroke_width=None, stroke="line", name=None) -> None:
        self.commands.append({
            "command": "shape.create",
            "params": {
                "kind": "ellipse",
                "rect": self._rect(cx - rx, cy - ry, rx * 2, ry * 2),
                "fill": color_of(self.palette, fill),
                "stroke": self._stroke(stroke_width, stroke),
                **({"name": str(name)} if name else {}),
            },
        })

    def line(self, x1, y1, x2, y2, width=2, color="line", name=None) -> None:
        self.commands.append({
            "command": "shape.create",
            "params": {
                "kind": "line",
                "from": [self._x(x1), self._x(y1)],
                "to": [self._x(x2), self._x(y2)],
                "weight": self._size(width),
                "fill": color_of(self.palette, color),
                **({"name": str(name)} if name else {}),
            },
        })

    def text(self, x, y, text, size=24, color="ink", font="Noto Serif CJK SC",
             align=None, weight=None, tracking=None, name=None) -> None:
        params = {
            "x": self._x(x),
            "y": self._x(y),
            "text": str(text),
            "font": str(font),
            "size": self._size(size),
            "color": color_of(self.palette, color),
        }
        if align:
            params["align"] = str(align)
        if weight:
            params["weight"] = int(weight)
        if tracking is not None:
            params["tracking"] = int(tracking)
        if name:
            params["name"] = str(name)
        self.commands.append({"command": "type.create", "params": params})
