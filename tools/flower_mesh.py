# -*- coding: utf-8 -*-
"""用网格管线画一枝海棠：三维枝条、花瓣曲面、花蕊、叶片，再投影成画面。

    python3 tools/flower_mesh.py

产物：out/flower-mesh.png
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from photocraft_draw.commands import Pen
from photocraft_draw.engine import Engine
from photocraft_draw.mesh import Camera, Mesh, make_sphere, render
from photocraft_draw.palette import resolve_palette

WIDTH = 900
HEIGHT = 1200


def _unit(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def frame_from(axis, hint=(0.0, 1.0, 0.0)):
    """给一个朝向，算出两个互相垂直的横向轴。"""
    n = _unit(axis)
    h = hint if abs(sum(n[i] * hint[i] for i in range(3))) < 0.95 else (1.0, 0.0, 0.0)
    u = _unit(_cross(h, n))
    v = _unit(_cross(n, u))
    return u, v, n


def tube(points, radii, color, name="枝", sides=10):
    """沿折线扫一根管，交给网格管线的 sweep，平行传输不会扭转。"""
    from photocraft_draw.mesh import sweep
    return sweep(points, radii, sides=sides, caps=True, color=color, name=name)


def petal(origin, axis, side, length, width, cup=0.35, bend=0.25, notch=0.12,
          color="#F2C0CE", name="花瓣", nu=7, nv=5):
    """一片花瓣：椭圆轮廓、顶端凹缺、中间微微内凹，底端收成爪。"""
    u_ax, v_ax, n_ax = frame_from(axis, hint=side)
    half_w = width * 0.5
    center_y = 0.42 * length
    radius_y = 0.58 * length
    steps = 18
    vertices = []
    outline = []
    for k in range(steps + 1):
        phi = math.radians(-126.0 + 252.0 * k / steps)
        x = half_w * math.sin(phi)
        y = center_y + radius_y * math.cos(phi)
        near_top = abs(phi) / math.radians(34.0)
        if near_top < 1.0:
            y -= notch * length * 0.55 * (1.0 - near_top) ** 1.4
        outline.append((x, y))

    def place(x, y):
        depth = cup * (x / half_w) ** 2 * width + bend * (y / length) ** 2 * length
        return _add(_add(origin, _mul(u_ax, x)),
                    _add(_mul(n_ax, y), _mul(v_ax, depth)))

    hub = len(vertices)
    vertices.append(place(0.0, center_y * 0.55))
    ring = []
    for x, y in outline:
        ring.append(len(vertices))
        vertices.append(place(x, y))
    base = len(vertices)
    vertices.append(place(0.0, 0.0))
    faces = []
    for k in range(steps):
        faces.append([hub, ring[k + 1], ring[k]])
    faces.append([base, hub, ring[0]])
    faces.append([base, ring[-1], hub])
    return Mesh(vertices=vertices, faces=faces, color=color, name=name)


def flower(center, axis, size=0.032, tilt=58.0, count=5, spin=0.0,
           petal_color="#F2C0CE", heart_color="#E9C25C", name="花",
           width_ratio=0.66, cup=0.50, bend=0.32, notch=0.18):
    """一朵五瓣花：花瓣绕着花轴排一圈，各自向外翻。"""
    meshes = []
    u_ax, v_ax, n_ax = frame_from(axis)
    base = _add(center, _mul(n_ax, -size * 0.10))
    for k in range(count):
        angle = 2 * math.pi * k / count + spin
        radial = _add(_mul(u_ax, math.cos(angle)), _mul(v_ax, math.sin(angle)))
        direction = _unit(_add(_mul(radial, math.sin(math.radians(tilt))),
                               _mul(n_ax, math.cos(math.radians(tilt)))))
        meshes.append(petal(base, direction, radial, size, size * width_ratio,
                            cup=cup, bend=bend, notch=notch,
                            color=petal_color, name="%s·瓣%d" % (name, k + 1),
                            nu=9, nv=7))
    heart = make_sphere(size * 0.16, segments=12, rings=8,
                        center=_add(center, _mul(n_ax, size * 0.02)),
                        color=heart_color, name="%s·心" % name)
    meshes.append(heart)
    return meshes


def leaf(origin, axis, side, length=0.030, width=0.010, color="#7FA05A", name="叶"):
    return petal(origin, axis, side, length, width, cup=0.18, bend=0.10,
                 notch=0.0, color=color, name=name, nu=5, nv=3)


def scene():
    meshes = []
    # 主枝：从画外伸进来，往上再往右，花的着生点比枝更靠近相机
    main = [(-0.120, -0.075, 0.042), (-0.075, -0.040, 0.040),
            (-0.030, -0.005, 0.038), (0.010, 0.030, 0.035),
            (0.045, 0.058, 0.032)]
    radii = [0.0092, 0.0082, 0.0070, 0.0058, 0.0046]
    meshes.append(tube(main, radii, "#6B4A36", "主枝"))

    # 两条短枝，一上一下
    shoot_a = [(0.010, 0.030, 0.035), (0.038, 0.062, 0.022), (0.058, 0.082, 0.014)]
    meshes.append(tube(shoot_a, [0.0048, 0.0038, 0.0028], "#6B4A36", "短枝上"))
    shoot_b = [(-0.030, -0.005, 0.038), (-0.008, 0.022, 0.022), (0.010, 0.042, 0.012)]
    meshes.append(tube(shoot_b, [0.0056, 0.0044, 0.0032], "#6B4A36", "短枝前"))

    # 三朵花：正面、侧对、下垂，着生点都在枝的前面
    meshes += flower((0.060, 0.086, 0.008), (0.18, 0.34, -0.92), size=0.032,
                     tilt=62, spin=0.25, name="花·正")
    meshes += flower((0.008, 0.040, 0.004), (0.88, 0.28, -0.38), size=0.029,
                     tilt=64, spin=-0.3, name="花·侧")
    meshes += flower((0.034, 0.066, 0.014), (0.10, -0.72, 0.68), size=0.027,
                     tilt=52, spin=0.8, name="花·垂")

    # 两个花苞
    bud_a = make_sphere(0.0078, segments=12, rings=8,
                        center=(0.076, 0.094, 0.022), color="#E8A8BA", name="苞·1")
    bud_a.transform = {"scale": [1.0, 1.3, 1.0]}
    meshes.append(bud_a)
    meshes.append(make_sphere(0.0062, segments=12, rings=8,
                              center=(-0.014, 0.032, 0.016),
                              color="#E8A8BA", name="苞·2"))

    # 叶片：在花后面，方向错开
    meshes.append(leaf((0.020, 0.018, 0.030), (0.55, 0.80, -0.20), (0.0, 1.0, 0.0),
                       name="叶·1"))
    meshes.append(leaf((0.058, 0.050, 0.028), (-0.30, 0.90, -0.25), (0.2, 1.0, 0.0),
                       name="叶·2"))
    meshes.append(leaf((-0.040, -0.012, 0.030), (0.72, 0.60, -0.30), (0.0, 1.0, 0.2),
                       name="叶·3"))
    return meshes


def camera():
    return Camera(
        position=(0.016, 0.042, -0.250),
        target=(0.024, 0.046, 0.020),
        up=(0.0, 1.0, 0.0),
        focal=900.0,
        frame=(float(WIDTH), float(HEIGHT)),
        center=(WIDTH * 0.52, HEIGHT * 0.46),
        projection="perspective",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="网格海棠一枝")
    parser.add_argument("--out", default="out/flower-mesh.png")
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    pen = Pen(WIDTH, HEIGHT, ref_width=WIDTH, palette=resolve_palette("fresco"))
    pen.rect(0, 0, WIDTH, HEIGHT, fill="#F4EBDF", stroke_width=None, stroke=None, name="底")
    stats = render(scene(), camera(), pen,
                   lighting={"direction": (-0.45, -0.55, -0.70), "ambient": 0.88,
                             "diffuse": 0.26},
                   named=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    with Engine(read_root=Path.cwd(), write_root=out.parent) as engine:
        engine.new_document(WIDTH, HEIGHT, "网格海棠")
        for command in pen.commands:
            engine.execute(command["command"], command.get("params") or {})
        engine.save(out)
    print("%d 个面，画了 %d 个，输出 %s" % (stats["faces"], stats["drawn"], out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
