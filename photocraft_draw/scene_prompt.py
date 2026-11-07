# -*- coding: utf-8 -*-
"""把场景方案编译成给生图模型的提示词。

两种产物：一段整体描述（caption），或者带像素包围盒的 Layout。
Layout 里的每个盒子都由场景里的三维位置投影算出，不是手填的。
"""
from __future__ import annotations

from .mesh import camera_from_dict, mesh_from_dict

CAPTIONS = {
    "blossom": "a pale rose-pink crabapple blossom with five rounded petals, "
               "a shallow notch at each tip and a ring of golden stamens at the heart",
    "bud": "a deep rose crabapple bud with green sepals, closed and rounded",
    "leaf": "a narrow dark green leaf with a fine serrated edge",
    "branch": "a slender brown twig with fine taper and small nodes",
}


def _camera(plan: dict):
    for layer in plan.get("layers", []):
        for component in layer.get("components", []):
            params = component.get("params") or {}
            if "camera" in params:
                return camera_from_dict(params["camera"])
    raise ValueError("方案里没有相机，无法算 Layout")


def _box(points, camera, scale_x, scale_y):
    xs = []
    ys = []
    for point in points:
        projected = camera.project(point)
        xs.append(projected.x * scale_x)
        ys.append(projected.y * scale_y)
    return [min(xs), min(ys), max(xs), max(ys)]


def _sprite_corners(item):
    center = tuple(float(v) for v in item["center"])
    facing = _unit(item.get("facing", (0.0, 0.0, -1.0)))
    radial = _unit(item.get("radial", (0.0, 1.0, 0.0)))
    size = float(item["size"])
    width = float(item.get("width", size * 0.5))
    if item.get("petals"):
        helper = (0.0, 1.0, 0.0) if abs(facing[1]) < 0.9 else (1.0, 0.0, 0.0)
        u = _unit(_cross(helper, facing))
        v = _unit(_cross(facing, u))
        return [_add(center, _add(_mul(u, sx * size), _mul(v, sy * size)))
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    dot = sum(radial[i] * facing[i] for i in range(3))
    grow = _unit(tuple(radial[i] - facing[i] * dot for i in range(3)))
    side = _unit(_cross(facing, grow))
    if item.get("shape") == "bud":
        return [_add(center, _add(_mul(side, sx * width), _mul(grow, sy * size)))
                for sx, sy in ((-0.75, -0.75), (0.75, -0.75), (0.75, 0.75), (-0.75, 0.75))]
    return [_add(center, _add(_mul(side, sx * width), _mul(grow, sy * size)))
            for sx, sy in ((-0.5, 0.0), (0.5, 0.0), (0.5, 1.0), (-0.5, 1.0))]


def _unit(v):
    import math
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _clamp(box, width, height):
    """把框夹进画布；夹完小于两像素就丢掉。"""
    x0 = max(0.0, min(float(width), box[0]))
    y0 = max(0.0, min(float(height), box[1]))
    x1 = max(0.0, min(float(width), box[2]))
    y1 = max(0.0, min(float(height), box[3]))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return [x0, y0, x1, y1]


def layout_from_plan(plan: dict, width: int, height: int, caption: str) -> dict:
    """把方案里的物体逐个投影成像素框，返回 Layout 草稿。"""
    canvas = plan.get("canvas") or [width, height]
    scale_x = width / float(canvas[0])
    scale_y = height / float(canvas[1])
    camera = _camera(plan)
    items = []
    for layer in plan.get("layers", []):
        for component in layer.get("components", []):
            params = component.get("params") or {}
            for item in params.get("items") or []:
                corners = _sprite_corners(item)
                box = _box(corners, camera, scale_x, scale_y)
                kind = "blossom" if item.get("petals") else str(item.get("shape", "petal"))
                label = CAPTIONS.get(kind, CAPTIONS["leaf"])
                if kind == "bud":
                    label = CAPTIONS["bud"]
                box = _clamp(box, width, height)
                if box:
                    items.append({"label": "object", "caption": label,
                                  "bbox": [round(v, 1) for v in box]})
            for mesh_data in params.get("meshes") or []:
                mesh = mesh_from_dict(mesh_data)
                box = _box(mesh.vertices, camera, scale_x, scale_y)
                box = _clamp(box, width, height)
                if box:
                    items.append({"label": "object", "caption": CAPTIONS["branch"],
                                  "bbox": [round(v, 1) for v in box]})
    if not items:
        raise ValueError("方案里没有可以投影的物体")
    return {"width": width, "height": height,
            "bbox_coord_space": "abs", "bbox_format": "xyxy",
            "summary": {"meta": ["botanical illustration", "gongbi"],
                        "canvas": "single", "caption": caption},
            "items": items}


def caption_from_plan(plan: dict) -> str:
    """从方案里读数量与主体，拼一段整体描述。"""
    flowers = buds = leaves = 0
    for layer in plan.get("layers", []):
        for component in layer.get("components", []):
            for item in (component.get("params") or {}).get("items") or []:
                if item.get("petals"):
                    flowers += 1
                elif item.get("shape") == "bud":
                    buds += 1
                elif item.get("shape") == "leaf":
                    leaves += 1
    parts = ["a crabapple branch with %d open blossoms" % flowers]
    if buds:
        parts.append("%d closed buds" % buds)
    if leaves:
        parts.append("%d narrow leaves" % leaves)
    return (", ".join(parts) +
            ", pale rose-pink petals with golden stamens, dark green serrated leaves, "
            "slender brown twigs, pale warm beige paper, traditional Chinese gongbi "
            "flower painting, flat colour planes, fine even outlines, soft diffuse "
            "light, no text, no border")
