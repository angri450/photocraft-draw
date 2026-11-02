# -*- coding: utf-8 -*-
"""绘制方案：读取、校验、按图层合成绘制指令。"""
from __future__ import annotations

import json
from pathlib import Path

from .commands import Pen
from .palette import resolve_palette
from .registry import get_component

NUMBER = (int, float)


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
        if not isinstance(item.get("params", {}), dict):
            errors.append(f"{label}的 params 必须是对象")


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
            for index, layer in enumerate(layers):
                label = f"第 {index + 1} 层"
                if not isinstance(layer, dict):
                    errors.append(f"{label}必须是一个对象")
                    continue
                name = layer.get("name")
                if not isinstance(name, str) or not name.strip():
                    errors.append(f"{label}缺少 name")
                _validate_component_list(layer.get("components"), f"{label}的 components", errors)
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
    pen = Pen(int(width), int(height), ref_width=ref_width, palette=palette)

    background = plan.get("background")
    if background:
        pen.rect(0, 0, pen.ref_width, pen.ref_height, fill=background,
                 stroke_width=None, stroke=None, name="底色")

    layers = plan.get("layers")
    if layers:
        for layer in layers:
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
        "layers": layer_count,
        "components": component_count,
        "commands": len(pen.commands),
    }
    return pen.commands, meta
