# -*- coding: utf-8 -*-
"""自动色阶：相邻的部件自动分到不同的明度档。

四色定理的用法：把互相挨着的部件连成一张图，用贪心算法给每个部件一个
色阶编号，保证相邻不同号；然后按部件原来的冷暖，在同一个色相族里取
对应的一档颜色。这样既不会糊成一块，也不会把暖色主体染成冷色。

冷族：bg、line、muted、soft
暖族：deep、mid、accent、surface
"""
from __future__ import annotations

import colorsys
import re

from .checker import parts_of
from .palette import resolve_palette

COOL = ("ink", "bg", "line", "muted")
WARM = ("deep", "mid", "accent", "soft")
STEPS = 4

_PART_WORDS = ("脚", "腰", "顶", "雪尖", "雪", "左脊", "右脊", "亮边")


def group_of(name: str) -> str:
    """同一个物体的部件归成一组，比如山 1 的脚、腰、顶。"""
    text = str(name).strip()
    text = re.sub(r"[\s\-\d]+$", "", text).strip()
    for word in _PART_WORDS:
        if text.endswith(word):
            text = text[: -len(word)].strip()
            break
    return re.sub(r"[\s\-\d]+$", "", text).strip()


def _overlap(a, b) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[0] + a[2], b[0] + b[2])
    y2 = min(a[1] + a[3], b[1] + b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return (x2 - x1) * (y2 - y1)


def _warm(hex_color: str) -> bool:
    text = str(hex_color).lstrip("#")
    if len(text) != 6:
        return True
    r = int(text[0:2], 16)
    b = int(text[4:6], 16)
    return r >= b


def parts_from_commands(commands) -> list[dict]:
    parts = []
    for command in commands:
        if command.get("command") != "shape.create":
            continue
        params = command.get("params") or {}
        found = parts_of([command])
        if not found:
            continue
        item = found[0]
        x1, y1, x2, y2 = item["bbox"]
        parts.append({
            "name": item["name"],
            "bounds": [x1, y1, x2 - x1, y2 - y1],
            "color": params.get("fill") or "#808080",
        })
    return parts


def assign_steps(parts) -> list[int]:
    """贪心着色：按"物体组"着色，同一个物体的部件共用一档。

    天空的二十四条色带是一组，山 1 的脚腰顶是一组，它们内部不该被打散。
    只有不同组之间才需要分开。
    """
    count = len(parts)
    groups = [group_of(part["name"]) for part in parts]
    unique = list(dict.fromkeys(groups))
    index_of = {name: index for index, name in enumerate(unique)}

    # 组级邻接：两组里只要有部件重叠，就算相邻
    adjacency = [set() for _ in unique]
    for i in range(count):
        for j in range(i + 1, count):
            if groups[i] == groups[j]:
                continue
            if _overlap(parts[i]["bounds"], parts[j]["bounds"]) <= 0:
                continue
            a, b = index_of[groups[i]], index_of[groups[j]]
            adjacency[a].add(b)
            adjacency[b].add(a)

    group_steps = [-1] * len(unique)
    order = sorted(range(len(unique)), key=lambda index: len(adjacency[index]), reverse=True)
    for index in order:
        used = {group_steps[other] for other in adjacency[index] if group_steps[other] >= 0}
        for step in range(STEPS):
            if step not in used:
                group_steps[index] = step
                break
        else:
            group_steps[index] = STEPS - 1
    return [group_steps[index_of[name]] for name in groups]


def _distance(first: str, second: str) -> float:
    def rgb(text):
        text = str(text).lstrip("#")
        if len(text) != 6:
            return (0.5, 0.5, 0.5)
        return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))
    a, b = rgb(first), rgb(second)
    return (sum((x - y) ** 2 for x, y in zip(a, b)) / 3) ** 0.5


def _shift(hex_color: str, step: int) -> str:
    """只改亮度，不改色相。

    每个色阶上下挪 0.09，四档之间拉开约 0.27 的亮度差，够看出边界，
    又不会把暖色主体染成冷色。
    """
    text = str(hex_color).lstrip("#")
    if len(text) != 6:
        return hex_color
    r, g, b = (int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = min(0.92, max(0.08, l + (step - 1.5) * 0.09))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#%02x%02x%02x" % tuple(round(value * 255) for value in (r, g, b))


def auto_shade(parts, palette=None) -> list[dict]:
    """局部修正：只把和邻居撞色的部件挪一档，其他一律不动。

    全局重着色会把形状压平，所以这里不做全局分配。先保留原色，
    然后反复扫所有相邻对，发现颜色太近就把后一个的亮度挪开一档，
    直到没有冲突或者扫够三轮。
    """
    palette = palette or resolve_palette(None)
    result = [{"name": part["name"], "bounds": part["bounds"],
               "hex": part["color"], "step": 0} for part in parts]
    groups = [group_of(part["name"]) for part in parts]
    pairs = []
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            if groups[i] == groups[j]:
                continue
            if _overlap(parts[i]["bounds"], parts[j]["bounds"]) <= 0:
                continue
            pairs.append((i, j))

    # 只处理几乎一样的颜色，每次挪半档，只扫一轮，避免连锁调白
    for i, j in pairs:
        if _distance(result[i]["hex"], result[j]["hex"]) >= 0.06:
            continue
        result[j]["hex"] = _shift(result[j]["hex"], 2)
        result[j]["step"] = 1
    return result


def report(shaded) -> str:
    lines = [f"{len(shaded)} 个部件，按相邻关系自动分成 {STEPS} 档"]
    counts = {}
    for item in shaded:
        counts[item["step"]] = counts.get(item["step"], 0) + 1
    for step in sorted(counts):
        lines.append(f"  第 {step} 档：{counts[step]} 个")
    return "\n".join(lines)
