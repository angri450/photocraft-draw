# -*- coding: utf-8 -*-
"""变宽笔触：沿中心线两侧算出轮廓，围成封闭多边形填充。

等宽的 ``line`` 画不出毛笔的提按；这里允许中心线上每个点有自己的宽度，
沿相邻线段的法线方向向两侧偏移，再把左右两条边首尾接起来。结果是
一条真实的多边形，粗细变化在轮廓里，不依赖描边宽度。

用法：

    branch = [[110, 405], [170, 360], [240, 310], [320, 275]]
    stroke_path(pen, branch, taper(len(branch), 12, 2), "mid", name="枝干")

    ring = [[240, 180], [320, 170], [350, 230], [300, 280], [235, 250]]
    stroke_path(pen, ring, taper(len(ring), 1.2, 9), "deep", closed=True,
                name="花瓣边缘")

拐角用斜接：把相邻两段的法线取平分方向，偏移量按夹角放大。夹角越小，
斜接越长，所以偏移量会被「相邻三个点的最小宽度」和「较短那段的一半」
同时截断，避免尖角戳出去造成自交。宽度给 0 时该点收成一个尖。
"""
from __future__ import annotations

import math

from .commands import Pen
from .palette import color_of

EPSILON = 1e-9


def _read_points(value) -> list[tuple[float, float]]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError("stroke_path 需要 points：至少两个 [x, y] 点")
    points = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("points 里每一项都要是 [x, y]")
        x, y = item
        if (isinstance(x, bool) or isinstance(y, bool)
                or not isinstance(x, (int, float)) or not isinstance(y, (int, float))):
            raise ValueError("points 里每一项都要是 [x, y]，坐标必须是数字")
        points.append((float(x), float(y)))
    return points


def _read_widths(value, count: int) -> list[float]:
    if isinstance(value, bool):
        raise ValueError("stroke_path 的 widths 要给一个数，或给与 points 等长的数组")
    if isinstance(value, (int, float)):
        values = [float(value)] * count
    elif isinstance(value, (list, tuple)):
        if len(value) != count:
            raise ValueError(
                f"widths 要和 points 等长：{count} 个点，收到 {len(value)} 个宽度"
            )
        values = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError("widths 里每一项都要是数字")
            values.append(float(item))
    else:
        raise ValueError("stroke_path 的 widths 要给一个数，或给与 points 等长的数组")
    for item in values:
        if item < 0:
            raise ValueError("widths 不能是负数")
    return values


def _distance(a, b) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _drop_duplicates(points, widths, closed: bool):
    """去掉相邻的重复点，否则算不出法线；重复点保留较大的宽度。"""
    kept_points = [points[0]]
    kept_widths = [widths[0]]
    for point, width in zip(points[1:], widths[1:]):
        if _distance(kept_points[-1], point) <= EPSILON:
            kept_widths[-1] = max(kept_widths[-1], width)
            continue
        kept_points.append(point)
        kept_widths.append(width)
    if closed and len(kept_points) > 2 and _distance(kept_points[0], kept_points[-1]) <= EPSILON:
        kept_points.pop()
        kept_widths.pop()
    return kept_points, kept_widths


def _segment(start, end) -> tuple[float, float, float]:
    """返回单位方向向量和段长。"""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    return dx / length, dy / length, length


def _offset_side(points, widths, closed: bool, side: float, miter_limit: float):
    """把中心线向一侧平移半个宽度，side 为 +1 或 -1。"""
    count = len(points)
    result = []
    for index in range(count):
        half = widths[index] / 2
        if not closed and index == 0:
            dx, dy, _ = _segment(points[0], points[1])
            result.append((points[0][0] - dy * side * half, points[0][1] + dx * side * half))
            continue
        if not closed and index == count - 1:
            dx, dy, _ = _segment(points[index - 1], points[index])
            result.append((points[index][0] - dy * side * half, points[index][1] + dx * side * half))
            continue

        previous = (index - 1) % count
        following = (index + 1) % count
        dx_in, dy_in, length_in = _segment(points[previous], points[index])
        dx_out, dy_out, length_out = _segment(points[index], points[following])
        nx_in, ny_in = -dy_in * side, dx_in * side
        nx_out, ny_out = -dy_out * side, dx_out * side

        bx = nx_in + nx_out
        by = ny_in + ny_out
        bisector_length = math.hypot(bx, by)
        if bisector_length <= EPSILON:
            # 原路折返，没有可用的平分线，按来向偏移。
            result.append((points[index][0] + nx_in * half, points[index][1] + ny_in * half))
            continue

        bx /= bisector_length
        by /= bisector_length
        cosine = max(bx * nx_in + by * ny_in, 0.2)
        miter = half / cosine

        # 斜接太尖时按最小宽度截断，同时不超过相邻较短线段的一半。
        smallest = min(widths[index], widths[previous], widths[following]) / 2
        limit = min(smallest * miter_limit,
                    max(0.5 * min(length_in, length_out), half))
        limit = max(limit, half)
        miter = min(max(miter, half), limit)

        result.append((points[index][0] + bx * miter, points[index][1] + by * miter))
    return result


def _signed_area(points) -> float:
    total = 0.0
    count = len(points)
    for index in range(count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % count]
        total += x1 * y2 - x2 * y1
    return total / 2


def _scaled(pen: Pen, points):
    return [[int(round(x * pen.k)), int(round(y * pen.k))] for x, y in points]


def _ring(pen: Pen, left, right, color, name) -> None:
    """闭合环：面积大的一条当外轮廓，另一条用 subtract 挖掉。

    Pen.path 只保留 closed 和 knots，会丢掉子路径的 op；这里直接拼一条
    shape.create，才能让引擎把内轮廓减掉。
    """
    if abs(_signed_area(left)) >= abs(_signed_area(right)):
        outer, inner = left, right
    else:
        outer, inner = right, left
    pen.commands.append({
        "command": "shape.create",
        "params": {
            "kind": "path",
            "path": {
                "subpaths": [
                    {"closed": True, "op": "combine", "knots": _scaled(pen, outer)},
                    {"closed": True, "op": "subtract", "knots": _scaled(pen, inner)},
                ],
                "fillRule": "nonzero",
            },
            "fill": color_of(pen.palette, color),
            "stroke": None,
            **({"name": str(name)} if name else {}),
        },
    })


def stroke_path(pen: Pen, points, widths, color, closed: bool = False,
                *, miter_limit: float = 2.0, name=None) -> None:
    """沿中心线画一条变宽笔触。

    参数：
        pen          绘图笔
        points       [[x, y], …]，中心线，参考坐标，至少两个点
        widths       每个点的宽度：一个数表示等宽，数组表示变宽（按参考坐标写，
                     pen 会统一放大）
        color        填充色，配色角色名或 #rrggbb
        closed       true 时中心线首尾相接，画成一条闭合的环
        miter_limit  斜接长度上限，按相邻最小宽度的倍数算，默认 2.0
        name         形状名，写进 PSD 图层，方便批注

    闭合环会输出两条子路径：面积大的是外轮廓，小的用 subtract 挖掉，
    所以中心线围出的形状是空心的。引擎对同向子路径不会自动挖孔，
    必须用 op 明确做差集。
    """
    if isinstance(miter_limit, bool) or not isinstance(miter_limit, (int, float)) or miter_limit <= 0:
        raise ValueError("miter_limit 要大于 0")

    pts = _read_points(points)
    ws = _read_widths(widths, len(pts))
    pts, ws = _drop_duplicates(pts, ws, closed)

    if len(pts) < 2:
        raise ValueError("stroke_path 的中心线至少要两个不同的点")
    if closed and len(pts) < 3:
        raise ValueError("闭合笔触的中心线至少要三个不同的点")

    left = _offset_side(pts, ws, closed, 1.0, float(miter_limit))
    right = _offset_side(pts, ws, closed, -1.0, float(miter_limit))

    if closed:
        _ring(pen, left, right, color, name)
        return

    subpaths = [{"closed": True, "knots": left + list(reversed(right))}]
    pen.path(subpaths, fill=color, stroke_width=None, stroke=None,
             fill_rule="nonzero", name=name)


def taper(n: int, w0: float, w1: float) -> list[float]:
    """生成 n 个从 w0 线性变到 w1 的宽度，画枝干和叶尖时用。"""
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError("taper 的 n 要是整数")
    if n < 1:
        raise ValueError("taper 的 n 至少为 1")
    for value, label in ((w0, "w0"), (w1, "w1")):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"taper 的 {label} 要是数字")
        if value < 0:
            raise ValueError(f"taper 的 {label} 不能是负数")
    if n == 1:
        return [float(w0)]
    start, end = float(w0), float(w1)
    return [start + (end - start) * index / (n - 1) for index in range(n)]


__all__ = ["stroke_path", "taper"]
