# -*- coding: utf-8 -*-
"""人物模型：先有关节，再有姿态。

动画里的白模靠关节说话：肩、肘、腕、髋、膝、踝各自一个点，点之间用
一段骨头连起来。画笔不能旋转矩形，所以骨头用粗线画，两端补一个圆当
关节，看上去是有粗细的骨段，不是一根棍。

坐标以髋部为原点，向上是负 y，身高按 1.0 归一，调用时给像素高度缩放。
这样同一套关节表能用在任何画幅上。
"""
from __future__ import annotations

from ..commands import Pen

# 每个姿态一张关节表，单位是身高比例，原点在髋部
POSES: dict[str, dict[str, tuple[float, float]]] = {
    "stand": {
        "hip": (0, 0),
        "chest": (0, -0.28),
        "neck": (0, -0.34),
        "head": (0, -0.41),
        "shoulder_l": (-0.11, -0.32),
        "shoulder_r": (0.11, -0.32),
        "elbow_l": (-0.15, -0.13),
        "elbow_r": (0.15, -0.13),
        "hand_l": (-0.16, 0.06),
        "hand_r": (0.16, 0.06),
        "knee_l": (-0.07, 0.42),
        "knee_r": (0.07, 0.42),
        "foot_l": (-0.08, 0.84),
        "foot_r": (0.08, 0.84),
    },
    "walk": {
        "hip": (0, 0),
        "chest": (0.01, -0.28),
        "neck": (0.02, -0.34),
        "head": (0.03, -0.41),
        "shoulder_l": (-0.1, -0.32),
        "shoulder_r": (0.13, -0.32),
        "elbow_l": (-0.18, -0.16),
        "elbow_r": (0.19, -0.12),
        "hand_l": (-0.22, -0.02),
        "hand_r": (0.15, 0.04),
        "knee_l": (-0.14, 0.4),
        "knee_r": (0.16, 0.36),
        "foot_l": (-0.24, 0.78),
        "foot_r": (0.2, 0.72),
    },
    "point": {
        "hip": (0, 0),
        "chest": (0, -0.28),
        "neck": (0, -0.34),
        "head": (0, -0.41),
        "shoulder_l": (-0.11, -0.32),
        "shoulder_r": (0.11, -0.32),
        "elbow_l": (-0.16, -0.14),
        "elbow_r": (0.3, -0.38),
        "hand_l": (-0.17, 0.05),
        "hand_r": (0.46, -0.4),
        "knee_l": (-0.07, 0.42),
        "knee_r": (0.07, 0.42),
        "foot_l": (-0.08, 0.84),
        "foot_r": (0.08, 0.84),
    },
    "sit": {
        "hip": (0, 0),
        "chest": (0, -0.26),
        "neck": (0, -0.32),
        "head": (0, -0.39),
        "shoulder_l": (-0.11, -0.3),
        "shoulder_r": (0.11, -0.3),
        "elbow_l": (-0.16, -0.14),
        "elbow_r": (0.16, -0.14),
        "hand_l": (-0.2, -0.02),
        "hand_r": (0.2, -0.02),
        "knee_l": (-0.22, 0.06),
        "knee_r": (0.22, 0.06),
        "foot_l": (-0.24, 0.42),
        "foot_r": (0.24, 0.42),
    },
    "ride": {
        "hip": (0, 0),
        "chest": (0, -0.26),
        "neck": (0, -0.32),
        "head": (0, -0.39),
        "shoulder_l": (-0.11, -0.3),
        "shoulder_r": (0.11, -0.3),
        "elbow_l": (-0.26, -0.4),
        "elbow_r": (0.2, -0.16),
        "hand_l": (-0.4, -0.48),
        "hand_r": (0.28, -0.04),
        "knee_l": (-0.3, 0.04),
        "knee_r": (0.3, 0.04),
        "foot_l": (-0.34, 0.34),
        "foot_r": (0.34, 0.34),
    },
}

# 骨段：起点、终点、粗细（相对身高）
BONES = (
    ("hip", "chest", 0.13),
    ("chest", "neck", 0.06),
    ("neck", "head", 0.06),
    ("chest", "shoulder_l", 0.09),
    ("shoulder_l", "elbow_l", 0.065),
    ("elbow_l", "hand_l", 0.05),
    ("chest", "shoulder_r", 0.09),
    ("shoulder_r", "elbow_r", 0.065),
    ("elbow_r", "hand_r", 0.05),
    ("hip", "knee_l", 0.095),
    ("knee_l", "foot_l", 0.07),
    ("hip", "knee_r", 0.095),
    ("knee_r", "foot_r", 0.07),
)

# 关节半径相对身高
JOINT_SCALE = {
    "hip": 0.065,
    "chest": 0.06,
    "neck": 0.045,
    "shoulder_l": 0.05,
    "shoulder_r": 0.05,
    "elbow_l": 0.04,
    "elbow_r": 0.04,
    "hand_l": 0.035,
    "hand_r": 0.035,
    "knee_l": 0.045,
    "knee_r": 0.045,
    "foot_l": 0.04,
    "foot_r": 0.04,
}


# 朝向词表：正面朝观众，侧身转向画面左或右，背对观众
FACE_WORDS = ("front", "left", "right", "back")

JOINT_NAMES = tuple(JOINT_SCALE) + ("head",)


def _pose_table(value) -> dict[str, tuple[float, float]]:
    if isinstance(value, str):
        if value not in POSES:
            raise ValueError(f"pose 只能是 {'、'.join(POSES)}，收到 {value}")
        return POSES[value]
    if isinstance(value, dict):
        missing = [name for name in JOINT_NAMES if name not in value]
        if missing:
            raise ValueError(f"自定义姿态缺少关节：{'、'.join(missing)}")
        table = {}
        for name in JOINT_NAMES:
            point = value[name]
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError(f"关节 {name} 要写成 [x, y]")
            table[name] = (float(point[0]), float(point[1]))
        return table
    raise ValueError("pose 给姿态名，或者直接给一张关节表")


def _draw_face(pen: Pen, face: str, points: dict, height: float,
                color: str) -> None:
    """在头上点出五官位置，让白模一眼看出脸朝哪边。

    白模只有关节和骨段，本来分不出正面和背面。脸上点上眼睛和鼻子，
    朝向就写在画面上了。back 不画五官，只在头后画一道后脑线。
    """
    hx, hy = points["head"]
    hr = 0.075 * height
    cy = hy - hr * 0.35
    if face == "back":
        pen.line(hx - hr * 0.5, cy - hr * 0.45, hx + hr * 0.5, cy - hr * 0.45,
                 width=max(1, hr * 0.18), color=color, name="后脑")
        return
    shift = 0.0
    if face == "left":
        shift = -hr * 0.34
    elif face == "right":
        shift = hr * 0.34
    eye = hr * 0.15
    for sign in (-1, 1):
        pen.ellipse(hx + shift + sign * hr * 0.28, cy - hr * 0.08, eye, eye,
                    fill=color, stroke_width=None, stroke=None, name="眼")
    if face == "front":
        pen.line(hx, cy + hr * 0.10, hx, cy + hr * 0.32,
                 width=max(1, hr * 0.14), color=color, name="鼻")
        pen.line(hx - hr * 0.20, cy + hr * 0.52, hx + hr * 0.20, cy + hr * 0.52,
                 width=max(1, hr * 0.14), color=color, name="嘴")
    else:
        direction = -1 if face == "left" else 1
        pen.line(hx + shift, cy + hr * 0.08,
                 hx + shift + direction * hr * 0.30, cy + hr * 0.26,
                 width=max(1, hr * 0.14), color=color, name="鼻")
        pen.line(hx + shift - hr * 0.12, cy + hr * 0.50,
                 hx + shift + hr * 0.12, cy + hr * 0.50,
                 width=max(1, hr * 0.14), color=color, name="嘴")


def build_figure_rig(params: dict, pen: Pen) -> None:
    """人物白模：关节加骨段，能看出肩肘腕和髋膝踝。

    参数：
        root    [x, y]，髋部位置，必填
        height  身高像素，必填
        pose    stand / walk / point / sit / ride，也可以直接给关节表
        body    身体颜色，默认 surface
        joint   关节颜色，默认 line
        head    头部颜色，默认 surface
        flip    是否左右翻转，默认 false
        face    朝向，front / left / right / back，默认不画
    """
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("人物模型需要 root：[x, y]，髋部位置")
    height = params.get("height")
    if isinstance(height, bool) or not isinstance(height, (int, float)) or height <= 0:
        raise ValueError("人物模型需要 height，大于 0 的像素高度")

    table = _pose_table(params.get("pose", "stand"))
    body = params.get("body", "surface")
    joint_color = params.get("joint", "line")
    head_color = params.get("head", body)
    flip = bool(params.get("flip", False))
    if flip:
        table = {name: (-x, y) for name, (x, y) in table.items()}

    face = params.get("face")
    if face is not None and face not in FACE_WORDS:
        raise ValueError("face 只能是 %s，收到 %s" % ("、".join(FACE_WORDS), face))

    ox, oy = float(root[0]), float(root[1])
    points = {name: (ox + x * height, oy + y * height) for name, (x, y) in table.items()}

    # 先画骨段
    for start, end, width in BONES:
        (x1, y1), (x2, y2) = points[start], points[end]
        pen.line(x1, y1, x2, y2, width=max(1, width * height),
                 color=body, name=f"骨段 {start}-{end}")

    # 再画关节，盖住线段端头，看起来是圆的
    for name, radius in JOINT_SCALE.items():
        x, y = points[name]
        r = max(1.5, radius * height)
        pen.ellipse(x, y, r, r, fill=joint_color, stroke_width=None, stroke=None,
                    name=f"关节 {name}")

    # 头最后画
    hx, hy = points["head"]
    hr = 0.075 * height
    pen.ellipse(hx, hy - hr * 0.35, hr * 0.86, hr,
                fill=head_color, stroke_width=None, stroke=None, name="头")

    if face in ("front", "left", "right"):
        _draw_face(pen, face, points, height, joint_color)
    elif face == "back":
        _draw_face(pen, "back", points, height, joint_color)


COMPONENTS = {
    "figure_rig": {
        "name": "人物白模",
        "description": "关节加骨段的人体模型，肩肘腕和髋膝踝都在，五种姿态可切",
        "params": {
            "root": "[x, y]，髋部位置，必填",
            "height": "身高像素，必填",
            "pose": "stand / walk / point / sit / ride，也可以直接给关节表",
            "body": "身体颜色，默认 surface",
            "joint": "关节颜色，默认 line",
            "head": "头部颜色，默认 surface",
            "flip": "是否左右翻转，默认 false",
            "face": "朝向，front / left / right / back，默认不画",
        },
        "build": build_figure_rig,
    },
}


__all__ = ["build_figure_rig", "POSES", "BONES", "COMPONENTS"]
