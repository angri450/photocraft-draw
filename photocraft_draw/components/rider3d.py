# -*- coding: utf-8 -*-
"""三维骑手：马和人都用三维坐标摆，投影后按 z 排序。

每个部件是"两个端点 + 一个宽度 + 一个深度"。端点给 x、y、z 三个坐标，
z 越大越远。投影到画面时 z 会变成一点偏移，绘制顺序按 z 从远到近排，
近的自动盖住远的，遮挡关系由坐标决定，不靠手调顺序。

坐标以马肩为原点，单位是肩高。
"""
from __future__ import annotations

import math

from ..commands import Pen
from .block import _capsule

SKEW_X = 0.42
SKEW_Y = 0.22


def _parts(pose: str) -> list[dict]:
    """部件的三维表。端点 [x, y, z]，宽度是按肩高的比例。"""
    legs = {
        "fl": {"x": 0.02, "z": -0.09, "angles": {"stand": (86, 90, 72), "walk": (70, 100, 62), "gallop": (55, 118, 40)}},
        "fr": {"x": 0.02, "z": 0.13, "angles": {"stand": (92, 94, 76), "walk": (98, 84, 86), "gallop": (40, 128, 30)}},
        "bl": {"x": -0.44, "z": -0.09, "angles": {"stand": (94, 88, 74), "walk": (108, 78, 80), "gallop": (120, 70, 60)}},
        "br": {"x": -0.44, "z": 0.13, "angles": {"stand": (90, 86, 70), "walk": (84, 94, 70), "gallop": (110, 78, 52)}},
    }
    lengths = (0.17, 0.17, 0.06)

    out = [
        # 马身：一个长条
        {"name": "马身", "a": (-0.55, -0.02, 0), "b": (0.0, -0.02, 0), "w": 0.27, "color": "mid"},
        # 颈、头
        {"name": "马颈下", "a": (0.0, -0.07, 0), "b": (0.11, -0.24, 0), "w": 0.14, "color": "mid"},
        {"name": "马颈上", "a": (0.11, -0.24, 0), "b": (0.22, -0.36, 0), "w": 0.115, "color": "mid"},
        {"name": "马头", "a": (0.22, -0.36, 0), "b": (0.42, -0.3, 0), "w": 0.11, "color": "mid"},
        # 鬃毛
        {"name": "鬃毛下", "a": (0.01, -0.15, 0.02), "b": (0.12, -0.32, 0.02), "w": 0.045, "color": "line"},
        {"name": "鬃毛上", "a": (0.12, -0.32, 0.02), "b": (0.23, -0.43, 0.02), "w": 0.04, "color": "line"},
        # 尾巴
        {"name": "尾 1", "a": (-0.56, -0.08, 0), "b": (-0.66, 0.04, 0), "w": 0.055, "color": "line"},
        {"name": "尾 2", "a": (-0.66, 0.04, 0), "b": (-0.7, 0.17, 0), "w": 0.05, "color": "line"},
        # 骑手：躯干在最前，两条腿分在马身两侧
        {"name": "躯干", "a": (-0.3, -0.16, -0.2), "b": (-0.3, -0.5, -0.2), "w": 0.24, "color": "deep"},
        {"name": "头", "a": (-0.3, -0.6, -0.2), "b": (-0.3, -0.6, -0.2), "w": 0.18, "color": "soft"},
        {"name": "右臂", "a": (-0.24, -0.46, -0.24), "b": (-0.05, -0.62, -0.24), "w": 0.075, "color": "deep"},
        {"name": "左臂", "a": (-0.36, -0.44, -0.24), "b": (-0.2, -0.22, -0.24), "w": 0.07, "color": "deep"},
        {"name": "斗篷", "a": (-0.38, -0.46, -0.1), "b": (-0.58, -0.28, -0.06), "w": 0.12, "color": "accent"},
        # 近侧腿：z 最小，最后画，压在马身上
        {"name": "近侧大腿", "a": (-0.28, -0.16, -0.18), "b": (-0.16, -0.04, -0.18), "w": 0.095, "color": "deep"},
        {"name": "近侧小腿", "a": (-0.16, -0.04, -0.18), "b": (-0.2, 0.22, -0.18), "w": 0.08, "color": "deep"},
        {"name": "近侧靴", "a": (-0.2, 0.22, -0.18), "b": (-0.14, 0.25, -0.18), "w": 0.08, "color": "ink"},
        # 远侧腿：z 最大，最先画，被马身挡住
        {"name": "远侧大腿", "a": (-0.3, -0.16, 0.16), "b": (-0.2, -0.04, 0.16), "w": 0.09, "color": "deep"},
        {"name": "远侧小腿", "a": (-0.2, -0.04, 0.16), "b": (-0.24, 0.2, 0.16), "w": 0.075, "color": "deep"},
        {"name": "远侧靴", "a": (-0.24, 0.2, 0.16), "b": (-0.18, 0.23, 0.16), "w": 0.075, "color": "ink"},
    ]

    # 马腿：每条三段，按关节角度连起来
    for key, spec in legs.items():
        x, z = spec["x"], spec["z"]
        angle_list = spec["angles"][pose]
        y = 0.1
        for index, (angle, length) in enumerate(zip(angle_list, lengths)):
            a = math.radians(angle)
            nx = x + math.cos(a) * length
            ny = y + math.sin(a) * length
            out.append({
                "name": f"腿 {key} {index + 1}",
                "a": (x, y, z), "b": (nx, ny, z),
                "w": 0.09 * (1.0 if index == 2 else 1.2),
                "color": "ink" if index == 2 else "mid",
            })
            x, y = nx, ny

    return out


def build_rider3d(params: dict, pen: Pen) -> None:
    """三维骑手：部件按 z 从远到近投影，遮挡自动正确。

    参数：
        root    [x, y]，马肩位置，必填
        length  肩高像素，必填
        pose    stand / walk / gallop
        skew_x  z 的横向偏移，默认 0.42
        skew_y  z 的纵向偏移，默认 0.22
    """
    root = params.get("root")
    if not isinstance(root, (list, tuple)) or len(root) != 2:
        raise ValueError("三维骑手需要 root：[x, y]，马肩位置")
    height = params.get("length")
    if isinstance(height, bool) or not isinstance(height, (int, float)) or height <= 0:
        raise ValueError("三维骑手需要 length，大于 0 的肩高像素")
    pose = str(params.get("pose", "stand"))
    if pose not in ("stand", "walk", "gallop"):
        raise ValueError("三维骑手 pose 只能是 stand、walk、gallop")
    skew_x = float(params.get("skew_x", SKEW_X))
    skew_y = float(params.get("skew_y", SKEW_Y))

    sx, sy = float(root[0]), float(root[1])
    u = float(height)
    parts = _parts(pose)

    def project(point):
        x, y, z = point
        return (sx + x * u + z * skew_x * u, sy + y * u - z * skew_y * u)

    # z 大的先画，小的后画
    parts.sort(key=lambda item: -((item["a"][2] + item["b"][2]) / 2))

    for item in parts:
        ax, ay = project(item["a"])
        bx, by = project(item["b"])
        width = item["w"] * u
        if item["name"] == "头":
            radius = width / 2
            pen.ellipse(ax, ay - radius * 0.4, radius, radius,
                        fill=item["color"], stroke_width=None, stroke=None, name=item["name"])
        else:
            _capsule(pen, ax, ay, bx, by, width, item["color"], item["name"])


COMPONENTS = {
    "rider3d": {
        "name": "三维骑手",
        "description": "马和人用三维坐标摆，按 z 从远到近投影，遮挡自动正确",
        "params": {
            "root": "[x, y]，马肩位置，必填",
            "length": "肩高像素，必填",
            "pose": "stand / walk / gallop",
            "skew_x": "z 的横向偏移，默认 0.42",
            "skew_y": "z 的纵向偏移，默认 0.22",
        },
        "build": build_rider3d,
    },
}

__all__ = ["build_rider3d", "COMPONENTS"]
