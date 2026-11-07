# -*- coding: utf-8 -*-
"""混合画法第二版：四朵花、两个花苞、四片叶，组成一枝完整的海棠花枝。

枝条、花梗、花苞用网格；花和叶是一个平面，按空间朝向做整体仿射。
主簇三朵在右上，副簇一朵退在左下，两个花苞挂在外缘。

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

# 花苞：一头收尖、一头让花萼压住的泪滴形，x 是半宽，y 从基部 -1 到尖端 1
BUD = [
    (0.00, 1.00), (-0.40, 0.72), (-0.78, 0.34), (-0.95, -0.02),
    (-0.84, -0.46), (-0.50, -0.80), (0.00, -0.95),
    (0.50, -0.80), (0.84, -0.46), (0.95, -0.02),
    (0.78, 0.34), (0.40, 0.72),
]


def _mix_hex(first, second, t):
    """两个十六进制颜色按 t 混合。"""
    def rgb(value):
        text = str(value).lstrip("#")
        return [int(text[index:index + 2], 16) for index in (0, 2, 4)]
    a, b = rgb(first), rgb(second)
    return "#%02X%02X%02X" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


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


def draw_heart(pen, camera, center, size, name, color="#E9C25C", scale=0.085):
    """花心单独画。等所有花瓣铺完再统一压上去，后画的花就不会盖住前花的花心。"""
    heart = camera.project(center)
    radius = size * scale * camera.focal / max(0.05, _depth(camera, center))
    pen.ellipse(heart.x, heart.y, radius, radius * 0.92, fill=color,
                stroke=None, name="%s·心" % name)


def draw_flower(pen, camera, center, axis, size, name, spin=0.0,
                color=None, heart=True, petals=5, disc=True):
    axis = _unit(axis)
    helper = (0.0, 1.0, 0.0) if abs(axis[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _unit(_cross(helper, axis))
    v = _unit(_cross(axis, u))
    to_screen = _affine(camera, center, _mul(u, size), _mul(v, size))
    tones = ["#F4C6D3", "#EFB4C5", "#F7D2DC"]
    tone = color or tones[sum(ord(ch) for ch in name) % len(tones)]
    # 同色实心圆垫底，填住五瓣之间的缺口，叠压时不透底；半开的花不垫
    middle = camera.project(center)
    if disc:
        radius = size * 0.72 * camera.focal / max(0.05, _depth(camera, center))
        pen.ellipse(middle.x, middle.y, radius, radius, fill=_mix_hex(tone, "#C8455F", 0.10),
                    stroke_width=None, stroke=None, name="%s·底" % name)
    for index in range(petals):
        angle = math.radians(360.0 / petals * index)
        ca, sa = math.cos(angle + spin), math.sin(angle + spin)
        points = []
        for point_index, (x, y) in enumerate(PETAL):
            if point_index == 6:
                y -= NOTCH
            rx = x * ca - (y - 0.05) * sa
            ry = x * sa + (y - 0.05) * ca + 0.05
            points.append(to_screen(rx, ry))
        pen.path([{"closed": True, "knots": _smooth(points)}], fill=tone,
                 stroke_width=1.2, stroke="#D98BA6", name="%s·瓣%d" % (name, index + 1))
    if heart:
        draw_heart(pen, camera, center, size, name, scale=0.085 if petals >= 5 else 0.060)


def draw_bud(pen, camera, center, axis, radial, length, width, color, name):
    """一个花苞：在画面平面上画泪滴形，尖端朝 axis 的投影方向。

    花苞只有几厘米，用三维平面贴形容易把宽度压没；直接投中心点和尖点，
    取屏幕上的方向，宽度按相机比例换算，形状稳定。
    """
    head = camera.project(center)
    tip = camera.project(_add(center, _mul(_unit(axis), length)))
    dx, dy = tip.x - head.x, tip.y - head.y
    span = math.hypot(dx, dy)
    if span < 1e-6:
        dx, dy, span = 0.0, -1.0, 1.0
    ux, uy = dx / span, dy / span
    px, py = -uy, ux
    scale = camera.focal / max(0.05, _depth(camera, center))
    half_l = length * scale * 0.5
    half_w = width * scale * 0.5
    knots = [[head.x + ux * (y * half_l) + px * (x * half_w),
              head.y + uy * (y * half_l) + py * (x * half_w)] for x, y in BUD]
    pen.path([{"closed": True, "knots": _smooth(knots)}], fill=color,
             stroke_width=None, stroke=None, name=name)
    base = (head.x - ux * half_l * 0.82, head.y - uy * half_l * 0.82)
    radius = width * scale * 0.26
    pen.ellipse(base[0], base[1], radius, radius * 0.82, fill="#6B4A36",
                stroke=None, name="%s·萼" % name)


def build():
    """返回 (网格列表, 花, 叶, 苞)。坐标单位米。"""
    meshes = []
    main = [(-0.155, -0.098, 0.054), (-0.062, -0.032, 0.050),
            (-0.030, -0.006, 0.046), (0.000, 0.018, 0.042),
            (0.026, 0.040, 0.038), (0.042, 0.056, 0.034)]
    meshes.append(tube(main, [0.0082, 0.0076, 0.0066, 0.0056, 0.0046, 0.0036],
                       "#6B4A36", "主枝"))

    shoots = {
        "上": ([(0.030, 0.050, 0.036), (0.040, 0.060, 0.028), (0.048, 0.068, 0.022)],
               [0.0042, 0.0032, 0.0024]),
        "下": ([(-0.045, -0.020, 0.048), (-0.032, -0.006, 0.032), (-0.024, 0.004, 0.024)],
               [0.0048, 0.0036, 0.0026]),
        "左": ([(-0.050, -0.020, 0.042), (-0.066, 0.024, 0.032), (-0.082, 0.060, 0.024)],
               [0.0044, 0.0032, 0.0022]),
    }
    for name, (points, radii) in shoots.items():
        meshes.append(tube(points, radii, "#6B4A36", "短枝" + name))

    # 主簇三朵压在一起，副簇一朵退在左下；颜色分三档，叠压处能看出前后
    flowers = [
        ((0.045, 0.086, 0.010), (0.12, 0.28, -0.95), 0.040, 0.20, "花·主", "#F4C6D3", 5),
        ((0.014, 0.064, 0.018), (-0.32, 0.30, -0.90), 0.029, -0.45, "花·主二", "#E8A8BA", 5),
        ((0.076, 0.062, 0.020), (0.48, 0.05, -0.88), 0.027, 1.10, "花·主三", "#E8A8BA", 5),
        ((-0.012, 0.018, 0.014), (0.20, -0.05, -0.98), 0.025, 0.60, "花·副", "#DFA0B3", 5),
        ((-0.046, -0.020, 0.018), (0.20, -0.15, -0.97), 0.022, 0.30, "花·副二", "#E0A4B6", 3),
    ]

    leaves = [
        ((0.018, 0.056, 0.034), (0.42, 0.78, -0.48), (0.30, 0.94, -0.15), 0.050, 0.022, 0.35),
        ((-0.014, 0.038, 0.038), (-0.38, 0.80, -0.48), (0.10, 0.96, -0.20), 0.046, 0.020, -0.45),
        ((-0.042, 0.002, 0.034), (0.30, 0.80, -0.52), (0.30, 0.92, -0.20), 0.044, 0.019, 0.85),
        ((0.060, 0.072, 0.030), (0.45, 0.75, -0.48), (0.60, 0.70, -0.20), 0.050, 0.022, 0.60),
        ((-0.058, -0.032, 0.032), (-0.30, 0.82, -0.48), (-0.20, 0.95, -0.10), 0.042, 0.018, -0.70),
    ]

    buds = [
        ((0.080, 0.098, 0.010), (0.55, 0.83, -0.10), (0.70, 0.71, 0.0),
         0.018, 0.0120, "#B3324C", "苞·上"),
        ((-0.062, -0.036, 0.008), (-0.35, -0.94, 0.0), (0.94, -0.35, 0.0),
         0.017, 0.0110, "#B3324C", "苞·下"),
    ]
    return meshes, flowers, leaves, buds


def proxy_meshes(flowers, buds):
    """三视图里用五瓣薄片表示整朵花，花苞用小扁球表示体积和位置。"""
    from photocraft_draw.ortho import make_blossom

    proxies = []
    for center, axis, size, spin, name, color, petals in flowers:
        proxies.append(make_blossom(center, diameter=size * 2.0, facing=axis,
                                    petals=petals, color=color, name=name + "·花"))
    for center, axis, radial, length, width, color, name in buds:
        proxies.append(make_sphere(length * 0.5, segments=12, rings=8,
                                   center=center, color=color, name=name))
    return proxies


def render_three_views(out: Path) -> None:
    from photocraft_draw.ortho import render_views

    meshes, flowers, leaves, buds = build()
    stems = []
    for center, axis, size, spin, name, color, petals in flowers:
        attach = (center[0] - axis[0] * 0.012, center[1] - axis[1] * 0.012,
                  center[2] + 0.014)
        stems.append(tube([attach, center], [0.0014, 0.0012], "#6B4A36", name + "·梗"))
    for center, axis, radial, length, width, color, name in buds:
        base = _add(center, _mul(_unit(axis), -length * 1.80))
        stems.append(tube([base, center], [0.0012, 0.0010], "#6B4A36", name + "·梗"))
    solids = meshes + stems + proxy_meshes(flowers, buds)
    summary = render_views(solids, out, width=640, height=820)
    print("三视图：%s" % summary.get("path", out))


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

    # 花梗和花苞梗先画，属于底层
    stems = []
    for center, axis, size, spin, name, color, petals in flowers:
        attach = (center[0] - axis[0] * 0.012, center[1] - axis[1] * 0.012,
                  center[2] + 0.014)
        stems.append(tube([attach, center], [0.0014, 0.0012], "#6B4A36", name + "·梗"))
    for center, axis, radial, length, width, color, name in buds:
        base = _add(center, _mul(_unit(axis), -length * 1.80))
        stems.append(tube([base, center], [0.0012, 0.0010], "#6B4A36", name + "·梗"))
    render(meshes + stems, cam, pen,
           lighting={"direction": (-0.45, -0.55, -0.70), "ambient": 0.88, "diffuse": 0.26})

    # 叶在花后，先画
    for center, axis, radial, length, width, spin in leaves:
        draw_shape(pen, cam, center, axis, radial, length, width, LEAF,
                   "#7FA05A", "叶", spin=spin)

    # 花分两遍：先按远近铺花瓣，再统一压花心，四朵的花心都不会被盖住
    ordered = sorted(flowers, key=lambda f: -_depth(cam, f[0]))
    for center, axis, size, spin, name, color, petals in ordered:
        draw_flower(pen, cam, center, axis, size, name, spin=spin,
                    color=color, heart=False, petals=petals, disc=petals >= 5)
    for center, axis, size, spin, name, color, petals in ordered:
        draw_heart(pen, cam, center, size, name,
                   scale=0.085 if petals >= 5 else 0.060)

    # 花苞最后画，挂在两簇的外缘
    for center, axis, radial, length, width, color, name in buds:
        draw_bud(pen, cam, center, axis, radial, length, width, color, name)

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
