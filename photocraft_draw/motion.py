# -*- coding: utf-8 -*-
"""动作状态：把"谁在往哪个方向使劲"写成数据，再拿几何去核对。

遮挡关系定的是谁挡住谁。动作状态定的是谁在使什么劲。这件事要在遮挡
之前定下来，因为人是先有了动作，兵器和身体的位置才跟着定。

模型写方案时容易取平均值：让两个角色都举着兵器朝同一侧使劲。画面读
出来是两个人一起站着，谁也没压住谁。这种含糊在方案里看不出来，只有
拿几何去量才量得出来。

这一层定三个量：

1. 意图向量。方案里每一层声明动作词和方向角，方向角是画面坐标里的
   角度，0 度朝右，90 度朝下，180 度朝左，270 度朝上。
2. 骨段方向。从关节表算出的每一段骨骼方向。
3. 器物主轴。从路径算出的兵器方向，取从持械者的手指向远端的那一段。

三者之间的关系就是这一层要查的事：

- 兵器主轴和意图向量必须同向，兵器拿反了要报。
- 手要落在兵器上，手悬在兵器旁边要报。
- 两个交战角色的意图向量夹角离 0 度太近，对抗读不出来，要报。

用法：
    photocraft-draw motion plans/a.json
    photocraft-draw motion plans/a.json --json out/motion.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .components.rig import JOINT_NAMES, POSES

# 动作词表：动作词对方向有要求，写错方向在校验阶段报出来
ACTION_RULES = {
    "press_down": ("自上而下压", 90.0, 45.0),
    "lift_up": ("自下而上挑", 270.0, 45.0),
    "push_out": ("向外推", 0.0, 60.0),
    "pull_in": ("向内拽", 180.0, 60.0),
    "sweep": ("横扫", 0.0, 45.0),
    "thrust": ("前刺", 0.0, 45.0),
    "parry": ("格挡", 0.0, 60.0),
    "guard": ("守势", 90.0, 90.0),
    "retreat": ("后撤", 180.0, 60.0),
    "leap": ("腾空", 270.0, 60.0),
    "stand": ("站立不动", 90.0, 180.0),
}

# 动作词到英文说法，画面稿给生图模型用
ACTION_EN = {
    "press_down": "pressing downward",
    "lift_up": "lifting upward",
    "push_out": "pushing outward",
    "pull_in": "pulling inward",
    "sweep": "sweeping sideways",
    "thrust": "thrusting forward",
    "parry": "parrying",
    "guard": "holding guard",
    "retreat": "retreating",
    "leap": "leaping up",
    "stand": "standing still",
}
# 动作词到中文说法，报告和画面稿都用
ACTION_TEXT = {key: value[0] for key, value in ACTION_RULES.items()}

# 骨段名，按人体部位分组
SEGMENTS = (
    ("torso", "躯干", ("hip", "chest")),
    ("head", "头颈", ("neck", "head")),
    ("arm_l_upper", "左上臂", ("shoulder_l", "elbow_l")),
    ("arm_l_fore", "左小臂", ("elbow_l", "hand_l")),
    ("arm_r_upper", "右上臂", ("shoulder_r", "elbow_r")),
    ("arm_r_fore", "右小臂", ("elbow_r", "hand_r")),
    ("leg_l_upper", "左大腿", ("hip", "knee_l")),
    ("leg_l_lower", "左小腿", ("knee_l", "foot_l")),
    ("leg_r_upper", "右大腿", ("hip", "knee_r")),
    ("leg_r_lower", "右小腿", ("knee_r", "foot_r")),
)

# 手臂骨段参与顺向判断
ARM_SEGMENTS = ("arm_l_upper", "arm_l_fore", "arm_r_upper", "arm_r_fore")

# 兵器形状的名字关键词
PROP_KEYWORDS = ("cudgel", "blade", "staff", "sword", "spear", "halberd",
                 "polearm", "axe", "mace", "whip", "chain", "rope", "stick",
                 "gun", "halberd")

# 手到兵器路径的距离上限，超过这个数说明手悬在兵器旁边，没握住
HOLD_TOLERANCE = 75.0

# 兵器主轴与意图向量的夹角上限，超过算兵器拿反了
PROP_TOLERANCE = 50.0

# 两个交战角色的意图向量夹角下界，低于这个数读作两人一起使劲
DUEL_MIN = 60.0

# 两件兵器在画面上的交叉角下界，低于这个数两件兵器叠成一条线
CROSS_MIN = 45.0


def _unit(vector):
    length = math.hypot(vector[0], vector[1])
    if length <= 0:
        return (0.0, 0.0)
    return (vector[0] / length, vector[1] / length)


def _angle_between(first, second) -> float:
    one, two = _unit(first), _unit(second)
    dot = one[0] * two[0] + one[1] * two[1]
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def _direction_angle(vector) -> float:
    """向量方向角，0 朝右，90 朝下，180 朝左，270 朝上。"""
    return math.degrees(math.atan2(vector[1], vector[0])) % 360.0


def _normalize_angle(value: float) -> float:
    return value % 360.0


def _angle_in_sector(angle: float, center: float, half_width: float) -> bool:
    """角度落在以 center 为中心、半宽 half_width 的扇区里。"""
    if half_width >= 180.0:
        return True
    diff = abs(_normalize_angle(angle) - _normalize_angle(center))
    diff = min(diff, 360.0 - diff)
    return diff <= half_width


def _pose_table(value) -> dict:
    """关节表。给字符串查内置姿态，给字典直接用。"""
    if isinstance(value, dict):
        table = {}
        for name in JOINT_NAMES:
            point = value[name]
            table[name] = (float(point[0]), float(point[1]))
        return table
    if isinstance(value, str):
        if value not in POSES:
            raise ValueError(f"pose 只能是 {'、'.join(POSES)}，收到 {value}")
        return {name: (float(x), float(y)) for name, (x, y) in POSES[value].items()}
    raise ValueError("pose 给姿态名，或者直接给关节表")


def _figures(plan: dict) -> list:
    """方案里每个人物白模，带绝对关节坐标。"""
    out = []
    for layer in plan.get("layers") or []:
        for item in layer.get("components") or []:
            if item.get("component") != "figure_rig":
                continue
            params = item.get("params") or {}
            table = _pose_table(params.get("pose", "stand"))
            if params.get("flip"):
                table = {name: (-x, y) for name, (x, y) in table.items()}
            ox, oy = float(params["root"][0]), float(params["root"][1])
            height = float(params["height"])
            joints = {name: (ox + x * height, oy + y * height)
                      for name, (x, y) in table.items()}
            out.append({
                "layer": str(layer.get("name", "")),
                "joints": joints,
                "height": height,
            })
    return out


def _segment_vectors(joints: dict) -> dict:
    out = {}
    for key, label, (start, end) in SEGMENTS:
        if start not in joints or end not in joints:
            continue
        begin, finish = joints[start], joints[end]
        out[key] = {
            "label": label,
            "vector": (finish[0] - begin[0], finish[1] - begin[1]),
        }
    return out


def _prop_axes(plan: dict) -> list:
    """每一层里兵器形状的主轴，两端点。"""
    out = []
    for layer in plan.get("layers") or []:
        layer_name = str(layer.get("name", ""))
        holder = layer.get("holder")
        for item in layer.get("components") or []:
            if item.get("component") != "custom_shape":
                continue
            params = item.get("params") or {}
            shape_name = str(params.get("name", ""))
            if not any(word in shape_name.lower() for word in PROP_KEYWORDS):
                continue
            points = []
            for subpath in params.get("subpaths") or []:
                for knot in subpath.get("knots") or []:
                    if isinstance(knot, dict):
                        points.append((float(knot["anchor"][0]), float(knot["anchor"][1])))
                    else:
                        points.append((float(knot[0]), float(knot[1])))
            if len(points) < 2:
                continue
            best = (0.0, None, None)
            for index, first in enumerate(points):
                for other in points[index + 1:]:
                    span = math.dist(first, other)
                    if span > best[0]:
                        best = (span, first, other)
            if best[1] is None:
                continue
            out.append({
                "layer": layer_name,
                "shape": shape_name,
                "holder": str(holder) if holder else "",
                "ends": [best[1], best[2]],
                "span": best[0],
            })
    return out


def _declared_motions(plan: dict) -> dict:
    out = {}
    for layer in plan.get("layers") or []:
        motion = layer.get("motion")
        if isinstance(motion, dict):
            out[str(layer.get("name", ""))] = motion
    return out


def _intent_vector(angle) -> tuple:
    radians = math.radians(float(angle))
    return (math.cos(radians), math.sin(radians))


def _point_to_segment(point, start, end) -> float:
    """点到线段的距离。手离兵器路径多远，就是握得牢不牢。"""
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    if length <= 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _prop_drive_vector(prop: dict, joints: dict):
    """兵器从持械者的手指向远端的方向。"""
    hands = [joints["hand_l"], joints["hand_r"]]
    best = None
    for hand in hands:
        for index, end in enumerate(prop["ends"]):
            gap = math.dist(hand, end)
            if best is None or gap < best[0]:
                best = (gap, hand, index)
    if best is None:
        return None
    _, hand, index = best
    far = prop["ends"][1 - index]
    return (far[0] - hand[0], far[1] - hand[1])


def analyze_plan(plan: dict) -> dict:
    """读方案，算出每个角色的方向关系。"""
    figures = _figures(plan)
    props = _prop_axes(plan)
    declared = _declared_motions(plan)
    layers = {str(layer.get("name", "")): layer for layer in plan.get("layers") or []}
    joints_of = {figure["layer"]: figure["joints"] for figure in figures}

    # 每件兵器的路径端点，用来量手离兵器多远
    prop_paths = {}
    for prop in props:
        prop_paths[prop["holder"]] = prop["ends"]

    actors = []
    for figure in figures:
        segments = _segment_vectors(figure["joints"])
        joints = figure["joints"]
        feet = ((joints["foot_l"][0] + joints["foot_r"][0]) / 2,
                (joints["foot_l"][1] + joints["foot_r"][1]) / 2)
        hands = ((joints["hand_l"][0] + joints["hand_r"][0]) / 2,
                 (joints["hand_l"][1] + joints["hand_r"][1]) / 2)
        line = (hands[0] - feet[0], hands[1] - feet[1])

        motion = declared.get(figure["layer"])
        angle = None
        action = ""
        intent = (0.0, 0.0)
        issues = []
        if motion:
            action = str(motion.get("action", ""))
            raw = motion.get("angle")
            if raw is not None:
                angle = _normalize_angle(float(raw))
                intent = _intent_vector(angle)
                rule = ACTION_RULES.get(action)
                if rule and not _angle_in_sector(angle, rule[1], rule[2]):
                    issues.append({
                        "kind": "action_angle",
                        "text": ("动作词「%s」要求方向在 %.0f 度上下 %.0f 度以内，"
                                 "声明的 %.1f 度对不上"
                                 % (rule[0], rule[1], rule[2], angle)),
                    })

        actor = {
            "layer": figure["layer"],
            "action": action,
            "action_text": ACTION_TEXT.get(action, action),
            "angle": angle,
            "intent_vector": [round(intent[0], 4), round(intent[1], 4)],
            "opponents": list(motion.get("opponents") or []) if motion else [],
            "segments": {
                key: {
                    "label": item["label"],
                    "vector": [round(item["vector"][0], 1), round(item["vector"][1], 1)],
                    "angle": round(_direction_angle(item["vector"]), 1),
                }
                for key, item in segments.items()
            },
            "action_line": [round(line[0], 1), round(line[1], 1)],
            "action_line_angle": round(_direction_angle(line), 1),
            "issues": issues,
        }

        if motion and angle is not None:
            gaps = {}
            for key in ARM_SEGMENTS:
                segment = segments.get(key)
                if not segment:
                    continue
                gap = _angle_between(segment["vector"], intent)
                gaps[key] = round(gap, 1)
            actor["arm_gaps"] = gaps

        # 持械的标准是手离兵器多远，不是手臂朝哪。
        # 举过头顶准备劈砍，手臂朝上、兵器朝下，这才是对的姿势。
        # 真正握不住的表现是手悬在兵器旁边，离得老远。
        ends = prop_paths.get(figure["layer"])
        if ends:
            hold_gaps = {}
            for key in ARM_SEGMENTS:
                if not segments.get(key):
                    continue
                hand_name = "hand_l" if key.startswith("arm_l") else "hand_r"
                hand = joints[hand_name]
                gap = _point_to_segment(hand, ends[0], ends[1])
                hold_gaps[key] = round(gap, 1)
            actor["hold_gaps"] = hold_gaps
            # 一只手握着就算握着，另一只手可以不碰兵器。
            # 标准看两只手里离兵器更近的那只。
            nearest = min(hold_gaps.items(), key=lambda item: item[1])
            actor["hold_nearest"] = {"arm": nearest[0], "gap": nearest[1],
                                     "label": segments[nearest[0]]["label"]}
            if nearest[1] > HOLD_TOLERANCE:
                actor["issues"].append({
                    "kind": "hand_off_weapon",
                    "text": "没有一只手握在兵器上：%s 离兵器 %.1f 像素" % (
                        segments[nearest[0]]["label"], nearest[1]),
                    "detail": {key: gap for key, gap in hold_gaps.items()
                                if gap > HOLD_TOLERANCE},
                })

        actors.append(actor)

    # 兵器主轴和持械者的意图向量
    prop_reports = []
    for prop in props:
        entry = {
            "layer": prop["layer"],
            "shape": prop["shape"],
            "holder": prop["holder"],
            "span": round(prop["span"], 1),
            "issues": [],
        }
        holder_joints = joints_of.get(prop["holder"])
        drive = _prop_drive_vector(prop, holder_joints) if holder_joints else None
        if drive:
            entry["drive_vector"] = [round(drive[0], 1), round(drive[1], 1)]
            entry["drive_angle"] = round(_direction_angle(drive), 1)
            holder_actor = next((item for item in actors
                                 if item["layer"] == prop["holder"]), None)
            if holder_actor and holder_actor["angle"] is not None:
                gap = _angle_between(drive, holder_actor["intent_vector"])
                entry["gap"] = round(gap, 1)
                if gap > PROP_TOLERANCE:
                    entry["issues"].append({
                        "kind": "prop_misaligned",
                        "text": ("%s 的施力方向 %.1f 度，和 %s 声明的 %.1f 度差 %.1f 度，"
                                 "兵器拿反了或者持械姿势不对"
                                 % (prop["shape"], entry["drive_angle"], prop["holder"],
                                    holder_actor["angle"], gap)),
                    })
        elif not prop["holder"]:
            entry["issues"].append({
                "kind": "prop_no_holder",
                "text": "%s 没有写 holder，不知道该谁拿" % prop["layer"],
            })
        prop_reports.append(entry)

    # 交战关系
    duels = []
    seen_duels = set()
    for actor in actors:
        for other_name in actor["opponents"]:
            other = next((item for item in actors if item["layer"] == other_name), None)
            if other is None:
                actor["issues"].append({
                    "kind": "opponent_missing",
                    "text": "opponents 里的 %s 不是方案里的层" % other_name,
                })
                continue
            if actor["angle"] is None or other["angle"] is None:
                continue
            gap = _angle_between(actor["intent_vector"], other["intent_vector"])
            entry = {
                "actors": [actor["layer"], other["layer"]],
                "gap": round(gap, 1),
            }
            if gap < DUEL_MIN:
                entry["issue"] = ("%s 和 %s 的动作方向夹角只有 %.1f 度，两人朝同一侧使劲，"
                                  "对抗读不出来" % (actor["layer"], other["layer"], gap))
            # 两件兵器在画面上的交叉角。引擎的投影对二维组件是恒等映射，
            # 深度只决定谁压谁，所以这个角就是方案里写下的角。
            first = next((item for item in prop_reports
                          if item["holder"] == actor["layer"]), None)
            second = next((item for item in prop_reports
                           if item["holder"] == other["layer"]), None)
            if first and second and "drive_angle" in first and "drive_angle" in second:
                diff = abs(first["drive_angle"] - second["drive_angle"]) % 360.0
                diff = min(diff, 360.0 - diff)
                crossing = min(diff, 180.0 - diff)
                entry["crossing"] = round(crossing, 1)
                if crossing < CROSS_MIN:
                    entry["crossing_issue"] = (
                        "%s 和 %s 的兵器交叉角只有 %.1f 度，画面上叠成一条线，"
                        "读不出交错" % (first["layer"], second["layer"], crossing))
            key = tuple(sorted(entry["actors"]))
            if key in seen_duels:
                continue
            seen_duels.add(key)
            duels.append(entry)

    return {
        "actors": actors,
        "props": prop_reports,
        "duels": duels,
        "declared": sorted(declared),
        "undeclared": sorted(item["layer"] for item in actors
                             if item["layer"] not in declared),
    }


def report(result: dict) -> str:
    lines = ["角色动作状态："]
    if not result["actors"]:
        lines.append("  方案里没有人物白模")
    for actor in result["actors"]:
        if actor["angle"] is None:
            lines.append("  %s：未声明 motion" % actor["layer"])
            continue
        lines.append("  %s：%s，方向 %.1f 度" % (
            actor["layer"], actor["action_text"], actor["angle"]))
        nearest = actor.get("hold_nearest")
        if nearest:
            lines.append("     握兵器的手：%s，离兵器 %.1f 像素"
                         % (nearest["label"], nearest["gap"]))
        for key, item in actor["segments"].items():
            parts = ["%.1f 度" % item["angle"]]
            if key in ARM_SEGMENTS:
                gap = (actor.get("arm_gaps") or {}).get(key)
                if gap is not None:
                    parts.append("与意图差 %.1f 度" % gap)
            hold = (actor.get("hold_gaps") or {}).get(key)
            if hold is not None:
                parts.append("离兵器 %.1f 像素" % hold)
            lines.append("     %s %s" % (item["label"], "，".join(parts)))

    if result["props"]:
        lines.append("")
        lines.append("兵器主轴：")
        for prop in result["props"]:
            if "drive_angle" in prop:
                lines.append("  %s（%s）：施力方向 %.1f 度，%s 跨度 %.1f%s" % (
                    prop["layer"], prop["shape"], prop["drive_angle"],
                    prop["holder"], prop["span"],
                    "，与意图向量差 %.1f 度" % prop["gap"] if "gap" in prop else ""))
            else:
                lines.append("  %s（%s）：%s 跨度 %.1f" % (
                    prop["layer"], prop["shape"], prop["holder"] or "没人持械",
                    prop["span"]))

    if result["duels"]:
        lines.append("")
        lines.append("交战方向：")
        for duel in result["duels"]:
            lines.append("  %s 与 %s：夹角 %.1f 度" % (
                duel["actors"][0], duel["actors"][1], duel["gap"]))
            if duel.get("crossing") is not None:
                lines.append("     兵器交叉角 %.1f 度" % duel["crossing"])
            if duel.get("issue"):
                lines.append("     " + duel["issue"])
            if duel.get("crossing_issue"):
                lines.append("     " + duel["crossing_issue"])

    issues = []
    for actor in result["actors"]:
        for issue in actor["issues"]:
            issues.append("%s：%s" % (actor["layer"], issue["text"]))
    for prop in result["props"]:
        for issue in prop["issues"]:
            issues.append("%s：%s" % (prop["layer"], issue["text"]))
    for duel in result["duels"]:
        if duel.get("issue"):
            issues.append(duel["issue"])
        if duel.get("crossing_issue"):
            issues.append(duel["crossing_issue"])

    if issues:
        lines.append("")
        lines.append("动作提示：")
        for text in issues:
            lines.append("  " + text)
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="检查角色的动作方向关系")
    parser.add_argument("plan", help="绘制方案文件")
    parser.add_argument("--json", help="结构化结果输出路径")
    args = parser.parse_args(argv)

    from .plan import load_plan

    result = analyze_plan(load_plan(args.plan))
    print(report(result))
    if args.json:
        Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
