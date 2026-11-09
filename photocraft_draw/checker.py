# -*- coding: utf-8 -*-
"""出图前的检查：不出图，只看指令，把结构问题挑出来。

每次改完都出图看一眼，既慢又费上下文。这里把判断写成规则：部件齐不齐、
有没有画出画布、关键部件在不在该在的位置。检查器读的是绘制指令，和出图
用的是同一份数据，所以它说没问题，图上就不会有结构错误。

用法：
    from photocraft_draw.checker import check_commands
    report = check_commands(commands, canvas=(900, 1200), expect="person")
"""
from __future__ import annotations

# 预期部件：名字里包含这些关键词，就算这一项存在
EXPECT = {
    "person": {
        "头部": ("头",),
        "躯干": ("躯干",),
        "左臂": ("左臂",),
        "右臂": ("右臂",),
        "左腿": ("左腿",),
        "右腿": ("右腿",),
    },
    "horse": {
        "头": ("头",),
        "颈": ("颈下段", "颈上段"),
        "躯干": ("躯干",),
        "臀": ("臀",),
        "胸": ("胸",),
        "四条腿": ("腿 fl", "腿 fr", "腿 bl", "腿 br"),
        "尾巴": ("尾 1",),
    },
}


def _bbox(params: dict):
    """从一条绘制指令里取包围盒。"""
    kind = params.get("kind")
    if kind == "line":
        x1, y1 = params.get("from") or (0, 0)
        x2, y2 = params.get("to") or (0, 0)
        return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
    if kind == "path":
        points = []
        for sub in (params.get("path") or {}).get("subpaths") or []:
            for knot in sub.get("knots") or []:
                anchor = knot.get("anchor") if isinstance(knot, dict) else knot
                if isinstance(anchor, (list, tuple)) and len(anchor) == 2:
                    points.append(anchor)
        if not points:
            return None
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return [min(xs), min(ys), max(xs), max(ys)]
    rect = params.get("rect")
    if isinstance(rect, (list, tuple)) and len(rect) == 4:
        x, y, w, h = rect
        return [x, y, x + w, y + h]
    return None


def parts_of(commands) -> list[dict]:
    """把绘制指令整理成部件表：名字、包围盒、形状类型。"""
    parts = []
    for command in commands:
        if command.get("command") != "shape.create":
            continue
        params = command.get("params") or {}
        box = _bbox(params)
        if box is None:
            continue
        parts.append({
            "name": str(params.get("name") or params.get("kind") or "未命名"),
            "kind": params.get("kind"),
            "bbox": box,
            "w": box[2] - box[0],
            "h": box[3] - box[1],
        })
    return parts


def _center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _find(parts, keywords):
    for part in parts:
        if any(key in part["name"] for key in keywords):
            return part
    return None


def check_commands(commands, canvas, expect=None) -> dict:
    """检查一批绘制指令，返回问题和统计。"""
    width, height = canvas
    parts = parts_of(commands)
    problems = []

    if not parts:
        return {"ok": False, "parts": 0, "problems": ["没有任何形状指令"], "detail": []}

    # 出画
    for part in parts:
        x1, y1, x2, y2 = part["bbox"]
        if x1 < -1 or y1 < -1 or x2 > width + 1 or y2 > height + 1:
            problems.append(f"{part['name']} 超出画布：{part['bbox']}，画布 {width}x{height}")

    # 部件齐全和相对位置
    table = EXPECT.get(expect) if expect else None
    if table:
        found = {}
        for label, keywords in table.items():
            part = _find(parts, keywords)
            if part is None:
                problems.append(f"缺少部件：{label}")
            else:
                found[label] = part

        head = found.get("头部") or found.get("头")
        torso = found.get("躯干")
        if head and torso and expect == "person":
            head_cx, head_cy = _center(head["bbox"])
            torso_cx, torso_cy = _center(torso["bbox"])
            if head_cy > torso_cy:
                problems.append("头在躯干下方，接反了")
            if abs(head_cx - torso_cx) > torso["w"] * 0.6:
                problems.append(f"头没有坐在躯干上，横向差了 {abs(head_cx - torso_cx):.0f} 像素")

        if expect == "person":
            for side, label in (("左臂", "左臂"), ("右臂", "右臂")):
                arm = found.get(label)
                if arm and torso:
                    arm_cx, _ = _center(arm["bbox"])
                    if side == "左臂" and arm_cx > torso["bbox"][0] + torso["w"] * 0.7:
                        problems.append("左臂长到了躯干右侧")
                    if side == "右臂" and arm_cx < torso["bbox"][0] + torso["w"] * 0.3:
                        problems.append("右臂长到了躯干左侧")
            legs = [found.get("左腿"), found.get("右腿")]
            if all(legs) and torso:
                for leg in legs:
                    if leg["bbox"][1] < torso["bbox"][3] - torso["h"] * 0.2:
                        problems.append(f"{leg['name']} 起点太高，插进躯干里了")

        if expect == "horse":
            if head and torso:
                if head["bbox"][3] > torso["bbox"][1] + torso["h"] * 0.5:
                    problems.append("马头没有高过马背")
                if head["bbox"][0] < torso["bbox"][0] + torso["w"] * 0.4:
                    problems.append("马头不在躯干前方")
            legs = [part for part in parts if part["name"].startswith("腿 ")]
            if len(legs) < 12:
                problems.append(f"马腿只有 {len(legs)} 段，应该是 12 段（四条腿各三段）")
            body = found.get("躯干")
            if body:
                for leg in legs:
                    if leg["bbox"][1] < body["bbox"][1] - body["h"] * 0.3:
                        problems.append(f"{leg['name']} 的起点高过马背")

    # 比例：用最高的部件当总高，看腿占多少
    if parts:
        top = min(part["bbox"][1] for part in parts)
        bottom = max(part["bbox"][3] for part in parts)
        total = bottom - top
        detail = {"总高": round(total, 1), "部件数": len(parts), "顶部": round(top, 1), "底部": round(bottom, 1)}
    else:
        detail = {}

    return {
        "ok": not problems,
        "parts": len(parts),
        "problems": problems,
        "detail": detail,
        "items": [{"name": part["name"], "bbox": [round(v, 1) for v in part["bbox"]]} for part in parts],
    }


def report_text(result: dict) -> str:
    lines = []
    status = "检查通过" if result["ok"] else "检查未通过"
    lines.append(f"{status} | {result['parts']} 个部件 | {result['detail']}")
    for problem in result["problems"]:
        lines.append(f"  - {problem}")
    return "\n".join(lines)
