# -*- coding: utf-8 -*-
"""立体关系与三维坐标：从分层文件反算每一层的深度和空间坐标。

遮挡分析给出谁压谁，接触分析给出压在哪里。这一层把层序翻译成深度，
按引擎的投影斜度反算出每个部件的三维坐标：把这张图按同一套斜度重新
投影一次，位置和原来的画面一致。

z 的约定和引擎里的三维组件一致：z 越大离观众越远，投影时横向偏移
z 乘 skew_x，纵向偏移 z 乘 skew_y。层序里越靠前的层 z 越小。

用法：
    photocraft-draw depth out/a.psd --json out/depth.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .engine import find_engine

SKEW_X = 0.45
SKEW_Y = 0.28


def _tree(psd_path: Path) -> dict:
    cli = find_engine()
    result = subprocess.run([str(cli), "info", str(psd_path)],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def _bounds(node: dict):
    bounds = node.get("bounds")
    if bounds:
        return [int(value) for value in bounds]
    boxes = [_bounds(child) for child in node.get("children") or []]
    boxes = [box for box in boxes if box]
    if not boxes:
        return None
    x0 = min(box[0] for box in boxes)
    y0 = min(box[1] for box in boxes)
    x1 = max(box[0] + box[2] for box in boxes)
    y1 = max(box[1] + box[3] for box in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


def _center(box):
    return round(box[0] + box[2] / 2, 1), round(box[1] + box[3] / 2, 1)


def _walk(node: dict, depth: int, out: list) -> None:
    for child in node.get("children") or []:
        out.append({
            "name": child.get("name") or child.get("kind") or "未命名",
            "kind": child.get("kind") or "",
            "depth": depth,
            "bounds": _bounds(child),
        })
        _walk(child, depth + 1, out)


def analyze_depth(psd_path: Path, unit: float = 1.0, skew_x: float = SKEW_X,
                  skew_y: float = SKEW_Y, ref_width: float | None = None) -> dict:
    """把分层文件翻译成深度表和三维坐标表。"""
    psd_path = Path(psd_path).resolve()
    data = _tree(psd_path)
    width = int(data.get("width") or 0)
    height = int(data.get("height") or 0)
    tops = list(data.get("layers") or [])
    ref = float(ref_width or width) or float(width)
    scale = ref / width if width else 1.0

    layers = []
    parts = []
    count = len(tops)
    for index, node in enumerate(tops):
        name = node.get("name") or node.get("kind") or "未命名"
        z = round(index * unit, 4)
        box = _bounds(node)
        row = {"index": index, "name": name, "z": z, "bounds": box}
        if box:
            cx, cy = _center(box)
            row["center"] = [cx, cy]
            row["xyz"] = [round(cx * scale - z * skew_x, 2),
                          round(cy * scale + z * skew_y, 2), z]
        layers.append(row)
        children = []
        _walk(node, 1, children)
        for child in children:
            if not child["bounds"]:
                continue
            cx, cy = _center(child["bounds"])
            parts.append({
                "layer": name,
                "name": child["name"],
                "z": z,
                "bounds": child["bounds"],
                "xyz": [round(cx * scale - z * skew_x, 2),
                        round(cy * scale + z * skew_y, 2), z],
            })

    return {"canvas": [width, height], "ref_width": ref, "unit": unit,
            "skew_x": skew_x, "skew_y": skew_y,
            "layers": layers, "parts": parts}


def public(result: dict) -> dict:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def _span(box):
    x0, y0, w, h = box
    return f"{x0},{y0} 到 {x0 + w - 1},{y0 + h - 1}"


def report_depth(result: dict) -> str:
    lines = [f"画布 {result['canvas'][0]}x{result['canvas'][1]} | "
             f"{len(result['layers'])} 层"]
    lines.append(f"深度单位 {result['unit']}，z 越大离观众越远；"
                 f"投影斜度 skew_x {result['skew_x']}、skew_y {result['skew_y']}")
    lines.append(f"参考画布宽 {result['ref_width']:.0f}，"
                 "三维坐标按这套斜度反算，重新投影一次位置不变")
    lines.append("坐标单位是参考像素，参考宽和画布宽不同时两者按比例换算；"
                 "同一层里的子部件和所在层同深度")

    lines.append("")
    lines.append("层深表（从后到前）：")
    for row in reversed(result["layers"]):
        xyz = row.get("xyz")
        where = f"范围 {_span(row['bounds'])}" if row.get("bounds") else "没有内容"
        point = f"三维坐标 ({xyz[0]}, {xyz[1]}, {xyz[2]})" if xyz else "没有坐标"
        lines.append(f"  z {row['z']:5.2f}  {row['name']:<26} {where}  {point}")

    lines.append("")
    lines.append("相邻两层的深度差与画面偏移：")
    layers = result["layers"]
    scale = result["ref_width"] / result["canvas"][0] if result["canvas"][0] else 1.0
    for index in range(1, len(layers)):
        front, back = layers[index - 1], layers[index]
        dz = back["z"] - front["z"]
        lines.append(f"  {front['name']} 比 {back['name']} 近 {dz:.2f} 层，"
                     f"同一世界坐标下 {back['name']} 在画面上偏右 "
                     f"{dz * result['skew_x'] / scale:.2f}、偏上 "
                     f"{dz * result['skew_y'] / scale:.2f}，单位画布像素")

    if result["parts"]:
        lines.append("")
        lines.append("每个部件的三维坐标（按层内形状拆开）：")
        for part in result["parts"]:
            xyz = part["xyz"]
            lines.append(f"  z {part['z']:5.2f}  {part['name']:<26} "
                         f"层 {part['layer']:<26} 范围 {_span(part['bounds'])}  "
                         f"三维坐标 ({xyz[0]}, {xyz[1]}, {xyz[2]})")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="反算分层文件的立体关系与三维坐标")
    parser.add_argument("psd")
    parser.add_argument("--unit", type=float, default=1.0, help="每层深度差，默认 1.0")
    parser.add_argument("--skew-x", type=float, default=SKEW_X, help="深度到横向偏移")
    parser.add_argument("--skew-y", type=float, default=SKEW_Y, help="深度到纵向偏移")
    parser.add_argument("--ref-width", type=float, help="参考画布宽度，默认跟画布同宽")
    parser.add_argument("--json", help="结构化结果输出路径")
    args = parser.parse_args(argv)
    result = analyze_depth(Path(args.psd), unit=args.unit, skew_x=args.skew_x,
                            skew_y=args.skew_y, ref_width=args.ref_width)
    print(report_depth(result))
    if args.json:
        Path(args.json).write_text(json.dumps(public(result), ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
