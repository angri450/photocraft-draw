# -*- coding: utf-8 -*-
"""混合画法第二版：五朵花、三个花苞、五片叶，组成一枝完整的海棠花枝。

枝条、花梗、花苞用网格；花和叶是一个平面，按空间朝向做整体仿射。
角度按三七停布置，主花簇在右上三分之一，枝条从画外左下伸进来。

    python3 tools/spray_hybrid.py
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from photocraft_draw.commands import Pen
from photocraft_draw.engine import Engine
from photocraft_draw.mesh import make_sphere, render
from photocraft_draw.palette import resolve_palette

from flower_mesh import camera, tube
from flower_hybrid import (_affine, _depth, _mul, _smooth, _unit, _add, _cross,
                           PETAL, NOTCH)

WIDTH = 900
HEIGHT = 1200

LEAF = [
    (0.00, 0.00), (-0.22, 0.12), (-0.40, 0.36), (-0.34, 0.62),
    (-0.14, 0.84), (0.00, 0.90), (0.14, 0.84), (0.34, 0.62),
    (0.40, 0.36), (0.22, 0.12),
]


def draw_shape(pen, camera, center, axis, radial, length, width, shape,
               color, name, notch=0.0, spin=0.0):
    """把一个二维形状按它在空间里的平面贴到画面上。"""
    axis = _unit(axis)
    radial = _unit(radial)
    tangent = _unit(_cross(axis, radial))
    tilted = _unit(_add(_mul(radial, 0.42), _mul(axis, 0.90)))
    to_screen = _affine(camera, center, _mul(tangent, width), _mul(tilted, length))
    ca, sa = math.cos(spin), math.sin(spin)
    points = []
    for index, (x, y) in enumerate(shape):
        if notch and index == len(shape) // 2:
            y -= notch
        rx = x * ca - y * sa
        ry = x * sa + y * ca
        points.append(to_screen(rx, ry))
    pen.path([{"closed": True, "knots": _smooth(points)}], fill=color,
             stroke_width=None, stroke=None, name=name)


def draw_flower(pen, camera, center, axis, size, name, spin=0.0):
    axis = _unit(axis)
    helper = (0.0, 1.0, 0.0) if abs(axis[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _unit(_cross(helper, axis))
    v = _unit(_cross(axis, u))
    to_screen = _affine(camera, center, _mul(u, size), _mul(v, size))
    for index in range(5):
        angle = math.radians(72.0 * index)
        ca, sa = math.cos(angle + spin), math.sin(angle + spin)
        points = []
        for point_index, (x, y) in enumerate(PETAL):
            if point_index == 6:
                y -= NOTCH
            rx = x * ca - (y - 0.05) * sa
            ry = x * sa + (y - 0.05) * ca + 0.05
            points.append(to_screen(rx * 0.92, ry * 0.92))
        pen.path([{"closed": True, "knots": _smooth(points)}], fill="#F2C0CE",
                 stroke_width=None, stroke=None, name="%s·瓣%d" % (name, index + 1))
    heart = to_screen(0.0, 0.0)
    radius = size * 0.085 * camera.focal / max(0.05, _depth(camera, center))
    pen.ellipse(heart[0], heart[1], radius, radius * 0.92, fill="#E9C25C",
                stroke=None, name="%s·心" % name)


def build():
    """返回 (网格列表, 花, 叶, 苞)。坐标单位米。"""
    meshes = []
    main = [(-0.095, -0.062, 0.054), (-0.062, -0.032, 0.050),
            (-0.030, -0.006, 0.046), (0.000, 0.018, 0.042),
            (0.026, 0.040, 0.038), (0.042, 0.056, 0.034)]
    meshes.append(tube(main, [0.0080, 0.0074, 0.0066, 0.0056, 0.0046, 0.0036],
                       "#6B4A36", "主枝"))

    shoots = {
        "上": ([(0.026, 0.040, 0.038), (0.038, 0.058, 0.030), (0.048, 0.072, 0.024)],
               [0.0042, 0.0032, 0.0024]),
        "中": ([(0.000, 0.018, 0.042), (0.012, 0.032, 0.032), (0.020, 0.042, 0.026)],
               [0.0044, 0.0034, 0.0026]),
        "下": ([(-0.030, -0.006, 0.046), (-0.018, 0.006, 0.034), (-0.010, 0.016, 0.028)],
               [0.0048, 0.0036, 0.0026]),
    }
    for name, (points, radii) in shoots.items():
        meshes.append(tube(points, radii, "#6B4A36", "短枝" + name))

    # 花的朝向都控制在视线正负四十五度内，靠大小和远近拉层次
    flowers = [
        ((0.055, 0.080, 0.024), (0.22, 0.32, -0.92), 0.033, 0.20, "花·主"),
        ((0.026, 0.050, 0.020), (-0.28, 0.26, -0.92), 0.030, -0.35, "花·副"),
        ((-0.004, 0.020, 0.022), (0.36, 0.14, -0.92), 0.028, 0.90, "花·三"),
        ((0.040, 0.062, 0.034), (0.08, -0.26, -0.96), 0.022, 1.60, "花·小"),
    ]

    leaves = [
        ((0.028, 0.030, 0.040), (0.42, 0.72, -0.55), (0.30, 0.94, -0.15), 0.040, 0.019, 0.35),
        ((-0.008, 0.008, 0.042), (-0.38, 0.74, -0.55), (0.10, 0.96, -0.20), 0.036, 0.018, -0.45),
        ((0.048, 0.048, 0.040), (0.52, 0.44, -0.73), (0.60, 0.75, -0.20), 0.032, 0.016, 0.85),
        ((-0.038, -0.020, 0.044), (0.30, 0.82, -0.48), (0.20, 0.94, -0.10), 0.030, 0.015, -0.15),
    ]

    buds = [
        ((0.062, 0.088, 0.036), 0.0072, "#E8A8BA", "苞·顶"),
        ((0.034, 0.058, 0.034), 0.0064, "#EDB6C4", "苞·中"),
        ((-0.014, 0.010, 0.036), 0.0058, "#E8A8BA", "苞·下"),
    ]
    return meshes, flowers, leaves, buds


def proxy_meshes(flowers, buds):
    """三视图里用扁球代替整朵花，表示花的体积和位置。"""
    proxies = []
    for center, axis, size, spin, name in flowers:
        proxies.append(make_sphere(size * 0.62, segments=16, rings=10,
                                   center=center, color="#E8B3C2", name=name + "·体积"))
    for center, radius, color, name in buds:
        proxies.append(make_sphere(radius, segments=12, rings=8,
                                   center=center, color=color, name=name))
    return proxies


def render_three_views(out: Path) -> None:
    from photocraft_draw.ortho import render_views

    meshes, flowers, leaves, buds = build()
    stems = []
    for center, axis, size, spin, name in flowers:
        attach = (center[0] - axis[0] * 0.012, center[1] - axis[1] * 0.012,
                  center[2] + 0.014)
        stems.append(tube([attach, center], [0.0014, 0.0012], "#6B4A36", name + "·梗"))
    solids = meshes + stems + proxy_meshes(flowers, buds)
    dimensions = [
        {"from": (-0.095, -0.062, 0.054), "to": (0.055, 0.080, 0.024),
         "label": "枝长 19cm", "views": ["front"], "offset": 30},
        {"from": (-0.095, -0.062, 0.054), "to": (0.055, 0.080, 0.024),
         "label": "高 15cm", "views": ["left"], "offset": 30},
    ]
    summary = render_views(solids, out, width=640, height=820, dimensions=dimensions)
    print("三视图：%s | %s" % (out, summary.get("views")))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="混合海棠花枝")
    parser.add_argument("--out", default="out/spray-hybrid.png")
    parser.add_argument("--views", default="", help="同时出三视图，写输出路径")
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()

    meshes, flowers, leaves, buds = build()
    cam = camera()
    pen = Pen(WIDTH, HEIGHT, ref_width=WIDTH, palette=resolve_palette("fresco"))
    pen.rect(0, 0, WIDTH, HEIGHT, fill="#F4EBDF", stroke_width=None, stroke=None, name="底")

    # 花梗和花苞先画，属于底层
    stems = []
    for center, axis, size, spin, name in flowers:
        attach = (center[0] - axis[0] * 0.012, center[1] - axis[1] * 0.012,
                  center[2] + 0.014)
        stems.append(tube([attach, center], [0.0014, 0.0012], "#6B4A36", name + "·梗"))
    for center, radius, color, name in buds:
        stems.append(make_sphere(radius, segments=12, rings=8, center=center,
                                 color=color, name=name))
    render(meshes + stems, cam, pen,
           lighting={"direction": (-0.45, -0.55, -0.70), "ambient": 0.88, "diffuse": 0.26})

    # 叶在花后，先画
    for center, axis, radial, length, width, spin in leaves:
        draw_shape(pen, cam, center, axis, radial, length, width, LEAF,
                   "#7FA05A", "叶", spin=spin)

    # 花按远近从远到近
    for center, axis, size, spin, name in sorted(flowers, key=lambda f: -_depth(cam, f[0])):
        draw_flower(pen, cam, center, axis, size, name, spin=spin)

    with Engine(read_root=Path.cwd(), write_root=out.parent) as engine:
        engine.new_document(WIDTH, HEIGHT, "海棠花枝·混合")
        for command in pen.commands:
            engine.execute(command["command"], command.get("params") or {})
        engine.save(out)
    print("输出 %s" % out)
    if args.views:
        render_three_views(Path(args.views).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
