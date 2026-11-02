# -*- coding: utf-8 -*-
"""高山场景：天空、雪山、岩地。

给「拿破仑翻越阿尔卑斯山」这类题材打底。画笔只有矩形、圆角矩形、椭圆和
直线，所以山用几层椭圆堆出圆顶的轮廓，再用山脊线和雪顶收形；远山颜色浅、
边缘软，近山颜色深、压得住前景。

坐标按 800 宽的参考画布写，颜色只写角色名或 #rrggbb。
"""
from __future__ import annotations

import math

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
            pen.ellipse(cx, base_y - height * 0.72, half_w * 0.15, height * 0.06,
                        fill=snow_color, stroke_width=None, stroke=None,
                        name=f"山 {index + 1} 雪")
            pen.ellipse(cx, base_y - height * 0.8, half_w * 0.09, height * 0.04,
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
    base_block = bool(params.get("base", True))
    colors = params.get("colors") or {}
    base = colors.get("base", "ink" if tone == "dark" else "muted")
    light = colors.get("light", "line")
    dark = colors.get("dark", "muted" if tone == "dark" else "ink")

    if base_block:
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


def _wave_line(pen: Pen, x0: float, x1: float, y: float, amplitude: float,
               cycles: float, weight: float, color: str, name: str) -> int:
    """用短直线段接成一条正弦波浪，返回段数。

    画笔没有曲线，段长取 14 到 20 像素时，折线接缝在 1600 宽的成图上
    看不出来，远看就是一条起伏的线。
    """
    span = x1 - x0
    segments = max(12, int(span / 16))
    step = span / segments
    previous = None
    for index in range(segments + 1):
        x = x0 + step * index
        y_at = y + math.sin(index / segments * cycles * math.tau) * amplitude
        if previous is not None:
            pen.line(previous[0], previous[1], x, y_at, width=weight, color=color,
                     name=f"{name} {index}")
        previous = (x, y_at)
    return segments


def build_river_water(params: dict, pen: Pen) -> None:
    """河流：水面、起伏的波浪线和波峰上的白色泡沫。

    参数：
        area     [x, y, 宽, 高]，水面范围，必填
        waves    波浪条数，0 到 8，默认 4
        amplitude 波浪起伏幅度，默认 5
        cycles   每条波浪里的起伏次数，默认 3
        foam     是否在每个波峰点一个白点，默认 true
        colors   {water, light, foam, dark}，可选
    """
    x, y, w, h = _box(params.get("area"), "河流需要 area：[x, y, 宽, 高]")
    waves = int(params.get("waves", 4))
    if not 0 <= waves <= 8:
        raise ValueError("河流的 waves 要在 0 到 8 之间")
    amplitude = float(params.get("amplitude", 5))
    if amplitude < 0:
        raise ValueError("河流的 amplitude 不能是负数")
    cycles = float(params.get("cycles", 3))
    if cycles <= 0:
        raise ValueError("河流的 cycles 要大于 0")
    foam = bool(params.get("foam", True))
    colors = params.get("colors") or {}
    water = colors.get("water", "bg")
    light = colors.get("light", "soft")
    foam_color = colors.get("foam", "surface")
    dark = colors.get("dark", "ink")

    pen.rect(x, y, w, h, fill=water, stroke_width=None, stroke=None, name="水面")
    pen.rect(x, y, w, max(1.5, h * 0.04), fill=dark, stroke_width=None, stroke=None,
             name="水岸线")

    for index in range(waves):
        band_y = y + h * (0.28 + 0.62 * (index / max(waves - 1, 1)))
        inset = w * 0.05 * (index % 2)
        _wave_line(pen, x + inset, x + w - inset, band_y,
                   amplitude * (0.7 + 0.15 * (index % 3)), cycles,
                   2.2 if index < 2 else 1.6, light, f"波浪 {index + 1}")

        if foam:
            for peak in range(int(cycles)):
                peak_ratio = (0.25 + peak) / cycles
                peak_x = x + inset + (w - inset * 2) * peak_ratio
                peak_y = band_y - amplitude * (0.7 + 0.15 * (index % 3))
                pen.ellipse(peak_x, peak_y - 2, 3.4, 1.3,
                            fill=foam_color, stroke_width=None, stroke=None,
                            name=f"浪花 {index + 1}-{peak + 1}")


def build_foreground_rocks(params: dict, pen: Pen) -> None:
    """前景石块：每块石头四个面，压住画面底部。

    一块石头用投影、主体、顶面亮部、底部暗部四层椭圆叠出来，比单画一个
    椭圆有体积。石头要比中景暗，才不会和岩地糊在一起。

    参数：
        rocks   [[中心x, 中心y, 半径x, 半径y], …]，必填
        colors  {stone, light, dark, shadow}，可选
    """
    rocks = _points(params.get("rocks"), 4,
                    "前景石块需要 rocks：[[中心x, 中心y, 半径x, 半径y], …]",
                    required=True)
    colors = params.get("colors") or {}
    stone = colors.get("stone", "line")
    light = colors.get("light", "muted")
    dark = colors.get("dark", "ink")
    shadow = colors.get("shadow", "ink")

    for index, (cx, cy, rx, ry) in enumerate(rocks):
        if rx <= 0 or ry <= 0:
            raise ValueError("前景石块的半径要大于 0")
        pen.ellipse(cx, cy + ry * 0.95, rx * 1.02, ry * 0.26,
                    fill=shadow, stroke_width=None, stroke=None, name=f"石影 {index + 1}")
        pen.ellipse(cx, cy, rx, ry, fill=stone, stroke_width=None, stroke=None,
                    name=f"石块 {index + 1}")
        pen.ellipse(cx - rx * 0.22, cy - ry * 0.3, rx * 0.42, ry * 0.22,
                    fill=light, stroke_width=None, stroke=None, name=f"石光 {index + 1}")
        # 主体下方一条投影，别塞进石头内部，不然像甜甜圈
        pen.ellipse(cx, cy + ry * 0.95, rx * 0.92, ry * 0.26,
                    fill=shadow, stroke_width=None, stroke=None, name=f"石底 {index + 1}")


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
    "foreground_rocks": {
        "name": "前景石块",
        "description": "带投影、顶面亮部和底部暗部的石块，用来压住画面底部",
        "params": {
            "rocks": "[[中心x, 中心y, 半径x, 半径y], …]，必填",
            "colors": "{stone, light, dark, shadow}，可选",
        },
        "build": build_foreground_rocks,
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
            "base": "是否铺一整块底色，默认 true；做前景石块时关掉",
            "colors": "{base, light, dark}，可选",
        },
        "build": build_rocky_ground,
    },
}


__all__ = ["build_alpine_sky", "build_alpine_peaks", "build_rocky_ground",
           "build_river_water", "COMPONENTS"]
