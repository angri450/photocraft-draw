# -*- coding: utf-8 -*-
"""几何相交：两个部件的填充形状有没有真的碰上。

包围盒相交只是粗筛。天空横贯整个画布，包围盒和任何东西都相交，
可它跟草坡之间隔着两层山和一条河。

这里直接拿绘制指令里的路径算。路径是贝塞尔曲线，先离散成多边形，
再做相交测试。椭圆和矩形也一并处理。

用法：
    from photocraft_draw.geometry import shapes_intersect
    hit = shapes_intersect(first_command, second_command)
"""
from __future__ import annotations

import math

# 贝塞尔曲线离散成线段的份数。一段贝塞尔最多跨 100 像素，
# 每 4 像素取一个点，弯曲的地方够准了。
CURVE_STEP = 4.0


def _bezier_points(p0, p1, p2, p3, step: float = CURVE_STEP):
    """三次贝塞尔离散成点列。"""
    # 估算弧长，决定取多少个点
    rough = (abs(p1[0] - p0[0]) + abs(p1[1] - p0[1])
             + abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])
             + abs(p3[0] - p2[0]) + abs(p3[1] - p2[1]))
    count = max(2, min(64, int(rough / step) + 1))
    points = []
    for index in range(count + 1):
        t = index / count
        u = 1.0 - t
        x = (u ** 3 * p0[0] + 3 * u * u * t * p1[0]
             + 3 * u * t * t * p2[0] + t ** 3 * p3[0])
        y = (u ** 3 * p0[1] + 3 * u * u * t * p1[1]
             + 3 * u * t * t * p2[1] + t ** 3 * p3[1])
        points.append((x, y))
    return points


def _polygon_of_path(params: dict) -> list[list[tuple[float, float]]]:
    """路径指令转成多边形列表。每个子路径一个多边形。"""
    polygons = []
    path = params.get("path") or {}
    for sub in path.get("subpaths") or []:
        knots = sub.get("knots") or []
        if len(knots) < 2:
            continue
        anchors = []
        controls = []
        for knot in knots:
            if isinstance(knot, dict):
                anchor = knot.get("anchor") or [0, 0]
                anchors.append((float(anchor[0]), float(anchor[1])))
                controls.append((knot.get("in"), knot.get("out")))
            else:
                anchors.append((float(knot[0]), float(knot[1])))
                controls.append((None, None))

        count = len(anchors)
        points = []
        for index in range(count):
            p0 = anchors[(index - 1) % count]
            p1 = anchors[index]
            p2 = anchors[(index + 1) % count]
            p3 = anchors[(index + 2) % count]
            in_control = controls[index][0]
            out_control = controls[index][1]
            if in_control is None and out_control is None:
                points.append(p1)
                continue
            c1 = (float(in_control[0]), float(in_control[1])) if in_control else p1
            c2 = (float(out_control[0]), float(out_control[1])) if out_control else p2
            points.extend(_bezier_points(p1, c1, c2, p2)[1:])
        if len(points) >= 3:
            polygons.append(points)
    return polygons


def _polygon_of_ellipse(params: dict) -> list[list[tuple[float, float]]]:
    rect = params.get("rect") or [0, 0, 0, 0]
    x, y, width, height = float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
    cx, cy = x + width / 2, y + height / 2
    rx, ry = max(width / 2, 0.5), max(height / 2, 0.5)
    steps = max(12, min(64, int(max(rx, ry) / 2) + 8))
    points = []
    for index in range(steps):
        angle = 2 * math.pi * index / steps
        points.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
    return [points]


def _polygon_of_rect(params: dict) -> list[list[tuple[float, float]]]:
    rect = params.get("rect") or [0, 0, 0, 0]
    x, y, width, height = float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
    return [[(x, y), (x + width, y), (x + width, y + height), (x, y + height)]]


def polygons_of(command: dict) -> list[list[tuple[float, float]]]:
    """一条绘制指令的填充形状，转成多边形列表。"""
    if command.get("command") != "shape.create":
        return []
    params = command.get("params") or {}
    kind = params.get("kind")
    if kind == "path":
        return _polygon_of_path(params)
    if kind == "ellipse":
        return _polygon_of_ellipse(params)
    if kind in ("rect", "roundedRect"):
        return _polygon_of_rect(params)
    if kind == "line":
        return []
    return []


def _point_in_polygon(point, polygon) -> bool:
    x, y = point
    inside = False
    count = len(polygon)
    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        if (y1 > y) != (y2 > y):
            cut = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < cut:
                inside = not inside
    return inside


def _segments_cross(a, b, c, d) -> bool:
    def orient(p, q, r):
        value = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        if value > 1e-9:
            return 1
        if value < -1e-9:
            return -1
        return 0

    def on_segment(p, q, r):
        return (min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
                and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9)

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_segment(a, c, b):
        return True
    if o2 == 0 and on_segment(a, d, b):
        return True
    if o3 == 0 and on_segment(c, a, d):
        return True
    if o4 == 0 and on_segment(c, b, d):
        return True
    return False


def _bbox(polygon):
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_overlap(a, b) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def polygons_intersect(first, second) -> bool:
    """两个多边形有没有相交。

    先用包围盒筛掉明显不挨着的，再用线段相交和点包含判断。
    """
    boxes_first = [_bbox(polygon) for polygon in first]
    boxes_second = [_bbox(polygon) for polygon in second]

    for index_a, a in enumerate(first):
        for index_b, b in enumerate(second):
            if not _bbox_overlap(boxes_first[index_a], boxes_second[index_b]):
                continue
            if _point_in_polygon(a[0], b) or _point_in_polygon(b[0], a):
                return True
            count_a = len(a)
            count_b = len(b)
            for i in range(count_a):
                p1 = a[i]
                p2 = a[(i + 1) % count_a]
                for j in range(count_b):
                    if _segments_cross(p1, p2, b[j], b[(j + 1) % count_b]):
                        return True
    return False


def shapes_intersect(first: dict, second: dict) -> bool:
    """两条绘制指令的填充形状有没有真的碰上。"""
    first_polygons = polygons_of(first)
    second_polygons = polygons_of(second)
    if not first_polygons or not second_polygons:
        return False
    return polygons_intersect(first_polygons, second_polygons)


def adjacent_by_geometry(commands: list[dict], groups: dict[str, str]) -> list[tuple[str, str]]:
    """按形状相交找相邻的部件。

    commands 是绘制指令，groups 是部件名到组名的对应。
    只在组与组之间判相邻，同一组内部的部件不算。
    """
    shapes = {}
    for command in commands:
        if command.get("command") != "shape.create":
            continue
        name = (command.get("params") or {}).get("name")
        if not name:
            continue
        polygons = polygons_of(command)
        if polygons:
            shapes[name] = (polygons, _bbox(polygons[0]))

    names = list(shapes)
    result = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            first, second = names[i], names[j]
            if groups.get(first) == groups.get(second):
                continue
            if not _bbox_overlap(shapes[first][1], shapes[second][1]):
                continue
            if polygons_intersect(shapes[first][0], shapes[second][0]):
                result.append((first, second))
    return result
