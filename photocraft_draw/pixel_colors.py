# -*- coding: utf-8 -*-
"""按真实接触判定相邻的配色检查。

原有的 colors 检查靠包围盒重叠来判相邻。两个部件的包围盒相交，
不一定意味着它们在画面上挨着。天空横贯整个画布，包围盒和任何东西
都相交，可它跟草坡之间隔着两层山和一条河。

这里按形状本身判断。绘制指令里存着完整的路径，把贝塞尔曲线离散成
多边形，再算两个形状有没有真的交叠。交叠才算挨着。

这样既准又快：不用出图，也不���渲染几百遍。

用法：
    photocraft-draw colors plans/a.json --pixel
"""
from __future__ import annotations

from .colorize import _distance, exempt_pair
from .geometry import adjacent_by_geometry
from .grouping import group as _group


def check_colors_touching(commands: list[dict], parts: list[dict], palette=None,
                          min_gap: float = 0.12) -> dict:
    """按形状交叠检查配色冲突。

    commands 是绘制指令，parts 每项：{name, bounds, color, group}。
    """
    from .palette import resolve_palette

    palette = palette or resolve_palette(None)

    groups = {}
    for command in commands:
        if command.get("command") != "shape.create":
            continue
        params = command.get("params") or {}
        name = params.get("name")
        if not name:
            continue
        groups[name] = _group(name, params.get("group"))

    touching = adjacent_by_geometry(commands, groups)

    def part_of(name):
        for part in parts:
            if part.get("name") == name:
                return part
        return None

    def hex_of(part):
        color = part.get("color") or "mid"
        if str(color).startswith("#"):
            return color
        return palette.get(color, color)

    problems = []
    contacts = []
    for first, second in touching:
        a = part_of(first)
        b = part_of(second)
        if a is None or b is None:
            continue
        if exempt_pair(a, b):
            continue
        gap = _distance(hex_of(a), hex_of(b))
        contacts.append({
            "upper": first,
            "lower": second,
            "pixels": None,
            "gap": round(gap, 3),
        })
        if hex_of(a).lower() == hex_of(b).lower():
            problems.append(
                f"{first} 和 {second} 挨在一起，颜色都是 {hex_of(a)}，会糊成一块"
            )
        elif gap < min_gap:
            problems.append(
                f"{first} 和 {second} 挨在一起，颜色只差 {gap:.3f}，边界不清"
            )

    return {
        "ok": not problems,
        "parts": len(parts),
        "problems": problems,
        "contacts": contacts,
    }


def report(result: dict) -> str:
    # 状态词用「检查通过」和「检查未通过」，避免子串匹配误判
    status = "检查通过" if result["ok"] else "检查未通过"
    lines = [f"{status} | {result['parts']} 个部件"]
    for item in result["problems"]:
        lines.append(f"  - {item}")
    contacts = result.get("contacts") or []
    if contacts:
        lines.append(f"真实接触 {len(contacts)} 处")
        for item in sorted(contacts, key=lambda x: x["gap"])[:8]:
            lines.append(
                f"  {item['upper']} 和 {item['lower']}：色差 {item['gap']:.3f}"
            )
    return "\n".join(lines)
