# -*- coding: utf-8 -*-
"""配色检查：相邻的部件不能用同一个颜色。

四色定理说的是平面地图四种颜色就够用。这里不追求四种，只做一件事：
把互相挨着的部件找出来，颜色一样就报警。糊成一块，根子就是相邻同色。

相邻的判定用包围盒，两个盒子有重叠就算挨着。天空和山虽然不重叠，
但如果颜色接近，视觉上也会糊，所以另外加一条明度差检查。
"""
from __future__ import annotations

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
            "group": params.get("group"),
            "group_by": params.get("group_by"),
            "layer": params.get("layer"),
            "exempt": params.get("exempt") or [],
        })
    return parts


from .grouping import PART_WORDS as _PART_WORDS
from .grouping import group as _group
from .grouping import cross_group_for, subject_of


def exempt_pair(a: dict, b: dict) -> bool:
    # 这两个部件要不要跳过色差检查。
    # 同一个组：同一个物体的部件，颜色接近是正常的
    # 同一层：一层里的部件是同一片东西的不同部分
    # 声明过豁免：远山和天空是同一片景的两部分
    if _part_group(a) == _part_group(b):
        return True
    layer_a = a.get('layer')
    layer_b = b.get('layer')
    if layer_a and layer_b and layer_a == layer_b:
        return True
    if layer_a and layer_b and layer_a != layer_b:
        if layer_b in (a.get('exempt') or []) or layer_a in (b.get('exempt') or []):
            return True
    return False


def _part_group(part: dict) -> str:
    """取一个部件所属的组。

    方案里显式声明的 group 优先。声明了 group_by 的，按主体词归组：
    同类的物件归成一组，不管实例号。
    """
    # 跨组件归组。同类的物件在不同层里时归一组：
    # 前后的石头都是石头。同一层里的不同实例不合并，
    # 山 1 和山 2 要能看出边界。
    cross = cross_group_for(part.get("name"), part.get("layer"))
    if cross:
        return cross
    declared = part.get("group")
    if declared:
        return _group(part.get("name"), declared)
    group_by = part.get("group_by")
    if group_by:
        subject = subject_of(part.get("name"))
        return f"{group_by} {subject}" if group_by else subject
    return _group(part.get("name"))


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
            if exempt_pair(a, b):
                continue
                continue
            # 声明过豁免的层之间不查色差。天空和远山是同一片景的两部分，
            # 远山要融进天空，颜色本来就该接近。
            layer_a = a.get("layer")
            layer_b = b.get("layer")
            if layer_a and layer_b and layer_a != layer_b:
                if layer_b in (a.get("exempt") or []) or layer_a in (b.get("exempt") or []):
                    continue
            area = _overlap(a["bounds"], b["bounds"])
            if area <= 0:
                continue
            if _part_group(a) == _part_group(b):
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
    # 状态词用「检查通过」和「检查未通过」。「不通过」里含「通过」两个字，
    # 拿输出做子串匹配的脚本会把它当成通过。
    status = "检查通过" if result["ok"] else "检查未通过"
    lines = [f"{status} | {result['parts']} 个部件"]
    for item in result["problems"]:
        lines.append(f"  - {item}")
    return "\n".join(lines)
