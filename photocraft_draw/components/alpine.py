# -*- coding: utf-8 -*-
"""高山场景：天空、雪山、岩地。

给「拿破仑翻越阿尔卑斯山」这类题材打底。画笔只有矩形、圆角矩形、椭圆和
直线，所以山用几层椭圆堆出圆顶的轮廓，再用山脊线和雪顶收形；远山颜色浅、
边缘软，近山颜色深、压得住前景。

坐标按 800 宽的参考画布写，颜色只写角色名或 #rrggbb。
"""
from __future__ import annotations

from ..commands import Pen

SKY_BANDS = ("bg", "muted", "mid", "soft", "accent")


def _box(value, message: str) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(message)
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(message)
    x, y, w, h = (float(item) for item in value)
    if w <= 0 or h <= 0:
        raise ValueError(message)
    return x, y, w, h


def _points(value, size: int, message: str, required: bool = False) -> list[list[float]]:
    if value is None:
        if required:
            raise ValueError(message)
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(message)
    if not value:
        if required:
            raise ValueError(message)
        return []
    rows = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) < size:
            raise ValueError(message)
        for number in item[:size]:
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                raise ValueError(message)
        rows.append([float(number) for number in item[:size]])
    return rows


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    text = str(value).lstrip("#")
    if len(text) != 6:
        raise ValueError(f"颜色要写成 #rrggbb，收到 {value}")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _mix(first: str, second: str, ratio: float) -> str:
    """两个色值之间按比例插值，用来做天空渐变。"""
    a = _hex_to_rgb(first)
    b = _hex_to_rgb(second)
    ratio = min(1.0, max(0.0, ratio))
    mixed = [round(a[index] + (b[index] - a[index]) * ratio) for index in range(3)]
    return "#%02x%02x%02x" % tuple(mixed)


def build_alpine_sky(params: dict, pen: Pen) -> None:
    """天空：从顶部到底部逐层插值的色带，可加几条云。

    参数：
        area    [x, y, 宽, 高]，天空范围，必填
        bands   色带数，4 到 24，默认 14，越多过渡越顺
        clouds  [[中心x, 中心y, 半径x, 半径y], …]，可选
        colors  {top, bottom, cloud}，可选，top 和 bottom 给角色名或 #rrggbb
    """
    x, y, w, h = _box(params.get("area"), "天空需要 area：[x, y, 宽, 高]")
    bands = int(params.get("bands", 14))
    if not 4 <= bands <= 24:
        raise ValueError("天空的 bands 要在 4 到 24 之间")
    colors = params.get("colors") or {}
    top = colors.get("top", "bg")
    bottom = colors.get("bottom", "accent")
    cloud = colors.get("cloud", "surface")
    top_hex = pen.palette.get(top, top) if not str(top).startswith("#") else top
    bottom_hex = pen.palette.get(bottom, bottom) if not str(bottom).startswith("#") else bottom
    cloud_hex = pen.palette.get(cloud, cloud) if not str(cloud).startswith("#") else cloud

    step = h / bands
    for index in range(bands):
        ratio = index / max(bands - 1, 1)
        pen.rect(x, y + index * step, w, step + 1,
                 fill=_mix(top_hex, bottom_hex, ratio ** 0.85),
                 stroke_width=None, stroke=None, name=f"天空 {index + 1}")

    for cloud_index, row in enumerate(_points(params.get("clouds") or [], 4,
                                             "云的每一朵要写 [中心x, 中心y, 半径x, 半径y]")):
        cx, cy, rx, ry = row
        pen.ellipse(cx, cy, rx, ry, fill=cloud_hex, stroke_width=None, stroke=None,
                    name=f"云 {cloud_index + 1}")
        pen.ellipse(cx + rx * 0.5, cy + ry * 0.2, rx * 0.55, ry * 0.7,
                    fill=cloud_hex, stroke_width=None, stroke=None,
                    name=f"云 {cloud_index + 1} 右")
        pen.ellipse(cx - rx * 0.45, cy + ry * 0.15, rx * 0.5, ry * 0.65,
                    fill=cloud_hex, stroke_width=None, stroke=None,
                    name=f"云 {cloud_index + 1} 左")


def build_alpine_peaks(params: dict, pen: Pen) -> None:
    """雪山：三层椭圆叠出圆顶山形，可选雪顶。

    横条堆三角会留台阶，画笔又没有多边形，所以这里回到椭圆：山脚最宽、
    山腰收窄、山顶再收，三层同心叠起来轮廓是平滑的弧，边缘没有锯齿。
    雪顶只盖最上面一小块，不会像扣了个碗。

    参数：
        peaks   [[中心x, 山脚y, 半宽, 高], …]，必填，先写的在后
        snow    是否画雪顶，默认 true
        colors  {far, near, snow, edge}，可选
    """
    peaks = _points(params.get("peaks"), 4,
                    "雪山需要 peaks：[[中心x, 山脚y, 半宽, 高], …]", required=True)
    snow = bool(params.get("snow", False))
    colors = params.get("colors") or {}
    far = colors.get("far", "muted")
    near = colors.get("near", "line")
    snow_color = colors.get("snow", "soft")
    edge = colors.get("edge", "ink")

    total = len(peaks)
    for index, (cx, base_y, half_w, height) in enumerate(peaks):
        if half_w <= 0 or height <= 0:
            raise ValueError("雪山的半宽和高度要大于 0")
        depth = index / max(total - 1, 1)
        body = far if depth < 0.5 else near

        # 山脚：圆心压到地面以下，只露上面一半
        pen.ellipse(cx, base_y + height * 0.18, half_w, height * 0.6,
                    fill=body, stroke_width=None, stroke=None, name=f"山 {index + 1} 脚")
        # 山腰
        pen.ellipse(cx, base_y - height * 0.12, half_w * 0.74, height * 0.52,
                    fill=body, stroke_width=None, stroke=None, name=f"山 {index + 1} 腰")
        # 山顶
        pen.ellipse(cx, base_y - height * 0.44, half_w * 0.44, height * 0.36,
                    fill=body, stroke_width=None, stroke=None, name=f"山 {index + 1} 顶")

        if snow:
            # 雪只盖山顶一小块，三层递减，贴着弧线走
            pen.ellipse(cx, base_y - height * 0.62, half_w * 0.2, height * 0.09,
                        fill=snow_color, stroke_width=None, stroke=None,
                        name=f"山 {index + 1} 雪")
            pen.ellipse(cx, base_y - height * 0.71, half_w * 0.13, height * 0.06,
                        fill=snow_color, stroke_width=None, stroke=None,
                        name=f"山 {index + 1} 雪尖")




def build_rocky_ground(params: dict, pen: Pen) -> None:
    """岩地：一块底色加几块石头。

    参数：
        area    [x, y, 宽, 高]，地面范围，必填
        rocks   [[中心x, 中心y, 半径x, 半径y], …]，可选
        tone    底色深浅，dark / mid，默认 dark
        colors  {base, light, dark}，可选
    """
    x, y, w, h = _box(params.get("area"), "岩地需要 area：[x, y, 宽, 高]")
    tone = str(params.get("tone", "dark"))
    if tone not in ("dark", "mid"):
        raise ValueError("岩地的 tone 只能是 dark 或 mid")
    colors = params.get("colors") or {}
    base = colors.get("base", "ink" if tone == "dark" else "muted")
    light = colors.get("light", "line")
    dark = colors.get("dark", "muted" if tone == "dark" else "ink")

    pen.rect(x, y, w, h, fill=base, stroke_width=None, stroke=None, name="地面")
    # 上沿一条亮边，把地面和山脚分开
    pen.rect(x, y, w, max(2, h * 0.06), fill=light, stroke_width=None, stroke=None,
             name="地面亮边")

    for index, (cx, cy, rx, ry) in enumerate(_points(
            params.get("rocks") or [], 4,
            "每块石头要写 [中心x, 中心y, 半径x, 半径y]")):
        pen.ellipse(cx, cy, rx, ry, fill=light, stroke_width=None, stroke=None,
                    name=f"石头 {index + 1}")
        pen.ellipse(cx - rx * 0.12, cy - ry * 0.18, rx * 0.62, ry * 0.55,
                    fill=dark, stroke_width=None, stroke=None, name=f"石影 {index + 1}")


def build_river_water(params: dict, pen: Pen) -> None:
    """河流：水面、横向波纹和几处水花。

    参数：
        area     [x, y, 宽, 高]，水面范围，必填
        waves    横向波纹条数，0 到 12，默认 5
        splashes [[中心x, 中心y, 半径x, 半径y], …]，水花位置，可选
        colors   {water, light, foam, dark}，可选
    """
    x, y, w, h = _box(params.get("area"), "河流需要 area：[x, y, 宽, 高]")
    waves = int(params.get("waves", 5))
    if not 0 <= waves <= 12:
        raise ValueError("河流的 waves 要在 0 到 12 之间")
    colors = params.get("colors") or {}
    water = colors.get("water", "bg")
    light = colors.get("light", "soft")
    foam = colors.get("foam", "surface")
    dark = colors.get("dark", "ink")

    pen.rect(x, y, w, h, fill=water, stroke_width=None, stroke=None, name="水面")
    # 远处一条暗带，把水面和岸分开
    pen.rect(x, y, w, max(1.5, h * 0.04), fill=dark, stroke_width=None, stroke=None,
             name="水岸线")

    for index in range(waves):
        ratio = (index + 1) / (waves + 1)
        band_y = y + h * ratio
        inset = w * 0.04 * ((index % 3) - 1) * 0.5
        pen.rect(x + inset, band_y, w * (0.2 + 0.1 * (index % 4)), max(1.5, h * 0.02),
                 fill=light, stroke_width=None, stroke=None, name=f"波纹 {index + 1}")
        pen.rect(x + w * (0.35 + 0.05 * ((index + 2) % 4)), band_y + h * 0.03,
                 w * (0.15 + 0.05 * (index % 3)), max(1.5, h * 0.015),
                 fill=light, stroke_width=None, stroke=None, name=f"波纹 {index + 1} 右")

    for index, (cx, cy, rx, ry) in enumerate(_points(
            params.get("splashes") or [], 4,
            "每处水花要写 [中心x, 中心y, 半径x, 半径y]")):
        # 贴着水面的白色泡沫，两层错开，避免排成一条
        pen.ellipse(cx, cy, rx, ry * 0.42, fill=foam, stroke_width=None, stroke=None,
                    name=f"水花 {index + 1}")
        pen.ellipse(cx + rx * 0.45, cy + ry * 0.3, rx * 0.42, ry * 0.26,
                    fill=foam, stroke_width=None, stroke=None, name=f"水花 {index + 1} 右")
        pen.ellipse(cx - rx * 0.4, cy - ry * 0.2, rx * 0.3, ry * 0.2,
                    fill=foam, stroke_width=None, stroke=None, name=f"水花 {index + 1} 左")


COMPONENTS = {
    "alpine_sky": {
        "name": "高山天空",
        "description": "从深到浅的横向色带，可加几朵云，给雪山场景打底",
        "params": {
            "area": "[x, y, 宽, 高]，必填",
            "bands": "色带数，2 到 8，默认 6",
            "clouds": "[[中心x, 中心y, 半径x, 半径y], …]，可选",
            "colors": "{top, bottom, cloud}，可选",
        },
        "build": build_alpine_sky,
    },
    "alpine_peaks": {
        "name": "雪山",
        "description": "几层椭圆堆出圆顶山形，带雪顶、山脊线和沟壑",
        "params": {
            "peaks": "[[中心x, 山脚y, 半宽, 高], …]，必填，后写的压在前面",
            "snow": "是否画雪顶，默认 true",
            "ridges": "每座山的沟壑数，0 到 4，默认 2",
            "colors": "{far, near, snow, edge}，可选",
        },
        "build": build_alpine_peaks,
    },
    "river_water": {
        "name": "河流",
        "description": "水面、横向波纹和几处水花，用来做前景的溪流",
        "params": {
            "area": "[x, y, 宽, 高]，必填",
            "waves": "波纹条数，0 到 12，默认 5",
            "splashes": "[[中心x, 中心y, 半径x, 半径y], …]，可选",
            "colors": "{water, light, foam, dark}，可选",
        },
        "build": build_river_water,
    },
    "rocky_ground": {
        "name": "岩地",
        "description": "地面底色、亮部和暗部，可摆几块石头做前景",
        "params": {
            "area": "[x, y, 宽, 高]，必填",
            "rocks": "[[中心x, 中心y, 半径x, 半径y], …]，可选",
            "tone": "dark / mid，默认 dark",
            "colors": "{base, light, dark}，可选",
        },
        "build": build_rocky_ground,
    },
}


__all__ = ["build_alpine_sky", "build_alpine_peaks", "build_rocky_ground",
           "build_river_water", "COMPONENTS"]
