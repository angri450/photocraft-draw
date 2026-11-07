#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重出网格加强版的图元演示：胶囊、旋转体、扫掠。

用法：
    python3 tools/mesh-primitives-demo.py

产物：
    out/mesh-primitives.png   三联页，1200x780
    out/mesh-primitives.psd   同一张图的 PSD

三栏各放一组图元，每栏标出顶点数、面数和是否水密。参数写死在脚本里，
改演示只改下面三张表。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

sys.path.insert(0, str(ROOT))

from photocraft_draw import mesh  # noqa: E402
from photocraft_draw.commands import Pen  # noqa: E402
from photocraft_draw.engine import Engine  # noqa: E402
from photocraft_draw.palette import resolve_palette  # noqa: E402

WIDTH, HEIGHT = 1200, 780
PANEL_Y = 430
PANEL_FRAME = (400, 620)

CAMERA = {
    "position": [0.0, 0.55, -5.4],
    "target": [0.0, 0.05, 0.0],
    "focal": 760,
    "projection": "perspective",
}
LIGHT = {"direction": [-0.5, -1.0, 0.55], "ambient": 0.58, "diffuse": 0.45}

# 胶囊：一根立着、一根斜着、一根小的，看两头的半球
CAPSULES = [
    dict(radius=0.34, height=1.0, segments=28, rings=9,
         center=(-0.55, 0.05, 0.0), color="#8a6a3a", name="立胶囊"),
    dict(radius=0.26, height=0.7, segments=28, rings=9,
         color="#6b2f24", name="斜胶囊",
         transform={"rotate": [0, 0, 62], "translate": [0.66, 0.35, 0.15]}),
    dict(radius=0.22, height=0.5, segments=24, rings=8,
         center=(0.6, -0.72, 0.35), color="#5f6f78", name="小胶囊"),
]

# 旋转体：花瓶、果子、花萼，母线都从下往上写
VASE = [[0.0, -0.72], [0.44, -0.72], [0.3, -0.18], [0.42, 0.3],
        [0.2, 0.6], [0.15, 0.7]]
FRUIT = [[0.0, -0.42], [0.3, -0.3], [0.34, 0.0], [0.26, 0.27], [0.0, 0.4]]
CALYX = [[0.0, -0.12], [0.12, -0.1], [0.18, -0.02], [0.2, 0.08], [0.25, 0.14], [0.27, 0.16]]

LATHES = [
    dict(profile=VASE, segments=32, center=(-0.55, -0.08, 0.0),
         color="#8a6a3a", name="花瓶"),
    dict(profile=FRUIT, segments=28, center=(0.55, 0.15, 0.25),
         color="#c8455f", name="果子"),
    dict(profile=CALYX, segments=24, center=(0.55, -0.5, 0.25),
         color="#7a9a5b", name="花萼"),
]

# 扫掠：一根主枝从下往上，在中段分成两叉，左叉粗、右叉细，三个枝梢都收成尖
MAIN_POINTS = [
    [-1.02, -1.0, 0.22], [-0.88, -0.6, 0.14], [-0.7, -0.18, 0.06],
    [-0.46, 0.22, 0.0],
]
MAIN_RADII = [0.13, 0.116, 0.102, 0.09]

FORK_HIGH_POINTS = [
    [-0.46, 0.22, 0.0], [-0.36, 0.6, -0.05], [-0.2, 0.94, -0.1],
    [-0.02, 1.06, -0.12],
]
FORK_HIGH_RADII = [0.088, 0.062, 0.032, 0.0]

FORK_LOW_POINTS = [
    [-0.46, 0.22, 0.0], [-0.12, 0.4, -0.06], [0.28, 0.58, -0.1],
    [0.62, 0.7, -0.12],
]
FORK_LOW_RADII = [0.058, 0.04, 0.022, 0.0]

SWEEPS = [
    dict(points=MAIN_POINTS, radii=MAIN_RADII, sides=16,
         color="#6b2f24", name="主枝"),
    dict(points=FORK_HIGH_POINTS, radii=FORK_HIGH_RADII, sides=14,
         color="#8a6a3a", name="左叉"),
    dict(points=FORK_LOW_POINTS, radii=FORK_LOW_RADII, sides=14,
         color="#a05a3c", name="右叉"),
]

PANELS = [
    ("胶囊  make_capsule", "花苞、果实的基础体：圆柱加两个半球"),
    ("旋转体  make_lathe", "二维母线绕竖轴转一圈：瓶、果、萼"),
    ("扫掠  sweep", "一根主枝分两叉，左粗右细，枝梢收尖"),
]


def build_group(specs):
    """按参数表造一组网格，同时统计顶点数、面数和是否水密。"""
    meshes = [mesh.mesh_from_dict(dict(spec, type=kind)) for kind, spec in specs]
    vertices = sum(len(item.vertices) for item in meshes)
    faces = sum(len(item.faces) for item in meshes)
    sealed = all(mesh.is_watertight(item) for item in meshes)
    return meshes, vertices, faces, sealed


def draw_panel(pen, center_x, meshes):
    camera = mesh.camera_from_dict(dict(CAMERA, frame=list(PANEL_FRAME),
                                        center=[center_x, PANEL_Y]))
    return mesh.render(meshes, camera, pen, lighting=LIGHT)


def draw_frame(pen):
    pen.rect(0, 0, WIDTH, HEIGHT, fill="surface", stroke_width=None, stroke=None,
             name="底色")
    pen.rect(0, 0, WIDTH, 96, fill="accent", stroke_width=None, stroke=None,
             name="页眉")
    pen.line(0, 96, WIDTH, 96, width=1, color="line", name="页眉线")
    for x in (400, 800):
        pen.line(x, 118, x, HEIGHT - 42, width=1, color="line", name="分栏线")
    pen.text(44, 44, "网格图元：胶囊、旋转体、扫掠", size=30, color="ink",
             name="总标题")
    pen.text(44, 74, "三联页  ·  每栏标出顶点数、面数和是否水密", size=14,
             color="muted", name="副标题")
    pen.text(WIDTH - 44, 74, "同色面缝描边，放大后看不到接缝", size=13,
             color="muted", align="right", name="脚注")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pen = Pen(WIDTH, HEIGHT, ref_width=WIDTH, palette=resolve_palette("fresco"))
    draw_frame(pen)

    groups = [
        [("capsule", spec) for spec in CAPSULES],
        [("lathe", spec) for spec in LATHES],
        [("sweep", spec) for spec in SWEEPS],
    ]
    for index, (group, (title, note)) in enumerate(zip(groups, PANELS)):
        center_x = 200 + index * 400
        meshes, vertices, faces, sealed = build_group(group)
        draw_panel(pen, center_x, meshes)
        pen.text(center_x - 168, 122, title, size=17, color="ink", name=f"{title}·标题")
        pen.text(center_x - 168, 146, note, size=12, color="muted", name=f"{title}·说明")
        mark = "水密" if sealed else "有开口"
        pen.text(center_x - 168, HEIGHT - 34,
                 f"顶点 {vertices}  ·  面 {faces}  ·  {mark}",
                 size=13, color="deep", name=f"{title}·计数")

    with Engine(read_root=str(ROOT), write_root=str(OUT.resolve())) as engine:
        engine.new_document(WIDTH, HEIGHT)
        for command in pen.commands:
            engine.execute(command["command"], command["params"])
        print(engine.save(OUT / "mesh-primitives.png"))
        print(engine.save(OUT / "mesh-primitives.psd"))
    print(f"指令 {len(pen.commands)} 条")


if __name__ == "__main__":
    main()
