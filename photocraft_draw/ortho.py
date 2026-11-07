# -*- coding: utf-8 -*-
"""正交投影与三视图。

同一份三维点集，换三个正交相机各看一次，全程不除以深度：

    front  沿 -Z 看  取 (x, y)
    left   沿 +X 看  取 (z, y)
    top    沿 -Y 看  取 (x, z)

ortho_project 只负责坐标映射，返回数学坐标，v 轴向上。render_views 把三个
视图横向并排画进一张画布，共用同一个比例尺；落纸的时候 v 轴翻成画布向下。

三个视图默认共用竖向中点。build_views 和 render_views 传 center_per_view=True
时，每个视图按自身内容的中点对齐画板中点，比例尺和横向对齐都不变；俯视图
深度大、把正视图和左视图压到面板底部时用这个开关。

视图里的线只画外轮廓和硬折边：背面剔掉，被前面物体挡住的段不画。折边阈值
用 crease_angle 调，默认 25 度；hidden_lines=True 时把被挡的边画成虚线，
默认关闭。线宽按深度走，近处 1.6 像素、远处 1.0 像素。

网格只按 vertices 和 faces 两个字段读，不 import mesh.py：传字典也行，传带
同名属性的对象也行。面的顶点按逆时针写，法向量朝外，背面会自动剔除。

花形用 make_blossom(center, diameter, facing=(0, 0, 1), petals=5) 生成，返回
带 shape="blossom" 标记的网格；带这个标记或者带 petals 字段的对象按花形画，
不做法向剔除，侧视压成一条也保留同色描边。

用法：
    from photocraft_draw.ortho import ortho_project, render_views

    flat = ortho_project([[1, 2, 3]], "front", 2)     # [[2, 4]]
    render_views(meshes, "out/ortho-demo.png")

演示图可以直接跑：
    python3 -m photocraft_draw.ortho --out out/ortho-demo.png
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from .commands import Pen
from .palette import color_of, resolve_palette

AXES = ("front", "left", "top")
AXIS_TITLES = {"front": "正视图", "left": "左视图", "top": "俯视图"}

# 相机看出去的方向。面和它同向就是背面，剔掉。
FORWARD = {
    "front": (0.0, 0.0, -1.0),
    "left": (1.0, 0.0, 0.0),
    "top": (0.0, -1.0, 0.0),
}

# 光从左上偏前来。三个视图各自能看到的那一面都不会太暗。
LIGHT = (-0.38, 0.82, 0.43)

PAGE_COLOR = "bg"
PANEL_COLOR = "surface"
LINE_COLOR = "line"
TEXT_COLOR = "muted"

MARGIN = 28
TITLE_BAND = 46
DEFAULT_OFFSET = 22.0
# 尺寸文字往物体那一侧收，贴着尺寸线内侧，不往画板边缘跑。
LABEL_OFFSET = -12.0

# 消隐轮廓：近处粗、远处细；折边超过这个角度才算硬折边。
EDGE_NEAR = 1.6
EDGE_FAR = 1.0
DEFAULT_CREASE = 46.0
EDGE_STEP = 3.0
EDGE_COLOR = "ink"
HIDDEN_COLOR = "muted"


def _numbers(point, where: str) -> list[float]:
    """读一个 [x, y, z]，形状不对就说清楚是哪一处。"""
    if not isinstance(point, (list, tuple)) or len(point) != 3:
        raise ValueError("%s 要写成 [x, y, z]" % where)
    try:
        return [float(value) for value in point]
    except (TypeError, ValueError):
        raise ValueError("%s 要写成 [x, y, z]" % where) from None


def ortho_project(points, axis: str, scale: float = 1.0):
    """把三维点按一个轴向压成二维，不除以深度。

    points 是 [[x, y, z], …]；axis 取 front、left、top；scale 是同一比例尺，
    乘在两个轴上。返回 [[x, y], …]，坐标是数学坐标，v 轴向上。
    """
    if axis not in AXES:
        raise ValueError("投影轴向只能是 %s，收到 %s" % ("、".join(AXES), axis))
    if not isinstance(points, (list, tuple)) or not points:
        raise ValueError("正交投影需要至少一个点，收到的是空点集")
    factor = float(scale)
    if factor == 0:
        raise ValueError("正交投影的比例尺不能是 0")

    flat = []
    for index, point in enumerate(points):
        x, y, z = _numbers(point, "第 %d 个点" % (index + 1))
        if axis == "front":
            u, v = x, y
        elif axis == "left":
            u, v = z, y
        else:
            u, v = x, z
        flat.append([u * factor, v * factor])
    return flat


def _field(mesh, key: str, default=None):
    """网格字段，字典和对象都能读。"""
    if isinstance(mesh, dict):
        return mesh.get(key, default)
    return getattr(mesh, key, default)


def _mesh_data(mesh, index: int):
    """读一份网格，返回 (顶点, 面, 颜色, 名字, 是不是花形)。

    只认 vertices 和 faces；带 shape="blossom" 或者带 petals 字段的按花形画，
    花形不做法向剔除，侧视压成一条也照样画出来。
    """
    number = index + 1
    vertices = _field(mesh, "vertices")
    faces = _field(mesh, "faces")
    if not isinstance(vertices, (list, tuple)) or not vertices:
        raise ValueError("第 %d 个网格没有 vertices，或者顶点是空的" % number)
    if not isinstance(faces, (list, tuple)) or not faces:
        raise ValueError("第 %d 个网格没有 faces，或者面是空的" % number)

    points = [_numbers(point, "第 %d 个网格的第 %d 个顶点" % (number, order + 1))
              for order, point in enumerate(vertices)]

    polygons = []
    for order, face in enumerate(faces):
        if not isinstance(face, (list, tuple)) or len(face) < 3:
            raise ValueError("第 %d 个网格的第 %d 个面至少要有三个顶点" % (number, order + 1))
        try:
            ids = [int(item) for item in face]
        except (TypeError, ValueError):
            raise ValueError("第 %d 个网格的第 %d 个面里，顶点编号必须都是整数"
                             % (number, order + 1)) from None
        if any(item < 0 or item >= len(points) for item in ids):
            raise ValueError("第 %d 个网格的第 %d 个面引用了不存在的顶点" % (number, order + 1))
        polygons.append(ids)

    color = _field(mesh, "color") or "mid"
    name = _field(mesh, "name") or "网格 %d" % number
    shape = str(_field(mesh, "shape") or "")
    blossom = shape == "blossom" or _field(mesh, "petals") is not None
    return points, polygons, str(color), str(name), blossom


def _normal(vertices, face):
    """面的法向量，用 Newell 方法算，凹多边形也稳。"""
    nx = ny = nz = 0.0
    count = len(face)
    for index in range(count):
        ax, ay, az = vertices[face[index]]
        bx, by, bz = vertices[face[(index + 1) % count]]
        nx += (ay - by) * (az + bz)
        ny += (az - bz) * (ax + bx)
        nz += (ax - bx) * (ay + by)
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-12:
        return 0.0, 0.0, 0.0
    return nx / length, ny / length, nz / length


def _center(vertices, face):
    count = len(face)
    x = sum(vertices[index][0] for index in face) / count
    y = sum(vertices[index][1] for index in face) / count
    z = sum(vertices[index][2] for index in face) / count
    return x, y, z


def _depth(point, axis: str) -> float:
    """离观众多远，越远值越大。画家算法按这个从大到小画。"""
    x, y, z = point
    if axis == "front":
        return z
    if axis == "left":
        return x
    return -y


def _dot(first, second) -> float:
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2]


def _cross(first, second):
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _normalize(vector):
    length = math.sqrt(_dot(vector, vector))
    if length <= 1e-12:
        raise ValueError("方向向量不能是零向量")
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def make_blossom(center=None, diameter=0.0, facing=(0.0, 0.0, 1.0), petals=5,
                 color="#C8455F", name="花"):
    """做一朵薄片花：花瓣绕中心排一圈，瓣尖带凹缺，厚度为零。

    参数：
        center   [x, y, z]，花心位置，必填
        diameter 花径，必填，必须大于 0
        facing   花面朝向，默认 [0, 0, 1]，零向量报错
        petals   花瓣数，默认 5，至少 3
        color    颜色，默认 #C8455F
        name     名字，默认「花」

    返回一份 dict 网格：vertices、faces、color、name，外加 shape="blossom"、
    petals、center、diameter、facing 几个标记。ortho 认这个标记，按花形画，
    不做法向剔除，侧视压成一条也保留同色描边，不会露白缝。
    """
    if center is None:
        raise ValueError("花形需要 center：[x, y, z]")
    cx, cy, cz = _numbers(center, "花形的 center")
    size = float(diameter)
    if size <= 0:
        raise ValueError("花形的 diameter 必须大于 0")
    count = int(petals)
    if count < 3:
        raise ValueError("花形的 petals 至少为 3")
    normal = _normalize(_numbers(facing, "花形的 facing"))

    # 花面里的两个基向量。朝向接近竖直时换辅助向量，免得叉积退化。
    helper = (0.0, 1.0, 0.0) if abs(normal[1]) < 0.9 else (1.0, 0.0, 0.0)
    axis_u = _normalize(_cross(helper, normal))
    axis_v = _normalize(_cross(normal, axis_u))

    radius = size / 2.0
    # 半宽略大于半个瓣距，相邻花瓣叠一点，同色描边把接缝盖住。
    half = (math.pi / count) * 1.06
    # 单瓣轮廓：中心、左缘、左肩、左尖、瓣尖凹缺、右尖、右肩、右缘。
    # 半径收到 0.35 再抬到 1.0，瓣与瓣之间才有清楚的 V 形缺口。
    profile = [
        (0.35, -1.00), (0.72, -0.80), (0.92, -0.62), (1.00, -0.45),
        (0.86, -0.22), (0.74, 0.00),
        (0.86, 0.22), (1.00, 0.45), (0.92, 0.62), (0.72, 0.80),
        (0.35, 1.00),
    ]

    vertices = []
    faces = []
    for petal in range(count):
        angle = 2.0 * math.pi * petal / count
        face = [len(vertices)]
        vertices.append([cx, cy, cz])
        for ratio, spread in profile:
            theta = angle + half * spread
            a = math.cos(theta) * radius * ratio
            b = math.sin(theta) * radius * ratio
            vertices.append([
                cx + axis_u[0] * a + axis_v[0] * b,
                cy + axis_u[1] * a + axis_v[1] * b,
                cz + axis_u[2] * a + axis_v[2] * b,
            ])
            face.append(len(vertices) - 1)
        faces.append(face)

    return {
        "vertices": vertices, "faces": faces,
        "color": str(color), "name": str(name),
        "shape": "blossom", "petals": count,
        "center": [cx, cy, cz], "diameter": size, "facing": list(normal),
    }


def _light(normal) -> float:
    """法向量跟光的夹角换成明度系数，保持平涂的克制。"""
    return 0.60 + 0.40 * max(0.0, _dot(normal, LIGHT))


def _shade(color: str, factor: float) -> str:
    text = str(color).lstrip("#")
    if len(text) != 6:
        return str(color)
    try:
        channels = [int(text[index:index + 2], 16) for index in (0, 2, 4)]
    except ValueError:
        return str(color)
    return "#%02X%02X%02X" % tuple(
        max(0, min(255, round(channel * factor))) for channel in channels)


def edge_width(depth, near_depth, far_depth, near_width=EDGE_NEAR, far_width=EDGE_FAR):
    """按深度给线宽：最近 near_width，最远 far_width，中间线性插值。"""
    if far_depth - near_depth <= 1e-9:
        return float(near_width)
    ratio = (float(depth) - float(near_depth)) / (float(far_depth) - float(near_depth))
    ratio = max(0.0, min(1.0, ratio))
    return float(near_width) + (float(far_width) - float(near_width)) * ratio


def _mesh_edges(faces) -> dict:
    """无向边到相邻面的表。一条边最多被两个面共用，开放边只有一个。"""
    edges = {}
    for face_index, face in enumerate(faces):
        count = len(face)
        for step in range(count):
            first = face[step]
            second = face[(step + 1) % count]
            key = (first, second) if first < second else (second, first)
            edges.setdefault(key, []).append(face_index)
    return edges


def _dihedral(first, second) -> float:
    """两个法向量的夹角，单位度。"""
    value = max(-1.0, min(1.0, _dot(first, second)))
    return math.degrees(math.acos(value))


class _DepthGrid:
    """投影平面上的粗略深度缓冲，判断一条边有没有被更近的面挡住。

    网格间距两像素，按屏幕位置查最近表面的深度就够了；只用来做可见性
    的粗判，不参与上色。
    """

    def __init__(self, left, top, width, height, step: float = 2.0):
        self.left = float(left)
        self.top = float(top)
        self.step = float(step)
        self.cols = max(1, int(math.ceil(float(width) / self.step)))
        self.rows = max(1, int(math.ceil(float(height) / self.step)))
        self.data = [None] * (self.cols * self.rows)

    def _index(self, px, py):
        col = int((px - self.left) / self.step)
        row = int((py - self.top) / self.step)
        if col < 0 or row < 0 or col >= self.cols or row >= self.rows:
            return None
        return row * self.cols + col

    def depth_at(self, px, py):
        index = self._index(px, py)
        return None if index is None else self.data[index]

    def _store(self, index, depth):
        old = self.data[index]
        if old is None or depth < old:
            self.data[index] = depth

    def fill(self, screen_points, depths) -> None:
        """把一块凸多边形按扇形拆成三角形铺进缓冲，只留最近深度。"""
        if len(screen_points) < 3:
            return
        for step in range(1, len(screen_points) - 1):
            self._fill_triangle(screen_points[0], screen_points[step],
                                screen_points[step + 1],
                                depths[0], depths[step], depths[step + 1])

    def _fill_triangle(self, a, b, c, da, db, dc) -> None:
        ax, ay = a
        bx, by = b
        cx, cy = c
        denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(denominator) < 1e-12:
            return
        col0 = max(0, int((min(ax, bx, cx) - self.left) / self.step) - 1)
        col1 = min(self.cols - 1, int((max(ax, bx, cx) - self.left) / self.step) + 1)
        row0 = max(0, int((min(ay, by, cy) - self.top) / self.step) - 1)
        row1 = min(self.rows - 1, int((max(ay, by, cy) - self.top) / self.step) + 1)
        for row in range(row0, row1 + 1):
            py = self.top + (row + 0.5) * self.step
            for col in range(col0, col1 + 1):
                px = self.left + (col + 0.5) * self.step
                w0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
                if w0 < -1e-9:
                    continue
                w1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
                if w1 < -1e-9:
                    continue
                w2 = 1.0 - w0 - w1
                if w2 < -1e-9:
                    continue
                self._store(row * self.cols + col, w0 * da + w1 * db + w2 * dc)

    def fill_ellipse(self, cx, cy, rx, ry, depth) -> None:
        """侧视花是一个扁椭圆，按椭圆覆盖的范围铺深度。"""
        if rx <= 0 or ry <= 0:
            return
        col0 = max(0, int((cx - rx - self.left) / self.step) - 1)
        col1 = min(self.cols - 1, int((cx + rx - self.left) / self.step) + 1)
        row0 = max(0, int((cy - ry - self.top) / self.step) - 1)
        row1 = min(self.rows - 1, int((cy + ry - self.top) / self.step) + 1)
        for row in range(row0, row1 + 1):
            py = self.top + (row + 0.5) * self.step
            for col in range(col0, col1 + 1):
                px = self.left + (col + 0.5) * self.step
                nx = (px - cx) / rx
                ny = (py - cy) / ry
                if nx * nx + ny * ny <= 1.0:
                    self._store(row * self.cols + col, depth)


def _visibility_runs(start, end, start_depth, end_depth, grid, epsilon):
    """沿屏幕线段采样，返回 [(起点比例, 终点比例, 是否可见), …]。"""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return []
    count = max(2, int(length / EDGE_STEP) + 1)
    flags = []
    for step in range(count):
        ratio = step / (count - 1)
        px = start[0] + dx * ratio
        py = start[1] + dy * ratio
        depth = start_depth + (end_depth - start_depth) * ratio
        blocker = grid.depth_at(px, py) if grid is not None else None
        flags.append(blocker is None or blocker >= depth - epsilon)

    runs = []
    begin = 0
    for step in range(1, count + 1):
        if step == count or flags[step] != flags[begin]:
            runs.append((begin / (count - 1), (step - 1) / (count - 1), flags[begin]))
            begin = step
    return runs


def _edge_line(pen, start, end, width, color, name) -> None:
    """画一条消隐线，线宽按像素给，绕开 Pen 的整数取整。"""
    pen.line(start[0], start[1], end[0], end[1], width=width, color=color, name=name)
    pen.commands[-1]["params"]["weight"] = max(0.4, round(width * pen.k, 2))


def _join_collinear(first, second, tolerance=0.8):
    """两条线段共线且首尾相接就接成一条，接不上返回 None。"""
    pairs = (
        (first["start"], first["end"], second["start"], second["end"]),
        (first["start"], first["end"], second["end"], second["start"]),
        (first["end"], first["start"], second["start"], second["end"]),
        (first["end"], first["start"], second["end"], second["start"]),
    )
    for shared_a, far_a, shared_b, far_b in pairs:
        if math.hypot(shared_a[0] - shared_b[0], shared_a[1] - shared_b[1]) > tolerance:
            continue
        ax = far_a[0] - shared_a[0]
        ay = far_a[1] - shared_a[1]
        bx = far_b[0] - shared_b[0]
        by = far_b[1] - shared_b[1]
        length_a = math.hypot(ax, ay)
        length_b = math.hypot(bx, by)
        if length_a < 1e-6 or length_b < 1e-6:
            continue
        # 两条线都从接点往外走，方向必须相反，不能是重叠的。
        if (ax * bx + ay * by) / (length_a * length_b) > -0.995:
            continue
        # 远端离第一条线太远就不算共线。
        if abs(ax * by - ay * bx) / length_a > tolerance * 2.0:
            continue
        total = length_a + length_b
        return {
            "start": far_a,
            "end": far_b,
            "width": (first["width"] * length_a + second["width"] * length_b) / total,
            "depth": (first["depth"] * length_a + second["depth"] * length_b) / total,
            "name": first["name"],
            "kind": first["kind"],
            "mesh": first["mesh"],
        }
    return None


def _merge_collinear(segments):
    """同一件物体、同一种边里，把共线且首尾相接的短线接成长线。"""
    groups = {}
    for segment in segments:
        groups.setdefault((segment["mesh"], segment["kind"]), []).append(segment)
    merged = []
    for items in groups.values():
        remaining = list(items)
        while remaining:
            current = remaining.pop()
            changed = True
            while changed:
                changed = False
                for index, other in enumerate(remaining):
                    joined = _join_collinear(current, other)
                    if joined:
                        current = joined
                        remaining.pop(index)
                        changed = True
                        break
            merged.append(current)
    return merged


def _dash_edge(pen, start, end, width, color, name, dash=5.0, gap=4.0) -> bool:
    """把一条线画成短虚线，返回是否画出了至少一段。"""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return False
    ux, uy = dx / length, dy / length
    position = 0.0
    drew = False
    while position < length - 1e-6:
        stop = min(position + dash, length)
        _edge_line(pen,
                   (start[0] + ux * position, start[1] + uy * position),
                   (start[0] + ux * stop, start[1] + uy * stop),
                   width, color, name)
        drew = True
        position += dash + gap
    return drew


def _draw_edges(pen, view, layout, prepared, mesh_edges, mesh_normals, skipped,
                grid, near_depth, far_depth, epsilon, hidden_lines,
                crease_angle):
    """一个视图里的消隐轮廓与折边。返回计数、线宽和深度。"""
    counts = {"silhouette": 0, "crease": 0, "visible": 0, "hidden": 0}
    widths = []
    depths = []
    solid = []
    forward = FORWARD[view]

    for mesh_index, (vertices, faces, color, name, blossom) in enumerate(prepared):
        if blossom or mesh_index in skipped:
            continue
        normals = mesh_normals[mesh_index]
        visible = [_dot(normal, forward) < -1e-9 for normal in normals]

        for (first_index, second_index), face_ids in mesh_edges[mesh_index].items():
            front_count = sum(1 for face_index in face_ids if visible[face_index])
            if front_count == 0:
                if not hidden_lines:
                    continue
                kind = "hidden"
                if len(face_ids) >= 2:
                    angle = max(_dihedral(normals[face_ids[a]], normals[face_ids[b]])
                                for a in range(len(face_ids))
                                for b in range(a + 1, len(face_ids)))
                    if angle <= crease_angle:
                        continue
            elif front_count == len(face_ids):
                if len(face_ids) < 2:
                    kind = "silhouette"
                else:
                    angle = max(_dihedral(normals[face_ids[a]], normals[face_ids[b]])
                                for a in range(len(face_ids))
                                for b in range(a + 1, len(face_ids)))
                    if angle <= crease_angle:
                        continue
                    kind = "crease"
            else:
                kind = "silhouette"

            first = vertices[first_index]
            second = vertices[second_index]
            start = project_panel(first, view, layout)
            end = project_panel(second, view, layout)
            if math.hypot(end[0] - start[0], end[1] - start[1]) < 0.8:
                continue
            start_depth = _depth(first, view)
            end_depth = _depth(second, view)
            width = edge_width((start_depth + end_depth) / 2.0, near_depth, far_depth)
            label = "%s·%s" % (name, "折边" if kind == "crease" else "轮廓")

            if kind == "hidden":
                if _dash_edge(pen, start, end, max(0.6, width * 0.8), HIDDEN_COLOR,
                              "%s·隐藏边" % name):
                    counts["hidden"] += 1
                continue

            counts[kind] += 1
            runs = _visibility_runs(start, end, start_depth, end_depth, grid, epsilon)
            dashed = False
            for begin, stop, ok in runs:
                if stop - begin < 0.012:
                    continue
                from_point = (start[0] + (end[0] - start[0]) * begin,
                              start[1] + (end[1] - start[1]) * begin)
                to_point = (start[0] + (end[0] - start[0]) * stop,
                            start[1] + (end[1] - start[1]) * stop)
                if ok:
                    solid.append({
                        "start": from_point, "end": to_point, "width": width,
                        "depth": (start_depth + end_depth) / 2.0,
                        "name": label, "kind": kind, "mesh": mesh_index,
                    })
                elif hidden_lines:
                    if _dash_edge(pen, from_point, to_point, max(0.6, width * 0.8),
                                  HIDDEN_COLOR, "%s·隐藏边" % name):
                        dashed = True
            if dashed:
                counts["hidden"] += 1

    # 同一条外框可能被折边拆成两段共线的短线，接起来才是图上的一条边。
    merged = _merge_collinear(solid)
    for segment in merged:
        _edge_line(pen, segment["start"], segment["end"], segment["width"],
                   EDGE_COLOR, segment["name"])
    counts["visible"] = len(merged)
    widths = [segment["width"] for segment in merged]
    depths = [segment["depth"] for segment in merged]
    return counts, widths, depths


def _layout(prepared, width: int, height: int, margin: int, title_band: int,
            center_per_view: bool = False) -> dict:
    """三个画板的位置，和一份全局比例尺。

    比例尺按三个视图合起来的包围盒算，三张图共用，位置才对得上。
    center_per_view 打开时，竖向按各视图自身内容的中点对齐画板中点，
    横向和比例尺都不变。
    """
    inner_w = max(1.0, width - margin * 2.0)
    inner_h = max(1.0, height - margin * 2.0 - title_band)

    us, vs = [], []
    view_vs = {view: [] for view in AXES}
    for vertices, _, _, _, _ in prepared:
        for view in AXES:
            for u, v in ortho_project(vertices, view, 1.0):
                us.append(u)
                vs.append(v)
                view_vs[view].append(v)
    u_min, u_max = min(us), max(us)
    v_min, v_max = min(vs), max(vs)
    v_center = (v_min + v_max) / 2.0

    if center_per_view:
        v_centers = {view: (min(values) + max(values)) / 2.0
                     for view, values in view_vs.items()}
    else:
        v_centers = {view: v_center for view in AXES}

    ratios = []
    if u_max - u_min > 1e-9:
        ratios.append(inner_w / (u_max - u_min))
    if v_max - v_min > 1e-9:
        ratios.append(inner_h / (v_max - v_min))
    scale = (min(ratios) if ratios else 1.0) * 0.82

    panels = []
    for index, view in enumerate(AXES):
        panels.append({
            "view": view,
            "left": index * width + margin,
            "top": margin,
            "width": inner_w,
            "height": inner_h,
        })
    return {
        "scale": scale,
        "u_center": (u_min + u_max) / 2.0,
        "v_center": v_center,
        "v_centers": v_centers,
        "v_ranges": {view: [min(values), max(values)]
                     for view, values in view_vs.items()},
        "bbox": {"u": [u_min, u_max], "v": [v_min, v_max]},
        "panels": panels,
        "center_per_view": bool(center_per_view),
    }


def project_panel(point, view: str, layout: dict):
    """一个三维点落到某个画板上的屏幕坐标。

    竖向用视图自己的中点（center_per_view 打开时），没写就退回全局中点。
    """
    if view not in AXES:
        raise ValueError("投影轴向只能是 %s，收到 %s" % ("、".join(AXES), view))
    x, y, z = _numbers(point, "投影点")
    panel = layout["panels"][AXES.index(view)]
    v_center = (layout.get("v_centers") or {}).get(view, layout["v_center"])
    u, v = ortho_project([[x, y, z]], view, 1.0)[0]
    return (
        panel["left"] + panel["width"] / 2.0 + (u - layout["u_center"]) * layout["scale"],
        panel["top"] + panel["height"] / 2.0 - (v - v_center) * layout["scale"],
    )


def _dimension(item, index: int):
    """读一条尺寸标注：两点、标签、画在哪些视图。"""
    number = index + 1
    if isinstance(item, dict):
        start = item.get("from")
        end = item.get("to")
        label = item.get("label", "")
        views = item.get("views") or list(AXES)
        offset = float(item.get("offset", DEFAULT_OFFSET))
    elif isinstance(item, (list, tuple)) and len(item) >= 2:
        start, end = item[0], item[1]
        label = item[2] if len(item) > 2 else ""
        views = list(AXES)
        offset = DEFAULT_OFFSET
    else:
        raise ValueError("第 %d 条尺寸要写成 {from, to, label} 或 [起点, 终点, 标签]" % number)

    start = _numbers(start, "第 %d 条尺寸的起点" % number)
    end = _numbers(end, "第 %d 条尺寸的终点" % number)
    if isinstance(views, str):
        views = [views]
    views = list(views)
    for view in views:
        if view not in AXES:
            raise ValueError("第 %d 条尺寸的 views 里有不认识的视图 %s" % (number, view))
    return start, end, str(label), views, offset


def _draw_dimension(pen, start, end, label, view, layout, offset, index) -> bool:
    """在一个视图里画一条尺寸线。两点在这个视图里重合就跳过。"""
    first = project_panel(start, view, layout)
    second = project_panel(end, view, layout)
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    length = math.hypot(dx, dy)
    if length < 1.0:
        return False

    nx, ny = -dy / length, dx / length
    a = (first[0] + nx * offset, first[1] + ny * offset)
    b = (second[0] + nx * offset, second[1] + ny * offset)

    pen.line(first[0], first[1], a[0] + nx * 4, a[1] + ny * 4,
             width=1, color=LINE_COLOR, name="尺寸界线 %d" % (index + 1))
    pen.line(second[0], second[1], b[0] + nx * 4, b[1] + ny * 4,
             width=1, color=LINE_COLOR, name="尺寸界线 %d" % (index + 1))
    pen.line(a[0], a[1], b[0], b[1], width=1, color=LINE_COLOR,
             name="尺寸线 %d" % (index + 1))
    for point in (a, b):
        pen.line(point[0] - nx * 4, point[1] - ny * 4,
                 point[0] + nx * 4, point[1] + ny * 4,
                 width=1, color=LINE_COLOR, name="尺寸端点 %d" % (index + 1))

    if label:
        text_size = 14
        width = sum(text_size if ord(ch) > 127 else text_size * 0.56 for ch in label)
        pen.rect((a[0] + b[0]) / 2.0 + nx * LABEL_OFFSET - width / 2.0 - 4,
                 (a[1] + b[1]) / 2.0 + ny * LABEL_OFFSET - text_size,
                 width + 8, text_size + 5,
                 fill=PANEL_COLOR, stroke_width=None, stroke=None,
                 name="尺寸文字底 %d" % (index + 1))
        pen.text((a[0] + b[0]) / 2.0 + nx * LABEL_OFFSET,
                 (a[1] + b[1]) / 2.0 + ny * LABEL_OFFSET,
                 label, size=text_size, color=TEXT_COLOR, align="center",
                 name="尺寸文字 %d" % (index + 1))
    return True



def _projected_box(vertices, view, layout):
    """一组点在某个视图里的屏幕包围盒：返回 (x0, y0, x1, y1)。"""
    xs = []
    ys = []
    for point in vertices:
        px, py = project_panel(point, view, layout)
        xs.append(px)
        ys.append(py)
    return min(xs), min(ys), max(xs), max(ys)


def _edge_grid(prepared, items, slivers, view, layout):
    """按一个视图里实际画出来的面铺一张深度缓冲，给消隐判断用。"""
    xs = []
    ys = []
    for vertices, *_ in prepared:
        for point in vertices:
            px, py = project_panel(point, view, layout)
            xs.append(px)
            ys.append(py)
    panel = layout["panels"][AXES.index(view)]
    left = max(panel["left"], min(xs) - 6)
    top = max(panel["top"], min(ys) - 6)
    right = min(panel["left"] + panel["width"], max(xs) + 6)
    bottom = min(panel["top"] + panel["height"], max(ys) + 6)
    grid = _DepthGrid(left, top, max(1.0, right - left), max(1.0, bottom - top))
    for item in items:
        mesh_index = item[1]
        face = item[3]
        vertices = prepared[mesh_index][0]
        points = [project_panel(vertices[index], view, layout) for index in face]
        depths = [_depth(vertices[index], view) for index in face]
        grid.fill(points, depths)
    for cx, cy, rx, ry, color, name, depth in slivers:
        grid.fill_ellipse(cx, cy, rx, ry, depth)
    return grid


def build_views(meshes, width: int = 900, height: int = 1200, palette="fresco",
                dimensions=None, margin: int = MARGIN, title_band: int = TITLE_BAND,
                center_per_view: bool = False, hidden_lines: bool = False,
                crease_angle: float = DEFAULT_CREASE):
    """生成三视图的绘制指令，返回 (指令, 摘要)。不写文件，方便测试。

    center_per_view 默认关闭，三个视图共用竖向中点，老图不变。打开后每个
    视图按自身内容的中点对齐画板中点，比例尺和横向对齐都不动，只解决
    俯视图深度大、正视图和左视图被压到面板底部的问题。

    hidden_lines 默认关闭：只画外轮廓和折边，被挡住的边不画；打开后把被挡
    住的边画成虚线。crease_angle 是折边的夹角阈值，默认 25 度。
    """
    if not isinstance(meshes, (list, tuple)) or not meshes:
        raise ValueError("三视图需要至少一个网格")
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        raise ValueError("三视图的画板宽高必须大于 0")
    crease_angle = float(crease_angle)
    if not 0.0 <= crease_angle <= 180.0:
        raise ValueError("三视图的 crease_angle 要在 0 到 180 度之间")

    prepared = [_mesh_data(mesh, index) for index, mesh in enumerate(meshes)]
    colors = resolve_palette(palette)
    total_width = width * len(AXES)
    pen = Pen(total_width, height, ref_width=total_width, palette=colors)
    layout = _layout(prepared, width, height, int(margin), int(title_band),
                     bool(center_per_view))

    mesh_edges = []
    mesh_normals = []
    for vertices, faces, color, name, blossom in prepared:
        if blossom:
            mesh_edges.append({})
            mesh_normals.append([])
        else:
            mesh_normals.append([_normal(vertices, face) for face in faces])
            mesh_edges.append(_mesh_edges(faces))
    edge_counts = {}
    edge_widths = []
    edge_depths = []

    pen.rect(0, 0, total_width, height, fill=PAGE_COLOR, stroke_width=None,
             stroke=None, name="页面")
    for panel in layout["panels"]:
        pen.rect(panel["left"], panel["top"], panel["width"], panel["height"],
                 fill=PANEL_COLOR, stroke_width=2, stroke=LINE_COLOR,
                 name="%s画板" % AXIS_TITLES[panel["view"]])

    drawn_faces = 0
    view_faces = {view: 0 for view in AXES}
    for view, panel in zip(AXES, layout["panels"]):
        items = []
        slivers = []
        skipped = set()
        for mesh_index, (vertices, faces, color, name, blossom) in enumerate(prepared):
            if not blossom:
                continue
            x0, y0, x1, y1 = _projected_box(vertices, view, layout)
            span_x = x1 - x0
            span_y = y1 - y0
            long_side = max(span_x, span_y)
            short_side = min(span_x, span_y)
            # 薄片花侧视会退化成一条线，花瓣尖会拉出长刺；这里按杯状截面
            # 画成一个扁椭圆，宽度和位置照投影包围盒，厚度给长边的十分之一；夹角小于约二十五度就按椭圆画。
            if long_side >= 6 and short_side <= long_side * 0.62:
                depth = sum(_depth(point, view) for point in vertices) / len(vertices)
                slivers.append(((x0 + x1) / 2.0, (y0 + y1) / 2.0, long_side / 2.0,
                                max(2.0, long_side * 0.10), color, name, depth))
                skipped.add(mesh_index)
        for mesh_index, (vertices, faces, color, name, blossom) in enumerate(prepared):
            if mesh_index in skipped:
                continue
            for face_index, face in enumerate(faces):
                normal = _normal(vertices, face)
                # 花形是零厚度的薄片，侧视会退化成一条，不能按法向剔掉。
                if not blossom and _dot(normal, FORWARD[view]) >= -1e-9:
                    continue
                items.append((-_depth(_center(vertices, face), view),
                              mesh_index, face_index, face, normal, color, name, blossom))
        items.sort(key=lambda item: item[0])
        for (_, mesh_index, face_index, face, normal, color, name,
             blossom) in items:
            knots = [list(project_panel(prepared[mesh_index][0][index], view, layout))
                     for index in face]
            # 描边跟填充同色：盖住相邻面之间的抗锯齿缝，近看不会有细白线。
            # 圆角接头是必须的：锥体顶点的夹角极尖，斜接会甩出两根长刺。
            if blossom:
                # 花形按平涂上色，不打光，免得粉花被压成灰紫
                tone = color_of(colors, color)
                if face_index % 2:
                    tone = _shade(tone, 0.94)
            else:
                tone = _shade(color_of(colors, color), _light(normal))
            pen.path([{"closed": True, "knots": knots}],
                     fill=tone, stroke_width=1, stroke=tone,
                     name=("%s·花瓣 %d" if blossom else "%s·面 %d")
                          % (name, face_index + 1))
            stroke = pen.commands[-1]["params"].get("stroke")
            if stroke:
                stroke["join"] = "round"
            drawn_faces += 1
            view_faces[view] += 1

        for cx, cy, rx, ry, color, name, depth in slivers:
            tone = _shade(color_of(colors, color), 0.95)
            pen.ellipse(cx, cy, rx, ry, fill=tone, stroke_width=1, stroke=tone,
                        name="%s·侧视" % name)
            drawn_faces += 1
            view_faces[view] += 1

        # 面画完之后再压轮廓线：先按朝向剔背面，只留外轮廓和硬折边；
        # 再用深度缓冲把被前面物体挡住的段切掉。
        view_depths = [_depth(point, view) for vertices, *_ in prepared
                       for point in vertices]
        near_depth = min(view_depths)
        far_depth = max(view_depths)
        span = far_depth - near_depth
        # 深度缓冲按两像素格子采样，边又落在面的边界上，半格偏移会带来
        # 一点深度误差；容差取场景深度的百分之二，既盖住误差，又能分出
        # 前后两根枝。
        epsilon = max(1e-4 * max(1.0, span), 0.02 * span)
        grid = _edge_grid(prepared, items, slivers, view, layout)
        counts, widths, depths = _draw_edges(
            pen, view, layout, prepared, mesh_edges, mesh_normals, skipped,
            grid, near_depth, far_depth, epsilon, bool(hidden_lines), crease_angle)
        edge_counts[view] = counts
        edge_widths.extend(widths)
        edge_depths.extend(depths)

    drawn_dimensions = 0
    for index, item in enumerate(dimensions or []):
        start, end, label, views, offset = _dimension(item, index)
        for view in views:
            if _draw_dimension(pen, start, end, label, view, layout, offset, index):
                drawn_dimensions += 1

    for panel in layout["panels"]:
        pen.text(panel["left"] + panel["width"] / 2.0,
                 panel["top"] + panel["height"] + title_band * 0.62,
                 "%s / %s" % (AXIS_TITLES[panel["view"]], panel["view"]),
                 size=20, color=TEXT_COLOR, align="center", name="视图名")

    meta = {
        "name": "三视图",
        "width": total_width,
        "height": height,
        "scale": layout["scale"],
        "bbox": layout["bbox"],
        "u_center": layout["u_center"],
        "v_center": layout["v_center"],
        "v_centers": dict(layout["v_centers"]),
        "v_ranges": {view: list(span) for view, span in layout["v_ranges"].items()},
        "center_per_view": layout["center_per_view"],
        "panels": [dict(panel) for panel in layout["panels"]],
        "meshes": len(prepared),
        "faces": drawn_faces,
        "view_faces": dict(view_faces),
        "edge_counts": edge_counts,
        "edge_widths": edge_widths,
        "edge_depths": edge_depths,
        "hidden_lines": bool(hidden_lines),
        "crease_angle": float(crease_angle),
        "dimensions": drawn_dimensions,
        "commands": len(pen.commands),
    }
    return pen.commands, meta


def render_views(meshes, out_path, width: int = 900, height: int = 1200,
                 dimensions=None, palette="fresco", center_per_view: bool = False,
                 hidden_lines: bool = False, crease_angle: float = DEFAULT_CREASE):
    """三个视图并排画进一张图，写成 PNG，返回摘要。"""
    from .engine import Engine

    commands, meta = build_views(meshes, width=width, height=height,
                                 dimensions=dimensions, palette=palette,
                                 center_per_view=center_per_view,
                                 hidden_lines=hidden_lines,
                                 crease_angle=crease_angle)
    target = Path(out_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with Engine(read_root=Path.cwd(), write_root=target.parent) as engine:
        engine.new_document(meta["width"], meta["height"], meta["name"])
        for command in commands:
            engine.execute(command["command"], command.get("params") or {})
        engine.save(target)
    summary = dict(meta)
    summary["path"] = str(target)
    return summary


# ---------------------------------------------------------------------------
# 演示用的四个基本体。只写给 ortho 自己跑演示，不依赖 mesh.py。
# ---------------------------------------------------------------------------

def _box_mesh(width, height, depth, x, z, color, name):
    half_w, half_d = width / 2.0, depth / 2.0
    vertices = [
        [x - half_w, 0.0, z - half_d], [x + half_w, 0.0, z - half_d],
        [x + half_w, 0.0, z + half_d], [x - half_w, 0.0, z + half_d],
        [x - half_w, height, z - half_d], [x + half_w, height, z - half_d],
        [x + half_w, height, z + half_d], [x - half_w, height, z + half_d],
    ]
    faces = [
        [0, 1, 2, 3], [4, 7, 6, 5],
        [3, 2, 6, 7], [0, 4, 5, 1],
        [0, 3, 7, 4], [1, 5, 6, 2],
    ]
    return {"vertices": vertices, "faces": faces, "color": color, "name": name}


def _sphere_mesh(radius, x, z, color, name, segments=16, rings=10):
    """球心抬到 y=radius，球底正好落在 y=0 的地面上。"""
    vertices = []
    for ring in range(rings + 1):
        theta = math.pi * ring / rings
        y = radius + radius * math.cos(theta)
        width = radius * math.sin(theta)
        for step in range(segments):
            phi = 2.0 * math.pi * step / segments
            vertices.append([x + width * math.cos(phi), y, z + width * math.sin(phi)])
    faces = []
    for ring in range(rings):
        for step in range(segments):
            a = ring * segments + step
            b = ring * segments + (step + 1) % segments
            c = (ring + 1) * segments + (step + 1) % segments
            d = (ring + 1) * segments + step
            faces.append([a, b, c, d])
    return {"vertices": vertices, "faces": faces, "color": color, "name": name}


def _cylinder_mesh(radius, height, x, z, color, name, segments=16):
    vertices = []
    for step in range(segments):
        phi = 2.0 * math.pi * step / segments
        vertices.append([x + radius * math.cos(phi), 0.0, z + radius * math.sin(phi)])
    for step in range(segments):
        phi = 2.0 * math.pi * step / segments
        vertices.append([x + radius * math.cos(phi), height, z + radius * math.sin(phi)])
    faces = []
    for step in range(segments):
        nxt = (step + 1) % segments
        faces.append([step, segments + step, segments + nxt, nxt])
    faces.append(list(range(segments)))
    faces.append([segments + step for step in range(segments - 1, -1, -1)])
    return {"vertices": vertices, "faces": faces, "color": color, "name": name}


def _cone_mesh(radius, height, x, z, color, name, segments=16):
    vertices = []
    for step in range(segments):
        phi = 2.0 * math.pi * step / segments
        vertices.append([x + radius * math.cos(phi), 0.0, z + radius * math.sin(phi)])
    vertices.append([x, height, z])
    apex = segments
    faces = []
    for step in range(segments):
        faces.append([step, apex, (step + 1) % segments])
    faces.append(list(range(segments)))
    return {"vertices": vertices, "faces": faces, "color": color, "name": name}


def _stick_mesh(start, end, radius, color, name, sides=8):
    """两点之间的一根细柱，给花枝用。"""
    first = [float(value) for value in start]
    second = [float(value) for value in end]
    axis = _normalize([second[0] - first[0], second[1] - first[1],
                       second[2] - first[2]])
    helper = (0.0, 1.0, 0.0) if abs(axis[1]) < 0.9 else (1.0, 0.0, 0.0)
    axis_u = _normalize(_cross(helper, axis))
    axis_v = _normalize(_cross(axis, axis_u))

    vertices = []
    for center in (first, second):
        for step in range(sides):
            phi = 2.0 * math.pi * step / sides
            offset = (math.cos(phi), math.sin(phi))
            vertices.append([
                center[0] + (axis_u[0] * offset[0] + axis_v[0] * offset[1]) * radius,
                center[1] + (axis_u[1] * offset[0] + axis_v[1] * offset[1]) * radius,
                center[2] + (axis_u[2] * offset[0] + axis_v[2] * offset[1]) * radius,
            ])

    faces = []
    for step in range(sides):
        nxt = (step + 1) % sides
        faces.append([step, sides + step, sides + nxt, nxt])
    faces.append(list(range(sides)))
    faces.append([sides + step for step in range(sides - 1, -1, -1)])
    return {"vertices": vertices, "faces": faces, "color": color, "name": name}


DEMO_DIMENSIONS = [
    # 三个尺寸都摆到物体外接框以外，线离物体至少 40 像素。
    # 同一条尺寸在左视图和俯视图里方向不同，拆成几条各给各的间距和位置。
    {"from": [-4.0, 0.0, 0.0], "to": [4.0, 0.0, 0.0], "label": "总宽 8.0",
     "views": ["front"], "offset": 44},
    {"from": [-4.0, 0.0, 2.5], "to": [4.0, 0.0, 2.5], "label": "总宽 8.0",
     "views": ["top"], "offset": -70},
    {"from": [4.25, 0.0, 3.4], "to": [4.25, 2.2, 3.4], "label": "总高 2.2",
     "views": ["front", "left"], "offset": 26},
    {"from": [4.25, 0.0, -2.0], "to": [4.25, 0.0, 2.5], "label": "总深 4.5",
     "views": ["left"], "offset": 44},
    {"from": [4.25, 0.0, -2.0], "to": [4.25, 0.0, 2.5], "label": "总深 4.5",
     "views": ["top"], "offset": 22},
]


def demo_meshes():
    """方块、球、柱、锥各一个，沿对角线排开，左视图才分得清前后。"""
    return [
        _box_mesh(1.8, 2.2, 1.1, -3.1, -1.45, "#B98F5E", "方块"),
        _sphere_mesh(0.78, -0.9, -0.35, "#9A7C63", "球"),
        _cylinder_mesh(0.58, 1.9, 1.2, 0.75, "#8E7150", "柱"),
        _cone_mesh(0.66, 2.0, 3.34, 1.84, "#A8896A", "锥"),
    ]


def demo_flower_meshes():
    """一枝花：主枝、两根侧枝、三朵朝向不同的花。

    顶花朝正前方、左花朝左边、右花朝上，三个视图各有一朵正对镜头的
    五瓣花；另外两朵在这个视图里压成一条，这是平面花的正确投影。
    """
    return [
        _stick_mesh((0.0, 0.0, 0.0), (0.12, 1.95, 0.03), 0.035, "#6B4A36", "主枝"),
        _stick_mesh((0.03, 1.05, 0.01), (-0.88, 1.50, 0.18), 0.024, "#6B4A36", "左枝"),
        _stick_mesh((0.08, 1.45, 0.02), (0.72, 1.26, -0.32), 0.024, "#6B4A36", "右枝"),
        make_blossom((0.16, 2.16, 0.06), 1.10, facing=(0.32, 0.22, 0.92),
                     color="#C8455F", name="顶花"),
        make_blossom((-1.00, 1.62, 0.22), 0.90, facing=(-0.86, 0.30, 0.42),
                     color="#D25A72", name="左花"),
        make_blossom((0.82, 1.32, -0.40), 0.85, facing=(0.28, 0.90, 0.34),
                     color="#B3324C", name="右花"),
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="正交投影演示：三视图")
    parser.add_argument("--scene", choices=("solids", "flower"), default="solids",
                        help="solids 是方块球柱锥，flower 是一枝花，默认 solids")
    parser.add_argument("--out", default=None, help="输出 PNG；不写时按场景取名")
    parser.add_argument("--width", type=int, default=800, help="单张视图宽，默认 800")
    parser.add_argument("--height", type=int, default=700, help="画布高，默认 700")
    parser.add_argument("--center-per-view", action="store_true",
                        help="每个视图按自身内容竖向居中，比例尺不变")
    args = parser.parse_args(argv)

    if args.scene == "flower":
        meshes = demo_flower_meshes()
        dimensions = None
        default_out = "out/ortho-flower.png"
    else:
        meshes = demo_meshes()
        dimensions = DEMO_DIMENSIONS
        default_out = "out/ortho-demo.png"

    summary = render_views(meshes, args.out or default_out,
                           width=args.width, height=args.height,
                           dimensions=dimensions,
                           center_per_view=args.center_per_view)
    print("%s | %dx%d | 3 个视图 | %d 个面 | 比例尺 %.3f | %d 条尺寸 | 居中 %s | %s"
          % (summary["name"], summary["width"], summary["height"],
             summary["faces"], summary["scale"], summary["dimensions"],
             "开" if summary["center_per_view"] else "关", summary["path"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
