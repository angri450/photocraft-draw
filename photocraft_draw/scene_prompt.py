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

# 网格按形状给出默认描述，写方案时不用逐个手写；写了 caption 就用写的那个。
MESH_CAPTIONS = {
    "sweep": "a slender brown tapered stem with small nodes",
    "capsule": "an elongated rounded form",
    "lathe": "a turned ceramic vessel with a narrow neck",
    "box": "a flat rectangular panel",
    "plane": "a flat rectangular panel",
    "sphere": "a smooth round fruit",
    "cylinder": "a straight cylindrical column",
    "cone": "a tapered cone",
}


def _rect(value):
    """[x, y, 宽, 高] 转成 [x0, y0, x1, y1]；不是合格的矩形就返回空。"""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x, y, w, h = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return [x, y, x + w, y + h]


def _rects(value):
    """一个矩形或者一组矩形，统一成 xyxy 列表。"""
    if not isinstance(value, (list, tuple)) or not value:
        return []
    if isinstance(value[0], (list, tuple)):
        found = [_rect(item) for item in value]
        return [box for box in found if box]
    single = _rect(value)
    return [single] if single else []


def _tree_boxes(params):
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        return []
    try:
        x, y = float(root[0]), float(root[1])
        height = float(params.get("height", 400))
        crown = float(params.get("crown", 0.225))
    except (TypeError, ValueError):
        return []
    half = height * (crown + 0.12)   # 树冠半径，再放一点枝条外倾
    return [([x - half, y - height, x + half, y],
             "a flowering crabapple tree with a full round crown")]


def _rock_boxes(params):
    return [(box, "a low mossy rock") for box in _rects(params.get("rocks"))]


def _window_boxes(params):
    return [(box, "a tall arched window with mullions and warm light")
            for box in _rects(params.get("windows"))]


def _table_boxes(params):
    return [(box, "a long banquet table with a pale linen cloth")
            for box in _rects(params.get("table"))]


def _tapestry_boxes(params):
    return [(box, "a hanging tapestry with soft folds")
            for box in _rects(params.get("tapestries"))]


# 老组件用屏幕坐标画，没有相机可投影。这里按各自的参数报出占位矩形，
# 只报看得见的物体，墙、地、天顶这类结构面不报，免得把主体盖住。
COMPONENT_LAYOUT = {
    "crabapple_tree": _tree_boxes,
    "foreground_rocks": _rock_boxes,
    "arched_windows": _window_boxes,
    "long_table": _table_boxes,
    "indoor_backdrop": _tapestry_boxes,
}

COMPONENT_SUBJECTS = {
    "crabapple_tree": ("flowering crabapple tree", "flowering crabapple trees"),
    "foreground_rocks": ("mossy rock", "mossy rocks"),
    "arched_windows": ("arched window", "arched windows"),
    "long_table": ("banquet table", "banquet tables"),
    "indoor_backdrop": ("tapestry", "tapestries"),
}


def _camera(plan: dict):
    for layer in plan.get("layers", []):
        for component in layer.get("components", []):
            params = component.get("params") or {}
            if "camera" in params:
                return camera_from_dict(params["camera"])
    raise ValueError("方案里没有相机，无法算 Layout")


def _needs_camera(plan: dict) -> bool:
    """只有网格和有机形状要用相机投影；老组件自己就有屏幕坐标。"""
    for layer in plan.get("layers", []):
        for component in layer.get("components", []):
            params = component.get("params") or {}
            if params.get("items") or params.get("meshes"):
                return True
    return False


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


def _meta(plan: dict) -> list:
    """画种按场景里有什么定，别让静物和风景也顶着花鸟画的标签。"""
    kinds = caption_from_plan(plan).lower()
    if "blossom" in kinds:
        return ["botanical illustration", "gongbi"]
    if "tree" in kinds or "grove" in kinds:
        return ["landscape painting", "gongbi"]
    if "building" in kinds or "street" in kinds:
        return ["night scene", "gongbi"]
    if "interior" in kinds:
        return ["interior scene", "gongbi"]
    return ["still life", "gongbi"]


def layout_from_plan(plan: dict, width: int, height: int, caption: str) -> dict:
    """把方案里的物体逐个投影成像素框，返回 Layout 草稿。"""
    canvas = plan.get("canvas") or [width, height]
    scale_x = width / float(canvas[0])
    scale_y = height / float(canvas[1])
    camera = _camera(plan) if _needs_camera(plan) else None
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
                if mesh_data.get("layout") is False:
                    continue   # 背景板和桌面这种，出图要，但不该占提示词的框
                mesh = mesh_from_dict(mesh_data)
                box = _box(mesh.vertices, camera, scale_x, scale_y)
                box = _clamp(box, width, height)
                if box:
                    kind = str(mesh_data.get("type", "sweep"))
                    label = mesh_data.get("caption") or MESH_CAPTIONS.get(
                        kind, MESH_CAPTIONS["sweep"])
                    size = mesh_data.get("size") or []
                    if kind in ("box", "plane") and len(size) == 3 and isinstance(size, list):
                        # 又宽又薄的写板子，又高又窄的写柱子，别把墙说成果子
                        wide, tall, deep = (float(v) for v in size)
                        if tall > wide * 1.6 and tall > deep * 1.6:
                            label = "a tall flat panel standing upright"
                    items.append({"label": "object", "caption": label,
                                  "bbox": [round(v, 1) for v in box]})
            report = COMPONENT_LAYOUT.get(str(component.get("component")))
            if report and not params.get("items") and not params.get("meshes"):
                factor = width / float(plan.get("ref_width", 800))
                for rect, label in report(params):
                    box = _clamp([rect[0] * factor, rect[1] * factor,
                                  rect[2] * factor, rect[3] * factor], width, height)
                    if box:
                        items.append({"label": "object", "caption": label,
                                      "bbox": [round(v, 1) for v in box]})
    if not items:
        raise ValueError("方案里没有可以投影的物体")
    return {"width": width, "height": height,
            "bbox_coord_space": "abs", "bbox_format": "xyxy",
            "summary": {"meta": _meta(plan),
                        "canvas": "single", "caption": caption},
            "items": items}


SUBJECT_NAMES = {
    "sweep": ("tapered stem", "tapered stems"),
    "lathe": ("turned vessel", "turned vessels"),
    "sphere": ("round fruit", "round fruits"),
    "box": ("rectangular panel", "rectangular panels"),
    "plane": ("rectangular panel", "rectangular panels"),
    "cylinder": ("cylindrical column", "cylindrical columns"),
    "cone": ("tapered cone", "tapered cones"),
    "capsule": ("rounded form", "rounded forms"),
}

STYLE = ("pale warm beige paper, flat colour planes, fine even outlines, "
         "soft diffuse light, no text, no border")


def caption_from_plan(plan: dict) -> str:
    """从方案里读数量与主体，拼一段整体描述；方案顶层写了 caption 就直接用。"""
    if plan.get("caption"):
        return str(plan["caption"])

    flowers = buds = leaves = 0
    shapes = {}
    subjects = {}
    components = {}
    for layer in plan.get("layers", []):
        for component in layer.get("components", []):
            params = component.get("params") or {}
            for item in params.get("items") or []:
                if item.get("petals"):
                    flowers += 1
                elif item.get("shape") == "bud":
                    buds += 1
                elif item.get("shape") == "leaf":
                    leaves += 1
            cid = str(component.get("component"))
            report = COMPONENT_LAYOUT.get(cid)
            if report:
                try:
                    count = len(report(params))
                except (TypeError, ValueError):
                    count = 0
                if count:
                    components[cid] = components.get(cid, 0) + count
            for mesh_data in params.get("meshes") or []:
                if mesh_data.get("layout") is False:
                    continue
                subject = mesh_data.get("subject")
                if subject:
                    subjects[str(subject)] = subjects.get(str(subject), 0) + 1
                else:
                    kind = str(mesh_data.get("type", "sweep"))
                    shapes[kind] = shapes.get(kind, 0) + 1

    if flowers or buds:
        parts = ["a crabapple branch with %d open blossoms" % flowers]
        if buds:
            parts.append("%d closed buds" % buds)
        if leaves:
            parts.append("%d narrow leaves" % leaves)
        return (", ".join(parts) +
                ", pale rose-pink petals with golden stamens, dark green serrated leaves, "
                "slender brown twigs, " + STYLE +
                ", traditional Chinese gongbi flower painting")

    # 没有花，就把场景里的主体按实际数量列出来，别把静物说成花枝。
    parts = []
    for cid, count in sorted(components.items(), key=lambda pair: -pair[1])[:4]:
        one, many = COMPONENT_SUBJECTS[cid]
        parts.append("%d %s" % (count, one if count == 1 else many))
    for name, count in sorted(subjects.items(), key=lambda pair: -pair[1])[:4]:
        parts.append("%d %s" % (count, name if count == 1 else name + "s"))
    counted = [(kind, count) for kind, count in shapes.items() if count > 0]
    counted.sort(key=lambda pair: -pair[1])
    for kind, count in counted[:4]:
        one, many = SUBJECT_NAMES.get(kind, ("object", "objects"))
        parts.append("%d %s" % (count, one if count == 1 else many))
    if leaves:
        parts.append("%d leaves" % leaves)
    subject = ", ".join(parts) if parts else "a simple arrangement"
    if "arched_windows" in components or "long_table" in components:
        scene = "a quiet interior lit from one side"
    elif "crabapple_tree" in components:
        scene = "a flowering grove under soft spring light"
    elif any("building" in name for name in subjects):
        scene = "a quiet night street receding to one vanishing point"
    elif "lathe" in shapes or subjects:
        scene = "a still life on a plain table"
    else:
        scene = "a simple geometric study"
    return subject + ", " + scene + ", " + STYLE
