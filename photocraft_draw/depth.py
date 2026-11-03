# -*- coding: utf-8 -*-
"""立体关系与三维坐标：从分层文件反算每一层的深度和空间坐标。

遮挡分析给出谁压谁，接触分析给出压在哪里。这一层把层序翻译成深度，
按引擎的投影斜度反算出每个部件的三维坐标：把这张图按同一套斜度重新
投影一次，位置和原来的画面一致。

z 的约定和引擎里的三维组件一致：z 越大离观众越远，投影时横向偏移
z 乘 skew_x，纵向偏移 z 乘 skew_y。层序里越靠前的层 z 越小。

用法：
    photocraft-draw depth out/a.psd --json out/depth.json
    photocraft-draw depth out/a.psd --plan plans/a.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .engine import find_engine

SKEW_X = 0.45
SKEW_Y = 0.28


def declared_depths(plan: dict) -> dict:
    """方案里每层声明的 depth，层名对数值。"""
    out = {}
    for layer in plan.get("layers") or []:
        if not isinstance(layer, dict) or "depth" not in layer:
            continue
        out[str(layer.get("name", ""))] = float(layer["depth"])
    return out


def depth_values(names: list, declared: dict, unit: float) -> list:
    """按成品里的前后顺序给每层算 z。

    方案声明过的层用声明值乘 unit；没声明过的层（底色、文字层）按前后邻居
    插值，位置和前后顺序都不变。
    """
    known = [declared.get(name) for name in names]
    values = []
    for index in range(len(names)):
        if known[index] is not None:
            values.append(known[index] * unit)
            continue
        front = None
        for j in range(index - 1, -1, -1):
            if known[j] is not None:
                front = known[j] * unit
                break
        back = None
        for j in range(index + 1, len(names)):
            if known[j] is not None:
                back = known[j] * unit
                break
        if front is None and back is None:
            values.append(0.0)
        elif front is None:
            values.append(back - unit)
        elif back is None:
            values.append(front + unit)
        else:
            values.append((front + back) / 2)
    return values


def depth_conflicts(names: list, declared: dict) -> list:
    """成品层序和方案声明对不上的地方。

    从前到后的层，depth 应该越来越大：前面那层如果声明得更远，就是对不上。
    """
    out = []
    for i in range(len(names)):
        first = names[i]
        if first not in declared:
            continue
        for j in range(i + 1, len(names)):
            second = names[j]
            if second not in declared:
                continue
            if declared[first] > declared[second]:
                out.append({
                    "front": first,
                    "back": second,
                    "front_depth": declared[first],
                    "back_depth": declared[second],
                })
    return out


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
                  skew_y: float = SKEW_Y, ref_width: float | None = None,
                  plan: dict | None = None) -> dict:
    """把分层文件翻译成深度表和三维坐标表。

    给了方案就用方案里声明的 depth 算 z，再核对成品层序和声明对不对得上。
    """
    psd_path = Path(psd_path).resolve()
    data = _tree(psd_path)
    width = int(data.get("width") or 0)
    height = int(data.get("height") or 0)
    tops = list(data.get("layers") or [])
    ref = float(ref_width or width) or float(width)
    scale = ref / width if width else 1.0

    declared = declared_depths(plan) if plan else {}
    names = [node.get("name") or node.get("kind") or "未命名" for node in tops]
    if declared:
        zs = [round(value, 4) for value in depth_values(names, declared, unit)]
    else:
        zs = [round(index * unit, 4) for index in range(len(tops))]
    conflicts = depth_conflicts(names, declared) if declared else []
    missing = [name for name in declared if name not in set(names)]

    layers = []
    parts = []
    count = len(tops)
    for index, node in enumerate(tops):
        name = names[index]
        z = zs[index]
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
            "declared": declared, "conflicts": conflicts, "missing": missing,
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
    if result.get("declared"):
        lines.append("深度取自方案里声明的 depth")
    else:
        lines.append("深度按成品层序推，每层差 1")
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
        if dz <= 0:
            lines.append(f"  {front['name']} 和 {back['name']} 的深度差是 {dz:.2f}，"
                         f"方案声明和成品层序对不上")
            continue
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

    if result.get("declared"):
        lines.append("")
        lines.append("方案声明和成品层序的对照：")
        for row in result["layers"]:
            name = row["name"]
            if name in result["declared"]:
                lines.append(f"  {name:<26} 声明 depth {result['declared'][name]:>5.2f}"
                             f"，成品 z {row['z']:>5.2f}")
            else:
                lines.append(f"  {name:<26} 方案里没有这一层，z 按前后位置算 {row['z']:.2f}")
        if result.get("conflicts"):
            lines.append("  对不上的地方：")
            for item in result["conflicts"]:
                lines.append(f"    {item['front']} 声明 depth {item['front_depth']:.2f}，"
                             f"{item['back']} 声明 depth {item['back_depth']:.2f}，"
                             f"成品里 {item['front']} 压在 {item['back']} 前面")
        else:
            lines.append("  方案声明和成品层序一致")
        if result.get("missing"):
            lines.append("  方案里有但成品里没有：" + "、".join(result["missing"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="反算分层文件的立体关系与三维坐标")
    parser.add_argument("psd")
    parser.add_argument("--plan", help="绘制方案文件，取方案里声明的 depth")
    parser.add_argument("--unit", type=float, default=1.0, help="每层深度差，默认 1.0")
    parser.add_argument("--skew-x", type=float, default=SKEW_X, help="深度到横向偏移")
    parser.add_argument("--skew-y", type=float, default=SKEW_Y, help="深度到纵向偏移")
    parser.add_argument("--ref-width", type=float, help="参考画布宽度，默认跟画布同宽")
    parser.add_argument("--json", help="结构化结果输出路径")
    args = parser.parse_args(argv)
    plan = None
    if args.plan:
        from .plan import load_plan
        plan = load_plan(args.plan)
    result = analyze_depth(Path(args.psd), unit=args.unit, skew_x=args.skew_x,
                            skew_y=args.skew_y, ref_width=args.ref_width, plan=plan)
    print(report_depth(result))
    if args.json:
        Path(args.json).write_text(json.dumps(public(result), ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
