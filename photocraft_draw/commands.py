# -*- coding: utf-8 -*-
"""绘图笔：把参考坐标换算成画布坐标，并生成绘制指令。"""
from __future__ import annotations

import contextlib

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
        self._group: str | None = None
        self._group_by: str | None = None
        self._group_prefix: str = ""
        self._layer: str | None = None
        self._exempt: list = []

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

    @contextlib.contextmanager
    def group(self, name: str | None):
        """声明在这个范围内画出的部件属于同一组。

        同一个物体的各个部位颜色接近是正常的，配色检查不该报冲突。
        部件名说不清归属的时候，组件在这里写明。例如一块石头的本体、
        投影、高光和底座：

            with pen.group("石头 1"):
                pen.ellipse(..., name="石块 1")
                pen.ellipse(..., name="石影 1")
                pen.ellipse(..., name="石光 1")
                pen.ellipse(..., name="石底 1")

        嵌套的时候用外层的组名。
        """
        previous = self._group
        self._group = str(name) if name is not None else previous
        try:
            yield self
        finally:
            self._group = previous

    @contextlib.contextmanager
    def group_by(self, prefix: str | None = None):
        """声明在这个范围内画出的部件按主体归组。

        同类的物件归成一组。树冠 1、树冠 2、树冠 3 都是树冠，同一组，
        它们之间不查色差。

        prefix 给的时候用「前缀 + 主体词」，可以在一段代码里画多种物件，
        各自成组。不给就用部件名去掉编号后的主体词。

        主体词怎么算，和 grouping.group 的规则一致。
        """
        previous = self._group
        self._group_by = str(prefix) if prefix is not None else ""
        self._group_prefix = str(prefix) if prefix is not None else ""
        try:
            yield self
        finally:
            self._group = previous
            self._group_by = None
            self._group_prefix = ""

    def _named(self, name):
        """给部件带上当前分组的声明。"""
        params = {"name": str(name)} if name else {}
        if self._layer:
            params["layer"] = self._layer
        if self._exempt:
            params["exempt"] = list(self._exempt)
        if self._group:
            params["group"] = self._group
        elif self._group_by is not None:
            # 按主体归组：主体词相同的部件落进同一组
            from .grouping import subject_of

            subject = subject_of(name)
            if self._group_prefix:
                params["group"] = f"{self._group_prefix} {subject}"
            else:
                params["group"] = subject
        return params

    def stage(self, name: str, nested: bool = False, exempt=None) -> None:
        if not nested:
            self._layer = str(name)
            self._exempt = [str(item) for item in (exempt or [])]
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
                **self._named(name),
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
                **self._named(name),
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
                **self._named(name),
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
                **self._named(name),
            },
        })

    def path(self, subpaths, fill="surface", stroke_width=None, stroke="line",
             fill_rule="nonzero", name=None) -> None:
        """画任意路径。

        subpaths 里每一项是 {"closed": 是否闭合, "knots": [...]}，knots 可以是
        [x, y]，也可以是 {"anchor": [x, y], "in": [x, y], "out": [x, y]}，
        带 in/out 的就是贝塞尔控制点。坐标按参考画布写，这里统一缩放。
        """
        scaled = []
        for sub in subpaths:
            knots = []
            for knot in sub.get("knots") or []:
                if isinstance(knot, dict):
                    item = {"anchor": self._xy(knot.get("anchor"))}
                    if knot.get("in") is not None:
                        item["in"] = self._xy(knot["in"])
                    if knot.get("out") is not None:
                        item["out"] = self._xy(knot["out"])
                    if knot.get("smooth"):
                        item["smooth"] = True
                    knots.append(item)
                else:
                    knots.append(self._xy(knot))
            scaled.append({"closed": bool(sub.get("closed", True)), "knots": knots})
        self.commands.append({
            "command": "shape.create",
            "params": {
                "kind": "path",
                "path": {"subpaths": scaled, "fillRule": fill_rule},
                "fill": color_of(self.palette, fill),
                "stroke": self._stroke(stroke_width, stroke),
                **self._named(name),
            },
        })

    def _xy(self, point) -> list[int]:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("路径点要写成 [x, y]")
        return [self._x(point[0]), self._x(point[1])]

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
