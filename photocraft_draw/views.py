# -*- coding: utf-8 -*-
"""三视图：正视图、左视图、俯视图。

白模是投影画出来的，看得见的只有画平面上的一张图。投影把深度扔掉了，
动作的意思也跟着扔掉。手举在头后面是蓄力，手伸在身前是劈下，这两张
画平面的图差不了多少，意思差得很远。画面上还看不出，谁也说不清。

三视图拿同一份关节坐标从三个方向各投一次。正视图是画平面上的位置，
左视图看动作的前后走向，俯视图看人物在场景里的前后位置。三个图摆
在一起，蓄力还是劈下、兵器能不能碰到对方，一眼就分得出来。

方向按第三角投影定。左视图从场景左边看过去，近的一侧在右边。俯视图
从上往下看，x 轴跟正视图一样，近的一侧在下边。

关节表里每个点可以写两个数，也可以写三个数。第三个数是深度 z，单位
是像素，正数离观众更远，作用在人物自己的身板平面上。写两个数的老规矩
照旧能用，z 当 0。

场景的深度来自图层声明的 depth：图层越靠前，离观众越近。人物的关节
在自己这一层的深度上再加上自己的 z。兵器不在图层上，它在持械者的手里，
所以兵器的深度取持械者那只手的深度。

z 的记号跟引擎别处一致：z 越大离观众越远，最近的一层是 0，往后一层
加一个 unit 像素。z 可以是负数，负数表示比最近的一层更靠前。

用法：
    photocraft-draw views plans/a.json --out-dir out
    photocraft-draw views plans/a.json --unit 40
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .commands import Pen
from .components.rig import BONES, JOINT_SCALE
from .components.rig import pose_table_3d
from .motion import HOLD_TOLERANCE, PROP_KEYWORDS, _prop_axes
from .palette import resolve_palette
from .plan import load_plan, ordered_layers, resolve_depths

VIEW_NAMES = ("front", "left", "top")
VIEW_TITLES = {"front": "正视图", "left": "左视图", "top": "俯视图"}

# 场景深度：图层 depth 每差 1，深度差多少像素
DEFAULT_UNIT = 40.0

# 两件兵器在画平面上交叉，深度差多少像素以内算真的碰上
TOUCH_TOLERANCE = 24.0

# 脚底离全场地面线多少像素算腾空
AIRBORNE_GAP = 60.0

# 头顶差多少像素算分出上下
LEVEL_GAP = 90.0

# 画视图用的颜色，按层轮着来
LAYER_COLORS = ("accent", "muted", "soft", "mid", "line")


def _third(value: float, size: float) -> int:
    """位置落在第几个三分之一里，0 是最前，2 是最后。"""
    if size <= 0:
        return 0
    ratio = value / size
    if ratio < 1.0 / 3.0:
        return 0
    if ratio < 2.0 / 3.0:
        return 1
    return 2


H_BAND_ZH = ("左", "中", "右")
H_BAND_EN = ("left", "centre", "right")
V_BAND_ZH = ("上", "中", "下")
V_BAND_EN = ("upper", "middle", "lower")


def _depth_of(plan: dict) -> dict:
    """层名到声明的 depth。"""
    out = {}
    for layer in plan.get("layers") or []:
        raw = layer.get("depth")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            continue
        out[str(layer.get("name", ""))] = float(raw)
    return out


def _segment_depths(segment: dict) -> dict:
    """一段兵器的深度。写 z 是平的，写 z_from 和 z_to 是斜坡。

    斜坡的意思是这一段的深度从 from 处的 z_from 变到 to 处的 z_to，
    中间按比例算。一根直兵器在空间里的深度本来就是这么变的，一段写一个
    数写不出来，俯视图上就成了一堆互相平行的横线。
    """
    z_from = segment.get("z_from")
    z_to = segment.get("z_to")
    if z_from is None and z_to is None:
        z_from = segment.get("z", 0.0)
        z_to = z_from
    elif z_from is None:
        z_from = segment.get("z", z_to)
    elif z_to is None:
        z_to = segment.get("z", z_from)
    return {
        "from": float(segment.get("from", 0.0)),
        "to": float(segment.get("to", 1.0)),
        "z": float(z_from),
        "z_from": float(z_from),
        "z_to": float(z_to),
        "depth": float(segment.get("depth", 0.0)),
    }


def _segments_of(plan: dict, name: str) -> list:
    """一层里兵器按深度分的那几段。"""
    out = []
    for layer in plan.get("layers") or []:
        if str(layer.get("name", "")) != name:
            continue
        for segment in layer.get("segments") or []:
            out.append(_segment_depths(segment))
        return out
    return out


def prop_z_at(prop: dict, ratio: float) -> float:
    """兵器主轴上某一点的深度。一段兵器的深度可以是一段斜坡。"""
    segments = prop.get("segments") or []
    chosen = None
    for segment in segments:
        if segment["from"] - 1e-9 <= ratio <= segment["to"] + 1e-9:
            chosen = segment
            break
    if chosen is None:
        if segments:
            return segments[-1]["z_to"]
        return prop["z"]
    low = chosen["from"]
    high = chosen["to"]
    if high - low <= 1e-9:
        return chosen["z_from"]
    step = (ratio - low) / (high - low)
    return chosen["z_from"] + (chosen["z_to"] - chosen["z_from"]) * step


def _figure_layers(plan: dict):
    for layer in plan.get("layers") or []:
        for item in layer.get("components") or []:
            if item.get("component") == "figure_rig":
                yield layer, item


def _prop_layers(plan: dict):
    for prop in _prop_axes(plan):
        yield prop


def _point_to_segment(point, start, end) -> float:
    px, py = point[0], point[1]
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    if length <= 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _segment_cross_params(first, second, third, fourth):
    """两条线段在画平面上相交的点，以及交点在两段上的位置。

    位置是从第一个端点算起的比例，用来查兵器在那一点是哪个深度。
    """
    x1, y1 = first
    x2, y2 = second
    x3, y3 = third
    x4, y4 = fourth
    den = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(den) < 1e-9:
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / den
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / den
    if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
        return None
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1)), t, u


def _segment_cross(first, second, third, fourth):
    """两条线段在画平面上相交的点。平行或者不相交返回 None。"""
    hit = _segment_cross_params(first, second, third, fourth)
    return hit[0] if hit else None


def _layer_z(plan: dict, name: str, depths: dict, near: float,
              unit: float) -> float:
    """一层的物理深度。方案里写了 z 就用 z，没写就按画面的 depth 推。

    画面的 depth 是遮挡顺序，是画的事。z 是空间里的深度，是画之前定好的
    事。两件事分开了，作者才能既把悟空的手画在棒上头，又让棒真正处在
    悟空手的高度上。

    z 越大离观众越远。没写 z 的层按 depth 排，最近的一层是 0。
    """
    for layer in plan.get("layers") or []:
        if str(layer.get("name", "")) != name:
            continue
        raw = layer.get("z")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            break
        return float(raw)
    return (depths.get(name, near) - near) * unit


def scene_3d(plan: dict, unit: float = DEFAULT_UNIT) -> dict:
    """方案的图层算成三维坐标。

    人物的关节在图层深度上加自己的 z。兵器的深度取持械者的手。
    """
    plan = resolve_depths(plan)
    canvas = plan.get("canvas") or [800, 600]
    widths = float(canvas[0])
    heights = float(canvas[1])
    depths = _depth_of(plan)
    if depths:
        far = max(depths.values())
        near = min(depths.values())
    else:
        far = 0.0
        near = 0.0

    figures = []
    for layer, item in _figure_layers(plan):
        params = item.get("params") or {}
        root = params.get("root") or [0, 0]
        height = float(params.get("height") or 0)
        table = pose_table_3d(params.get("pose", "stand"))
        if params.get("flip"):
            table = {name: (-x, y, z) for name, (x, y, z) in table.items()}
        layer_z = _layer_z(plan, str(layer.get("name", "")), depths, near, unit)
        joints = {}
        for name, (x, y, z) in table.items():
            joints[name] = (root[0] + x * height, root[1] + y * height, layer_z + z)
        figures.append({
            "layer": str(layer.get("name", "")),
            "depth": depths.get(str(layer.get("name", "")), 0.0),
            "z": layer_z,
            "height": height,
            "joints": joints,
        })

    figures_of = {figure["layer"]: figure for figure in figures}

    props = []
    for prop in _prop_layers(plan):
        holder = prop.get("holder") or ""
        holder_figure = figures_of.get(holder)
        prop_z = _layer_z(plan, prop["layer"], depths, near, unit)
        segments = _segments_of(plan, prop["layer"])
        if segments:
            prop_z = segments[0]["z_from"]
        hands = []
        if holder_figure:
            ends = prop["ends"]
            joints = holder_figure["joints"]
            for hand_name in ("hand_l", "hand_r"):
                hand = joints.get(hand_name)
                if hand is None:
                    continue
                gap = _point_to_segment((hand[0], hand[1]), ends[0], ends[1])
                if gap <= HOLD_TOLERANCE:
                    hands.append(hand)
            # 兵器分了段的，每一段自己写深度，整体深度按第一段算，
            # 不拿手的高度改写，免得把分段的意思抹掉
            if not segments:
                if hands:
                    prop_z = sum(hand[2] for hand in hands) / len(hands)
                else:
                    nearest = min(
                        (joints.get(name) for name in ("hand_l", "hand_r")
                         if joints.get(name) is not None),
                        key=lambda hand: _point_to_segment(
                            (hand[0], hand[1]), prop["ends"][0], prop["ends"][1]),
                        default=None,
                    )
                    if nearest is not None:
                        prop_z = nearest[2]
        props.append({
            "layer": prop["layer"],
            "shape": prop["shape"],
            "holder": holder,
            "depth": depths.get(prop["layer"], 0.0),
            "z": prop_z,
            "segments": segments,
            "ends": [(float(end[0]), float(end[1])) for end in prop["ends"]],
            "span": float(prop["span"]),
        })

    zs = []
    for figure in figures:
        zs.extend(point[2] for point in figure["joints"].values())
    for prop in props:
        zs.append(prop["z"])
    z_range = (min(zs), max(zs)) if zs else (0.0, 0.0)

    return {
        "canvas": (widths, heights),
        "unit": unit,
        "depths": depths,
        "far": far,
        "figures": figures,
        "props": props,
        "z_range": z_range,
    }


def _ground(scene: dict) -> float:
    """全场地面线：最低的脚底。"""
    feet = []
    for figure in scene["figures"]:
        for name in ("foot_l", "foot_r"):
            point = figure["joints"].get(name)
            if point:
                feet.append(point[1])
    return max(feet) if feet else float(scene["canvas"][1])


def analyze_plan(plan: dict, unit: float = DEFAULT_UNIT) -> dict:
    """读方案，量出三维里的站位关系。"""
    scene = scene_3d(plan, unit)
    width, height = scene["canvas"]
    ground = _ground(scene)

    entries = []
    for figure in scene["figures"]:
        joints = figure["joints"]
        shoulders = [joints["shoulder_l"], joints["shoulder_r"]]
        center_x = (shoulders[0][0] + shoulders[1][0]) / 2
        head = joints["head"]
        feet_y = max(joints["foot_l"][1], joints["foot_r"][1])
        entry = {
            "layer": figure["layer"],
            "height": figure["height"],
            "depth": figure["depth"],
            "z": figure["z"],
            "center_x": center_x,
            "head_y": head[0 + 1],
            "feet_y": feet_y,
            "head_band": _third(head[1], height),
            "body_band": _third(center_x, width),
            "body_ratio": figure["height"] / height if height else 0.0,
            "airborne": feet_y < ground - AIRBORNE_GAP,
            "air_gap": ground - feet_y,
            "issues": [],
        }
        entries.append(entry)

    # 两人之间的高低
    for entry in entries:
        others = [item for item in entries if item["layer"] != entry["layer"]]
        if not others:
            continue
        other = others[0]
        gap = other["head_y"] - entry["head_y"]
        entry["head_gap"] = gap
        if abs(gap) < LEVEL_GAP:
            entry["level"] = "same"
        elif gap > 0:
            entry["level"] = "higher"
        else:
            entry["level"] = "lower"

    # 两件兵器在画平面上交叉，深度差多少
    crossings = []
    props = scene["props"]
    for index, first in enumerate(props):
        for second in props[index + 1:]:
            if not first["holder"] or first["holder"] == second["holder"]:
                continue
            hit = _segment_cross_params(first["ends"][0], first["ends"][1],
                                       second["ends"][0], second["ends"][1])
            if hit is None:
                continue
            point, at_first, at_second = hit
            gap = abs(prop_z_at(first, at_first) - prop_z_at(second, at_second))
            crossing = {
                "props": [first["layer"], second["layer"]],
                "point": point,
                "z_gap": gap,
                "touch": gap <= TOUCH_TOLERANCE,
            }
            crossings.append(crossing)
            if not crossing["touch"]:
                text = ("%s 和 %s 在画上交叉，可两件兵器的深度差 %.0f 像素，"
                        "它们碰不到一起"
                        % (first["layer"], second["layer"], gap))
                for entry in entries:
                    if entry["layer"] in (first["holder"], second["holder"]):
                        entry["issues"].append(text)

    issues = []
    for entry in entries:
        issues.extend(entry["issues"])
        if entry["airborne"] and entry["feet_y"] > height:
            issues.append("%s 的脚底跑出画幅" % entry["layer"])
        if entry["height"] > height:
            issues.append("%s 的身高超过画幅高度" % entry["layer"])
    for crossing in crossings:
        if not crossing["touch"]:
            issues.append(
                "%s 和 %s 在画上交叉，可两件兵器的深度差 %.0f 像素，它们碰不到一起"
                % (crossing["props"][0], crossing["props"][1], crossing["z_gap"]))

    return {
        "canvas": scene["canvas"],
        "unit": unit,
        "ground": ground,
        "z_range": scene["z_range"],
        "characters": entries,
        "props": props,
        "crossings": crossings,
        "issues": issues,
    }


def _scene_text(result: dict, lang: str) -> str:
    """整幅画面的空间关系，一句话。"""
    characters = result["characters"]
    if len(characters) < 2:
        return ""
    parts = []
    first, second = characters[0], characters[1]
    if lang == "zh":
        if abs(first["z"] - second["z"]) > 1:
            near = first if first["z"] < second["z"] else second
            far = second if near is first else first
            parts.append("%s 比 %s 靠近观众 %.0f 像素"
                         % (near["layer"], far["layer"], abs(first["z"] - second["z"])))
        for crossing in result["crossings"]:
            point = crossing["point"]
            parts.append("两件兵器的交叉点在画面%s，"
                         "离画面中心 %s %d 像素"
                         % (_band_text(point[0], result["canvas"][0], lang),
                            _band_text(point[1], result["canvas"][1], lang),
                            abs(point[1] - result["canvas"][1] / 2)))
    else:
        if abs(first["z"] - second["z"]) > 1:
            near = first if first["z"] < second["z"] else second
            far = second if near is first else first
            parts.append("%s stands %.0f pixels nearer to the viewer than %s"
                         % (near["layer"], abs(first["z"] - second["z"]), far["layer"]))
        for crossing in result["crossings"]:
            point = crossing["point"]
            parts.append("the two weapons cross in the %s of the frame, %.0f pixels "
                         "%s the centre"
                         % (_band_text(point[0], result["canvas"][0], lang),
                            abs(point[1] - result["canvas"][1] / 2),
                            "below" if point[1] > result["canvas"][1] / 2 else "above"))
    return "；".join(parts) if lang == "zh" else "; ".join(parts)


def _band_text(value: float, size: float, lang: str) -> str:
    band = _third(value, size)
    if lang == "zh":
        return ("左", "中", "右")[band]
    return ("left", "centre", "right")[band]


def staging_notes(plan: dict, unit: float = DEFAULT_UNIT) -> dict:
    """每个角色层的站位说明，中英文各一句。"""
    result = analyze_plan(plan, unit)
    notes = {}
    for entry in result["characters"]:
        zh_parts = []
        en_parts = []
        zh_parts.append("人在画面%s三分之一" % H_BAND_ZH[entry["body_band"]])
        en_parts.append("in the %s third of the frame" % H_BAND_EN[entry["body_band"]])
        zh_parts.append("头顶在画面%s三分之一" % V_BAND_ZH[entry["head_band"]])
        en_parts.append("head in the %s third of the frame" % V_BAND_EN[entry["head_band"]])
        percent = round(entry["body_ratio"] * 100 / 5) * 5
        zh_parts.append("身子占画幅高度%d%%" % percent)
        en_parts.append("body about %d%% of the frame height" % percent)
        if entry.get("airborne"):
            zh_parts.append("脚不沾地，离地%.0f像素" % entry["air_gap"])
            en_parts.append("feet off the ground, %.0f pixels above the ground"
                            % entry["air_gap"])
        else:
            zh_parts.append("双脚踩在地上")
            en_parts.append("both feet planted on the ground")
        level = entry.get("level")
        if level == "higher":
            zh_parts.append("全身比对手高%.0f像素" % abs(entry["head_gap"]))
            en_parts.append("his whole body %.0f pixels higher than his opponent"
                            % abs(entry["head_gap"]))
        elif level == "lower":
            zh_parts.append("全身比对手低%.0f像素" % abs(entry["head_gap"]))
            en_parts.append("his whole body %.0f pixels lower than his opponent"
                            % abs(entry["head_gap"]))
        notes[entry["layer"]] = {
            "zh": "，".join(zh_parts),
            "en": ", ".join(en_parts),
        }
    return {
        "notes": notes,
        "scene_zh": _scene_text(result, "zh"),
        "scene_en": _scene_text(result, "en"),
        "result": result,
    }


def _view_transform(scene: dict, view: str):
    """视图的坐标换算。返回 (函数, 说明)。"""
    width, height = scene["canvas"]
    low, high = scene["z_range"]
    middle = (low + high) / 2
    if view == "front":
        return (lambda point: (point[0], point[1])), "画平面上的位置"
    if view == "left":
        shift = width / 2 + middle
        return (lambda point: (shift - point[2], point[1])), "左右深浅"
    shift = height / 2 + middle
    return (lambda point: (point[0], shift - point[2])), "上下深浅"


def render_view(plan: dict, view: str, unit: float = DEFAULT_UNIT):
    """一个视图的绘制指令。"""
    if view not in VIEW_NAMES:
        raise ValueError("视图只能是 %s，收到 %s" % ("、".join(VIEW_NAMES), view))
    scene = scene_3d(plan, unit)
    width, height = scene["canvas"]
    palette = resolve_palette(plan.get("palette"))
    ref_width = float(plan.get("ref_width") or width)
    pen = Pen(int(width), int(height), ref_width, palette)
    project, _ = _view_transform(scene, view)

    pen.rect(0, 0, width, height, fill="bg", stroke_width=None, stroke=None,
             name="底色")
    pen.rect(6, 6, width - 12, height - 12, fill=None, stroke_width=2,
             stroke="line", name="画框")

    for index, figure in enumerate(scene["figures"]):
        color = LAYER_COLORS[index % len(LAYER_COLORS)]
        joints = figure["joints"]
        for start, end, width_ratio in BONES:
            a = joints.get(start)
            b = joints.get(end)
            if a is None or b is None:
                continue
            pa = project(a)
            pb = project(b)
            pen.line(pa[0], pa[1], pb[0], pb[1],
                     width=max(1.0, width_ratio * figure["height"]),
                     color=color, name="骨段 %s-%s" % (start, end))
        for name, radius in JOINT_SCALE.items():
            point = joints.get(name)
            if point is None:
                continue
            p = project(point)
            r = max(1.5, radius * figure["height"])
            pen.ellipse(p[0], p[1], r, r, fill=color, stroke_width=None,
                        stroke=None, name="关节 %s" % name)
        head = joints.get("head")
        if head:
            p = project(head)
            r = 0.075 * figure["height"]
            pen.ellipse(p[0], p[1], r * 0.86, r, fill=color, stroke_width=None,
                        stroke=None, name="头")

    for index, prop in enumerate(scene["props"]):
        color = LAYER_COLORS[(index + len(scene["figures"])) % len(LAYER_COLORS)]
        segments = prop.get("segments") or []
        if segments:
            length = math.dist(prop["ends"][0], prop["ends"][1]) or 1.0
            ux = (prop["ends"][1][0] - prop["ends"][0][0]) / length
            uy = (prop["ends"][1][1] - prop["ends"][0][1]) / length
            for segment in segments:
                a = project((prop["ends"][0][0] + ux * length * segment["from"],
                             prop["ends"][0][1] + uy * length * segment["from"],
                             segment["z_from"]))
                b = project((prop["ends"][0][0] + ux * length * segment["to"],
                             prop["ends"][0][1] + uy * length * segment["to"],
                             segment["z_to"]))
                pen.line(a[0], a[1], b[0], b[1],
                         width=max(2.0, prop["span"] * 0.025), color=color,
                         name="兵器 %s" % prop["shape"])
            continue
        a = project((prop["ends"][0][0], prop["ends"][0][1], prop["z"]))
        b = project((prop["ends"][1][0], prop["ends"][1][1], prop["z"]))
        pen.line(a[0], a[1], b[0], b[1],
                 width=max(2.0, prop["span"] * 0.025), color=color,
                 name="兵器 %s" % prop["shape"])

    return pen.commands, {"width": int(width), "height": int(height),
                          "name": "%s %s" % (plan.get("name", "画面"), VIEW_TITLES[view])}


def render_all(plan: dict, out_dir: Path, unit: float = DEFAULT_UNIT) -> list:
    """三张视图各出一张 PNG。"""
    from .engine import Engine

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for view in VIEW_NAMES:
        commands, meta = render_view(plan, view, unit)
        path = out_dir / ("view-%s.png" % view)
        with Engine(read_root=Path.cwd(), write_root=out_dir) as engine:
            engine.new_document(meta["width"], meta["height"], meta["name"],
                                background=meta.get("document_background"))
            for command in commands:
                engine.execute(command["command"], command.get("params") or {})
            engine.save(path)
        written.append(path)
    return written


def report(result: dict) -> str:
    lines = ["人物站位："]
    if not result["characters"]:
        lines.append("  方案里没有人物白模")
    for entry in result["characters"]:
        band = H_BAND_ZH[entry["body_band"]]
        head = V_BAND_ZH[entry["head_band"]]
        state = "腾空，离地 %.0f 像素" % entry["air_gap"] if entry["airborne"] else "双脚踩地"
        lines.append("  %s：画面%s边，头顶在%s，身高占画幅 %.0f%%，%s，"
                     "场景深度 z=%.0f"
                     % (entry["layer"], band, head, entry["body_ratio"] * 100,
                        state, entry["z"]))
    if result["props"]:
        lines.append("")
        lines.append("兵器深度：")
        for prop in result["props"]:
            lines.append("  %s（%s）：z=%.0f，%s"
                         % (prop["layer"], prop["shape"], prop["z"],
                            "在 %s 手里" % prop["holder"] if prop["holder"] else "没人持械"))
    if result["crossings"]:
        lines.append("")
        lines.append("兵器交叉：")
        for crossing in result["crossings"]:
            lines.append("  %s 与 %s 在 (%.0f, %.0f) 交叉，深度差 %.0f 像素，%s"
                         % (crossing["props"][0], crossing["props"][1],
                            crossing["point"][0], crossing["point"][1],
                            crossing["z_gap"],
                            "碰得到" if crossing["touch"] else "碰不到"))
    if result["issues"]:
        lines.append("")
        lines.append("站位提示：")
        for text in result["issues"]:
            lines.append("  " + text)
    return "\n".join(lines)


def run(plan_path, out_dir, unit: float = DEFAULT_UNIT, json_path=None) -> int:
    """量站位，出一张三视图，写结果。命令行和界面走同一段。"""
    plan = load_plan(plan_path)
    result = analyze_plan(plan, unit)
    print(report(result))
    written = render_all(plan, Path(out_dir), unit)
    print("")
    for view, path in zip(VIEW_NAMES, written):
        print("  %s：%s" % (VIEW_TITLES[view], path))
    if json_path:
        Path(json_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
        print("结构化结果：%s" % json_path)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="按三个方向出三视图")
    parser.add_argument("plan", help="绘制方案文件")
    parser.add_argument("--out-dir", default="out", help="输出目录，默认 out")
    parser.add_argument("--unit", type=float, default=DEFAULT_UNIT,
                        help="图层 depth 每差 1 相当于多少像素，默认 %.0f" % DEFAULT_UNIT)
    parser.add_argument("--json", help="结构化结果输出路径")
    args = parser.parse_args(argv)
    return run(args.plan, args.out_dir, args.unit, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
