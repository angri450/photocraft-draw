# -*- coding: utf-8 -*-
"""逐朵匹配布局评估：计划花位和成图上每一朵花对位。

整簇矩形交并比会把「花画大一点」的分数压低，也看不出是哪一朵偏了。
这里改成逐朵：从 Layout 草稿里取 caption 含 blossom 的框，在成图上做
粉色掩膜，先腐蚀 3 像素把贴在一起的花分开，再分连通域、按腐蚀量还原
包围盒；计划框和连通域按交并比从高到低一对一分配，一个连通域只归一朵
花。整簇交并比留作参考。

    python3 tools/eval_layout.py out/spray-layout.json imgs/spray_layout_seed42.png
    python3 tools/eval_layout.py out/spray-layout.json imgs/spray_layout_seed42.png --json out/eval.json

退出码：平均交并比低于 0.45，或匹配上的朵数不到计划数的八成，返回 1。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

# 连通域面积小于画面万分之五就丢掉，避免花蕊、花苞边缘的碎点算成一朵。
MIN_AREA_SHARE = 0.0005
# 单朵交并比达到这个值才算匹配上。
MATCH_IOU = 0.3
# 平均交并比低于这个值判不通过。
MEAN_IOU_MIN = 0.45
# 匹配上的朵数至少要占计划数的这个比例。
MATCH_SHARE_MIN = 0.8
# 默认腐蚀半径，用来把相邻花瓣贴在一起的花分开。相切的两块要 4 像素才分得开。
ERODE_RADIUS = 4


def planned_boxes(draft: dict, keyword: str = "blossom") -> list:
    """草稿里所有计划花位的框。"""
    boxes = [[float(value) for value in item["bbox"]]
             for item in draft.get("items") or []
             if keyword in str(item.get("caption", ""))]
    if not boxes:
        raise ValueError("布局里没有含 %s 的项" % keyword)
    return boxes


def planned_union(draft: dict, keyword: str = "blossom") -> list:
    """所有计划花位的并集，整簇交并比用。"""
    boxes = planned_boxes(draft, keyword)
    return [min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes)]


def iou(a, b) -> float:
    """矩形交并比。"""
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def pink_mask(image: np.ndarray) -> np.ndarray:
    """粉色花瓣的掩膜。和旧版用的阈值一致。"""
    r = image[:, :, 0]
    g = image[:, :, 1]
    b = image[:, :, 2]
    return (r > 150) & (r - g > 25) & (r - b > 15)


def erode(mask: np.ndarray, radius: int) -> np.ndarray:
    """方形结构元的腐蚀，radius 小于 1 时原样返回。"""
    if radius <= 0:
        return mask.copy()
    out = mask.copy()
    for step in range(1, radius + 1):
        out[step:, :] &= mask[:-step, :]
        out[:-step, :] &= mask[step:, :]
        out[:, step:] &= mask[:, :-step]
        out[:, :-step] &= mask[:, step:]
    return out


def components(mask: np.ndarray, min_area: int, restore: int = 0) -> list:
    """四邻域连通域，返回外接框、面积和重心。

    先按 restore 像素腐蚀，把贴在一起的花分开；标记完再把外接框向外
    扩 restore 像素还原。面积用还原后的框面积算。
    """
    height, width = mask.shape
    body = erode(mask, restore)
    seen = np.zeros((height, width), dtype=bool)
    rows, cols = np.nonzero(body)
    found = []
    for start_y, start_x in zip(rows.tolist(), cols.tolist()):
        if seen[start_y, start_x]:
            continue
        queue = deque([(start_y, start_x)])
        seen[start_y, start_x] = True
        min_x = max_x = start_x
        min_y = max_y = start_y
        count = 0
        sum_x = sum_y = 0
        while queue:
            y, x = queue.popleft()
            count += 1
            sum_x += x
            sum_y += y
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < height and 0 <= nx < width and body[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        box = [max(0, min_x - restore), max(0, min_y - restore),
               min(width, max_x + 1 + restore), min(height, max_y + 1 + restore)]
        area = (box[2] - box[0]) * (box[3] - box[1])
        if area >= min_area:
            found.append({
                "bbox": box,
                "area": area,
                "pixels": count,
                "centroid": [round(sum_x / count, 2), round(sum_y / count, 2)],
            })
    return found


def _size_note(ratio: float) -> str:
    if ratio >= 1.1:
        return "偏大"
    if ratio <= 0.9:
        return "偏小"
    return "接近"


def match_one_to_one(planned: list, blobs: list) -> dict:
    """按交并比从高到低贪心分配，一个连通域只归一朵花。"""
    pairs = []
    for plan_index, box in enumerate(planned):
        for blob_index, blob in enumerate(blobs):
            value = iou(box, blob["bbox"])
            if value > 0:
                pairs.append((value, plan_index, blob_index))
    pairs.sort(key=lambda item: (-item[0], item[1], item[2]))
    assigned = {}
    used = set()
    for value, plan_index, blob_index in pairs:
        if plan_index in assigned or blob_index in used:
            continue
        assigned[plan_index] = (value, blob_index)
        used.add(blob_index)
    return {"assigned": assigned, "used": used}


def evaluate(draft: dict, image_path, match_iou: float = MATCH_IOU,
             min_area_share: float = MIN_AREA_SHARE,
             erode_radius: int = ERODE_RADIUS) -> dict:
    """逐朵对位，返回表格和汇总。"""
    image = np.asarray(Image.open(image_path).convert("RGB"), dtype=int)
    height, width, _ = image.shape
    mask = pink_mask(image)
    min_area = max(1, int(round(min_area_share * width * height)))
    blobs = components(mask, min_area, restore=erode_radius)

    boxes = planned_boxes(draft)
    scale_x = width / float(draft.get("width") or width)
    scale_y = height / float(draft.get("height") or height)
    planned = [[box[0] * scale_x, box[1] * scale_y,
                box[2] * scale_x, box[3] * scale_y] for box in boxes]

    matching = match_one_to_one(planned, blobs)
    assigned = matching["assigned"]
    used = matching["used"]

    rows = []
    for index, box in enumerate(planned):
        plan_area = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
        pair = assigned.get(index)
        row = {
            "index": index + 1,
            "planned": [round(value, 1) for value in box],
            "actual": None,
            "iou": 0.0,
            "dx": None,
            "dy": None,
            "actual_area": 0,
            "area_ratio": None,
            "size": None,
            "matched": False,
        }
        if pair is not None:
            value, blob_index = pair
            blob = blobs[blob_index]
            ratio = blob["area"] / plan_area if plan_area > 0 else 0.0
            row["actual"] = blob["bbox"]
            row["iou"] = round(value, 4)
            row["dx"] = round(blob["centroid"][0] - (box[0] + box[2]) / 2, 1)
            row["dy"] = round(blob["centroid"][1] - (box[1] + box[3]) / 2, 1)
            row["actual_area"] = int(blob["area"])
            row["area_ratio"] = round(ratio, 3)
            row["size"] = _size_note(ratio)
            row["matched"] = value >= match_iou
        rows.append(row)

    ys, xs = np.nonzero(mask)
    actual_bbox = None
    if len(xs):
        actual_bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]

    union_planned = planned_union(draft)
    union_planned = [union_planned[0] * scale_x, union_planned[1] * scale_y,
                     union_planned[2] * scale_x, union_planned[3] * scale_y]
    cluster_iou = iou(union_planned, actual_bbox) if actual_bbox else 0.0

    matched = sum(1 for row in rows if row["matched"])
    mean_iou = sum(row["iou"] for row in rows) / len(rows) if rows else 0.0
    extras = [blobs[index] for index in range(len(blobs)) if index not in used]
    ok = bool(rows) and mean_iou >= MEAN_IOU_MIN and matched >= MATCH_SHARE_MIN * len(rows)

    ratios = [row["area_ratio"] for row in rows if row["area_ratio"] is not None]
    median_ratio = float(np.median(ratios)) if ratios else None
    deviations = [abs(1.0 - ratio) for ratio in ratios]
    median_deviation = float(np.median(deviations)) if deviations else None

    return {
        "image": str(image_path),
        "canvas": [width, height],
        "planned_count": len(rows),
        "rows": rows,
        "summary": {
            "mean_iou": round(mean_iou, 4),
            "matched": matched,
            "extras": len(extras),
            "cluster_iou": round(cluster_iou, 4),
            "pixel_share": round(float(mask.mean()), 6),
            "median_area_ratio": round(median_ratio, 3) if median_ratio is not None else None,
            "median_area_deviation": round(median_deviation, 3)
            if median_deviation is not None else None,
            "ok": bool(ok),
        },
        "extra_blobs": extras,
        "thresholds": {
            "match_iou": match_iou,
            "mean_iou_min": MEAN_IOU_MIN,
            "match_share_min": MATCH_SHARE_MIN,
            "min_area_share": min_area_share,
            "erode_radius": erode_radius,
        },
    }


def format_table(result: dict) -> str:
    rows = result["rows"]
    lines = ["序号  计划框                        实际框                        IoU    dx     dy     实际面积  面积比      匹配"]
    for row in rows:
        planned = "(%d, %d, %d, %d)" % tuple(int(value) for value in row["planned"])
        if row["actual"] is None:
            actual = "（没有连通域）"
            dx = dy = "  -  "
            area = "     -"
            ratio = "     -"
        else:
            actual = "(%d, %d, %d, %d)" % tuple(int(value) for value in row["actual"])
            dx = "%+.1f" % row["dx"]
            dy = "%+.1f" % row["dy"]
            area = "%6d" % row["actual_area"]
            ratio = "%.2f×%s" % (row["area_ratio"], row["size"])
        lines.append("%-4d  %-28s  %-28s  %.3f  %-5s  %-5s  %-8s  %-8s  %s"
                     % (row["index"], planned, actual, row["iou"], dx, dy,
                        area, ratio, "是" if row["matched"] else "否"))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="逐朵匹配布局评估")
    parser.add_argument("layout", help="Layout 草稿 JSON")
    parser.add_argument("image", help="成图")
    parser.add_argument("--json", help="结构化结果输出路径")
    parser.add_argument("--match-iou", type=float, default=MATCH_IOU,
                        help="单朵交并比达到多少算匹配，默认 %.2f" % MATCH_IOU)
    parser.add_argument("--min-area-share", type=float, default=MIN_AREA_SHARE,
                        help="连通域最小面积占画面的比例，默认 %.4f" % MIN_AREA_SHARE)
    parser.add_argument("--erode", type=int, default=ERODE_RADIUS,
                        help="腐蚀半径，默认 %d 像素" % ERODE_RADIUS)
    args = parser.parse_args(argv)

    try:
        draft = json.loads(Path(args.layout).read_text(encoding="utf-8"))
        result = evaluate(draft, args.image, args.match_iou, args.min_area_share, args.erode)
    except (FileNotFoundError, ValueError) as error:
        print("fail | %s" % error, file=sys.stderr)
        return 2

    print(format_table(result))
    summary = result["summary"]
    print("")
    print("平均交并比 %.3f | 匹配 %d/%d | 多余连通域 %d | 整簇交并比 %.3f | 面积比中位数 %s | 面积偏差中位数 %s | 花像素占比 %.1f%%"
          % (summary["mean_iou"], summary["matched"], result["planned_count"],
             summary["extras"], summary["cluster_iou"],
             "%.2f" % summary["median_area_ratio"] if summary["median_area_ratio"] is not None else "-",
             "%.2f" % summary["median_area_deviation"]
             if summary["median_area_deviation"] is not None else "-",
             summary["pixel_share"] * 100))
    print("判定：%s" % ("通过" if summary["ok"] else "不通过"))
    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("结构化结果：%s" % target)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
