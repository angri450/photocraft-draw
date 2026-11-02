# -*- coding: utf-8 -*-
"""配色角色。

绘制方案里写角色名（bg、ink、line 等），这里负责换成色值。
"""

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
