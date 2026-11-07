# -*- coding: utf-8 -*-
"""网格回归基线与性能基准。

网格改动会动到渲染，改完得知道老场景有没有被画坏。这条命令做三件事：
跑 plans/mesh-solids.json，和基线图算前景交并比；跑一个五千面的压力
场景，记录面数、指令数和耗时；把基线和当前并排拼成一张对照图。

前景按 alpha 认：透明底图里 alpha 大于 0 就是画出来的部分。没有 alpha
的图按边框主色当背景，和背景差得多的像素算前景。

用法：
    python3 tools/regression.py                # 比对，交并比低于 0.97 退出码 1
    python3 tools/regression.py --update       # 重出基线，不比对
    python3 tools/regression.py --threshold 0.98 --json out/r.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageChops, ImageDraw, ImageFont  # noqa: E402

from photocraft_draw.commands import Pen  # noqa: E402
from photocraft_draw.engine import Engine  # noqa: E402
from photocraft_draw.mesh import (  # noqa: E402
    Camera,
    make_cone,
    make_cylinder,
    make_sphere,
    render,
)
from photocraft_draw.palette import resolve_palette  # noqa: E402
from photocraft_draw.plan import compose_plan, load_plan  # noqa: E402

PLAN = ROOT / "plans" / "mesh-solids.json"
BASELINE = ROOT / "tests" / "baseline" / "mesh-solids.png"
CURRENT = ROOT / "out" / "regression-current.png"
COMPARE = ROOT / "out" / "regression-compare.png"
RESULT = ROOT / "out" / "regression.json"

DEFAULT_THRESHOLD = 0.97
GAP = 12

FONT_PATHS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def render_plan(plan_path, png_path) -> dict:
    """按方案出图，返回摘要。和 cli 的 draw 走同一条路。"""
    plan = load_plan(plan_path)
    commands, meta = compose_plan(plan)
    target = Path(png_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with Engine(read_root=ROOT, write_root=target.parent) as engine:
        engine.new_document(meta["width"], meta["height"], meta["name"],
                            background=meta.get("document_background"))
        for command in commands:
            result = engine.execute(command["command"], command.get("params") or {})
            if command["command"] == "layer.new.group" and not command.get("_nested"):
                layer_id = result.get("layer") if isinstance(result, dict) else None
                if layer_id is not None:
                    engine.execute("layer.arrange.bringToFront", {"layer": layer_id})
        if meta.get("document_background") == "transparent":
            engine.execute("file.scripts.deleteAllEmptyLayers", {})
        engine.save(target, "png")
    return meta


def _border_background(image: Image.Image):
    width, height = image.size
    pixels = image.load()
    colors = []
    for x in range(width):
        colors.append(pixels[x, 0])
        colors.append(pixels[x, height - 1])
    for y in range(height):
        colors.append(pixels[0, y])
        colors.append(pixels[width - 1, y])
    return Counter(colors).most_common(1)[0][0]


def foreground_mask(image: Image.Image) -> Image.Image:
    """前景蒙版：透明图看 alpha，不透明图看和边框主色的差。"""
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 255:
        return alpha.point(lambda value: 255 if value > 0 else 0)
    rgb = image.convert("RGB")
    background = _border_background(rgb)
    difference = ImageChops.difference(
        rgb, Image.new("RGB", rgb.size, background)).convert("L")
    return difference.point(lambda value: 255 if value > 12 else 0)


def iou(baseline_path, current_path) -> float:
    """两张图前景的交并比。没有前景时记 0。"""
    with Image.open(baseline_path) as raw:
        first = foreground_mask(raw)
    with Image.open(current_path) as raw:
        second = foreground_mask(raw)
    if first.size != second.size:
        raise ValueError("基线图和当前图尺寸不一致：%s 对 %s" % (first.size, second.size))
    intersection = ImageChops.darker(first, second).histogram()[255]
    union = ImageChops.lighter(first, second).histogram()[255]
    if union == 0:
        return 0.0
    return intersection / union


def stress_scene() -> dict:
    """五千面左右的压力场景：十球、六柱、四锥，跑了多久、多少面。"""
    meshes = []
    for index in range(10):
        x = (index % 5) * 1.2 - 2.4
        z = 3.0 + (index // 5) * 1.4
        meshes.append(make_sphere(0.32, segments=28, rings=16,
                                  center=(x, 0.32, z), color="#C8455F", name="球%d" % index))
    for index in range(6):
        x = (index % 3) * 1.4 - 1.4
        z = 6.0 + (index // 3) * 1.2
        meshes.append(make_cylinder(0.22, 1.0, segments=28,
                                    center=(x, 0.5, z), color="#7A9A5B", name="柱%d" % index))
    for index in range(4):
        x = (index % 2) * 1.6 - 0.8
        z = 8.0 + (index // 2) * 1.2
        meshes.append(make_cone(0.28, 0.9, segments=28,
                                center=(x, 0.45, z), color="#B3324C", name="锥%d" % index))

    camera = Camera(
        position=(0.0, 1.6, 0.0),
        target=(0.0, 1.6, 4.0),
        up=(0.0, 1.0, 0.0),
        focal=900.0,
        frame=(900.0, 1200.0),
        center=(450.0, 660.0),
        projection="perspective",
    )
    pen = Pen(900, 1200, ref_width=900, palette=resolve_palette("fresco"))
    started = time.perf_counter()
    stats = render(meshes, camera, pen,
                   lighting={"direction": (0.5, -1.0, 0.5), "ambient": 0.85, "diffuse": 0.28})
    elapsed = time.perf_counter() - started
    return {
        "meshes": len(meshes),
        "faces": stats["faces"],
        "drawn": stats["drawn"],
        "commands": len(pen.commands),
        "seconds": round(elapsed, 3),
    }


def _font(size: int):
    for candidate in FONT_PATHS:
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def build_compare(baseline_path, current_path, out_path, value=None) -> Path:
    """左基线、右当前，中间一条白缝。"""
    with Image.open(baseline_path) as raw:
        first = raw.convert("RGBA")
    with Image.open(current_path) as raw:
        second = raw.convert("RGBA")
    if first.size != second.size:
        raise ValueError("基线图和当前图尺寸不一致：%s 对 %s" % (first.size, second.size))
    width, height = first.size
    canvas = Image.new("RGB", (width * 2 + GAP, height), "white")
    canvas.paste(first.convert("RGB"), (0, 0), first)
    canvas.paste(second.convert("RGB"), (width + GAP, 0), second)

    draw = ImageDraw.Draw(canvas, "RGBA")
    font = _font(18)
    for label, left in (("基线", 12), ("当前", width + GAP + 12)):
        draw.rounded_rectangle([left - 6, 10, left + 64, 40], radius=4,
                               fill=(255, 255, 255, 220))
        draw.text((left, 14), label, font=font, fill=(58, 48, 38, 255))
    if value is not None:
        text = "IoU %.4f" % value
        centre = width + GAP // 2
        draw.rounded_rectangle([centre - 62, height - 48, centre + 62, height - 14],
                               radius=4, fill=(255, 255, 255, 220))
        draw.text((centre - 48, height - 44), text, font=font, fill=(58, 48, 38, 255))

    target = Path(out_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, "PNG")
    return target


def compare(baseline_path, current_path, threshold=DEFAULT_THRESHOLD) -> dict:
    baseline_path = Path(baseline_path)
    if not baseline_path.is_file():
        raise FileNotFoundError("找不到基线图：%s" % baseline_path)
    value = iou(baseline_path, current_path)
    return {
        "baseline": str(baseline_path),
        "current": str(current_path),
        "threshold": threshold,
        "iou": round(value, 6),
        "ok": value >= threshold,
    }


def run(plan=PLAN, baseline=BASELINE, current=CURRENT, out=COMPARE,
        json_path=RESULT, threshold=DEFAULT_THRESHOLD, update=False) -> int:
    started = time.perf_counter()
    render_started = time.perf_counter()
    meta = render_plan(plan, current)
    render_seconds = round(time.perf_counter() - render_started, 3)

    if update:
        baseline = Path(baseline)
        baseline.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(current) as raw:
            raw.save(baseline, "PNG")
        print("基线已更新：%s（%d 字节，渲染 %.3f 秒）"
              % (baseline, baseline.stat().st_size, render_seconds))
        return 0

    compare_started = time.perf_counter()
    result = compare(baseline, current, threshold)
    compare_seconds = round(time.perf_counter() - compare_started, 3)

    stress_started = time.perf_counter()
    stress = stress_scene()
    stress_seconds = round(time.perf_counter() - stress_started, 3)
    result["stress"] = stress
    result["plan"] = {"path": str(plan), "layers": meta.get("layers", 1),
                      "components": meta.get("components", 1),
                      "commands": meta.get("commands", 0)}
    result["timings"] = {
        "render": render_seconds,
        "iou": compare_seconds,
        "stress": stress_seconds,
    }
    build_compare(baseline, current, out, result["iou"])
    result["timings"]["total"] = round(time.perf_counter() - started, 3)

    target = Path(json_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("交并比 %.4f（阈值 %.2f）%s" % (result["iou"], threshold,
                                          "通过" if result["ok"] else "不通过"))
    print("压力场景 %d 个网格，%d 个面，画了 %d 个，%d 条指令，%.3f 秒"
          % (stress["meshes"], stress["faces"], stress["drawn"],
             stress["commands"], stress["seconds"]))
    print("耗时：渲染方案 %.2f 秒，交并比 %.2f 秒，压力场景 %.2f 秒，合计 %.2f 秒"
          % (render_seconds, compare_seconds, stress_seconds,
             result["timings"]["total"]))
    print("对照图：%s" % out)
    print("结果：%s" % target)
    return 0 if result["ok"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="网格回归基线与性能基准")
    parser.add_argument("--update", action="store_true", help="重出基线，不比对")
    parser.add_argument("--plan", default=str(PLAN), help="回归用的绘制方案")
    parser.add_argument("--baseline", default=str(BASELINE), help="基线图路径")
    parser.add_argument("--current", default=str(CURRENT), help="当前渲染输出路径")
    parser.add_argument("--out", default=str(COMPARE), help="对照图路径")
    parser.add_argument("--json", default=str(RESULT), help="结果 JSON 路径")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help="交并比阈值，默认 %.2f" % DEFAULT_THRESHOLD)
    args = parser.parse_args(argv)
    try:
        return run(args.plan, args.baseline, args.current, args.out,
                   args.json, args.threshold, args.update)
    except (FileNotFoundError, ValueError) as error:
        print("fail | %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
