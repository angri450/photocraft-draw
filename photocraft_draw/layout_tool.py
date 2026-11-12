# -*- coding: utf-8 -*-
"""模型无关的画面结构：实际部件、人物关节和兵器轴线。"""
from __future__ import annotations

from .checker import parts_of
from .commands import Pen
from .components.rig import pose_table_3d
from .geometry import polygons_of
from .plan import compose_plan, ordered_layers
from .split import axis_of, lerp_point


def _scale_box(box, sx, sy, width, height):
    """把坐标放进目标画布；缩放不等于实际渲染后的采样。"""
    values = (value * (sx if index % 2 == 0 else sy)
              for index, value in enumerate(box))
    return [round(max(0.0, min(width if index % 2 == 0 else height, value)), 2)
            for index, value in enumerate(values)]


def _shape_box(command):
    """返回真实部件范围及其来源，不把曲线控制点框当成填充框。"""
    points = [point for polygon in polygons_of(command) for point in polygon]
    if points:
        return ([min(point[0] for point in points),
                 min(point[1] for point in points),
                 max(point[0] for point in points),
                 max(point[1] for point in points)], "fill_polygon")
    part = parts_of([command])
    if not part:
        return None, None
    source = "centerline" if part[0]["kind"] == "line" else "primitive"
    return part[0]["bbox"], source


def _text_box(command, sx, sy, width, height):
    """原生文字的估算框；它不是字体光栅化后的精确测量。"""

    params = command.get("params") or {}
    text = str(params.get("text") or "")
    if not text.strip():
        return None

    size = float(params.get("size") or 24)
    x, baseline = float(params.get("x") or 0), float(params.get("y") or 0)

    tracking = float(params.get("tracking") or 0) * size / 1000

    lines = text.split("\n")

    longest = max(lines, key=len)

    units = sum(1 if ord(char) > 255 else 0.56 for char in longest)

    extent = max(size, units * size + tracking * len(longest) * 1.2)

    alignment = str(params.get("align") or "left")

    center = x if alignment == "center" else x + extent / 2

    if alignment == "right":

        center = x - extent / 2

    box = _scale_box([center - extent * 0.55,

                      baseline - len(lines) * size * 1.12,

                      center + extent * 0.55,

                      baseline + size * 0.38], sx, sy, width, height)

    return {"label": "text", "text": text, "bbox": box,

            "bbox_source": "font_estimate",

            "font": params.get("font"), "size": size,

            "color": params.get("color"),"weight": params.get("weight"),

            "align": alignment}





def text_annotations(plan, width, height):

    commands, _ = compose_plan(plan)

    reference = float(plan.get("ref_width", 800))

    sx = sy = width / float(plan["canvas"][0])

    scale = reference / float(plan["canvas"][0])

    annotations = []

    for command in commands:

        if command.get("command") != "type.create":

            continue

        item = _text_box(command, scale * sx, scale * sy, width, height)

        if item:

            annotations.append(item)

    return annotations


def command_geometry(plan):
    """按实际绘制顺序导出组件，曲线范围包含路径离散得到的点。"""
    commands, _ = compose_plan(plan)
    result = []
    current = None
    for command in commands:
        if command.get("command") == "layer.new.group" and not command.get("_nested"):
            source = command.get("_layout") or {"role": "annotation"}
            current = {"name": command["params"]["name"],
                       "role": source.get("role", "structure"),
                       "depth": source.get("depth"), "z": source.get("z"),
                       "holder": source.get("holder"), "parts": []}
            for key in ("z_from", "z_to"):
                if key in source:
                    current[key] = source[key]
            if "from" in source and "to" in source:
                current["ratio"] = [source["from"], source["to"]]
            result.append(current)
        elif command.get("command") == "shape.create":
            box, source = _shape_box(command)
            params = command["params"]
            if current is None and params.get("name") == "底色" and plan.get("background"):
                current = {"name": "background", "role": "canvas_background",
                           "depth": None, "z": None, "holder": None, "parts": []}
                result.append(current)
            if box is None or current is None or current["role"] == "annotation":
                continue
            current["parts"].append({
                "name": params.get("name") or params["kind"],
                "kind": params["kind"], "bbox": box,
                "bbox_source": source, "group": params.get("group"),
            })
    for layer in result:
        parts = layer["parts"]
        layer["bbox"] = [min(part["bbox"][0] for part in parts),
                         min(part["bbox"][1] for part in parts),
                         max(part["bbox"][2] for part in parts),
                         max(part["bbox"][3] for part in parts)] if parts else None
    return result


def geometry_scaled(plan, width, height):
    result = command_geometry(plan)
    sx = width / plan["canvas"][0]
    sy = height / plan["canvas"][1]
    for layer in result:
        layer["bbox"] = _scale_box(layer["bbox"], sx, sy, width, height) if layer["bbox"] is not None else None
        for part in layer["parts"]:
            part["bbox"] = _scale_box(part["bbox"], sx, sy, width, height)
    return result


def skeletons(plan, width, height):
    """人物关节与白模使用同一参考高度、同一像素量化规则。"""
    result = []
    reference = float(plan.get("ref_width", 800))
    sx = sy = width / float(plan["canvas"][0])
    pen = Pen(int(plan["canvas"][0]), int(plan["canvas"][1]),
              ref_width=int(reference))
    for layer in plan.get("layers", []):
        for component in layer.get("components", []):
            if component["component"] != "figure_rig":
                continue
            params = component.get("params") or {}
            height = float(params["height"])
            ox, oy = params["root"]
            flip = -1 if params.get("flip") else 1
            joints = {}
            for name, (x, y, z) in pose_table_3d(params.get("pose", "stand")).items():
                joints[name] = {
                    "xy": [round(pen._x(ox + flip * x * height) * sx, 2),
                           round(pen._x(oy + y * height) * sy, 2)],
                    "z_offset": z,
                }
            result.append({"name": layer["name"], "component": "figure_rig",
                           "z": layer.get("z"), "face": params.get("face"),
                           "pose": params.get("pose", "stand"), "joints": joints,
                           "z_offset_unit": "reference_canvas_pixels",
                           "note": "白模关节位置，不代表生成图已经遵循该姿态"})
    return result


def prop_axes(plan, width, height):
    """轴线来自切分器使用的端点；分段的深度来自各段声明。"""
    result = []
    reference = float(plan.get("ref_width", 800))
    sx = sy = width / float(plan["canvas"][0])
    reference_scale = reference / float(plan["canvas"][0])

    def point(value):
        # 保留切分器的连续轴线；只有实际绘制时才取整像素。
        return [round(value[0] * reference_scale * sx, 2),
                round(value[1] * reference_scale * sy, 2)]

    for layer in plan.get("layers", []):
        axis = axis_of(layer.get("components", []), layer.get("axis"))
        if not layer.get("holder") or axis is None:
            continue
        segments = [{"name": segment.get("name"),
                     "ratio": [segment["from"], segment["to"]],
                     "depth": segment.get("depth"),
                     "z_from": segment.get("z_from", segment.get("z", layer.get("z"))),
                     "z_to": segment.get("z_to", segment.get("z", layer.get("z"))),
                     "axis": [point(lerp_point(axis, float(segment["from"]))),
                              point(lerp_point(axis, float(segment["to"])))]}
                    for segment in layer.get("segments", [])]
        result.append({"name": layer["name"], "holder": layer["holder"],
                       "z": layer.get("z"),
                       "axis": [point(axis[0]), point(axis[1])],
                       "segments": segments})
    return result


def details_view(plan):
    if not plan.get("details"):
        return {}
    from .details import build_details
    return build_details(plan)


def export_layout(plan, width, height, caption, detail="geometry"):
    """按实际绘制结构导出，保留明确标注的文字或参考职责。"""
    geometry = geometry_scaled(plan, width, height)
    texts = text_annotations(plan, width, height)
    if not any(layer["parts"] for layer in geometry) and not texts:
        raise ValueError("方案中没有可导出的实际形状或文字")
    base = {"layout_version": "photocraft-layout/v2",
            "width": width, "height": height,
            "bbox_coord_space": "abs", "bbox_format": "xyxy",
            "coordinate_space": "target_canvas_pixels",
            "summary": {"canvas": "single", "caption": caption},
            "layers": [{"name": layer.get("name"), "depth": layer.get("depth"),
                        "z": layer.get("z"), "holder": layer.get("holder")}
                       for layer in ordered_layers(plan)]}
    if texts:
        base["annotations"] = texts
    bones = skeletons(plan, width, height)
    if bones:
        base["skeletons"] = bones
    axes = prop_axes(plan, width, height)
    if axes:
        base["axes"] = axes
    if detail == "semantic":
        details = details_view(plan)
        base["objects"] = [{"name": item["target"], "priority": item["priority"],
                            "aspects": item["aspects"]}
                           for item in details.get("subjects", [])]
        base["references"] = details.get("references", [])
        base["roles"] = [{"name": layer.get("name"),
                          "describe_zh": layer.get("describe_zh"),
                          "describe_en": layer.get("describe_en")}
                         for layer in ordered_layers(plan)]
    elif detail == "components":
        base["components"] = geometry
    elif detail == "geometry":
        base["layers"] = geometry
    else:
        raise ValueError("detail 只能是 semantic、components 或 geometry")
    return base
