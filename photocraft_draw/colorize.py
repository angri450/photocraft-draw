# -*- coding: utf-8 -*-
"""配色检查：相邻的部件不能用同一个颜色。

四色定理说的是平面地图四种颜色就够用。这里不追求四种，只做一件事：
把互相挨着的部件找出来，颜色一样就报警。糊成一块，根子就是相邻同色。

相邻的判定用包围盒，两个盒子有重叠就算挨着。天空和山虽然不重叠，
但如果颜色接近，视觉上也会糊，所以另外加一条明度差检查。
"""
from __future__ import annotations

import re

from .palette import resolve_palette
from .checker import parts_of


def _rgb(hex_color: str):
    text = str(hex_color).lstrip("#")
    if len(text) != 6:
        return (0.5, 0.5, 0.5)
    return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _distance(first: str, second: str) -> float:
    """两个颜色在 RGB 空间里的距离，0 到 1。"""
    a, b = _rgb(first), _rgb(second)
    return (sum((x - y) ** 2 for x, y in zip(a, b)) / 3) ** 0.5


def _overlap(a, b) -> float:
    """两个盒子的重叠面积，没有重叠返回 0。"""
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[0] + a[2], b[0] + b[2])
    y2 = min(a[1] + a[3], b[1] + b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return (x2 - x1) * (y2 - y1)


def parts_from_commands(commands) -> list[dict]:
    """从绘制指令里取部件名、包围盒和填充色。"""
    parts = []
    for command in commands:
        if command.get("command") != "shape.create":
            continue
        params = command.get("params") or {}
        box = parts_of([command])
        if not box:
            continue
        item = box[0]
        x1, y1, x2, y2 = item["bbox"]
        parts.append({
            "name": item["name"],
            "bounds": [x1, y1, x2 - x1, y2 - y1],
            "color": params.get("fill") or "mid",
        })
    return parts


_PART_WORDS = ("脚", "腰", "顶", "雪尖", "雪", "左脊", "右脊", "亮边")


def _group(name: str) -> str:
    """把同一个物体的部件归成一组。

    天空 1 到天空 24 是同一片渐变；山 1 的脚、腰、顶是同一座山。
    同组内部颜色接近是正常的，不该报冲突。
    """
    text = str(name).strip()
    text = re.sub(r"[\s\-\d]+$", "", text).strip()
    for word in _PART_WORDS:
        if text.endswith(word):
            text = text[: -len(word)].strip()
            break
    text = re.sub(r"[\s\-\d]+$", "", text).strip()
    return text


def check_colors(parts, palette=None, min_gap: float = 0.12) -> dict:
    """检查相邻部件的颜色冲突。

    parts 每项：{name, bounds: [x, y, 宽, 高], color: 角色名或 #rrggbb}
    """
    palette = palette or resolve_palette(None)
    problems = []
    resolved = []
    for part in parts:
        color = part.get("color") or "mid"
        hex_value = palette.get(color, color) if not str(color).startswith("#") else color
        resolved.append({**part, "hex": hex_value})

    for i in range(len(resolved)):
        for j in range(i + 1, len(resolved)):
            a, b = resolved[i], resolved[j]
            area = _overlap(a["bounds"], b["bounds"])
            if area <= 0:
                continue
            if _group(a["name"]) == _group(b["name"]):
                continue
            if a["hex"].lower() == b["hex"].lower():
                problems.append(
                    f"{a['name']} 和 {b['name']} 挨在一起，颜色都是 {a['hex']}，会糊成一块"
                )
            else:
                gap = _distance(a["hex"], b["hex"])
                if gap < min_gap:
                    problems.append(
                        f"{a['name']} 和 {b['name']} 挨在一起，颜色只差 {gap:.3f}，边界不清"
                    )

    return {
        "ok": not problems,
        "parts": len(resolved),
        "problems": problems,
        "colors": [{"name": item["name"], "hex": item["hex"]} for item in resolved],
    }


def report(result: dict) -> str:
    status = "通过" if result["ok"] else "不通过"
    lines = [f"{status} | {result['parts']} 个部件"]
    for item in result["problems"]:
        lines.append(f"  - {item}")
    return "\n".join(lines)
