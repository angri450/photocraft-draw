# -*- coding: utf-8 -*-
"""构图检查：黄金分割、三分法、三七停。

只出线和数字，不做自动调整。输入是已经出好的一张图，量四件事：

1. center_offset：主体重心到最近黄金分割线的像素距离，横向纵向各一个。
   带符号，正值表示主体在那条线的左边或者上边。
2. density：画面四象限的非背景像素占比。
3. axis_angle：主体长轴与水平线的夹角，用主轴分析算。
4. margin：主体外接框到四边的距离。

背景按颜色认：整幅图里占比超过阈值的、又出现在画布边上的颜色，都算
背景。白模常见的天色和地面两种底色能一起认出来，纯色图的密度自然是 0。

用法：
    from photocraft_draw.layout import analyze, draw_grid
    result = analyze("out/perspective-solids.png")
    draw_grid("out/perspective-solids.png", "out/layout-demo.png")

命令行：
    python3 -m photocraft_draw.layout out/a.png --out out/a-layout.png
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

# 默认规则。rules 参数只覆盖给出的项，其余照旧。
DEFAULT_RULES = {
    "golden": [0.382, 0.618],
    "thirds": [1 / 3, 2 / 3],
    "three_seven": [0.3, 0.7],
    "offset_warn": 30.0,
    "background_share": 0.05,
    "background_tolerance": 24.0,
    "margin_warn": 0.02,
}

GROUPS = (
    ("golden", "黄金分割"),
    ("thirds", "三分法"),
    ("three_seven", "三七停"),
)

# 三套线用三种颜色，覆盖图上一眼能分开。
GROUP_COLORS = {
    "golden": (191, 61, 45),
    "thirds": (41, 110, 173),
    "three_seven": (57, 150, 96),
}
HIGHLIGHT = (126, 64, 158)
CENTROID = (226, 122, 32)
INK = (58, 48, 38)

# 优先找中文字体，找不到再退回 PIL 自带的位图字体。
FONT_PATHS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:  # pragma: no cover - 只有没装 Pillow 才会走到
        raise RuntimeError("构图检查要读图片像素，先装 Pillow：python3 -m pip install pillow") from error
    return Image, ImageDraw, ImageFont


def merge_rules(rules: dict | None = None) -> dict:
    """补全规则。只覆盖给出的项，没有的用默认值。"""
    merged = {key: (list(value) if isinstance(value, list) else value)
              for key, value in DEFAULT_RULES.items()}
    if not rules:
        return merged
    if not isinstance(rules, dict):
        raise ValueError("rules 必须是一个对象")
    for key, value in rules.items():
        if key in ("golden", "thirds", "three_seven"):
            if not isinstance(value, (list, tuple)) or not value:
                raise ValueError(f"{key} 要是非空数组")
            ratios = [float(item) for item in value]
            if any(item <= 0 or item >= 1 for item in ratios):
                raise ValueError(f"{key} 的比例要在 0 和 1 之间")
            merged[key] = ratios
        elif key in ("offset_warn", "background_share", "background_tolerance", "margin_warn"):
            merged[key] = float(value)
        else:
            merged[key] = value
    return merged


def grid_lines(width: int, height: int, rules: dict | None = None) -> list[dict]:
    """三套网格的全部参考线，按黄金分割、三分法、三七停的顺序。"""
    if width <= 0 or height <= 0:
        raise ValueError("画布宽高必须大于 0")
    merged = merge_rules(rules)
    lines = []
    for group, name in GROUPS:
        for ratio in merged[group]:
            lines.append({
                "group": group,
                "name": name,
                "kind": "vertical",
                "ratio": round(ratio, 6),
                "pos": ratio * width,
                "label": f"{name} {ratio:.3f}",
            })
            lines.append({
                "group": group,
                "name": name,
                "kind": "horizontal",
                "ratio": round(ratio, 6),
                "pos": ratio * height,
                "label": f"{name} {ratio:.3f}",
            })
    return lines


def _dist2(first, second) -> float:
    return ((first[0] - second[0]) ** 2
            + (first[1] - second[1]) ** 2
            + (first[2] - second[2]) ** 2)


def _border_colors(raw: bytes, width: int, height: int) -> list:
    colors = []
    for x in range(width):
        colors.append(_pixel_at(raw, x, 0, width))
        colors.append(_pixel_at(raw, x, height - 1, width))
    for y in range(height):
        colors.append(_pixel_at(raw, 0, y, width))
        colors.append(_pixel_at(raw, width - 1, y, width))
    return colors


def _pixel_at(raw: bytes, x: int, y: int, width: int):
    base = (y * width + x) * 3
    return (raw[base], raw[base + 1], raw[base + 2])


def _backgrounds(raw: bytes, width: int, height: int, rules: dict) -> list:
    """按面积占比和贴边两条一起认背景色。

    白模常常是两种背景：上面天色、下面地面。只看一个角落会把地面当成
    主体，所以先取占比够大的颜色，再筛出真的出现在画布边上的那些。
    """
    total = width * height
    counts = Counter(zip(raw[0::3], raw[1::3], raw[2::3]))
    share = float(rules["background_share"])
    tolerance = float(rules["background_tolerance"])
    limit = tolerance * tolerance
    border = _border_colors(raw, width, height)
    found = []
    for color, count in counts.most_common(8):
        if count / total < share:
            continue
        if any(_dist2(color, edge) <= limit for edge in border):
            found.append(color)
    if not found:
        found.append(Counter(border).most_common(1)[0][0])
    return found


def _is_background(raw: bytes, base: int, backgrounds: list, limit: float) -> bool:
    red, green, blue = raw[base], raw[base + 1], raw[base + 2]
    for color in backgrounds:
        if ((red - color[0]) ** 2 + (green - color[1]) ** 2
                + (blue - color[2]) ** 2) <= limit:
            return True
    return False


def _mask_stats(raw: bytes, width: int, height: int, backgrounds: list,
                tolerance: float) -> dict:
    """一次遍历算出主体像素的件数、外接框、重心和主轴。"""
    limit = tolerance * tolerance
    mid_x = width // 2
    mid_y = height // 2
    counts = [0, 0, 0, 0]
    total = 0
    sum_x = sum_y = 0
    sum_xx = sum_yy = sum_xy = 0
    x0, y0 = width, height
    x1, y1 = -1, -1
    base = 0
    for y in range(height):
        for x in range(width):
            if _is_background(raw, base, backgrounds, limit):
                base += 3
                continue
            total += 1
            sum_x += x
            sum_y += y
            sum_xx += x * x
            sum_yy += y * y
            sum_xy += x * y
            if x < x0:
                x0 = x
            if y < y0:
                y0 = y
            if x > x1:
                x1 = x
            if y > y1:
                y1 = y
            counts[(0 if x < mid_x else 1) + (0 if y < mid_y else 2)] += 1
            base += 3

    areas = [mid_x * mid_y,
             (width - mid_x) * mid_y,
             mid_x * (height - mid_y),
             (width - mid_x) * (height - mid_y)]
    ratios = [counts[item] / areas[item] if areas[item] else 0.0 for item in range(4)]
    if total == 0:
        return {
            "pixels": 0, "ratio": 0.0, "bbox": None, "centroid": None,
            "quadrants": [0.0, 0.0, 0.0, 0.0], "counts": counts,
        }

    mean_x = sum_x / total
    mean_y = sum_y / total
    sxx = sum_xx - total * mean_x * mean_x
    syy = sum_yy - total * mean_y * mean_y
    sxy = sum_xy - total * mean_x * mean_y
    if abs(sxx) < 1e-9 and abs(syy) < 1e-9 and abs(sxy) < 1e-9:
        angle = 0.0
    else:
        angle = math.degrees(0.5 * math.atan2(2 * sxy, sxx - syy))
    if angle <= -90.0:
        angle += 180.0
    if angle > 90.0:
        angle -= 180.0

    return {
        "pixels": total,
        "ratio": total / (width * height),
        "bbox": [x0, y0, x1, y1],
        "centroid": [round(mean_x, 2), round(mean_y, 2)],
        "quadrants": [round(ratio, 6) for ratio in ratios],
        "counts": counts,
        "spread": {
            "left_right": round(ratios[0] + ratios[2] - ratios[1] - ratios[3], 6),
            "top_bottom": round(ratios[0] + ratios[1] - ratios[2] - ratios[3], 6),
        },
        "covariance": {"xx": sxx, "yy": syy, "xy": sxy},
        "angle": round(angle, 2),
    }


def _axis_note(angle: float) -> str:
    size = abs(angle)
    if size <= 15:
        return "横向"
    if size >= 75:
        return "纵向"
    return "斜向"


def _nearest_line(value: float, size: float, ratios: list):
    best = None
    for ratio in ratios:
        line = ratio * size
        gap = abs(value - line)
        if best is None or gap < best[1]:
            best = (ratio, gap, line)
    return best


def _analyze_image(image, rules: dict) -> dict:
    width, height = image.size
    raw = image.tobytes()
    backgrounds = _backgrounds(raw, width, height, rules)
    stats = _mask_stats(raw, width, height, backgrounds,
                        float(rules["background_tolerance"]))

    margin = None
    center_offset = None
    if stats["bbox"]:
        x0, y0, x1, y1 = stats["bbox"]
        margin = {
            "left": x0,
            "right": width - 1 - x1,
            "top": y0,
            "bottom": height - 1 - y1,
        }
        margin["min"] = min(margin.values())
        margin["tight"] = margin["min"] <= float(rules["margin_warn"]) * min(width, height)

        cx, cy = stats["centroid"]
        golden = rules["golden"]
        line_x, gap_x, line_x_px = _nearest_line(cx, width, golden)
        line_y, gap_y, line_y_px = _nearest_line(cy, height, golden)
        warn = float(rules["offset_warn"])
        center_offset = {
            # 正号表示主体在线的左边（横向）或上边（纵向）
            "x": round(line_x_px - cx, 2),
            "y": round(line_y_px - cy, 2),
            "gap_x": round(gap_x, 2),
            "gap_y": round(gap_y, 2),
            "line_x": line_x,
            "line_y": line_y,
            "line_x_px": round(line_x_px, 2),
            "line_y_px": round(line_y_px, 2),
            "warn_x": gap_x > warn,
            "warn_y": gap_y > warn,
            "warn": warn,
        }

    issues = []
    if center_offset:
        if center_offset["warn_x"]:
            issues.append(
                "横向离最近黄金分割线 %.1f 像素，超过警戒线 %.0f"
                % (center_offset["gap_x"], center_offset["warn"]))
        if center_offset["warn_y"]:
            issues.append(
                "纵向离最近黄金分割线 %.1f 像素，超过警戒线 %.0f"
                % (center_offset["gap_y"], center_offset["warn"]))
    if margin and margin["tight"]:
        issues.append("主体离画布边缘最近只有 %d 像素，画面偏挤" % margin["min"])
    if not stats["pixels"]:
        issues.append("没有非背景像素，密度为 0")

    return {
        "image": {
            "path": "",
            "width": width,
            "height": height,
        },
        "rules": rules,
        "background": [list(color) for color in backgrounds],
        "subject": {
            "pixels": stats["pixels"],
            "ratio": round(stats["ratio"], 6),
            "bbox": stats["bbox"],
            "centroid": stats["centroid"],
        },
        "center_offset": center_offset,
        "density": {
            "quadrants": stats["quadrants"],
            "counts": stats["counts"],
            "left_right": stats["spread"]["left_right"] if stats["pixels"] else 0.0,
            "top_bottom": stats["spread"]["top_bottom"] if stats["pixels"] else 0.0,
            "overall": round(stats["ratio"], 6),
        },
        "axis_angle": stats["angle"] if stats["pixels"] else None,
        "axis_note": _axis_note(stats["angle"]) if stats["pixels"] else None,
        "margin": margin,
        "issues": issues,
    }


def analyze(png_path, rules: dict | None = None) -> dict:
    """量一张图：重心偏移、四象限密度、长轴、边距。

    rules 可以只写要改的项，例如 {"offset_warn": 40}。
    """
    Image, _, _ = _pil()
    path = Path(png_path)
    if not path.is_file():
        raise FileNotFoundError(f"找不到图片：{path}")
    merged = merge_rules(rules)
    with Image.open(path) as raw:
        image = raw.convert("RGB")
        result = _analyze_image(image, merged)
    result["image"]["path"] = str(path)
    return result


def _font(size: int):
    _, _, ImageFont = _pil()
    for candidate in FONT_PATHS:
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _dashed(draw, start, end, fill, dash=6, gap=4) -> None:
    length = math.dist(start, end)
    if length <= 0:
        return
    step = dash + gap
    distance = 0.0
    while distance < length:
        part = min(dash, length - distance)
        x1 = start[0] + (end[0] - start[0]) * distance / length
        y1 = start[1] + (end[1] - start[1]) * distance / length
        x2 = start[0] + (end[0] - start[0]) * (distance + part) / length
        y2 = start[1] + (end[1] - start[1]) * (distance + part) / length
        draw.line([(x1, y1), (x2, y2)], fill=fill, width=1)
        distance += step


def _draw_legend(draw, width: int, height: int, font, small) -> None:
    if width < 360 or height < 220:
        return
    box_w, box_h = 258, 100
    x1 = width - 12
    y0 = 12
    x0 = x1 - box_w
    draw.rounded_rectangle([x0, y0, x1, y0 + box_h], radius=6,
                           fill=(255, 255, 255, 232), outline=INK + (255,), width=1)
    draw.text((x0 + 10, y0 + 8), "构图网格", font=font, fill=INK + (255,))
    for index, (group, name) in enumerate(GROUPS):
        y = y0 + 34 + index * 20
        draw.line([(x0 + 12, y), (x0 + 36, y)], fill=GROUP_COLORS[group] + (255,), width=3)
        draw.text((x0 + 44, y - 7), name, font=small, fill=INK + (255,))


def draw_grid(png_path, out_path, rules: dict | None = None, result: dict | None = None) -> dict:
    """在原图上叠三套网格，标出主体重心和最近的交点。

    最近的黄金分割线加粗，再用虚线把重心连到线上，一眼能看出主体离
    哪条线最近。图例放在右上角，小图放不下就不画图例。
    """
    Image, ImageDraw, _ = _pil()
    path = Path(png_path)
    if not path.is_file():
        raise FileNotFoundError(f"找不到图片：{path}")
    merged = merge_rules(rules)
    with Image.open(path) as raw:
        image = raw.convert("RGB")
        data = result or _analyze_image(image, merged)

    width, height = image.size
    draw = ImageDraw.Draw(image, "RGBA")
    lines = grid_lines(width, height, merged)
    center_offset = data.get("center_offset") or {}

    for line in lines:
        nearest = ((line["kind"] == "vertical" and line["ratio"] == center_offset.get("line_x"))
                   or (line["kind"] == "horizontal" and line["ratio"] == center_offset.get("line_y")))
        weight = 3 if nearest else 1
        if line["kind"] == "vertical":
            draw.line([(line["pos"], 0), (line["pos"], height)],
                      fill=GROUP_COLORS[line["group"]] + (255,), width=weight)
        else:
            draw.line([(0, line["pos"]), (width, line["pos"])],
                      fill=GROUP_COLORS[line["group"]] + (255,), width=weight)

    subject = data.get("subject") or {}
    centroid = subject.get("centroid")
    if centroid:
        cx, cy = centroid
        if center_offset:
            _dashed(draw, (cx, cy), (center_offset["line_x_px"], cy), HIGHLIGHT + (230,))
            _dashed(draw, (cx, cy), (cx, center_offset["line_y_px"]), HIGHLIGHT + (230,))
            for point in ((center_offset["line_x_px"], cy), (cx, center_offset["line_y_px"])):
                draw.ellipse([point[0] - 3, point[1] - 3, point[0] + 3, point[1] + 3],
                             outline=HIGHLIGHT + (255,), width=2)

        verticals = [line["pos"] for line in lines if line["kind"] == "vertical"]
        horizontals = [line["pos"] for line in lines if line["kind"] == "horizontal"]
        if verticals and horizontals:
            best = min(((math.hypot(cx - vx, cy - hy), vx, hy)
                        for vx in verticals for hy in horizontals))
            draw.ellipse([best[1] - 8, best[2] - 8, best[1] + 8, best[2] + 8],
                         outline=HIGHLIGHT + (255,), width=2)

        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=CENTROID + (255,))
        draw.line([(cx - 12, cy), (cx + 12, cy)], fill=CENTROID + (255,), width=2)
        draw.line([(cx, cy - 12), (cx, cy + 12)], fill=CENTROID + (255,), width=2)

    _draw_legend(draw, width, height, _font(16), _font(13))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, "PNG")
    data["output"] = str(out)
    return data


def report(result: dict) -> str:
    image = result["image"]
    subject = result["subject"]
    lines = [
        "图 %dx%d | 背景 %d 色 | 主体像素 %d（%.1f%%）"
        % (image["width"], image["height"], len(result["background"]),
           subject["pixels"], subject["ratio"] * 100),
    ]
    if not subject["pixels"]:
        lines.append("主体是空的：整幅图都是背景，密度 0")
        return "\n".join(lines)

    lines.append("主体外接框 %s，重心 (%.1f, %.1f)"
                 % (subject["bbox"], subject["centroid"][0], subject["centroid"][1]))
    offset = result["center_offset"]
    lines.append(
        "重心偏移：横向 %+.1f 像素（最近黄金分割 %.3f，%s），"
        "纵向 %+.1f 像素（%.3f，%s），警戒线 %.0f"
        % (offset["x"], offset["line_x"],
           "偏右" if offset["x"] < 0 else "偏左",
           offset["y"], offset["line_y"],
           "偏下" if offset["y"] < 0 else "偏上",
           offset["warn"]))
    density = result["density"]
    quadrants = density["quadrants"]
    lines.append("疏密：左上 %.1f%% 右上 %.1f%% 左下 %.1f%% 右下 %.1f%% | 左右 %+.1f%% 上下 %+.1f%%"
                 % (quadrants[0] * 100, quadrants[1] * 100,
                    quadrants[2] * 100, quadrants[3] * 100,
                    density["left_right"] * 100, density["top_bottom"] * 100))
    lines.append("长轴：%.1f°，%s" % (result["axis_angle"], result["axis_note"]))
    margin = result["margin"]
    lines.append("边距：左 %d 右 %d 上 %d 下 %d，最小 %d"
                 % (margin["left"], margin["right"], margin["top"],
                    margin["bottom"], margin["min"]))
    if result["issues"]:
        lines.append("提示：")
        for text in result["issues"]:
            lines.append("  - " + text)
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="构图检查：网格、重心偏移、疏密、长轴、边距")
    parser.add_argument("image", help="要检查的 PNG 或 JPG")
    parser.add_argument("--out", help="覆盖图输出路径，默认 <原名>-layout.png")
    parser.add_argument("--no-draw", action="store_true", help="只出数字，不出覆盖图")
    parser.add_argument("--rules", help="规则 JSON，只写要改的项")
    parser.add_argument("--json", help="结构化结果输出路径")
    args = parser.parse_args(argv)

    rules = None
    if args.rules:
        try:
            rules = json.loads(args.rules)
        except json.JSONDecodeError as error:
            raise ValueError(f"--rules 不是合法 JSON：{error}") from error

    result = analyze(args.image, rules)
    print(report(result))
    if not args.no_draw:
        out = Path(args.out) if args.out else Path(args.image).with_name(
            Path(args.image).stem + "-layout.png")
        draw_grid(args.image, out, rules, result)
        print("覆盖图：%s" % out)
    if args.json:
        Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
        print("结构化结果：%s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
