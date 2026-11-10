# -*- coding: utf-8 -*-
"""组件目录：列出可用的构图组件和它们的参数。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import mesh, organic
from .components import (alpine, architecture, arched_windows, block, box3d, crabapple,
                         figures, indoor_backdrop, long_table, modern, perspective,
                         rider3d, rig, tableware)


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    description: str
    params: dict
    build: Callable[[dict, object], None]


_SPECS: dict[str, dict] = {
    "indoor_backdrop": {
        "name": "室内背景",
        "description": "墙面、地面、天顶和两侧帷幔，给室内场景打底",
        "params": {
            "wall": "[x, y, 宽, 高]，必填",
            "floor": "[x, y, 宽, 高]，可选",
            "ceiling": "[x, y, 宽, 高]，可选",
            "tapestries": "[[x, y, 宽, 高], …]，可选",
            "colors": "{wall, floor, ceiling, tapestry, fold}，可选",
        },
        "build": indoor_backdrop.build,
    },
    "arched_windows": {
        "name": "拱形窗户",
        "description": "一组拱窗，带窗光、竖棂和横档",
        "params": {
            "windows": "[[x, y, 宽, 高], …]，必填",
            "mullions": "是否画窗棂，默认 true",
            "colors": "{frame, glass, light}，可选",
        },
        "build": arched_windows.build,
    },
    "long_table": {
        "name": "长条餐桌",
        "description": "桌布、前垂、桌沿、成排盘子和面包",
        "params": {
            "table": "[x, y, 宽, 高]，必填",
            "front": "前垂高度，默认 38",
            "plates": "[x, …]，可选",
            "plate_y": "盘子纵向位置，可选",
            "cup_x": "酒杯横向位置，可选",
            "colors": "{cloth, front, edge, plate, bread}，可选",
        },
        "build": long_table.build,
    },
    "coffered_ceiling": {
        "name": "藻井天顶",
        "description": "顶棚底色、向灭点收窄的纵向透视线、横向梁和檐线",
        "params": {
            "ceiling": "[x, y, 宽, 高]，顶棚可见范围，必填",
            "vanish": "[x, y]，透视灭点，可选",
            "columns": "横向格数，默认 6",
            "rows": "纵深格数，默认 4",
            "back_ratio": "后沿宽度比例，默认 0.42",
            "colors": "{panel, rib, shadow}，可选",
        },
        "build": architecture.coffered_ceiling,
    },
    "side_drapery": {
        "name": "两侧帷幔",
        "description": "墙面投影、挂杆、布面、顶褶、竖褶、束带和底边",
        "params": {
            "draperies": "[[x, y, 宽, 高], …]，每块帷幔的位置，必填",
            "cast_shadow": "是否在墙上画投影，默认 true",
            "colors": "{cloth, fold, highlight, rod, shadow}，可选",
        },
        "build": architecture.side_drapery,
    },
    "window_glow": {
        "name": "窗光",
        "description": "窗周渐亮的光晕、人物背后的亮部和桌面上被照亮的一块",
        "params": {
            "window": "[x, y, 宽, 高]，中间那扇窗，必填",
            "glow_steps": "窗周光晕层数，1 到 4，默认 3",
            "halo": "[中心x, 中心y, 半径x, 半径y]，人物背后亮部，可选",
            "pool": "[中心x, 中心y, 半径x, 半径y]，桌面光斑，可选",
            "colors": "{glow, hot, halo, pool}，可选",
        },
        "build": architecture.window_glow,
    },
    "soft_vignette": {
        "name": "四角阴影",
        "description": "四角老化压暗和桌下柔和暗部，压在整幅画的最上层",
        "params": {
            "frame": "[x, y, 宽, 高]，要压暗的画面范围，必填",
            "corners": "是否压暗四角，默认 true",
            "corner_x": "四角暗部横向半径，默认 frame 宽的 0.23",
            "corner_y": "四角暗部纵向半径，默认 frame 高的 0.22",
            "under_shadow": "[中心x, 中心y, 半径x, 半径y]，桌下暗部，可选",
            "colors": "{deep, mid, far, shade_deep, shade_far}，可选",
        },
        "build": architecture.soft_vignette,
    },
}

_SPECS.update(tableware.COMPONENTS)
_SPECS.update(figures.COMPONENTS)
_SPECS.update(alpine.COMPONENTS)
_SPECS.update(rig.COMPONENTS)
_SPECS.update(block.COMPONENTS)
_SPECS.update(box3d.COMPONENTS)
_SPECS.update(rider3d.COMPONENTS)
_SPECS.update(crabapple.COMPONENTS)
_SPECS.update(perspective.COMPONENTS)
_SPECS.update(mesh.COMPONENTS)
_SPECS.update(organic.COMPONENTS)
_SPECS.update(modern.COMPONENTS)

REGISTRY: dict[str, Component] = {
    key: Component(
        id=key,
        name=spec["name"],
        description=spec["description"],
        params=spec["params"],
        build=spec["build"],
    )
    for key, spec in _SPECS.items()
}


def get_component(key: str) -> Component:
    if key not in REGISTRY:
        raise KeyError(f"组件目录里没有 {key}，可选 {', '.join(REGISTRY)}")
    return REGISTRY[key]


def list_components() -> list[Component]:
    return list(REGISTRY.values())
