# -*- coding: utf-8 -*-
"""接触点分析：在遮挡表之上，给出接触位置、关节归属和穿帮提示。

遮挡分析只说「谁压谁、挡了多少」，看不出「压在哪里」。这一层把每一对部件
的交叠区拆成一片一片，给出质心坐标、面积和范围；再把方案里的关节坐标对
上去，能查出「一件兵器从某只手穿过去了」这类问题。

用法：
    photocraft-draw contact out/a.psd --plan plans/a.json --map out/contact-map.png
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .annotate import read_layers, render_layer_images
from .components.rig import JOINT_SCALE, POSES
from .engine import find_engine
from .occlusion import _alpha_from_src

JOINT_NAMES = tuple(JOINT_SCALE) + ("head",)

# 名字里带这些词的层按「专门画的手形」看待，报夹手时不当成遮住手的部件
HAND_SHAPE_WORDS = ("hand", "手", "grip", "握", "palm")

PRESS = 0.50       # 部件盖住关节圆盘多少算压住
MENTION = 0.25     # 同一处还提一句别的部件的门槛
CROSS_RATIO = 0.40  # 两手压点相距占部件跨度的比例上限
CROWD_RADIUS = 30   # 相距多少像素算挤在一处

# 头部和颈部：前面的道具盖住多少比例算挡住了
PROP_COVER = {"head": 0.40, "neck": 0.45}
# 另一个角色的身体盖住脸到这个比例，脸就看不清了
FACE_COVER = 0.70


def _pose_table(value) -> dict:
    if isinstance(value, str):
        if value not in POSES:
            raise ValueError(f"pose 只能是 {'、'.join(POSES)}")
        return POSES[value]
    if isinstance(value, dict):
        missing = [name for name in JOINT_NAMES if name not in value]
        if missing:
            raise ValueError(f"自定义姿态缺少关节：{'、'.join(missing)}")
        table = {}
        for name in JOINT_NAMES:
            point = value[name]
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError(f"关节 {name} 要写成 [x, y]")
            table[name] = (float(point[0]), float(point[1]))
        return table
    raise ValueError("pose 给姿态名，或者直接给一张关节表")


def _blobs(mask: np.ndarray, min_area: int = 10) -> list[dict]:
    """把布尔掩码拆成一片一片，返回面积、质心坐标和范围。"""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    cells = set(zip(xs.tolist(), ys.tolist()))
    blobs = []
    while cells:
        start = cells.pop()
        queue = deque([start])
        group = [start]
        while queue:
            x, y = queue.popleft()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    neighbour = (x + dx, y + dy)
                    if neighbour in cells:
                        cells.discard(neighbour)
                        queue.append(neighbour)
                        group.append(neighbour)
        if len(group) < min_area:
            continue
        arr = np.array(group)
        x0, y0 = int(arr[:, 0].min()), int(arr[:, 1].min())
        x1, y1 = int(arr[:, 0].max()), int(arr[:, 1].max())
        blobs.append({
            "area": len(group),
            "x": round(float(arr[:, 0].mean()), 1),
            "y": round(float(arr[:, 1].mean()), 1),
            "bbox": [x0, y0, x1 - x0 + 1, y1 - y0 + 1],
        })
    blobs.sort(key=lambda item: -item["area"])
    return blobs


def _layer_masks(psd_path: Path, tmp_dir: Path | None):
    """取出每层的透明掩码。返回 (宽, 高, 层序, 掩码表)。

    层序按引擎给出的顺序，从前到后：第一个在最上面。
    """
    width, height, _ = read_layers(psd_path)
    work = tmp_dir or psd_path.parent / "_contact"
    work.mkdir(parents=True, exist_ok=True)
    rendered = render_layer_images(psd_path, work)
    masks = {}
    for item in rendered:
        mask = _alpha_from_src(item.get("src") or "")
        if mask is not None:
            masks[item["name"]] = mask
    order = [name for name in (item["name"] for item in rendered) if name in masks]
    return width, height, order, masks


def _background_layers(masks: dict, width: int, height: int) -> set:
    """铺满整张画布的层是底色，不参与接触统计。"""
    full = width * height
    return {name for name, mask in masks.items()
            if full and mask.sum() >= full * 0.98}


def _figures(plan: dict, width: int) -> list[dict]:
    """把方案里每个人物白模拆出来，带上关节表和画布比例。"""
    ref_width = plan.get("ref_width", 800)
    scale = width / float(ref_width)
    figures = []
    for layer in plan.get("layers") or []:
        layer_name = layer.get("name", "")
        rigs = [item for item in layer.get("components") or []
                if item.get("component") == "figure_rig"]
        for number, item in enumerate(rigs, 1):
            params = item.get("params") or {}
            table = _pose_table(params.get("pose", "stand"))
            if params.get("flip"):
                table = {name: (-x, y) for name, (x, y) in table.items()}
            ox, oy = float(params["root"][0]), float(params["root"][1])
            height = float(params["height"])
            label = layer_name if len(rigs) <= 1 else f"{layer_name}第{number}个"
            figures.append({
                "layer": layer_name,
                "figure": number,
                "label": label,
                "table": table,
                "ox": ox,
                "oy": oy,
                "height": height,
                "scale": scale,
            })
    return figures


def _plan_joints(plan: dict, width: int) -> list[dict]:
    """从方案里反算每个人物的关节画布坐标。"""
    joints = []
    for fig in _figures(plan, width):
        scale = fig["scale"]
        height = fig["height"]
        for name, (x, y) in fig["table"].items():
            joints.append({
                "layer": fig["layer"],
                "figure": fig["figure"],
                "label": fig["label"],
                "joint": name,
                "x": round((fig["ox"] + x * height) * scale, 1),
                "y": round((fig["oy"] + y * height) * scale, 1),
                "radius": round(JOINT_SCALE.get(name, 0.04) * height * scale, 1),
            })
    return joints


def _plan_regions(plan: dict, width: int) -> list[dict]:
    """每个人物的头部椭圆和脖子圆盘，画布坐标。

    头部椭圆按白模组件画法算：半径是身高的 0.075，横向收到 0.86，
    中心比头关节点高 0.35 个半径。脖子按关节圆盘算，半径是身高的 0.045。
    """
    regions = []
    for fig in _figures(plan, width):
        scale = fig["scale"]
        height = fig["height"]
        table = fig["table"]
        hx, hy = table["head"]
        ry = 0.075 * height * scale
        regions.append({
            "layer": fig["layer"],
            "label": fig["label"],
            "part": "head",
            "x": (fig["ox"] + hx * height) * scale,
            "y": (fig["oy"] + hy * height) * scale - ry * 0.35,
            "rx": ry * 0.86,
            "ry": ry,
        })
        nx, ny = table["neck"]
        radius = 0.045 * height * scale
        regions.append({
            "layer": fig["layer"],
            "label": fig["label"],
            "part": "neck",
            "x": (fig["ox"] + nx * height) * scale,
            "y": (fig["oy"] + ny * height) * scale,
            "rx": radius,
            "ry": radius,
        })
    return regions


_DISKS: dict[int, np.ndarray] = {}


def _disk(radius: int) -> np.ndarray:
    if radius not in _DISKS:
        ys, xs = np.mgrid[-radius:radius + 1, -radius:radius + 1]
        _DISKS[radius] = (xs * xs + ys * ys) <= radius * radius
    return _DISKS[radius]


def _joint_hits(joints: list[dict], masks: dict, order: list[str]) -> list[dict]:
    """每个关节压住哪些部件，以及压住多少。

    side 分三种：own 是角色自己这一层，front 在角色前面，back 在角色后面。
    """
    index_of = {name: index for index, name in enumerate(order)}
    for joint in joints:
        hits = []
        radius = max(1, int(round(joint["radius"])))
        cx, cy = int(round(joint["x"])), int(round(joint["y"]))
        own = index_of.get(joint["layer"], 0)
        for name, mask in masks.items():
            height, width = mask.shape
            x0, x1 = max(0, cx - radius), min(width, cx + radius + 1)
            y0, y1 = max(0, cy - radius), min(height, cy + radius + 1)
            if x1 <= x0 or y1 <= y0:
                continue
            patch = mask[y0:y1, x0:x1]
            disk = _disk(radius)[y0 - (cy - radius):y1 - (cy - radius),
                               x0 - (cx - radius):x1 - (cx - radius)]
            total = float(disk.sum())
            if total <= 0:
                continue
            coverage = float((patch & disk).sum()) / total
            if coverage < 0.02:
                continue
            here = index_of.get(name, 0)
            hits.append({
                "part": name,
                "coverage": round(coverage, 3),
                "side": "own" if here == own else ("front" if here < own else "back"),
            })
        hits.sort(key=lambda item: -item["coverage"])
        joint["hits"] = hits
    return joints


def _span(mask: np.ndarray) -> float:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return 0.0
    box_w = int(xs.max() - xs.min()) + 1
    box_h = int(ys.max() - ys.min()) + 1
    return math.hypot(box_w, box_h)


def _components(mask: np.ndarray) -> list[int]:
    """连通块的面积，从大到小。"""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    cells = set(zip(xs.tolist(), ys.tolist()))
    areas = []
    while cells:
        start = cells.pop()
        queue = deque([start])
        area = 0
        while queue:
            x, y = queue.popleft()
            area += 1
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    neighbour = (x + dx, y + dy)
                    if neighbour in cells:
                        cells.discard(neighbour)
                        queue.append(neighbour)
        areas.append(area)
    areas.sort(reverse=True)
    return areas


def _region_hit(region: dict, mask: np.ndarray) -> dict:
    """这一层盖住区域多少，以及有没有从中间把区域断开。

    断开指这一层横穿区域中间，把区域分成两半。只压掉边上一小片不算，
    那种读起来就是压在边上。
    """
    height, width = mask.shape
    rx = max(1.0, region["rx"])
    ry = max(1.0, region["ry"])
    x0 = max(0, int(region["x"] - rx) - 1)
    x1 = min(width, int(region["x"] + rx) + 2)
    y0 = max(0, int(region["y"] - ry) - 1)
    y1 = min(height, int(region["y"] + ry) + 2)
    if x1 <= x0 or y1 <= y0:
        return {"coverage": 0.0, "cut": False}
    ys, xs = np.mgrid[y0:y1, x0:x1]
    inside = ((xs - region["x"]) / rx) ** 2 + ((ys - region["y"]) / ry) ** 2 <= 1.0
    total = float(inside.sum())
    if total <= 0:
        return {"coverage": 0.0, "cut": False}
    patch = mask[y0:y1, x0:x1]
    covered = float(np.logical_and(patch, inside).sum())
    areas = _components(np.logical_and(inside, ~patch))
    cut = bool(len(areas) >= 2 and areas[1] >= total * 0.15 and covered >= total * 0.03)
    return {"coverage": covered / total, "cut": cut}


def _region_coverage(region: dict, mask: np.ndarray) -> float:
    """区域被这一层盖住的比例。"""
    height, width = mask.shape
    rx = max(1.0, region["rx"])
    ry = max(1.0, region["ry"])
    x0 = max(0, int(region["x"] - rx))
    x1 = min(width, int(region["x"] + rx) + 1)
    y0 = max(0, int(region["y"] - ry))
    y1 = min(height, int(region["y"] + ry) + 1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    ys, xs = np.mgrid[y0:y1, x0:x1]
    inside = ((xs - region["x"]) / rx) ** 2 + ((ys - region["y"]) / ry) ** 2 <= 1.0
    total = float(inside.sum())
    if total <= 0:
        return 0.0
    covered = float(np.logical_and(mask[y0:y1, x0:x1], inside).sum())
    return covered / total


def _plan_props(plan: dict) -> dict:
    """每层的道具形状名，以及道具是不是排在身体之后。

    同一个层里组件按顺序排，后排的压在前排上面。兵器排在身体后面，
    兵器就压在身体前面。
    """
    props = {}
    for layer in plan.get("layers") or []:
        name = layer.get("name", "")
        names = set()
        after_body = False
        seen_body = False
        for item in layer.get("components") or []:
            kind = item.get("component")
            if kind == "custom_shape":
                shape_name = (item.get("params") or {}).get("name")
                if shape_name:
                    names.add(shape_name)
                if seen_body:
                    after_body = True
            elif kind == "figure_rig":
                seen_body = True
        props[name] = {"names": names, "after_body": after_body}
    return props


def _shape_index(psd_path: Path) -> list[dict]:
    """列出文件里所有形状：所属顶层层、名字、范围、编号。"""
    cli = find_engine()
    result = subprocess.run([str(cli), "info", str(psd_path)],
                            capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    shapes = []
    for top in data.get("layers") or []:
        layer_name = top.get("name") or ""
        stack = [top]
        while stack:
            node = stack.pop()
            if node.get("kind") == "Shape":
                shapes.append({
                    "layer": layer_name,
                    "name": node.get("name") or "",
                    "id": node.get("id"),
                    "bounds": node.get("bounds"),
                })
                continue
            for child in node.get("children") or []:
                stack.append(child)
    return shapes


def _alpha_from_file(path: Path):
    """读一张 PNG，取不透明区域。"""
    try:
        image = Image.open(path).convert("RGBA")
    except OSError:
        return None
    return np.asarray(image)[..., 3] > 24


def _render_shapes(psd_path: Path, tmp_dir: Path, wanted: list[dict],
                   all_ids: list) -> dict:
    """把指定形状单独渲染出来，取各自的透明区域。"""
    cli = find_engine()
    work = Path(tmp_dir) / "_shapes"
    work.mkdir(parents=True, exist_ok=True)
    out = {}
    for shape in wanted:
        args = [str(cli), "run", str(psd_path)]
        for other in all_ids:
            if other == shape["id"]:
                continue
            args += ["--cmd", "layer.setProps", "--params",
                     json.dumps({"layer": other, "visible": False})]
        target = work / f"{shape['id']}.png"
        args += ["--out", str(target)]
        subprocess.run(args, capture_output=True, check=True)
        mask = _alpha_from_file(target)
        if mask is not None:
            out[shape["id"]] = mask
    return out


def _bounds_overlap(bounds, region: dict) -> bool:
    """形状的范围和区域有没有交叠。"""
    if not bounds:
        return False
    x, y, w, h = bounds
    return not (x > region["x"] + region["rx"] or x + w < region["x"] - region["rx"]
                or y > region["y"] + region["ry"] or y + h < region["y"] - region["ry"])


def _region_hazards(regions, order, masks, props, shapes,
                    psd_path: Path, tmp_dir: Path) -> list[dict]:
    """头部和颈部的穿帮检查。

    分辨到形状一级：兵器横穿头部读作穿帮，另一个角色的身体压上来读作遮脸。
    """
    index_of = {name: index for index, name in enumerate(order)}
    by_layer = {}
    for shape in shapes:
        by_layer.setdefault(shape["layer"], []).append(shape)
    all_ids = [shape["id"] for shape in shapes]

    plans = []
    wanted = {}
    for region in regions:
        own_index = index_of.get(region["layer"], 0)
        picks = []
        for layer_name, layer_shapes in by_layer.items():
            here = index_of.get(layer_name, 0)
            info = props.get(layer_name, {"names": set(), "after_body": False})
            if here == own_index:
                if not info["after_body"]:
                    continue
                candidates = [item for item in layer_shapes
                              if item["name"] in info["names"]]
            elif here < own_index:
                candidates = layer_shapes
            else:
                continue
            mask = masks.get(layer_name)
            if mask is not None:
                rough = _region_hit(region, mask)
                if rough["coverage"] < 0.02 and not rough["cut"]:
                    continue
            for shape in candidates:
                if not _bounds_overlap(shape["bounds"], region):
                    continue
                picks.append(shape)
                wanted[shape["id"]] = shape
        plans.append((region, picks))

    if not wanted:
        return []
    rendered = _render_shapes(psd_path, tmp_dir, list(wanted.values()), all_ids)

    notes = []
    for region, picks in plans:
        best = {}
        for shape in picks:
            mask = rendered.get(shape["id"])
            if mask is None:
                continue
            hit = _region_hit(region, mask)
            if hit["coverage"] < 0.02 and not hit["cut"]:
                continue
            info = props.get(shape["layer"], {"names": set()})
            is_prop = shape["name"] in info["names"]
            key = (shape["layer"], is_prop)
            current = best.get(key)
            if current is None or (hit["cut"] and not current["hit"]["cut"]) \
                    or hit["coverage"] > current["hit"]["coverage"]:
                best[key] = {"shape": shape, "hit": hit, "is_prop": is_prop}
        for (layer_name, is_prop), item in best.items():
            hit = item["hit"]
            shape = item["shape"]
            part_name = "头部" if region["part"] == "head" else "脖子"
            where = f"{region['x']:.0f}, {region['y']:.0f}"
            bounds = shape["bounds"]
            if bounds:
                spot = (f"{bounds[0] + bounds[2] // 2}, "
                        f"{bounds[1] + bounds[3] // 2}")
            else:
                spot = "位置不明"
            same_layer = layer_name == region["layer"]
            side = "本层" if same_layer else "前面"
            if is_prop:
                if not hit["cut"] and hit["coverage"] < PROP_COVER[region["part"]]:
                    continue
                kind = "穿头" if region["part"] == "head" else "穿颈"
                if hit["cut"]:
                    reason = (f"{side}的兵器 {shape['name']}（{spot}）"
                              f"从中间横穿 {part_name}")
                else:
                    reason = (f"{side}的兵器 {shape['name']}（{spot}）"
                              f"盖住 {hit['coverage'] * 100:.0f}%")
            else:
                if hit["coverage"] < FACE_COVER:
                    continue
                kind = "遮脸" if region["part"] == "head" else "遮颈"
                reason = (f"{side} {layer_name} 的身体盖住 "
                          f"{hit['coverage'] * 100:.0f}%")
            notes.append({
                "kind": kind,
                "x": region["x"], "y": region["y"],
                "text": f"{region['label']} 的 {part_name}（{where}）{reason}",
            })
    return notes

def _hazards(joints: list[dict], masks: dict, contacts: list[dict],
             layers: list[str], canvas_area: int,
             crowd_radius: int = CROWD_RADIUS) -> list[dict]:
    """穿帮提示：夹手、疑似穿手、挤在一处。"""
    notes = []
    # 最后那一层是底板，占画面很大一块的场景层也不参与「挤在一处」
    backdrop = set(layers[-1:]) if layers else set()
    for name, mask in masks.items():
        if canvas_area and mask.sum() >= canvas_area * 0.25:
            backdrop.add(name)

    # 一、一只手同时被两件以上前层部件压住
    for joint in joints:
        if joint["joint"] not in ("hand_l", "hand_r"):
            continue
        pressed = [h for h in joint.get("hits") or []
                   if h["side"] == "front" and h["coverage"] >= PRESS
                   and not _is_hand_shape(h["part"])]
        if len(pressed) < 2:
            continue
        behind = [h for h in joint.get("hits") or []
                  if h["side"] == "back" and h["coverage"] >= MENTION]
        detail = "、".join(f"{h['part']} {h['coverage'] * 100:.0f}%" for h in pressed)
        tail = ("，后面还有 " + "、".join(f"{h['part']} {h['coverage'] * 100:.0f}%"
                                          for h in behind)) if behind else ""
        notes.append({
            "kind": "夹手",
            "x": joint["x"], "y": joint["y"],
            "text": (f"{joint['label']} 的 {joint['joint']}（{joint['x']:.0f}, "
                     f"{joint['y']:.0f}）同时被前面的 {detail} 共 {len(pressed)} 件压住"
                     f"{tail}，这一带多半有一件兵器不该穿过这只手"),
        })

    # 二、同一角色的两只手压在同一部件上。只看角色前面的部件：
    # 后面的部件挡不住手，前面的部件挡得住，穿帮都出在前面的部件上
    grouped: dict[tuple, list[dict]] = {}
    for joint in joints:
        if joint["joint"] not in ("hand_l", "hand_r"):
            continue
        for hit in joint.get("hits") or []:
            if hit["side"] != "front" or hit["coverage"] < PRESS:
                continue
            grouped.setdefault((joint["layer"], hit["part"]), []).append(joint)
    for (layer_name, part), group in grouped.items():
        if len(group) < 2:
            continue
        first, second = group[0], group[1]
        distance = math.hypot(first["x"] - second["x"], first["y"] - second["y"])
        span = _span(masks.get(part)) if part in masks else 0.0
        ratio = distance / span if span else 1.0
        if ratio >= CROSS_RATIO:
            continue
        others = []
        for joint in group:
            for hit in joint.get("hits") or []:
                if hit["part"] != part and hit["side"] == "front" \
                        and hit["coverage"] >= MENTION:
                    others.append(hit["part"])
        extra = "、".join(sorted(set(others))) or "无"
        notes.append({
            "kind": "疑似穿手",
            "x": round((first["x"] + second["x"]) / 2, 1),
            "y": round((first["y"] + second["y"]) / 2, 1),
            "text": (f"{first['label']} 的 {first['joint']} 与 {second['label']} 的 "
                     f"{second['joint']} 都压在 {part} 上，两点相距 {distance:.0f} 像素，"
                     f"占该部件跨度 {span:.0f} 像素的 {ratio * 100:.0f}%；"
                     f"这一带还压着 {extra}"),
        })

    # 三、几个部件挤在同一处
    spots = []
    for pair in contacts:
        for spot in pair["spots"]:
            spots.append((spot, pair["upper"], pair["lower"]))
    clusters: list[list[int]] = []
    for index, (spot, _, _) in enumerate(spots):
        placed = False
        for cluster in clusters:
            head = spots[cluster[0]][0]
            if math.hypot(spot["x"] - head["x"], spot["y"] - head["y"]) <= crowd_radius:
                cluster.append(index)
                placed = True
                break
        if not placed:
            clusters.append([index])
    for cluster in clusters:
        parts = []
        for index in cluster:
            spot, upper, lower = spots[index]
            for name in (upper, lower):
                if name in backdrop:
                    continue
                if name not in parts:
                    parts.append(name)
        if len(parts) < 3:
            continue
        spot = spots[cluster[0]][0]
        notes.append({
            "kind": "挤在一处",
            "x": spot["x"], "y": spot["y"],
            "text": (f"（{spot['x']:.0f}, {spot['y']:.0f}）一带挤着 {len(parts)} 个部件："
                     f"{'、'.join(parts)}"),
        })

    return notes


def analyze(psd_path: Path, plan_path: Path | None = None,
            tmp_dir: Path | None = None, min_area: int = 10) -> dict:
    """读分层文件，算出接触位置、关节归属和穿帮提示。"""
    psd_path = Path(psd_path).resolve()
    width, height, order, masks = _layer_masks(psd_path, tmp_dir)
    background = _background_layers(masks, width, height)
    parts = [name for name in order if name not in background]
    part_masks = {name: masks[name] for name in parts}

    contacts = []
    number = 0
    for upper_index, upper in enumerate(parts):
        for lower in parts[upper_index + 1:]:
            inter = np.logical_and(masks[upper], masks[lower])
            total = int(inter.sum())
            if total <= 0:
                continue
            upper_area = int(masks[upper].sum())
            lower_area = int(masks[lower].sum())
            spots = _blobs(inter, min_area)
            for spot in spots:
                number += 1
                spot["number"] = number
            contacts.append({
                "upper": upper,
                "lower": lower,
                "pixels": total,
                "ratio_upper": round(total / max(upper_area, 1), 4),
                "ratio_lower": round(total / max(lower_area, 1), 4),
                "spots": spots,
            })
    contacts.sort(key=lambda item: -item["pixels"])

    joints = []
    hazards = []
    regions = []
    if plan_path:
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        joints = _joint_hits(_plan_joints(plan, width), part_masks, order)
        regions = _plan_regions(plan, width)
        work = Path(tmp_dir) if tmp_dir else psd_path.parent / "_contact"
        hazards = _hazards(joints, part_masks, contacts, parts, width * height)
        hazards += _region_hazards(regions, order, part_masks,
                                   _plan_props(plan), _shape_index(psd_path),
                                   psd_path, work)

    return {
        "canvas": [width, height],
        "layers": parts,
        "areas": {name: int(masks[name].sum()) for name in parts},
        "background": sorted(background),
        "contacts": contacts,
        "joints": joints,
        "regions": regions,
        "hazards": hazards,
        "_masks": part_masks,
        "_order": order,
    }


def public(result: dict) -> dict:
    """去掉内部数据，留可以存成 JSON 的部分。"""
    return {key: value for key, value in result.items() if not key.startswith("_")}


def report(result: dict) -> str:
    lines = [f"画布 {result['canvas'][0]}x{result['canvas'][1]} | "
             f"{len(result['layers'])} 个部件层"]
    if result.get("background"):
        lines.append("底色不计：" + "、".join(result["background"]))
    lines.append("层序（前 → 后）：" + " → ".join(result["layers"]))

    lines.append("")
    lines.append("接触点（上面 压 下面），编号和显露图上的圈一致：")
    if not result["contacts"]:
        lines.append("  没有接触")
    for item in result["contacts"]:
        lines.append(f"  {item['upper']} 压 {item['lower']}：{item['pixels']} 像素，"
                     f"占下层 {item['ratio_lower'] * 100:.1f}%，{len(item['spots'])} 处")
        for spot in item["spots"]:
            x0, y0, w, h = spot["bbox"]
            lines.append(f"     [{spot['number']}] ({spot['x']}, {spot['y']}) "
                         f"面积 {spot['area']} 范围 {x0},{y0} 到 {x0 + w - 1},{y0 + h - 1}")

    lines.append("")
    lines.append("关节归属：")
    for joint in result["joints"]:
        hits = joint.get("hits") or []
        front = [h for h in hits if h["side"] == "front"]
        back = [h for h in hits if h["side"] == "back"]
        if not front and not back:
            continue
        lines.append(f"  {joint['label']} {joint['joint']} "
                     f"({joint['x']:.0f}, {joint['y']:.0f})")
        if front:
            lines.append("     前层：" + "、".join(
                f"{h['part']} {h['coverage'] * 100:.0f}%" for h in front))
        if back:
            lines.append("     后层：" + "、".join(
                f"{h['part']} {h['coverage'] * 100:.0f}%" for h in back))

    if result["hazards"]:
        lines.append("")
        lines.append("穿帮提示：")
        for note in result["hazards"]:
            lines.append(f"  [{note['kind']}] {note['text']}")
    return "\n".join(lines)


PALETTE = [
    (255, 92, 92), (86, 214, 118), (86, 156, 255), (255, 196, 66),
    (206, 116, 255), (72, 224, 224), (255, 132, 196), (188, 226, 96),
    (255, 168, 72), (150, 176, 255), (240, 120, 160), (120, 220, 190),
]


def _is_hand_shape(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in HAND_SHAPE_WORDS)


def _font(size: int):
    for name in ("msyh.ttc", "msyh.ttf", "arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_composite(psd_path: Path, out_path: Path) -> Path | None:
    """让引擎把分层文件合成一张 PNG，当显露图的底图。"""
    try:
        cli = find_engine()
    except Exception:
        return None
    try:
        subprocess.run([str(cli), "run", str(psd_path), "--out", str(out_path)],
                       capture_output=True, check=True)
    except Exception:
        return None
    return out_path if out_path.exists() else None


def write_map(result: dict, out_path: Path, base_image: Path | None = None) -> Path:
    """生成遮挡显露图：接触区用上面那层的颜色填，质心画圈并编号。"""
    width, height = result["canvas"]
    if base_image and Path(base_image).exists():
        base = Image.open(base_image).convert("RGB").resize((width, height))
        canvas = np.asarray(base).astype(np.float32)
    else:
        canvas = np.zeros((height, width, 3), dtype=np.float32)
        canvas[:, :] = 30
    gray = canvas.mean(axis=2)
    canvas = np.dstack([gray * 0.46, gray * 0.46, gray * 0.52])

    order = result["layers"]
    masks = result.get("_masks") or {}
    colors = {name: PALETTE[index % len(PALETTE)] for index, name in enumerate(order)}

    texts = []
    for pair in result["contacts"]:
        upper, lower = pair["upper"], pair["lower"]
        inter = np.logical_and(masks[upper], masks[lower]) if masks else None
        tint = np.array(colors.get(upper, (255, 255, 255)), dtype=np.float32)
        color = tuple(int(value) for value in tint)
        for spot in pair["spots"]:
            x0, y0, w, h = spot["bbox"]
            if inter is not None:
                region = canvas[y0:y0 + h, x0:x0 + w]
                patch = inter[y0:y0 + h, x0:x0 + w]
                region[patch] = region[patch] * 0.30 + tint * 0.70
            _draw_box(canvas, x0, y0, x0 + w, y0 + h, color)
            cx, cy = int(spot["x"]), int(spot["y"])
            _draw_ring(canvas, cx, cy, 20, color)
            texts.append((f"[{spot['number']}]", cx + 24, cy - 9, color))

    for note in result.get("hazards") or []:
        cx, cy = int(note["x"]), int(note["y"])
        _draw_ring(canvas, cx, cy, 36, (255, 64, 64))
        _draw_disc(canvas, cx, cy, 15, (255, 64, 64))
        texts.append(("!", cx - 6, cy - 10, (255, 255, 255)))

    image = Image.fromarray(canvas.clip(0, 255).astype(np.uint8))
    font = _font(max(13, min(width, height) // 70))

    # 图例底板，保证浅色底图上也读得清
    label_width = 0
    for name in order:
        label_width = max(label_width, int(draw_length(font, name)))
    panel = [8, 8, 56 + label_width, 16 + len(order) * 26]
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle(panel, fill=(8, 10, 14, 185))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(image)
    for text, x, y, color in texts:
        draw.text((x, y), text, fill=color, font=font)
    legend_top = 14
    for name in order:
        draw.rectangle([16, legend_top, 40, legend_top + 20], fill=colors[name])
        draw.text((48, legend_top + 2), name, fill=(235, 235, 235), font=font)
        legend_top += 26

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    return out_path


def draw_length(font, text: str) -> int:
    """量一段文字的宽度，量不到就按字数估。"""
    try:
        from PIL import ImageFont
        if hasattr(font, "getlength"):
            return font.getlength(text)
    except Exception:
        pass
    return len(text) * 10


def _draw_rect(canvas, x0, y0, x1, y1, color) -> None:
    height, width = canvas.shape[:2]
    x0, x1 = max(0, x0), min(width, x1)
    y0, y1 = max(0, y0), min(height, y1)
    if x1 <= x0 or y1 <= y0:
        return
    canvas[y0:y1, x0:x1] = color


def _draw_box(canvas, x0, y0, x1, y1, color) -> None:
    _draw_rect(canvas, x0, y0, x1, y0 + 3, color)
    _draw_rect(canvas, x0, y1 - 3, x1, y1, color)
    _draw_rect(canvas, x0, y0, x0 + 3, y1, color)
    _draw_rect(canvas, x1 - 3, y0, x1, y1, color)


def _draw_disc(canvas, cx, cy, radius, color) -> None:
    height, width = canvas.shape[:2]
    ys, xs = np.mgrid[0:height, 0:width]
    inside = ((xs - cx) ** 2 + (ys - cy) ** 2) <= radius * radius
    canvas[inside] = color


def _draw_ring(canvas, cx, cy, radius, color) -> None:
    height, width = canvas.shape[:2]
    for angle in range(0, 360, 3):
        rad = math.radians(angle)
        x = int(cx + math.cos(rad) * radius)
        y = int(cy + math.sin(rad) * radius)
        if 0 <= x < width and 0 <= y < height:
            canvas[y, x] = color


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="分析分层文件的接触位置与关节归属")
    parser.add_argument("psd")
    parser.add_argument("--plan", help="绘制方案文件，用来查关节归属")
    parser.add_argument("--map", help="遮挡显露图输出路径")
    parser.add_argument("--json", help="结构化结果输出路径")
    parser.add_argument("--tmp", help="临时目录")
    args = parser.parse_args(argv)
    result = analyze(Path(args.psd), Path(args.plan) if args.plan else None,
                     Path(args.tmp) if args.tmp else None)
    print(report(result))
    if args.map:
        print(f"显露图：{write_map(result, Path(args.map))}")
    if args.json:
        Path(args.json).write_text(json.dumps(public(result), ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
