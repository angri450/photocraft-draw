# -*- coding: utf-8 -*-
"""人物组件：坐姿躯干、头部、手、前倾身体。

壁画里的人物只露桌面以上，所以躯干组件只画肩到桌沿这一段，头部和手
单独成组件，方便在方案里分别调姿态。坐标按 800 宽的参考画布写。

画法约定（见 docs/component-references.md 第四节）：
    脸分额头、颊部、下颌三块面，眼睛只画上眼睑，嘴是一条短线；
    头发和胡子是整块形状，不画一根根线条；
    手只做手掌加并拢的四指，不分开画指头；
    袍子先大色块，再压两三块暗褶，最后一条亮边，不描黑边。
"""
from __future__ import annotations

from ..commands import Pen

TURNS = ("left", "front", "right")
POSES = ("front", "side", "open", "point", "grip")
HAND_KINDS = ("open", "grip", "point", "rest")


def _box(value, message: str) -> tuple[float, float, float, float]:
    """把参数读成 [x, y, 宽, 高]，形状不对或宽高不为正就报错。"""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(message)
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(message)
    x, y, w, h = (float(item) for item in value)
    if w <= 0 or h <= 0:
        raise ValueError(message)
    return x, y, w, h


def _point(value, message: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(message)
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(message)
    return float(value[0]), float(value[1])


def _positive(value, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{what}要大于 0")
    return float(value)


def _limb(pen: Pen, points, width: float, color: str, name: str, taper: float = 0.7) -> None:
    """沿折线摆一串重叠椭圆，拼出有粗细变化的手臂或躯干。

    画笔没有旋转和路径，斜向的肢体只能用一连串小椭圆接出来；椭圆互相
    重叠，看上去是一整条，不会露出接头。
    """
    if not points:
        raise ValueError(f"{name}缺少落笔点")
    start_width = width
    total = len(points) - 1
    steps = 3 if total > 0 else 1
    index = 0
    for seg in range(max(total, 1)):
        (x1, y1), (x2, y2) = points[seg], points[seg + 1] if total else points[0]
        for step in range(steps + 1):
            t = step / steps
            ratio = (seg + t) / max(total, 1)
            radius = (start_width * (1 - (1 - taper) * ratio)) / 2
            pen.ellipse(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, radius, radius,
                        fill=color, stroke_width=None, stroke=None,
                        name=f"{name} {index + 1}")
            index += 1


def build_seated_figure(params: dict, pen: Pen) -> None:
    """坐姿人物的躯干，肩以下到桌沿。

    所有形状都收在 seat 框里，不往外长，保证并排时不会互相压成串珠。

    参数：
        seat    [x, y, 宽, 高]，肩线到桌沿的框，必填
        pose    front 端坐 / side 侧身 / open 摊手 / point 手指向前 / grip 扶桌沿
        robe    袍子主色，默认 deep
        trim    内袍颜色，默认 soft
        shade   袖子和暗褶，默认 ink
        collar  领口肤色，默认 soft
    """
    x, y, w, h = _box(params.get("seat"), "坐姿人物需要 seat：[x, y, 宽, 高]")
    pose = str(params.get("pose", "front"))
    if pose not in POSES:
        raise ValueError(f"pose 只能是 {'、'.join(POSES)}，收到 {pose}")
    robe = params.get("robe", "deep")
    trim = params.get("trim", "soft")
    shade = params.get("shade", "ink")
    collar = params.get("collar", "soft")

    cx = x + w / 2
    lean = -w * 0.03 if pose == "side" else 0.0

    # 座椅暗部：只在袍子底下露一条
    pen.ellipse(cx, y + h * 0.82, w * 0.4, h * 0.12,
                fill=shade, stroke_width=None, stroke=None, name="座椅暗部")

    # 袍身：一个圆角方块，半径很小，避免变成花瓶
    pen.rounded_rect(x + w * 0.14 + lean, y + h * 0.16, w * 0.72, h * 0.74,
                     radius=w * 0.05, fill=robe, stroke_width=None, stroke=None, name="袍身")

    # 肩：比袍身宽一截的横椭圆，压出肩线
    pen.ellipse(cx + lean, y + h * 0.14, w * 0.56, h * 0.1,
                fill=robe, stroke_width=None, stroke=None, name="肩")

    # 领口和内袍
    pen.ellipse(cx + lean, y + h * 0.1, w * 0.09, h * 0.03,
                fill=collar, stroke_width=None, stroke=None, name="领口")
    pen.ellipse(cx + lean, y + h * 0.42, w * 0.15, h * 0.17,
                fill=trim, stroke_width=None, stroke=None, name="内袍")

    # 袍褶：全部落在袍身里面
    pen.ellipse(cx - w * 0.2 + lean, y + h * 0.62, w * 0.04, h * 0.16,
                fill=shade, stroke_width=None, stroke=None, name="左袍褶")
    pen.ellipse(cx + w * 0.22 + lean, y + h * 0.58, w * 0.035, h * 0.13,
                fill=shade, stroke_width=None, stroke=None, name="右袍褶")

    # 姿态：袖子只用窄椭圆，中心到边缘都在框里
    if pose == "open":
        pen.ellipse(x + w * 0.14 + lean, y + h * 0.68, w * 0.13, h * 0.27,
                    fill=shade, stroke_width=None, stroke=None, name="左袖")
        pen.ellipse(x + w * 0.86 + lean, y + h * 0.68, w * 0.13, h * 0.27,
                    fill=shade, stroke_width=None, stroke=None, name="右袖")
    elif pose == "point":
        pen.ellipse(x + w * 0.16 + lean, y + h * 0.6, w * 0.1, h * 0.22,
                    fill=shade, stroke_width=None, stroke=None, name="收起的左袖")
        pen.ellipse(x + w * 0.7 + lean, y + h * 0.92, w * 0.2, h * 0.045,
                    fill=shade, stroke_width=None, stroke=None, name="右前臂")
    elif pose == "grip":
        pen.ellipse(cx - w * 0.18 + lean, y + h * 0.93, w * 0.17, h * 0.045,
                    fill=shade, stroke_width=None, stroke=None, name="左前臂")
        pen.ellipse(cx + w * 0.18 + lean, y + h * 0.93, w * 0.17, h * 0.045,
                    fill=shade, stroke_width=None, stroke=None, name="右前臂")
    elif pose == "side":
        pen.ellipse(x + w * 0.16 + lean, y + h * 0.58, w * 0.1, h * 0.2,
                    fill=shade, stroke_width=None, stroke=None, name="近侧袖")
        pen.line(x + w * 0.24 + lean, y + h * 0.2, x + w * 0.2 + lean, y + h * 0.78,
                 width=1.2, color=trim, name="侧身亮边")

    # 肩线亮边，只走一小段
    if pose != "side":
        pen.line(x + w * 0.26, y + h * 0.14, cx - w * 0.08, y + h * 0.32,
                 width=1.2, color=trim, name="肩部亮边")


def build_leaning_figure(params: dict, pen: Pen) -> None:
    """前倾撑桌的人物，比如犹大。

    身体压向桌面，一侧手肘落在桌上。用三块椭圆拼出斜向的重心，
    不使用椭圆串，避免和旁边的人糊成一团。

    参数：
        seat    [x, y, 宽, 高]，肩线到桌沿的框，必填
        elbow   [x, y]，撑桌的手肘落点，必填
        robe    袍子主色，默认 mid
        trim    亮边颜色，默认 soft
        shade   暗褶颜色，默认 ink
    """
    x, y, w, h = _box(params.get("seat"), "前倾人物需要 seat：[x, y, 宽, 高]")
    ex, ey = _point(params.get("elbow"), "前倾人物需要 elbow：[手肘x, 手肘y]")
    robe = params.get("robe", "mid")
    trim = params.get("trim", "soft")
    shade = params.get("shade", "ink")

    cx = x + w / 2
    # 后背：偏向一侧，形成前倾的斜度
    pen.ellipse(x + w * 0.32, y + h * 0.24, w * 0.34, h * 0.2,
                fill=robe, stroke_width=None, stroke=None, name="后背")
    # 躯干：压在桌上的一块斜椭圆
    pen.ellipse(cx + w * 0.1, y + h * 0.56, w * 0.4, h * 0.34,
                fill=robe, stroke_width=None, stroke=None, name="前倾躯干")
    # 靠近手肘的下半身
    pen.ellipse(ex - w * 0.1, ey - h * 0.16, w * 0.3, h * 0.18,
                fill=robe, stroke_width=None, stroke=None, name="下摆")
    # 撑桌的前臂，横着落在桌面
    pen.ellipse((cx + ex) / 2 + w * 0.1, ey - h * 0.04, w * 0.3, h * 0.04,
                fill=shade, stroke_width=None, stroke=None, name="撑桌前臂")
    # 内袍和背褶
    pen.ellipse(cx + w * 0.16, y + h * 0.5, w * 0.13, h * 0.12,
                fill=trim, stroke_width=None, stroke=None, name="内袍")
    pen.ellipse(x + w * 0.3, y + h * 0.5, w * 0.05, h * 0.14,
                fill=shade, stroke_width=None, stroke=None, name="背褶")
    # 钱袋，犹大的标记，挂在腰侧
    pen.ellipse(ex - w * 0.18, ey - h * 0.1, w * 0.08, h * 0.05,
                fill="mid", stroke_width=None, stroke=None, name="钱袋")


def build_figure_head(params: dict, pen: Pen) -> None:
    """人物头部，含脸、发、胡须和五官。

    参数：
        center  [中心x, 中心y]，必填
        size    头高，默认 42
        turn    left / front / right，默认 front
        beard   是否留胡须，默认 false
        hair    头发颜色，默认 ink
        skin    肤色，默认 soft
        shade   阴影颜色，默认 line
    """
    cx, cy = _point(params.get("center"), "头部需要 center：[中心x, 中心y]")
    size = _positive(params.get("size", 42), "头部的 size ")
    turn = str(params.get("turn", "front"))
    if turn not in TURNS:
        raise ValueError(f"turn 只能是 {'、'.join(TURNS)}，收到 {turn}")
    beard = bool(params.get("beard", False))
    hair = params.get("hair", "ink")
    skin = params.get("skin", "soft")
    shade = params.get("shade", "line")

    r = size / 2
    face_w = r * 0.58
    face_h = r * 0.72

    # 脖子：短而粗，只露出下巴到肩线的一小段
    pen.rect(cx - r * 0.23, cy + r * 0.62, r * 0.46, r * 0.62,
             fill=shade, stroke_width=None, stroke=None, name="脖子")

    # 头发整块，脸压上去后头顶只露一道月牙
    pen.ellipse(cx, cy - r * 0.06, r * 0.64, r * 0.78,
                fill=hair, stroke_width=None, stroke=None, name="头发")
    pen.ellipse(cx, cy + r * 0.08, face_w, face_h,
                fill=skin, stroke_width=None, stroke=None, name="脸")

    # 两侧鬓发，压在脸的外缘
    pen.ellipse(cx - r * 0.5, cy + r * 0.02, r * 0.12, r * 0.3,
                fill=hair, stroke_width=None, stroke=None, name="左鬓")
    pen.ellipse(cx + r * 0.5, cy + r * 0.02, r * 0.12, r * 0.3,
                fill=hair, stroke_width=None, stroke=None, name="右鬓")

    # 下颌阴影，把脸分成额头、颊部、下颌三块
    pen.ellipse(cx, cy + r * 0.42, face_w * 0.8, face_h * 0.24,
                fill=shade, stroke_width=None, stroke=None, name="下颌阴影")

    if beard:
        pen.ellipse(cx, cy + r * 0.52, r * 0.26, r * 0.22,
                    fill=hair, stroke_width=None, stroke=None, name="胡须")
        pen.ellipse(cx, cy + r * 0.16, r * 0.18, r * 0.05,
                    fill=hair, stroke_width=None, stroke=None, name="唇上须")

    # 五官随转头方向整体偏移
    offset = {"left": -r * 0.07, "right": r * 0.07, "front": 0.0}[turn]
    for sign in (-1, 1):
        ex = cx + offset + sign * r * 0.19
        pen.line(ex - r * 0.07, cy - r * 0.06, ex + r * 0.07, cy - r * 0.05,
                 width=1.6, color=shade, name="眼睑")
    # 鼻：一条侧影
    pen.line(cx + offset * 1.5, cy + r * 0.02,
             cx + offset * 1.5 + r * 0.04, cy + r * 0.16,
             width=1, color=shade, name="鼻影")
    if not beard:
        pen.line(cx + offset - r * 0.07, cy + r * 0.3,
                 cx + offset + r * 0.07, cy + r * 0.3,
                 width=1, color=shade, name="嘴")

    # 耳朵只在侧脸露出来
    if turn != "front":
        ear_x = cx + (-r * 0.56 if turn == "right" else r * 0.56)
        pen.ellipse(ear_x, cy + r * 0.06, r * 0.08, r * 0.13,
                    fill=skin, stroke_width=1, stroke=shade, name="耳朵")


def _hand_shape(pen: Pen, cx: float, cy: float, s: float, kind: str,
                skin: str, shade: str) -> None:
    """一只手的四种基本形，只用三四个形状。"""
    # 暗底让手从浅色桌布上浮起来
    pen.ellipse(cx + s * 0.06, cy + s * 0.08, s * 0.46, s * 0.34,
                fill=shade, stroke_width=None, stroke=None, name="手影")
    if kind == "open":
        pen.ellipse(cx, cy, s * 0.42, s * 0.32,
                    fill=skin, stroke_width=None, stroke=None, name="手掌")
        pen.ellipse(cx + s * 0.36, cy - s * 0.04, s * 0.28, s * 0.2,
                    fill=skin, stroke_width=None, stroke=None, name="四指")
        pen.ellipse(cx - s * 0.14, cy - s * 0.24, s * 0.16, s * 0.1,
                    fill=skin, stroke_width=None, stroke=None, name="拇指")
        pen.line(cx - s * 0.1, cy + s * 0.08, cx + s * 0.3, cy + s * 0.06,
                 width=1, color=shade, name="指缝")
    elif kind == "grip":
        pen.ellipse(cx, cy, s * 0.4, s * 0.3,
                    fill=skin, stroke_width=None, stroke=None, name="手掌")
        pen.ellipse(cx + s * 0.3, cy - s * 0.1, s * 0.2, s * 0.16,
                    fill=shade, stroke_width=None, stroke=None, name="握起的指")
        pen.ellipse(cx - s * 0.1, cy - s * 0.2, s * 0.18, s * 0.1,
                    fill=skin, stroke_width=None, stroke=None, name="拇指")
    elif kind == "point":
        pen.ellipse(cx, cy, s * 0.38, s * 0.28,
                    fill=skin, stroke_width=None, stroke=None, name="手掌")
        pen.ellipse(cx + s * 0.46, cy - s * 0.1, s * 0.32, s * 0.09,
                    fill=skin, stroke_width=None, stroke=None, name="食指")
        pen.ellipse(cx + s * 0.24, cy + s * 0.12, s * 0.2, s * 0.14,
                    fill=shade, stroke_width=None, stroke=None, name="收起的指")
    else:
        pen.ellipse(cx, cy, s * 0.4, s * 0.26,
                    fill=skin, stroke_width=None, stroke=None, name="手掌")
        for index in range(3):
            pen.ellipse(cx + s * (0.12 + index * 0.16), cy + s * 0.2, s * 0.09, s * 0.16,
                        fill=skin, stroke_width=None, stroke=None, name=f"垂指 {index + 1}")


def build_figure_hands(params: dict, pen: Pen) -> None:
    """一组手，按方案给的落点逐个画。

    参数：
        hands   [[x, y, 姿态], …]，姿态取 open / grip / point / rest，必填
        size    手的大小，默认 14
        skin    肤色，默认 soft
        shade   阴影颜色，默认 line
    """
    hands = params.get("hands")
    if not isinstance(hands, (list, tuple)) or not hands:
        raise ValueError("手部需要 hands：[[x, y, 姿态], …]")
    size = _positive(params.get("size", 14), "手部的 size ")
    skin = params.get("skin", "soft")
    shade = params.get("shade", "line")
    for index, item in enumerate(hands):
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            raise ValueError(f"第 {index + 1} 只手要写成 [x, y, 姿态]")
        cx, cy = _point(item[:2], f"第 {index + 1} 只手的位置要写成 [x, y]")
        kind = str(item[2])
        if kind not in HAND_KINDS:
            raise ValueError(f"第 {index + 1} 只手的姿态只能是 {'、'.join(HAND_KINDS)}")
        _hand_shape(pen, cx, cy, size, kind, skin, shade)


def build_figure_row(params: dict, pen: Pen) -> None:
    """一排坐姿人物，按起点等距排开，用来快速铺满长桌。

    参数：
        row      [起点x, 肩线y, 单人宽, 单人高]，必填
        count    人数，必填
        gap      两人之间的横向间距，默认等于单人宽
        poses    姿态列表，长度不足时循环使用
        robe     袍子主色，默认 deep
        trim     亮边颜色，默认 soft
    """
    x, y, w, h = _box(params.get("row"), "一排人物需要 row：[起点x, 肩线y, 单人宽, 单人高]")
    count = params.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("一排人物需要 count：人数，要大于 0")
    gap = params.get("gap")
    gap = float(gap) if isinstance(gap, (int, float)) else w * 1.12
    poses = params.get("poses") or ["front", "side", "open", "point", "grip"]
    if not isinstance(poses, (list, tuple)) or not poses:
        raise ValueError("poses 要给姿态列表")
    robe = params.get("robe", "deep")
    trim = params.get("trim", "soft")
    for index in range(count):
        build_seated_figure({
            "seat": [x + index * gap, y, w, h],
            "pose": poses[index % len(poses)],
            "robe": robe,
            "trim": trim,
        }, pen)


COMPONENTS = {
    "seated_figure": {
        "name": "坐姿人物",
        "description": "肩到桌沿的坐姿躯干，五种姿态：端坐、侧身、摊手、前指、扶桌",
        "params": {
            "seat": "[x, y, 宽, 高]，肩线到桌沿，必填",
            "pose": "front / side / open / point / grip，默认 front",
            "robe": "袍子主色，默认 deep",
            "trim": "内袍和亮边，默认 soft",
            "shade": "暗褶颜色，默认 ink",
            "collar": "领口肤色，默认 soft",
        },
        "build": build_seated_figure,
    },
    "leaning_figure": {
        "name": "前倾人物",
        "description": "身体压向桌面、手肘撑桌的人物，用来画犹大这类姿态",
        "params": {
            "seat": "[x, y, 宽, 高]，肩线到桌沿，必填",
            "elbow": "[手肘x, 手肘y]，撑桌落点，必填",
            "robe": "袍子主色，默认 mid",
            "trim": "亮边颜色，默认 soft",
            "shade": "暗褶颜色，默认 ink",
        },
        "build": build_leaning_figure,
    },
    "figure_head": {
        "name": "人物头部",
        "description": "脸、头发、胡须和五官，眼睛只画上眼睑，转头时五官整体偏移",
        "params": {
            "center": "[中心x, 中心y]，必填",
            "size": "头高，默认 42",
            "turn": "left / front / right，默认 front",
            "beard": "是否留胡须，默认 false",
            "hair": "头发颜色，默认 ink",
            "skin": "肤色，默认 soft",
            "shade": "阴影颜色，默认 line",
        },
        "build": build_figure_head,
    },
    "figure_hands": {
        "name": "一组手",
        "description": "按落点画多只手，四种姿态：摊开、握住、前指、垂下",
        "params": {
            "hands": "[[x, y, 姿态], …]，必填",
            "size": "手的大小，默认 14",
            "skin": "肤色，默认 soft",
            "shade": "阴影颜色，默认 line",
        },
        "build": build_figure_hands,
    },
    "figure_row": {
        "name": "一排人物",
        "description": "按起点等距排开的一排坐姿人物，姿态循环使用",
        "params": {
            "row": "[起点x, 肩线y, 单人宽, 单人高]，必填",
            "count": "人数，必填",
            "gap": "横向间距，默认单人宽的 1.12 倍",
            "poses": "姿态列表，默认五种姿态循环",
            "robe": "袍子主色，默认 deep",
            "trim": "亮边颜色，默认 soft",
        },
        "build": build_figure_row,
    },
}


__all__ = [
    "build_seated_figure",
    "build_leaning_figure",
    "build_figure_head",
    "build_figure_hands",
    "build_figure_row",
    "COMPONENTS",
]
