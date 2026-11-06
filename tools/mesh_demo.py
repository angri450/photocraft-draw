#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重出网格演示图：一张静物，一张和透视稿的并排对比。

用法：
    python3 tools/mesh_demo.py

产物：
    out/mesh-demo.png      静物演示，1600x900
    out/mesh-demo.psd      同一张图的 PSD
    out/mesh-repro.png     透视稿的网格重画，900x1200
    out/mesh-compare.png   左参考、右网格重画，中间一条白缝

参数写死在脚本里，不读外部文件；改演示只改下面两张表。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

sys.path.insert(0, str(ROOT))

from photocraft_draw import mesh  # noqa: E402
from photocraft_draw.commands import Pen  # noqa: E402
from photocraft_draw.engine import Engine  # noqa: E402
from photocraft_draw.palette import resolve_palette  # noqa: E402

# 静物：桌面、木箱、球、柱、锥、小方块，透视加一束方向光
STILL_LIFE = {
    "meshes": [
        {"type": "box", "size": [7.4, 0.22, 4.0], "center": [0, -1.02, 0.2],
         "color": "#9c8a6e", "name": "桌面"},
        {"type": "box", "size": [1.15, 1.9, 1.0], "center": [-2.15, -0.05, 1.3],
         "color": "#6b2f24", "name": "木箱"},
        {"type": "sphere", "radius": 0.62, "segments": 24, "rings": 14,
         "center": [0.05, -0.29, 0.55], "color": "#8a6a3a", "name": "球"},
        {"type": "cylinder", "radius": 0.42, "height": 1.5, "segments": 24,
         "center": [1.75, -0.16, 0.95], "color": "#5f6f78", "name": "柱"},
        {"type": "cone", "radius": 0.5, "height": 1.15, "segments": 24,
         "center": [-0.95, -0.335, -0.55], "color": "#c9b48a", "name": "锥"},
        {"type": "box", "size": [0.5, 0.5, 0.5], "center": [0.95, -0.66, -0.85],
         "color": "#7a6a55", "name": "小方块"},
    ],
    "camera": {
        "position": [0.2, 1.35, -7.6],
        "target": [0, -0.25, 0.3],
        "focal": 760,
        "projection": "perspective",
    },
    "lighting": {"direction": [-0.5, -1.0, 0.55], "ambient": 0.52, "diffuse": 0.52},
    "seal": True,
}

# 透视稿的六个物体：两个方块、球、柱、锥、一棵柱加球拼的树
PERSPECTIVE = {
    "meshes": [
        {"type": "box", "size": [0.6, 0.6, 0.6], "center": [1.2, 0.3, 3.5],
         "color": "#88B4B9", "name": "蓝方块"},
        {"type": "box", "size": [1.0, 1.0, 1.0], "center": [-1.0, 0.5, 4.0],
         "color": "#C9A227", "name": "金方块"},
        {"type": "sphere", "radius": 0.6, "segments": 28, "rings": 16,
         "center": [0.0, 0.6, 6.0], "color": "#C8455F", "name": "玫红球"},
        {"type": "cylinder", "radius": 0.45, "height": 1.6, "segments": 28,
         "center": [1.2, 0.8, 8.0], "color": "#7A9A5B", "name": "绿柱"},
        {"type": "cone", "radius": 0.6, "height": 1.7, "segments": 28,
         "center": [2.2, 0.85, 11.0], "color": "#B3324C", "name": "深红锥"},
        # 树：树干高 2.75，冠心 3.2，和 perspective.py 里 _tree 的算法一致
        {"type": "cylinder", "radius": 0.12, "height": 2.75, "segments": 16,
         "center": [-1.0, 1.375, 14.0], "color": "#6B4A36", "name": "树干"},
        {"type": "sphere", "radius": 0.9, "segments": 28, "rings": 16,
         "center": [-1.0, 3.2, 14.0], "color": "#E3AEC4", "name": "树冠"},
    ],
    "camera": {
        "position": [0, 1.6, 0],
        "target": [0, 1.6, 1],
        "focal": 965,
        "frame": [900, 1200],
        "center": [450, 660],
        "projection": "perspective",
    },
    "lighting": {"direction": [0.5, -1.0, 0.5], "ambient": 0.85, "diffuse": 0.28},
    "seal": True,
}

SKY = "#F4EBDF"
GROUND = "#E8DDC4"
HORIZON = 660


def _new_pen(width: int, height: int, ref_width: float) -> Pen:
    return Pen(width, height, ref_width=ref_width, palette=resolve_palette("fresco"))


def _draw(pen: Pen, width: int, height: int, name: str, psd: bool = False) -> Path:
    target = OUT / name
    with Engine(read_root=str(ROOT), write_root=str(OUT)) as engine:
        engine.new_document(width, height)
        for command in pen.commands:
            engine.execute(command["command"], command["params"])
        engine.save(target)
        if psd:
            engine.save(target.with_suffix(".psd"))
    return target


def render_still_life() -> Path:
    pen = _new_pen(1600, 900, 800)
    stats = mesh.build(STILL_LIFE, pen)
    path = _draw(pen, 1600, 900, "mesh-demo.png", psd=True)
    print(f"静物：{stats['drawn']}/{stats['faces']} 个面，{path}")
    return path


def render_perspective() -> Path:
    pen = _new_pen(900, 1200, 900)
    pen.rect(0, 0, 900, HORIZON, fill=SKY, stroke_width=None, stroke=None, name="天空")
    pen.rect(0, HORIZON, 900, 1200 - HORIZON, fill=GROUND, stroke_width=None, stroke=None,
             name="地面")
    stats = mesh.build(PERSPECTIVE, pen)
    path = _draw(pen, 900, 1200, "mesh-repro.png")
    print(f"透视重画：{stats['drawn']}/{stats['faces']} 个面，{path}")
    return path


def compose_compare(repro: Path) -> Path:
    reference = OUT / "perspective-solids.png"
    if not reference.is_file():
        raise SystemExit(f"找不到参考图：{reference}")
    left = Image.open(reference).convert("RGB")
    right = Image.open(repro).convert("RGB")
    if left.size != right.size:
        raise SystemExit(f"两张图尺寸不同：参考 {left.size}，重画 {right.size}")
    gap = 6
    canvas = Image.new("RGB", (left.width + gap + right.width, left.height), (255, 255, 255))
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + gap, 0))
    target = OUT / "mesh-compare.png"
    canvas.save(target)
    print(f"对比图：{target}（{canvas.width}x{canvas.height}，中间 {gap} 像素白缝）")
    return target


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    render_still_life()
    repro = render_perspective()
    compose_compare(repro)
    (OUT / "mesh-demo-params.json").write_text(
        json.dumps(STILL_LIFE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
