# -*- coding: utf-8 -*-
"""配色角色。

绘制方案里写角色名（bg、ink、line 等），这里负责换成色值。
"""
from __future__ import annotations

import colorsys

PALETTES = {
    "fresco": {
        "name": "湿壁画",
        "bg": "#d9c7a3",
        "surface": "#e6d7b8",
        "ink": "#3a2a1e",
        "muted": "#7a6a55",
        "deep": "#6b2f24",
        "mid": "#8a6a3a",
        "soft": "#c9b48a",
        "line": "#9c8a6e",
        "accent": "#f6e6bd",
    },
    "alpine": {
        "name": "阿尔卑斯",
        "bg": "#3f4d57",
        "surface": "#8d8b7c",
        "ink": "#211c18",
        "muted": "#5a5f5e",
        "deep": "#7c3a2c",
        "mid": "#7d7059",
        "soft": "#cfc6b2",
        "line": "#3c3a35",
        "accent": "#d9c089",
    },
    "dawn": {
        "name": "晨光",
        "bg": "#2f4356",
        "surface": "#efe4cf",
        "ink": "#1d1a16",
        "muted": "#7d8d97",
        "deep": "#b2563c",
        "mid": "#c8915a",
        "soft": "#f4ebda",
        "line": "#3e4c59",
        "accent": "#f3c579",
    },
    "dusk": {
        "name": "暮色",
        "bg": "#1b1524",
        "surface": "#241c30",
        "ink": "#f6ece0",
        "muted": "#b8a9a0",
        "deep": "#f2b880",
        "mid": "#d97a5a",
        "soft": "#6d3a5c",
        "line": "#3a2f4a",
        "accent": "#ffd88a",
    },
}


def resolve_palette(value):
    """把方案里的 palette 字段换成完整的角色表。"""
    if value is None or value == "":
        return dict(PALETTES["fresco"])
    if isinstance(value, dict):
        merged = dict(PALETTES["fresco"])
        merged.update({str(k): str(v) for k, v in value.items()})
        return merged
    key = str(value)
    if key not in PALETTES:
        raise ValueError(f"没有这套配色：{key}，可选 {', '.join(PALETTES)}")
    return dict(PALETTES[key])


def _hex_to_rgb(text: str):
    text = str(text).lstrip("#")
    if len(text) != 6:
        return None
    try:
        return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None


def _rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{int(round(min(1.0, max(0.0, c)) * 255)):02x}" for c in rgb)


def shade(hex_color: str, steps: int) -> str:
    """在同一个色相里按档位调明度，返回新的色值。

    steps 为 0 时原样返回。正数往亮里走，负数往暗里走。
    每一档改动约 6% 明度，几档之内还是同一个颜色家族，
    远看能分出层次，近看不刺眼。
    """
    rgb = _hex_to_rgb(hex_color)
    if rgb is None:
        return hex_color
    hue, light, sat = colorsys.rgb_to_hls(*rgb)
    light = max(0.04, min(0.96, light + steps * 0.06))
    return _rgb_to_hex(colorsys.hls_to_rgb(hue, light, sat))


def shade_by(hex_color: str, amount: float) -> str:
    # 在同一个色相里按比例调明度。
    # amount 是明度的变化量，正数往亮里走，负数往暗里走。
    rgb = _hex_to_rgb(hex_color)
    if rgb is None:
        return hex_color
    hue, light, sat = colorsys.rgb_to_hls(*rgb)
    light = max(0.04, min(0.96, light + amount))
    return _rgb_to_hex(colorsys.hls_to_rgb(hue, light, sat))


def mix(first: str, second: str, ratio: float) -> str:
    """两个色值按比例混在一起。ratio 为 0 取第一个，为 1 取第二个。"""
    a = _hex_to_rgb(first)
    b = _hex_to_rgb(second)
    if a is None or b is None:
        return first
    ratio = max(0.0, min(1.0, float(ratio)))
    return _rgb_to_hex(tuple(x + (y - x) * ratio for x, y in zip(a, b)))


def color_of(palette, value):
    """角色名换成色值；本来就是 #rrggbb 的原样返回。"""
    if value is None:
        return None
    text = str(value)
    if text.startswith("#"):
        return text
    if text not in palette:
        raise ValueError(f"配色里没有角色 {text}，可选 {', '.join(palette)}")
    return palette[text]
