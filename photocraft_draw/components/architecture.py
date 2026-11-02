# -*- coding: utf-8 -*-
"""建筑与光影：藻井、帷幔、窗光、四角阴影。

四个组件各自是 build(params, pen) 形式的函数，只画形状，不建图层，
坐标按 800 宽的参考画布写。登记时直接引用函数名：

    coffered_ceiling  藻井：顶棚底色、纵向透视线、横向梁、檐线
    side_drapery      帷幔：墙投影、挂杆、布面、顶褶、竖褶、束带、底边
    window_glow       窗光：窗周渐亮的光晕、人物背后的亮部、桌面光斑
    soft_vignette     阴影：四角老化压暗、桌下柔和暗部

建议的图层顺序：室内背景 → 藻井 → 帷幔 → 窗光 → 人物与桌面 → 四角阴影。
窗光要排在人物之前，亮部才会落在人物背后；桌下暗部要排在桌子之前，
可以用 corners=false 单独调一次 soft_vignette。
"""
from __future__ import annotations

from ..commands import Pen


def _numbers(value, count: int, message: str) -> list[float]:
    """把参数读成定长数字数组，形状不对就报参数错误。"""
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(message)
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        raise ValueError(message) from None


def coffered_ceiling(params: dict, pen: Pen) -> None:
    """藻井天顶。

    参数：
        ceiling     [x, y, 宽, 高]，顶棚可见范围，必填
        vanish      [x, y]，透视线汇聚的灭点，可选；给了就按灭点算后沿宽度，
                    灭点要落在顶棚下沿以下
        columns     横向格数，默认 6
        rows        纵深格数，默认 4，间距向远处收窄
        back_ratio  后沿宽度相对前缘的比例，默认 0.42，没给 vanish 时生效
        colors      {panel, rib, shadow}，可选
    """
    x, y, w, h = _numbers(params.get("ceiling"), 4, "藻井需要 ceiling：[x, y, 宽, 高]")
    if w <= 0 or h <= 0:
        raise ValueError("藻井的 ceiling 宽高必须大于 0")

    colors = params.get("colors") or {}
    panel = colors.get("panel", "muted")
    rib = colors.get("rib", "line")
    shadow = colors.get("shadow", "ink")

    columns = int(params.get("columns", 6))
    rows = int(params.get("rows", 4))
    if columns < 2 or rows < 2:
        raise ValueError("藻井的 columns 和 rows 至少为 2")

    back = float(params.get("back_ratio", 0.42))
    if not 0 < back <= 1:
        raise ValueError("藻井的 back_ratio 要在 0 到 1 之间")

    vanish = params.get("vanish")
    if vanish is None:
        vx = x + w / 2
        scale = back
    else:
        vx, vy = _numbers(vanish, 2, "藻井的 vanish 要给 [x, y]")
        if vy <= y + h:
            raise ValueError("藻井的 vanish 的 y 要在顶棚下沿以下，否则透视线收不起来")
        scale = (vy - (y + h)) / (vy - y)

    pen.rect(x, y, w, h, fill=panel, stroke_width=None, stroke=None, name="天顶")

    near_left, near_right = x, x + w
    far_left = vx - w * scale / 2
    far_right = vx + w * scale / 2

    def section(depth: float) -> tuple[float, float, float]:
        """深度 0 是前缘，1 是后沿，返回该处的左右端和纵坐标。"""
        return (
            near_left + (far_left - near_left) * depth,
            near_right + (far_right - near_right) * depth,
            y + h * depth,
        )

    # 横向梁：按等比数列压密，越靠后越挤。
    ratio = 0.78
    span = 1 - ratio ** rows
    for index in range(1, rows):
        left, right, line_y = section((1 - ratio ** index) / span)
        pen.line(left, line_y, right, line_y, width=2, color=rib, name="藻井横梁")

    # 纵向梁：全部指向后沿中心的灭点，最外两条压重一档当边梁。
    for index in range(columns + 1):
        t = index / columns
        edge = index in (0, columns)
        pen.line(
            near_left + w * t, y,
            far_left + (far_right - far_left) * t, y + h,
            width=3 if edge else 2,
            color=shadow if edge else rib,
            name="藻井边梁" if edge else "藻井纵梁",
        )

    pen.line(near_left, y + h, near_right, y + h, width=2, color=shadow, name="藻井檐线")


def side_drapery(params: dict, pen: Pen) -> None:
    """两侧帷幔。

    参数：
        draperies     [[x, y, 宽, 高], …]，每块帷幔的位置，必填
        cast_shadow   是否在墙上画投影，默认 true
        colors        {cloth, fold, highlight, rod, shadow}，可选
    """
    drapes = params.get("draperies")
    if not isinstance(drapes, (list, tuple)) or not drapes:
        raise ValueError("帷幔需要 draperies：[[x, y, 宽, 高], …]")

    colors = params.get("colors") or {}
    cloth = colors.get("cloth", "deep")
    fold = colors.get("fold", "ink")
    highlight = colors.get("highlight", "mid")
    rod = colors.get("rod", "ink")
    shadow = colors.get("shadow", "soft")
    cast = bool(params.get("cast_shadow", True))

    folds = (
        (0.16, fold, 2),
        (0.34, highlight, 2),
        (0.52, fold, 3),
        (0.71, highlight, 2),
        (0.88, fold, 2),
    )

    for index, item in enumerate(drapes):
        label = index + 1
        x, y, w, h = _numbers(item, 4, f"draperies 第 {label} 项要写成 [x, y, 宽, 高]")
        if w <= 0 or h <= 0:
            raise ValueError(f"draperies 第 {label} 项的宽高必须大于 0")

        if cast:
            pen.rect(x + w * 0.82, y + h * 0.03, w * 0.22, h * 0.94,
                     fill=shadow, stroke_width=None, stroke=None, name=f"帷幔投影 {label}")

        bar_h = max(2, h * 0.025)
        pen.rect(x - w * 0.08, y - bar_h, w * 1.16, bar_h,
                 fill=rod, stroke_width=None, stroke=None, name=f"挂杆 {label}")
        pen.rect(x, y, w, h, fill=cloth, stroke_width=None, stroke=None, name=f"帷幔 {label}")
        pen.ellipse(x + w / 2, y + h * 0.03, w * 0.5, h * 0.05,
                    fill=fold, stroke_width=None, stroke=None, name="帷幔顶褶")

        for step, tone, width in folds:
            fx = x + w * step
            pen.line(fx, y + h * 0.06, fx, y + h * 0.97, width=width, color=tone, name="帷幔褶")

        tie_y = y + h * 0.62
        pen.line(x + w * 0.3, tie_y, x + w * 0.7, tie_y,
                 width=max(2, h * 0.012), color=rod, name="束带")
        pen.ellipse(x + w * 0.5, tie_y, w * 0.07, h * 0.035,
                    fill=highlight, stroke_width=None, stroke=None, name="束带结")

        pen.rect(x, y + h - h * 0.02, w, h * 0.02,
                 fill=fold, stroke_width=None, stroke=None, name="帷幔底边")


def window_glow(params: dict, pen: Pen) -> None:
    """窗光。

    参数：
        window      [x, y, 宽, 高]，中间那扇窗的范围，必填
        glow_steps  窗周光晕层数，1 到 4，默认 3
        halo        [中心x, 中心y, 半径x, 半径y]，人物背后的亮部，可选；
                    默认取窗下沿、宽约窗宽的两倍
        pool        [中心x, 中心y, 半径x, 半径y]，桌面上被照亮的一块，可选
        colors      {glow, hot, halo, pool}，可选
    """
    x, y, w, h = _numbers(params.get("window"), 4, "窗光需要 window：[x, y, 宽, 高]")
    if w <= 0 or h <= 0:
        raise ValueError("窗光的 window 宽高必须大于 0")

    colors = params.get("colors") or {}
    glow = colors.get("glow", "surface")
    hot = colors.get("hot", "accent")
    halo_color = colors.get("halo", "surface")
    pool_color = colors.get("pool", "accent")

    steps = max(1, min(4, int(params.get("glow_steps", 3))))
    for level in range(steps, 0, -1):
        pad = w * 0.15 * level
        full_w = w + pad * 2
        pen.rounded_rect(x - pad, y - pad, full_w, h + pad * 2,
                         radius=[full_w / 2, full_w / 2, 0, 0],
                         fill=hot if level == 1 else glow,
                         stroke_width=None, stroke=None, name="窗光晕")

    halo = params.get("halo")
    if halo is None:
        hx, hy, hrx, hry = x + w / 2, y + h * 0.8, w * 1.9, h * 0.7
    else:
        hx, hy, hrx, hry = _numbers(halo, 4, "窗光的 halo 要给 [中心x, 中心y, 半径x, 半径y]")
    pen.ellipse(hx, hy, hrx, hry, fill=halo_color, stroke_width=None, stroke=None,
                name="人物背后亮部")

    pool = params.get("pool")
    if pool is not None:
        px, py, prx, pry = _numbers(pool, 4, "窗光的 pool 要给 [中心x, 中心y, 半径x, 半径y]")
        pen.ellipse(px, py, prx, pry, fill=pool_color, stroke_width=None, stroke=None,
                    name="桌面光斑")


def soft_vignette(params: dict, pen: Pen) -> None:
    """四角阴影与桌下暗部。

    参数：
        frame         [x, y, 宽, 高]，要压暗的画面范围，必填
        corners       是否压暗四角，默认 true
        corner_x      四角暗部的横向半径，默认 frame 宽的 0.23
        corner_y      四角暗部的纵向半径，默认 frame 高的 0.22
        under_shadow  [中心x, 中心y, 半径x, 半径y]，桌下柔光暗部，可选
        colors        {deep, mid, far, shade_deep, shade_far}，可选
    """
    fx, fy, fw, fh = _numbers(params.get("frame"), 4, "四角阴影需要 frame：[x, y, 宽, 高]")
    if fw <= 0 or fh <= 0:
        raise ValueError("四角阴影的 frame 宽高必须大于 0")

    colors = params.get("colors") or {}
    deep = colors.get("deep", "muted")
    mid = colors.get("mid", "line")
    far = colors.get("far", "soft")
    shade_deep = colors.get("shade_deep", "muted")
    shade_far = colors.get("shade_far", "soft")

    if bool(params.get("corners", True)):
        rx = float(params.get("corner_x", fw * 0.23))
        ry = float(params.get("corner_y", fh * 0.22))
        if rx <= 0 or ry <= 0:
            raise ValueError("四角阴影的 corner_x 和 corner_y 必须大于 0")
        # 三层椭圆从外到内加深，圆心落在角上，画布外的一半由引擎裁掉。
        for cx, cy in ((fx, fy), (fx + fw, fy), (fx, fy + fh), (fx + fw, fy + fh)):
            pen.ellipse(cx, cy, rx, ry, fill=far, stroke_width=None, stroke=None, name="边角老化")
            pen.ellipse(cx, cy, rx * 0.62, ry * 0.62, fill=mid,
                        stroke_width=None, stroke=None, name="边角老化")
            pen.ellipse(cx, cy, rx * 0.3, ry * 0.3, fill=deep,
                        stroke_width=None, stroke=None, name="边角老化")

    under = params.get("under_shadow")
    if under is not None:
        ux, uy, urx, ury = _numbers(under, 4, "四角阴影的 under_shadow 要给 [中心x, 中心y, 半径x, 半径y]")
        pen.ellipse(ux, uy, urx * 1.18, ury * 1.6, fill=shade_far,
                    stroke_width=None, stroke=None, name="桌下暗部")
        pen.ellipse(ux, uy, urx, ury, fill=shade_deep,
                    stroke_width=None, stroke=None, name="桌下暗部")
