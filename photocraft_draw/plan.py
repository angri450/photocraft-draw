# -*- coding: utf-8 -*-
"""绘制方案：读取、校验、按图层合成绘制指令。"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .commands import Pen
from .components.rig import FACE_WORDS
from .motion import ACTION_RULES
from .palette import resolve_palette
from .registry import get_component

NUMBER = (int, float)


def ordered_layers(plan: dict) -> list[dict]:
    """按 depth 排层序，最远的层排在前面。

    每层都写了 depth 时，层序由 depth 决定：depth 大的更远，先画。
    depth 相同按方案里的先后排。一层没写 depth 就按方案里的顺序。
    """
    layers = plan.get("layers") or []
    if not layers or not all(isinstance(layer, dict) and "depth" in layer
                             for layer in layers):
        return list(layers)
    indexed = list(enumerate(layers))
    indexed.sort(key=lambda item: (-float(item[1]["depth"]), item[0]))
    return [layer for _, layer in indexed]


def load_plan(path: str | Path) -> dict:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"找不到绘制方案：{source}")
    try:
        plan = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"绘制方案不是合法 JSON：{error}") from error
    errors = validate_plan(plan)
    if errors:
        raise ValueError("绘制方案有问题：\n- " + "\n- ".join(errors))
    return plan


def _validate_component_list(items, where: str, errors: list[str]) -> None:
    if not isinstance(items, list) or not items:
        errors.append(f"{where}必须是非空数组")
        return
    for index, item in enumerate(items):
        label = f"{where}第 {index + 1} 项"
        if not isinstance(item, dict):
            errors.append(f"{label}必须是一个对象")
            continue
        key = item.get("component")
        if not isinstance(key, str) or not key:
            errors.append(f"{label}缺少 component")
            continue
        try:
            get_component(key)
        except KeyError as error:
            errors.append(f"{label}：{error.args[0]}")
        params = item.get("params", {})
        if not isinstance(params, dict):
            errors.append(f"{label}的 params 必须是对象")
            continue
        if key == "figure_rig" and "face" in params:
            face = params.get("face")
            if not isinstance(face, str) or face not in FACE_WORDS:
                errors.append(f"{label}的 face「{face}」不在朝向词表里，可用的是："
                              + "、".join(FACE_WORDS))


def _validate_motion(layer: dict, label: str, names: set, errors: list) -> None:
    """校验一层的 motion 声明。

    motion 写三样：action 动作词、angle 方向角、opponents 交战对象。
    action 必须在词表里，angle 要落在动作词要求的扇区里，
    opponents 里的层名要真实存在。
    """
    motion = layer.get("motion")
    if motion is None:
        return
    if not isinstance(motion, dict):
        errors.append(f"{label}的 motion 必须是对象")
        return
    action = motion.get("action")
    if not isinstance(action, str) or not action:
        errors.append(f"{label}的 motion 缺少 action")
    elif action not in ACTION_RULES:
        errors.append(f"{label}的 action「{action}」不在动作词表里，可用的是："
                      + "、".join(ACTION_RULES))
    angle = motion.get("angle")
    if isinstance(angle, bool) or not isinstance(angle, (int, float)):
        errors.append(f"{label}的 motion 缺少 angle，方向角要写数字")
    elif not math.isfinite(float(angle)):
        errors.append(f"{label}的 motion 里的 angle 必须是有限数字")
    else:
        if action in ACTION_RULES:
            _, center, half = ACTION_RULES[action]
            diff = abs(float(angle) % 360 - center % 360)
            diff = min(diff, 360 - diff)
            if diff > half:
                errors.append(f"{label}的 motion 声明的 {float(angle):.1f} 度，"
                              f"和动作词「{action}」要求的 {center:.0f} 度上下 "
                              f"{half:.0f} 度对不上")
    opponents = motion.get("opponents")
    if opponents is not None:
        if not isinstance(opponents, list):
            errors.append(f"{label}的 opponents 必须是数组")
        else:
            for item in opponents:
                if not isinstance(item, str) or item not in names:
                    errors.append(f"{label}的 opponents 里的「{item}」不是方案里的层")


def _validate_holder(layer: dict, label: str, names: set, errors: list) -> None:
    """兵器层要写 holder，指明这层兵器归谁拿。"""
    holder = layer.get("holder")
    if holder is None:
        return
    if not isinstance(holder, str) or not holder:
        errors.append(f"{label}的 holder 要写层名")
    elif holder not in names:
        errors.append(f"{label}的 holder「{holder}」不是方案里的层")

def validate_plan(plan: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["顶层必须是一个对象"]

    canvas = plan.get("canvas")
    if not isinstance(canvas, (list, tuple)) or len(canvas) != 2:
        errors.append("canvas 必须是 [宽, 高]")
    else:
        for label, value in zip(("宽", "高"), canvas):
            if not isinstance(value, NUMBER) or isinstance(value, bool) or value <= 0:
                errors.append(f"canvas 的{label}必须是大于 0 的数字")

    ref_width = plan.get("ref_width", 800)
    if not isinstance(ref_width, NUMBER) or isinstance(ref_width, bool) or ref_width <= 0:
        errors.append("ref_width 必须是大于 0 的数字")

    background = plan.get("background")
    if background is not None and not isinstance(background, str):
        errors.append("background 必须是配色角色名或 #rrggbb")

    document_background = plan.get("document_background")
    if document_background is not None and not isinstance(document_background, str):
        errors.append("document_background 必须是 white、black、transparent 或 #rrggbb")

    caption = plan.get("caption")
    if caption is not None and not isinstance(caption, str):
        errors.append("caption 必须是字符串")

    caption_color = plan.get("caption_color")
    if caption_color is not None and not isinstance(caption_color, str):
        errors.append("caption_color 必须是配色角色名或 #rrggbb")

    palette = plan.get("palette")
    if palette is not None and not isinstance(palette, (str, dict)):
        errors.append("palette 必须是配色名或角色表")

    has_components = "components" in plan
    has_layers = "layers" in plan
    if has_components and has_layers:
        errors.append("components 和 layers 只能给一个")
    elif not has_components and not has_layers:
        errors.append("要有 components 或 layers")
    elif has_layers:
        layers = plan.get("layers")
        if not isinstance(layers, list) or not layers:
            errors.append("layers 必须是非空数组")
        else:
            names = {str(layer.get("name", "")) for layer in layers
                     if isinstance(layer, dict)}
            for index, layer in enumerate(layers):
                label = f"第 {index + 1} 层"
                if not isinstance(layer, dict):
                    errors.append(f"{label}必须是一个对象")
                    continue
                name = layer.get("name")
                if not isinstance(name, str) or not name.strip():
                    errors.append(f"{label}缺少 name")
                if "depth" in layer:
                    value = layer["depth"]
                    if not isinstance(value, NUMBER) or isinstance(value, bool):
                        errors.append(f"{label}的 depth 必须是数字")
                    elif not math.isfinite(value):
                        errors.append(f"{label}的 depth 必须是有限数字")
                _validate_component_list(layer.get("components"), f"{label}的 components", errors)
                _validate_motion(layer, label, names, errors)
                _validate_holder(layer, label, names, errors)
            depths = [index for index, layer in enumerate(layers)
                      if isinstance(layer, dict) and "depth" in layer]
            if depths and len(depths) != len(layers):
                missing = [f"第 {index + 1} 层" for index, layer in enumerate(layers)
                           if not (isinstance(layer, dict) and "depth" in layer)]
                errors.append("depth 要么每层都写，要么都不写；没写 depth 的有："
                              + "、".join(missing))
    else:
        _validate_component_list(plan.get("components"), "components", errors)

    return errors


def compose_plan(plan: dict) -> tuple[list[dict], dict]:
    """把绘制方案展开成绘制指令，返回 (指令, 摘要信息)。"""
    errors = validate_plan(plan)
    if errors:
        raise ValueError("绘制方案有问题：\n- " + "\n- ".join(errors))

    width, height = plan["canvas"]
    ref_width = plan.get("ref_width", 800)
    palette = resolve_palette(plan.get("palette"))
    document_background = plan.get("document_background", "transparent")
    base_layer = "Layer 1" if document_background == "transparent" else "Background"
    pen = Pen(int(width), int(height), ref_width=ref_width, palette=palette, base_layer=base_layer)

    background = plan.get("background")
    if background:
        pen.rect(0, 0, pen.ref_width, pen.ref_height, fill=background,
                 stroke_width=None, stroke=None, name="底色")

    layers = plan.get("layers")
    if layers:
        for layer in ordered_layers(plan):
            pen.stage(layer["name"])
            for item in layer["components"]:
                component = get_component(item["component"])
                pen.stage(component.name, nested=True)
                component.build(item.get("params") or {}, pen)
        component_count = sum(len(layer["components"]) for layer in layers)
        layer_count = len(layers)
    else:
        for item in plan["components"]:
            component = get_component(item["component"])
            pen.stage(component.name)
            component.build(item.get("params") or {}, pen)
        component_count = len(plan["components"])
        layer_count = 1

    caption = plan.get("caption")
    if caption:
        pen.stage("文字层")
        pen.text(
            pen.ref_width * 0.04, pen.ref_height * 0.96, caption,
            size=14, color=plan.get("caption_color", "surface"),
            font="DejaVu Sans Mono", tracking=120, name="画面标题",
        )

    meta = {
        "name": plan.get("name") or "未命名",
        "width": int(width),
        "height": int(height),
        "document_background": plan.get("document_background", "transparent"),
        "layers": layer_count,
        "components": component_count,
        "commands": len(pen.commands),
    }
    return pen.commands, meta
