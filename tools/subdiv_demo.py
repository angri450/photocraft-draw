# -*- coding: utf-8 -*-
"""细分演示：粗网格花瓣和细分两次的花瓣并排。

    python3 tools/subdiv_demo.py

产物：out/subdiv-demo.png
"""
from __future__ import annotations

import math
from pathlib import Path

from photocraft_draw.commands import Pen
from photocraft_draw.engine import Engine
from photocraft_draw.mesh import Camera, Mesh, render, subdivide
from photocraft_draw.palette import resolve_palette

W, H = 1200, 620


def coarse_petal(offset_x: float, color: str, name: str) -> Mesh:
    """4×4 个顶点的粗网格花瓣，中间凹、边上翻，像一片弯的纸。"""
    rows = cols = 4
    vertices = []
    for row in range(rows):
        t = row / (rows - 1.0)
        half = 0.10 + 0.16 * math.sin(math.pi * min(1.0, t * 1.05)) ** 0.8
        for col in range(cols):
            u = -1.0 + 2.0 * col / (cols - 1.0)
            x = u * half
            y = t * 0.46
            z = 0.05 * (u * u) + 0.06 * t * t
            vertices.append((x + offset_x, y, z))
    faces = []
    for row in range(rows - 1):
        for col in range(cols - 1):
            a = row * cols + col
            faces.append([a, a + cols, a + cols + 1, a + 1])
    return Mesh(vertices=vertices, faces=faces, color=color, name=name)


def main() -> None:
    coarse = coarse_petal(-0.34, "#B9AFA0", "粗网格")
    fine = subdivide(coarse_petal(0.16, "#E8B3C2", "细分后"), 2)

    camera = Camera(position=(0.0, 0.22, -0.95), target=(0.0, 0.20, 0.0),
                    up=(0.0, 1.0, 0.0), focal=900.0,
                    frame=(float(W), float(H)), center=(W / 2.0, H * 0.62),
                    projection="perspective")
    pen = Pen(W, H, ref_width=W, palette=resolve_palette("fresco"))
    pen.rect(0, 0, W, H, fill="#F4EBDF", stroke_width=None, stroke=None, name="底")
    stats = render([coarse, fine], camera, pen,
                   lighting={"direction": (-0.4, -0.7, -0.6), "ambient": 0.9,
                             "diffuse": 0.2}, named=False)
    pen.text(W * 0.25, H - 46, "粗网格 9 个面", size=22, color="#5B4A38", align="center")
    pen.text(W * 0.75, H - 46, "细分两级 144 个面", size=22, color="#5B4A38", align="center")

    out = Path("out/subdiv-demo.png").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with Engine(read_root=Path.cwd(), write_root=out.parent) as engine:
        engine.new_document(W, H, "细分演示")
        for command in pen.commands:
            engine.execute(command["command"], command.get("params") or {})
        engine.save(out)
    print("%d 面画了 %d 面，输出 %s" % (stats["faces"], stats["drawn"], out))


if __name__ == "__main__":
    main()
