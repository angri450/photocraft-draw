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

网格只按 vertices 和 faces 两个字段读，不 import mesh.py：传字典也行，传带
同名属性的对象也行。面的顶点按逆时针写，法向量朝外，背面会自动剔除。

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
    """读一份网格，返回 (顶点, 面, 颜色, 名字)。不依赖 mesh.py 的类型。"""
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
    return points, polygons, str(color), str(name)


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
    for vertices, _, _, _ in prepared:
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


def build_views(meshes, width: int = 900, height: int = 1200, palette="fresco",
                dimensions=None, margin: int = MARGIN, title_band: int = TITLE_BAND,
                center_per_view: bool = False):
    """生成三视图的绘制指令，返回 (指令, 摘要)。不写文件，方便测试。

    center_per_view 默认关闭，三个视图共用竖向中点，老图不变。打开后每个
    视图按自身内容的中点对齐画板中点，比例尺和横向对齐都不动，只解决
    俯视图深度大、正视图和左视图被压到面板底部的问题。
    """
    if not isinstance(meshes, (list, tuple)) or not meshes:
        raise ValueError("三视图需要至少一个网格")
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        raise ValueError("三视图的画板宽高必须大于 0")

    prepared = [_mesh_data(mesh, index) for index, mesh in enumerate(meshes)]
    colors = resolve_palette(palette)
    total_width = width * len(AXES)
    pen = Pen(total_width, height, ref_width=total_width, palette=colors)
    layout = _layout(prepared, width, height, int(margin), int(title_band),
                     bool(center_per_view))

    pen.rect(0, 0, total_width, height, fill=PAGE_COLOR, stroke_width=None,
             stroke=None, name="页面")
    for panel in layout["panels"]:
        pen.rect(panel["left"], panel["top"], panel["width"], panel["height"],
                 fill=PANEL_COLOR, stroke_width=2, stroke=LINE_COLOR,
                 name="%s画板" % AXIS_TITLES[panel["view"]])

    drawn_faces = 0
    for view, panel in zip(AXES, layout["panels"]):
        items = []
        for mesh_index, (vertices, faces, color, name) in enumerate(prepared):
            for face_index, face in enumerate(faces):
                normal = _normal(vertices, face)
                if _dot(normal, FORWARD[view]) >= -1e-9:
                    continue
                items.append((-_depth(_center(vertices, face), view),
                              mesh_index, face_index, face, normal, color, name))
        items.sort(key=lambda item: item[0])
        for _, mesh_index, face_index, face, normal, color, name in items:
            knots = [list(project_panel(prepared[mesh_index][0][index], view, layout))
                     for index in face]
            # 描边跟填充同色：盖住相邻面之间的抗锯齿缝，近看不会有细白线。
            # 圆角接头是必须的：锥体顶点的夹角极尖，斜接会甩出两根长刺。
            tone = _shade(color_of(colors, color), _light(normal))
            pen.path([{"closed": True, "knots": knots}],
                     fill=tone, stroke_width=1, stroke=tone,
                     name="%s·面 %d" % (name, face_index + 1))
            stroke = pen.commands[-1]["params"].get("stroke")
            if stroke:
                stroke["join"] = "round"
            drawn_faces += 1

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
        "dimensions": drawn_dimensions,
        "commands": len(pen.commands),
    }
    return pen.commands, meta


def render_views(meshes, out_path, width: int = 900, height: int = 1200,
                 dimensions=None, palette="fresco", center_per_view: bool = False):
    """三个视图并排画进一张图，写成 PNG，返回摘要。"""
    from .engine import Engine

    commands, meta = build_views(meshes, width=width, height=height,
                                 dimensions=dimensions, palette=palette,
                                 center_per_view=center_per_view)
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="正交投影演示：方块、球、柱、锥的三视图")
    parser.add_argument("--out", default="out/ortho-demo.png", help="输出 PNG，默认 out/ortho-demo.png")
    parser.add_argument("--width", type=int, default=800, help="单张视图宽，默认 800")
    parser.add_argument("--height", type=int, default=700, help="画布高，默认 700")
    parser.add_argument("--center-per-view", action="store_true",
                        help="每个视图按自身内容竖向居中，比例尺不变")
    args = parser.parse_args(argv)
    summary = render_views(demo_meshes(), args.out, width=args.width, height=args.height,
                           dimensions=DEMO_DIMENSIONS,
                           center_per_view=args.center_per_view)
    print("%s | %dx%d | 3 个视图 | %d 个面 | 比例尺 %.3f | %d 条尺寸 | 居中 %s | %s"
          % (summary["name"], summary["width"], summary["height"],
             summary["faces"], summary["scale"], summary["dimensions"],
             "开" if summary["center_per_view"] else "关", summary["path"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
