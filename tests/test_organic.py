# -*- coding: utf-8 -*-
"""有机形状层：花瓣、叶片、花苞的投影与遮挡顺序。"""
import pytest

from photocraft_draw.commands import Pen
from photocraft_draw.organic import build
from photocraft_draw.palette import resolve_palette

CAMERA = {"position": [0, 0, -1], "target": [0, 0, 0], "up": [0, 1, 0],
          "focal": 600, "frame": [800, 800], "center": [400, 400],
          "projection": "perspective"}


def pen():
    return Pen(800, 800, ref_width=800, palette=resolve_palette("fresco"))


def test_sprite_draws_one_path():
    target = pen()
    build({"camera": CAMERA, "items": [
        {"shape": "leaf", "center": [0, 0, 0], "facing": [0, 0, -1],
         "radial": [0, 1, 0], "size": 0.2, "width": 0.08, "color": "#6F8F52"}
    ]}, target)
    assert len(target.commands) == 1


def test_blossom_draws_petals_and_heart():
    target = pen()
    build({"camera": CAMERA, "items": [
        {"center": [0, 0, 0], "facing": [0, 0, -1], "size": 0.15,
         "petals": 5, "color": "#F2C0CE"}
    ]}, target)
    assert len(target.commands) == 6


def test_far_item_is_drawn_first():
    target = pen()
    build({"camera": CAMERA, "items": [
        {"shape": "leaf", "center": [0, 0, -0.2], "facing": [0, 0, -1],
         "radial": [0, 1, 0], "size": 0.2, "width": 0.08, "name": "近"},
        {"shape": "leaf", "center": [0, 0, 0.3], "facing": [0, 0, -1],
         "radial": [0, 1, 0], "size": 0.2, "width": 0.08, "name": "远"}
    ]}, target)
    assert target.commands[0]["params"]["name"] == "远"


def test_unknown_shape_raises():
    with pytest.raises(ValueError, match="不认识的形状"):
        build({"camera": CAMERA, "items": [
            {"shape": "wing", "center": [0, 0, 0], "size": 0.2}
        ]}, pen())


def test_empty_items_raise():
    with pytest.raises(ValueError, match="items"):
        build({"camera": CAMERA, "items": []}, pen())
