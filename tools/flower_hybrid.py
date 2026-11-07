# -*- coding: utf-8 -*-
"""混合画法：枝条用网格，花瓣用曲线形状按三维朝向投影。

网格负责位置、朝向、遮挡；花瓣不手搓顶点，直接把一条贝塞尔花瓣
按花瓣平面的投影做仿射变换，形状还是原来那套。

    python3 tools/flower_hybrid.py
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from photocraft_draw.commands import Pen
from photocraft_draw.engine import Engine
from photocraft_draw.mesh import Camera, make_sphere, render
from photocraft_draw.palette import resolve_palette

from flower_mesh import scene as branch_scene, camera as branch_camera

WIDTH = 900
HEIGHT = 1200

PETAL = [
    (0.00, 0.00), (-0.15, 0.08), (-0.29, 0.28), (-0.34, 0.55),
    (-0.30, 0.80), (-0.18, 0.93), (0.00, 0.96),
    (0.18, 0.93), (0.30, 0.80), (0.34, 0.55),
    (0.29, 0.28), (0.15, 0.08),
]
NOTCH = 0.10


def _unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _project(camera, point):
    p = camera.project(point)
    return (p.x, p.y)


def _affine(camera, origin, x_axis, y_axis):
    """把单位平面的 (x, y) 映射到屏幕：返回一个二维仿射函数。"""
    o = _project(camera, origin)
    px = _project(camera, _add(origin, x_axis))
    py = _project(camera, _add(origin, y_axis))
    ex = (px[0] - o[0], px[1] - o[1])
    ey = (py[0] - o[0], py[1] - o[1])
    return lambda x, y: (o[0] + ex[0] * x + ey[0] * y,
                         o[1] + ex[1] * x + ey[1] * y)


def petal_knots(camera, center, axis, radial, length, width):
    """一片花瓣的贝塞尔节点：单位形状乘上花瓣平面的仿射，再用切线定手柄。"""
    axis = _unit(axis)
    radial = _unit(radial)
    tangent = _unit(_cross(axis, radial))
    tilted = _unit(_add(_mul(radial, 0.48), _mul(axis, 0.88)))
    to_screen = _affine(camera, center, _mul(tangent, width), _mul(tilted, length))
    points = []
    for index, (x, y) in enumerate(PETAL):
        if index == 5:
            y -= NOTCH
        points.append(to_screen(x, y))
    knots = []
    total = len(points)
    for index, point in enumerate(points):
        prev = points[(index - 1) % total]
        nxt = points[(index + 1) % total]
        tx, ty = nxt[0] - prev[0], nxt[1] - prev[1]
        norm = math.hypot(tx, ty) or 1.0
        tx, ty = tx / norm, ty / norm
        span = 0.20 * (math.dist(point, nxt) + math.dist(point, prev)) * 0.5
        knots.append({
            "anchor": [point[0], point[1]],
            "in": [point[0] - tx * span, point[1] - ty * span],
            "out": [point[0] + tx * span, point[1] + ty * span],
        })
    return knots


def _smooth(points, closed=True):
    knots = []
    total = len(points)
    for index, point in enumerate(points):
        prev = points[(index - 1) % total]
        nxt = points[(index + 1) % total]
        tx, ty = nxt[0] - prev[0], nxt[1] - prev[1]
        norm = math.hypot(tx, ty) or 1.0
        tx, ty = tx / norm, ty / norm
        span = 0.20 * (math.dist(point, nxt) + math.dist(point, prev)) * 0.5
        knots.append({
            "anchor": [point[0], point[1]],
            "in": [point[0] - tx * span, point[1] - ty * span],
            "out": [point[0] + tx * span, point[1] + ty * span],
        })
    return knots


def draw_blossom(pen, camera, center, axis, size, petal_color, heart_color,
                 spin=0.0, name="花"):
    """一整朵花当作一个平面：先算花的平面，再把二维花瓣整体仿射过去。"""
    axis = _unit(axis)
    helper = (0.0, 1.0, 0.0) if abs(axis[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _unit(_cross(helper, axis))
    v = _unit(_cross(axis, u))
    to_screen = _affine(camera, center, _mul(u, size), _mul(v, size))

    for index in range(5):
        angle = math.radians(72.0 * index)
        ca, sa = math.cos(angle), math.sin(angle)
        pts = []
        for point_index, (x, y) in enumerate(PETAL):
            if point_index == 6:
                y -= NOTCH
            rx = x * ca - (y - 0.05) * sa
            ry = x * sa + (y - 0.05) * ca + 0.05
            pts.append(to_screen(rx * 0.92, ry * 0.92))
        pen.path([{"closed": True, "knots": _smooth(pts)}], fill=petal_color,
                 stroke_width=None, stroke=None, name="%s·瓣%d" % (name, index + 1))

    heart = to_screen(0.0, 0.0)
    radius = size * 0.10 * camera.focal / max(0.05, _depth(camera, center))
    pen.ellipse(heart[0], heart[1], radius, radius * 0.92,
                fill=heart_color, stroke=None, name="%s·心" % name)


def _depth(camera, point):
    return math.dist(camera.position, point)


def flower_specs():
    """三朵花：位置、朝向、大小。朝向不同是这次要验证的重点。"""
    return [
        ((0.060, 0.086, 0.008), (0.18, 0.34, -0.92), 0.033, 0.25, "花·正"),
        ((0.008, 0.040, 0.004), (0.88, 0.28, -0.38), 0.030, -0.30, "花·侧"),
        ((0.034, 0.066, 0.014), (0.10, -0.72, 0.68), 0.028, 0.80, "花·垂"),
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="网格枝条 + 曲线花瓣")
    parser.add_argument("--out", default="out/flower-hybrid.png")
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()

    camera = branch_camera()
    pen = Pen(WIDTH, HEIGHT, ref_width=WIDTH, palette=resolve_palette("fresco"))
    pen.rect(0, 0, WIDTH, HEIGHT, fill="#F4EBDF", stroke_width=None, stroke=None, name="底")

    meshes = [m for m in branch_scene() if m.name.startswith(("主枝", "短枝"))]
    # 花梗：从枝上的着生点连到花心，细一点，画在花下面
    from flower_mesh import tube
    pedicels = [
        ([(0.045, 0.058, 0.032), (0.052, 0.070, 0.020), (0.058, 0.082, 0.012)], 0.0016),
        ([(0.010, 0.030, 0.035), (0.010, 0.034, 0.020), (0.009, 0.038, 0.008)], 0.0015),
        ([(0.038, 0.062, 0.022), (0.036, 0.064, 0.018), (0.035, 0.065, 0.015)], 0.0013),
    ]
    for index, (points, radius) in enumerate(pedicels):
        meshes.append(tube(points, [radius, radius, radius], "#6B4A36", "花梗%d" % (index + 1)))
    render(meshes, camera, pen,
           lighting={"direction": (-0.45, -0.55, -0.70), "ambient": 0.88, "diffuse": 0.26})

    # 花按远近排序，远的先画
    specs = sorted(flower_specs(), key=lambda s: -_depth(camera, s[0]))
    for center, axis, size, spin, name in specs:
        draw_blossom(pen, camera, center, axis, size, "#F2C0CE", "#E9C25C",
                    spin=spin, name=name)

    with Engine(read_root=Path.cwd(), write_root=out.parent) as engine:
        engine.new_document(WIDTH, HEIGHT, "混合海棠")
        for command in pen.commands:
            engine.execute(command["command"], command.get("params") or {})
        engine.save(out)
    print("输出 %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
