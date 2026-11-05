# -*- coding: utf-8 -*-
"""兵器和肢体之间的空间关系。

白模是投影画出来的，看得见的只有画平面上的一张图。兵器和手臂在画面上
挨得多近、兵器有没有从武器和手臂之间的那个缝里穿过去，光靠看图容易
看错，所以这里拿线段算。

算出来的东西有四样：
一、两条线段在空间里的最近距离。
二、两条线段在空间里是不是真的相交，交点在哪一段的百分之几。
三、一条线段在另一条线段的哪一侧，按画面投影算带符号距离。
四、兵器有没有从另一件兵器和持械者的胳膊之间的那个缝里穿过去。

缝在兵器和手相接的那个点上张开，两条边是胳膊和兵器。兵器从缝里穿过去，
画面上就是被夹在中间，读不出来。缝有多大由手边的距离说了算。

用法：
    photocraft-draw relations plans/a.json
    photocraft-draw relations plans/a.json --json out/relations.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .motion import SEGMENTS
from .plan import load_plan
from .views import DEFAULT_UNIT, prop_z_at, scene_3d

# 缝的半径：从手边往外这么远算缝里，大约一条小臂那么长
GAP_RADIUS = 120.0

# 兵器和手臂在画面上离多远算挨上了
NEAR_TOLERANCE = 30.0

# 兵器比人物身前多少像素，就算从人物身前扫过去，不算穿缝，也不算挨上
FRONT_CLEARANCE = 30.0

# 兵器和兵器、胳膊的深度差多少像素以内，算卡在缝里
GAP_DEPTH_TOLERANCE = 10.0

# 两件兵器的深度差多少像素以内算真的碰上
TOUCH_TOLERANCE = 24.0


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def seg_seg_distance(p1, q1, p2, q2):
    """两条线段在空间里的最近距离。"""
    d1 = sub(q1, p1)
    d2 = sub(q2, p2)
    r = sub(p1, p2)
    a = dot(d1, d1)
    e = dot(d2, d2)
    f = dot(d2, r)
    if a <= 1e-9 and e <= 1e-9:
        return math.dist(p1, p2), 0.0, 0.0
    if a <= 1e-9:
        s = 0.0
        t = f / e
    else:
        c = dot(d1, r)
        if e <= 1e-9:
            t = 0.0
            s = -c / a
        else:
            b = dot(d1, d2)
            den = a * e - b * b
            s = 0.0 if den <= 1e-9 else max(0.0, min(1.0, (b * f - c * e) / den))
            t = (b * s + f) / e
            if t < 0.0:
                t = 0.0
                s = max(0.0, min(1.0, -c / a))
            elif t > 1.0:
                t = 1.0
                s = max(0.0, min(1.0, (b - c) / a))
    cp1 = (p1[0] + d1[0] * s, p1[1] + d1[1] * s, p1[2] + d1[2] * s)
    cp2 = (p2[0] + d2[0] * t, p2[1] + d2[1] * t, p2[2] + d2[2] * t)
    return math.dist(cp1, cp2), s, t


def seg_seg_distance_2d(p1, q1, p2, q2):
    """两条线段在画面平面上的最近距离。"""
    return seg_seg_distance((p1[0], p1[1], 0.0), (q1[0], q1[1], 0.0),
                             (p2[0], p2[1], 0.0), (q2[0], q2[1], 0.0))


def seg_seg_cross(p1, q1, p2, q2):
    """两条线段在空间里真不相交就返回 None。"""
    d1 = sub(q1, p1)
    d2 = sub(q2, p2)
    r = sub(p1, p2)
    a = dot(d1, d1)
    e = dot(d2, d2)
    f = dot(d2, r)
    c = dot(d1, r)
    b = dot(d1, d2)
    den = a * e - b * b
    if abs(den) < 1e-9:
        return None
    s = (b * f - c * e) / den
    t = (b * s + f) / e
    if -1e-9 <= s <= 1 + 1e-9 and -1e-9 <= t <= 1 + 1e-9:
        return ((p1[0] + d1[0] * s, p1[1] + d1[1] * s, p1[2] + d1[2] * s), s, t)
    return None


def signed_side_2d(line_a, line_b, point):
    """点相对一条画面平面上的直线在哪一侧。"""
    return ((line_b[0] - line_a[0]) * (point[1] - line_a[1])
            - (line_b[1] - line_a[1]) * (point[0] - line_a[0]))


def cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def in_wedge(vertex, first, second, point, radius, margin=0.06):
    """点是不是落在顶点处由两条射线张开的那个角里，并且离顶点不远。

四个点都用画面平面上的坐标。角是画面上的角，半径也是画面上的距离。
    余量是三度半。点正好压在边上不算，兵器在边上交叉跟穿进缝里是两件事。
    """
    if math.hypot(point[0] - vertex[0], point[1] - vertex[1]) > radius:
        return False
    one = (first[0] - vertex[0], first[1] - vertex[1])
    two = (second[0] - vertex[0], second[1] - vertex[1])
    to_point = (point[0] - vertex[0], point[1] - vertex[1])
    if math.hypot(one[0], one[1]) < 1e-9 or math.hypot(two[0], two[1]) < 1e-9:
        return False

    def side(vec_a, vec_b):
        value = cross2(vec_a, vec_b)
        norm = (math.hypot(vec_a[0], vec_a[1])
                * math.hypot(vec_b[0], vec_b[1]))
        if norm < 1e-9:
            return 0.0
        return value / norm

    if cross2(one, two) >= 0:
        return side(one, to_point) >= margin and side(to_point, two) >= margin
    return side(one, to_point) <= -margin and side(to_point, two) <= -margin


def prop_segments(prop):
    """兵器在空间里的线段。兵器按深度分段，每一段一个深度。"""
    (start, end) = prop["ends"]
    segments = prop.get("segments") or []
    if not segments:
        return [{"name": prop["layer"], "z": prop["z"],
                 "a": (start[0], start[1], prop["z"]),
                 "b": (end[0], end[1], prop["z"]),
                 "from": 0.0, "to": 1.0}]
    out = []
    length = math.dist(start, end) or 1.0
    ux = (end[0] - start[0]) / length
    uy = (end[1] - start[1]) / length
    for segment in segments:
        a = (start[0] + ux * length * segment["from"],
             start[1] + uy * length * segment["from"], segment["z"])
        b = (start[0] + ux * length * segment["to"],
             start[1] + uy * length * segment["to"], segment["z"])
        out.append({"name": prop["layer"], "z": segment["z"], "a": a, "b": b,
                    "from": segment["from"], "to": segment["to"]})
    return out


def bone_segments(scene):
    """每个人物身上的骨段，带深度。"""
    out = []
    for figure in scene["figures"]:
        joints = figure["joints"]
        for key, label, (start, end) in SEGMENTS:
            if start not in joints or end not in joints:
                continue
            out.append({
                "layer": figure["layer"],
                "name": label,
                "key": key,
                "figure_z": figure["z"],
                "a": joints[start],
                "b": joints[end],
            })
    return out


def analyze(plan: dict, unit: float = DEFAULT_UNIT) -> dict:
    """读方案，算出兵器和肢体之间的空间关系。"""
    scene = scene_3d(plan, unit)
    props = scene["props"]
    bones = bone_segments(scene)

    entries = []
    issues = []

    # 兵器和兵器
    for index, first in enumerate(props):
        for second in props[index + 1:]:
            hit = seg_seg_cross(prop_segments(first)[0]["a"],
                                prop_segments(first)[-1]["b"],
                                prop_segments(second)[0]["a"],
                                prop_segments(second)[-1]["b"])
            if hit is None:
                continue
            point, s, t = hit
            length_first = math.dist(first["ends"][0], first["ends"][1]) or 1.0
            length_second = math.dist(second["ends"][0], second["ends"][1]) or 1.0
            ratio_first = s * length_first / (math.dist(first["ends"][0],
                                                        first["ends"][1]) or 1.0)
            ratio_second = t
            gap = abs(prop_z_at(first, ratio_first) - prop_z_at(second, ratio_second))
            entry = {
                "props": [first["layer"], second["layer"]],
                "point": list(point),
                "z_gap": gap,
                "touch": gap <= TOUCH_TOLERANCE,
                "at_first": ratio_first,
                "at_second": ratio_second,
            }
            entries.append(entry)
            if not entry["touch"]:
                issues.append(
                    "%s 和 %s 在画面上交叉，可两件兵器的深度差 %.0f 像素，它们碰不到一起"
                    % (first["layer"], second["layer"], gap))

    # 兵器和骨段。距离算画面平面上的，深度另算一笔，两样分开看。
    distances = []
    notes = []
    for prop in props:
        for bone in bones:
            if bone["layer"] == prop.get("holder"):
                continue
            best = None
            for segment in prop_segments(prop):
                gap, _, t = seg_seg_distance(segment["a"], segment["b"],
                                             bone["a"], bone["b"])
                if best is None or gap < best[0]:
                    best = (gap, segment, t)
            if best is None:
                continue
            _, segment, t = best
            flat = seg_seg_distance_2d(segment["a"], segment["b"],
                                       bone["a"], bone["b"])[0]
            prop_z = segment["z"]
            bone_z = bone["a"][2] + (bone["b"][2] - bone["a"][2]) * t
            entry = {
                "prop": prop["layer"],
                "bone": bone["name"],
                "figure": bone["layer"],
                "distance": round(flat, 1),
                "z_gap": round(prop_z - bone_z, 1),
            }
            distances.append(entry)
            if flat < NEAR_TOLERANCE and bone["key"].startswith("arm_"):
                if prop_z - bone_z <= -FRONT_CLEARANCE:
                    notes.append(
                        "%s 从 %s 的%s前面扫过去，前后差 %.0f 像素"
                        % (prop["layer"], bone["layer"], bone["name"],
                           bone_z - prop_z))
                elif prop_z - bone_z >= FRONT_CLEARANCE:
                    notes.append(
                        "%s 从 %s 的%s后面过去，前后差 %.0f 像素"
                        % (prop["layer"], bone["layer"], bone["name"],
                           prop_z - bone_z))
                else:
                    issues.append(
                        "%s 离 %s 的%s只有 %.0f 像素，挨得太近"
                        % (prop["layer"], bone["layer"], bone["name"], flat))

    # 兵器有没有从另一件兵器和胳膊之间的缝里穿过去
    gaps = []
    for prop in props:
        for other in props:
            if other["layer"] == prop["layer"]:
                continue
            holder = other.get("holder")
            if not holder:
                continue
            figure = next((item for item in scene["figures"]
                           if item["layer"] == holder), None)
            if figure is None:
                continue
            joints = figure["joints"]
            hands = [(name, joints.get(name))
                     for name in ("hand_l", "hand_r")]
            hands = [(name, hand) for name, hand in hands if hand]
            if not hands:
                continue
            vertex_name, vertex = min(hands, key=lambda item: min(
                math.dist(item[1][:2], other["ends"][0]),
                math.dist(item[1][:2], other["ends"][1])))
            elbow = joints.get("elbow_" + vertex_name[-1])
            if elbow is None:
                continue
            far = max(other["ends"], key=lambda end: math.dist(vertex[:2], end))
            # 缝张开的地方就到手边到胳膊肘这一段，肘子往后胳膊已经拐弯了
            radius = min(GAP_RADIUS, math.dist(vertex[:2], elbow[:2]))
            for segment in prop_segments(prop):
                hit = None
                steps = 240
                for step in range(steps + 1):
                    ratio = step / steps
                    point = (segment["a"][0] + (segment["b"][0] - segment["a"][0]) * ratio,
                             segment["a"][1] + (segment["b"][1] - segment["a"][1]) * ratio)
                    if in_wedge(vertex[:2], elbow[:2], far, point, radius):
                        hit = point
                        break
                if hit is None:
                    continue
                # 卡在兵器和胳膊中间才是穿进缝里，从前面扫过去不算。
                prop_z = segment["z"]
                weapon_z = other["z"]
                arm_z = elbow[2]
                low = min(weapon_z, arm_z) - GAP_DEPTH_TOLERANCE
                high = max(weapon_z, arm_z) + GAP_DEPTH_TOLERANCE
                trapped = low <= prop_z <= high
                distance = math.dist(hit, vertex[:2])
                gaps.append({
                    "prop": prop["layer"],
                    "other": other["layer"],
                    "figure": holder,
                    "point": [hit[0], hit[1]],
                    "distance": round(distance, 1),
                    "z_gap": round(prop_z - arm_z, 1),
                    "trapped": trapped,
                })
                if trapped:
                    issues.append(
                        "%s 从 %s 和 %s 的胳膊之间的那个缝里穿过去了，离手边 %.0f 像素"
                        % (prop["layer"], other["layer"], holder, distance))
                else:
                    notes.append(
                        "%s 从 %s 的胳膊前面扫过去，离手边 %.0f 像素，"
                        "前后差 %.0f 像素，没有穿进缝里"
                        % (prop["layer"], holder, distance, arm_z - prop_z))

    # 交叉点离持械者的手有多远
    hands_gap = []
    for entry in entries:
        for prop in props:
            if prop["layer"] != entry["props"][0]:
                continue
            holder = prop.get("holder")
            figure = next((item for item in scene["figures"]
                           if item["layer"] == holder), None)
            if figure is None:
                continue
            for name in ("hand_l", "hand_r"):
                hand = figure["joints"].get(name)
                if hand is None:
                    continue
                gap = math.dist(hand, entry["point"])
                hands_gap.append({
                    "prop": prop["layer"],
                    "hand": name,
                    "distance": round(gap, 1),
                })
                if gap < 80.0:
                    issues.append(
                        "交叉点离 %s 的%s只有 %.0f 像素，太近"
                        % (holder, name, gap))

    return {
        "canvas": scene["canvas"],
        "unit": unit,
        "props": [{"layer": prop["layer"], "holder": prop.get("holder"),
                   "z": prop["z"], "segments": prop.get("segments") or [],
                   "ends": [list(end) for end in prop["ends"]]}
                  for prop in props],
        "crossings": entries,
        "distances": distances,
        "gaps": gaps,
        "hands_gap": hands_gap,
        "notes": notes,
        "issues": issues,
    }


def report(result: dict) -> str:
    lines = ["兵器和肢体之间的空间关系："]
    if result["crossings"]:
        lines.append("")
        lines.append("两件兵器的交叉：")
        for entry in result["crossings"]:
            point = entry["point"]
            lines.append("  %s 与 %s 在 (%.0f, %.0f) 交叉，深度差 %.0f 像素，%s"
                         % (entry["props"][0], entry["props"][1],
                            point[0], point[1], entry["z_gap"],
                            "碰得到" if entry["touch"] else "碰不到"))
    else:
        lines.append("")
        lines.append("  两件兵器在画面上没有交叉")

    if result["distances"]:
        lines.append("")
        lines.append("兵器离骨段最近的几个：")
        picked = sorted(result["distances"], key=lambda item: item["distance"])[:12]
        for item in picked:
            lines.append("  %s 离 %s 的%s %.0f 像素，前后差 %.0f 像素"
                         % (item["prop"], item["figure"], item["bone"],
                            item["distance"], item["z_gap"]))

    if result["hands_gap"]:
        lines.append("")
        lines.append("交叉点离持械者的手：")
        for item in result["hands_gap"]:
            lines.append("  %s 的%s %.0f 像素"
                         % (item["prop"], item["hand"], item["distance"]))

    if result["gaps"]:
        lines.append("")
        lines.append("兵器经过兵器和胳膊之间那个角的地方：")
        for item in result["gaps"]:
            if item["trapped"]:
                lines.append("  %s 从 %s 和 %s 的胳膊之间穿过去，离手边 %.0f 像素"
                             % (item["prop"], item["other"], item["figure"],
                                item["distance"]))
            else:
                lines.append("  %s 经过那个角，离手边 %.0f 像素，"
                             "在 %s 的胳膊前面 %.0f 像素"
                             % (item["prop"], item["distance"],
                                item["figure"], -item["z_gap"]))

    if result.get("notes"):
        lines.append("")
        lines.append("看过的几处：")
        for text in result["notes"]:
            lines.append("  " + text)

    if result["issues"]:
        lines.append("")
        lines.append("空间提示：")
        for text in result["issues"]:
            lines.append("  " + text)
    return "\n".join(lines)


def run(plan_path, unit: float = DEFAULT_UNIT, json_path=None) -> int:
    plan = load_plan(plan_path)
    result = analyze(plan, unit)
    print(report(result))
    if json_path:
        Path(json_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
        print("结构化结果：%s" % json_path)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="算兵器和肢体之间的空间关系")
    parser.add_argument("plan", help="绘制方案文件")
    parser.add_argument("--unit", type=float, default=DEFAULT_UNIT,
                        help="图层 depth 每差 1 相当于多少像素，默认 %.0f" % DEFAULT_UNIT)
    parser.add_argument("--json", help="结构化结果输出路径")
    args = parser.parse_args(argv)
    return run(args.plan, args.unit, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
