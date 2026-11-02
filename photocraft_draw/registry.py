# -*- coding: utf-8 -*-
"""组件目录：列出可用的构图组件和它们的参数。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .components import arched_windows, indoor_backdrop, long_table


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    description: str
    params: dict
    build: Callable[[dict, object], None]


REGISTRY: dict[str, Component] = {
    "indoor_backdrop": Component(
        id="indoor_backdrop",
        name="室内背景",
        description="墙面、地面、天顶和两侧帷幔，给室内场景打底",
        params={
            "wall": "[x, y, 宽, 高]，必填",
            "floor": "[x, y, 宽, 高]，可选",
            "ceiling": "[x, y, 宽, 高]，可选",
            "tapestries": "[[x, y, 宽, 高], …]，可选",
            "colors": "{wall, floor, ceiling, tapestry, fold}，可选",
        },
        build=indoor_backdrop.build,
    ),
    "arched_windows": Component(
        id="arched_windows",
        name="拱形窗户",
        description="一组拱窗，带窗光、竖棂和横档",
        params={
            "windows": "[[x, y, 宽, 高], …]，必填",
            "mullions": "是否画窗棂，默认 true",
            "colors": "{frame, glass, light}，可选",
        },
        build=arched_windows.build,
    ),
    "long_table": Component(
        id="long_table",
        name="长条餐桌",
        description="桌布、前垂、桌沿、成排盘子和面包",
        params={
            "table": "[x, y, 宽, 高]，必填",
            "front": "前垂高度，默认 38",
            "plates": "[x, …]，可选",
            "plate_y": "盘子纵向位置，可选",
            "cup_x": "酒杯横向位置，可选",
            "colors": "{cloth, front, edge, plate, bread}，可选",
        },
        build=long_table.build,
    ),
}


def get_component(key: str) -> Component:
    if key not in REGISTRY:
        raise KeyError(f"组件目录里没有 {key}，可选 {', '.join(REGISTRY)}")
    return REGISTRY[key]


def list_components() -> list[Component]:
    return list(REGISTRY.values())
