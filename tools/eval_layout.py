# -*- coding: utf-8 -*-
"""量一张成图和计划布局的贴合度：花簇矩形交并比、重心偏移、面积占比。

    python3 tools/eval_layout.py out/spray-layout.json imgs/spray_moss_layout.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def planned_union(draft, keyword="blossom"):
    boxes = [item["bbox"] for item in draft["items"] if keyword in item["caption"]]
    if not boxes:
        raise SystemExit("布局里没有含 %s 的项" % keyword)
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def iou(a, b):
    x0 = max(a[0], b[0]); y0 = max(a[1], b[1])
    x1 = min(a[2], b[2]); y1 = min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="量成图和计划布局的贴合度")
    parser.add_argument("layout")
    parser.add_argument("image")
    args = parser.parse_args(argv)

    draft = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    image = np.asarray(Image.open(args.image).convert("RGB"), dtype=int)
    h, w, _ = image.shape
    r, g, b = image[:, :, 0], image[:, :, 1], image[:, :, 2]
    mask = (r > 150) & (r - g > 25) & (r - b > 15)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        print("没有找到花的像素")
        return 1
    actual = [xs.min(), ys.min(), xs.max(), ys.max()]
    planned = planned_union(draft)
    scale_x = w / draft["width"]
    scale_y = h / draft["height"]
    planned = [planned[0] * scale_x, planned[1] * scale_y,
               planned[2] * scale_x, planned[3] * scale_y]
    print("花簇矩形交并比 %.3f" % iou(actual, planned))
    print("计划框 %s" % [round(v) for v in planned])
    print("实际框 %s" % [round(v) for v in actual])
    print("重心 计划 (%.0f, %.0f) 实际 (%.0f, %.0f)" % (
        (planned[0] + planned[2]) / 2, (planned[1] + planned[3]) / 2,
        (actual[0] + actual[2]) / 2, (actual[1] + actual[3]) / 2))
    print("花像素占比 %.1f%%" % (100.0 * mask.sum() / (w * h)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
