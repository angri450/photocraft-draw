# -*- coding: utf-8 -*-
"""四模块合流验证：mesh → stroke → ortho → layout 一条链跑通。

这条脚本不替代任何一个模块的测试，它只回答一个问题：四份分开做的代码
拼在一起还能不能用。场景按 plans/perspective-solids.json 摆，四个几何体
的位置和配色照抄；透视底图交给 stroke 补一根枝条和一片花瓣，三视图交给
ortho，网格和数字交给 layout。

产物：
    out/compose-persp.png   900x1200，透视底图加枝条花瓣
    out/compose-views.png   1800x700，正、左、俯三视图
    out/compose-grid.png    透视底图加构图网格和数字

用法：
    python3 tools/compose_check.py
    python3 tools/compose_check.py --out-dir out
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from photocraft_draw.commands import Pen  # noqa: E402
from photocraft_draw.engine import Engine  # noqa: E402
from photocraft_draw.layout import analyze, draw_grid, report  # noqa: E402
from photocraft_draw.mesh import (  # noqa: E402
    Camera,
    make_box,
    make_cone,
    make_cylinder,
    make_sphere,
    render,
)
from photocraft_draw.ortho import render_views  # noqa: E402
from photocraft_draw.palette import resolve_palette  # noqa: E402
from photocraft_draw.stroke import stroke_path, taper  # noqa: E402

WIDTH = 900
HEIGHT = 1200
HORIZON = 660
SKY = "#F4EBDF"
GROUND = "#E8DDC4"

# 枝条和花瓣都放在左上角的空处，不压住几何体。
BRANCH = [[60, 700], [110, 655], [175, 610], [240, 560], [300, 505], [346, 456]]
TWIG = [[222, 583], [252, 556], [282, 540]]
PETAL_BASE = (346.0, 456.0)
PETAL_ANGLE = -55.0
PETAL_LENGTH = 132.0
PETAL_PROFILE = ((0.0, 3.0), (0.10, 13.0), (0.25, 30.0), (0.45, 46.0),
                 (0.62, 54.0), (0.78, 50.0), (0.90, 38.0), (0.97, 22.0))

FONT_PATHS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def scene_meshes() -> list:
    """四个几何体和一棵树，坐标和配色照 plans/perspective-solids.json。"""
    return [
        make_box(0.6, 0.6, 0.6, center=(1.2, 0.3, 3.5), color="#88B4B9", name="小方块"),
        make_box(1.0, 1.0, 1.0, center=(-1.0, 0.5, 4.0), color="#C9A227", name="大方块"),
        make_sphere(0.6, segments=20, rings=10, center=(0.0, 0.6, 6.0),
                    color="#C8455F", name="球"),
        make_cylinder(0.45, 1.6, segments=20, center=(1.2, 0.8, 8.0),
                      color="#7A9A5B", name="柱"),
        make_cone(0.6, 1.7, segments=20, center=(2.2, 0.85, 11.0),
                  color="#B3324C", name="锥"),
        make_cylinder(0.12, 2.705, segments=12, center=(-1.0, 1.3525, 14.0),
                      color="#6B4A36", name="树干"),
        make_sphere(0.9, segments=18, rings=9, center=(-1.0, 3.2, 14.0),
                    color="#E3AEC4", name="树冠"),
    ]


def scene_camera() -> Camera:
    """平视相机，视平线落在画高 0.55 处。

    相机比方案里的站位后退 0.8 米，让整组物体缩一点，四边留出余量，
    世界坐标本身没动。
    """
    return Camera(
        position=(0.0, 1.6, -0.8),
        target=(0.0, 1.6, 9.2),
        up=(0.0, 1.0, 0.0),
        focal=965.0,
        frame=(float(WIDTH), float(HEIGHT)),
        center=(WIDTH / 2.0, float(HORIZON)),
        projection="perspective",
    )


def draw_backdrop(pen: Pen) -> None:
    pen.rect(0, 0, WIDTH, HORIZON, fill=SKY, stroke_width=None, stroke=None, name="天空")
    pen.rect(0, HORIZON, WIDTH, HEIGHT - HORIZON, fill=GROUND,
             stroke_width=None, stroke=None, name="地面")


def _profile_width(t: float) -> float:
    """花瓣在长度方向上的半宽，基部窄、中间宽、头部收圆。"""
    for index in range(1, len(PETAL_PROFILE)):
        low_t, low_w = PETAL_PROFILE[index - 1]
        high_t, high_w = PETAL_PROFILE[index]
        if t <= high_t:
            ratio = (t - low_t) / (high_t - low_t)
            return low_w + (high_w - low_w) * ratio
    return PETAL_PROFILE[-1][1]


def petal_points(count: int = 16) -> list:
    """一片斜着长的花瓣：基部窄，头部圆，沿 -55 度方向伸出。"""
    rad = math.radians(PETAL_ANGLE)
    dx, dy = math.cos(rad), math.sin(rad)
    nx, ny = -dy, dx
    base_x, base_y = PETAL_BASE
    points = []
    for step in range(count):
        t = 0.97 * step / (count - 1)
        width = _profile_width(t)
        points.append([base_x + dx * PETAL_LENGTH * t + nx * width,
                       base_y + dy * PETAL_LENGTH * t + ny * width])
    points.append([base_x + dx * PETAL_LENGTH, base_y + dy * PETAL_LENGTH])
    for step in range(count - 1, -1, -1):
        t = 0.97 * step / (count - 1)
        width = _profile_width(t)
        points.append([base_x + dx * PETAL_LENGTH * t - nx * width,
                       base_y + dy * PETAL_LENGTH * t - ny * width])
    return points


def fold_strip(points, center, start, width_start, width_end, count=12):
    """沿花瓣一侧取一段，向里收出一条折过去的边。

    宽度从 width_start 收到 width_end，用背面色填，看起来像纸片翻过来
    的一条。返回折边多边形和折痕点列。
    """
    indices = [(start + step) % len(points) for step in range(count)]
    outer = [points[index] for index in indices]
    span = max(1, count - 1)
    inner = []
    for step, index in enumerate(indices):
        px, py = points[index]
        vx, vy = center[0] - px, center[1] - py
        length = math.hypot(vx, vy) or 1.0
        depth = width_start + (width_end - width_start) * step / span
        inner.append([px + vx / length * depth, py + vy / length * depth])
    return outer + list(reversed(inner)), inner


def petal_center() -> tuple:
    rad = math.radians(PETAL_ANGLE)
    return (PETAL_BASE[0] + math.cos(rad) * PETAL_LENGTH * 0.55,
            PETAL_BASE[1] + math.sin(rad) * PETAL_LENGTH * 0.55)


def draw_branch(pen: Pen) -> None:
    """一根从 12 收到 2 的枝条，带侧枝和一片折边的花瓣。"""
    stroke_path(pen, BRANCH, taper(len(BRANCH), 12, 2), "#8A6A3A", name="枝条")
    stroke_path(pen, TWIG, taper(len(TWIG), 5, 1.2), "#8A6A3A", name="侧枝")
    pen.ellipse(TWIG[-1][0], TWIG[-1][1], 4.0, 6.0, fill="#8E2238",
                stroke_width=None, stroke=None, name="芽")

    points = petal_points()
    pen.path([{"closed": True, "knots": points}], fill="#E8B3BE", name="花瓣")

    # 右边缘从头部往基部折回来的一条，10 收到 3
    start = 17
    strip, crease = fold_strip(points, petal_center(), start, 10, 3)
    pen.path([{"closed": True, "knots": strip}], fill="#A93B57", name="花瓣背面")
    pen.path([{"closed": False, "knots": crease}], fill=None,
             stroke_width=1.4, stroke="#7E1F35", name="折痕")
    stroke_path(pen, points, 1.6, "#C8455F", closed=True, name="花瓣边缘")

    pen.ellipse(PETAL_BASE[0], PETAL_BASE[1], 7, 5, fill="#8E2238",
                stroke_width=None, stroke=None, name="花萼")


def save(commands: list[dict], path: Path, name: str) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with Engine(read_root=Path.cwd(), write_root=path.parent) as engine:
        engine.new_document(WIDTH, HEIGHT, name)
        for command in commands:
            engine.execute(command["command"], command.get("params") or {})
        engine.save(path)
    return path


def _font(size: int):
    from PIL import ImageFont

    for candidate in FONT_PATHS:
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def annotate(path: Path, result: dict) -> None:
    """把四个指标写在网格图左上角，图上直接能读到数字。"""
    from PIL import Image, ImageDraw

    with Image.open(path) as raw:
        image = raw.convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    offset = result["center_offset"]
    quadrants = result["density"]["quadrants"]
    lines = [
        "重心偏移 x %+.1f  y %+.1f 像素" % (offset["x"], offset["y"]),
        "长轴 %.1f°  %s" % (result["axis_angle"], result["axis_note"]),
        "密度 左上 %.1f%%  右上 %.1f%%  左下 %.1f%%  右下 %.1f%%"
        % (quadrants[0] * 100, quadrants[1] * 100, quadrants[2] * 100, quadrants[3] * 100),
    ]
    font = _font(16)
    draw.rounded_rectangle([14, 14, 526, 108], radius=6,
                           fill=(255, 255, 255, 228), outline=(58, 48, 38, 255), width=1)
    for index, text in enumerate(lines):
        draw.text((28, 24 + index * 27), text, font=font, fill=(58, 48, 38, 255))
    image.save(path, "PNG")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="四模块合流验证：mesh、stroke、ortho、layout")
    parser.add_argument("--out-dir", default="out", help="输出目录，默认 out")
    args = parser.parse_args(argv)
    out = Path(args.out_dir)

    meshes = scene_meshes()
    camera = scene_camera()

    # 1. mesh 透视底图，2. stroke 在同一张图上补枝条和花瓣
    pen = Pen(WIDTH, HEIGHT, ref_width=WIDTH, palette=resolve_palette("fresco"))
    draw_backdrop(pen)
    stats = render(meshes, camera, pen, lighting={"direction": (-0.5, -1.0, 0.35)},
                   named=True)
    draw_branch(pen)
    persp = save(pen.commands, out / "compose-persp.png", "四模块合流 · 透视底图")

    # 3. ortho 用同一组网格出三视图，每块面板 600x700，拼起来 1800x700
    dimensions = [
        {"from": (-1.5, 0.0, 4.0), "to": (2.8, 0.0, 4.0), "label": "总宽 4.3",
         "views": ["front"], "offset": 26},
        {"from": (0.0, 0.0, 3.5), "to": (0.0, 0.0, 14.0), "label": "总深 10.5",
         "views": ["left"], "offset": 26},
    ]
    views = render_views(meshes, out / "compose-views.png",
                         width=600, height=700, dimensions=dimensions,
                         center_per_view=True)

    # 4. layout 读透视底图出数字，再叠一张网格图
    result = analyze(persp)
    grid = out / "compose-grid.png"
    draw_grid(persp, grid, result=result)
    annotate(grid, result)

    print("透视底图：%s | %d 个面，画了 %d 个 | %d 条指令"
          % (persp, stats["faces"], stats["drawn"], len(pen.commands)))
    print("三视图：%s | %dx%d | %s"
          % (views["path"], views["width"], views["height"],
             "、".join(panel["view"] for panel in views["panels"])))
    print("网格图：%s" % grid)
    print("")
    print(report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
