# -*- coding: utf-8 -*-
"""有机形状层：花瓣、叶片、花苞的投影与遮挡顺序。"""
import math

import pytest

from photocraft_draw.commands import Pen
from photocraft_draw.organic import build
from photocraft_draw.palette import resolve_palette

CAMERA = {"position": [0, 0, -1], "target": [0, 0, 0], "up": [0, 1, 0],
          "focal": 600, "frame": [800, 800], "center": [400, 400],
          "projection": "perspective"}


def pen():
    return Pen(800, 800, ref_width=800, palette=resolve_palette("fresco"))


def blossom(**overrides):
    item = {"center": [0, 0, 0], "facing": [0, 0, -1], "size": 0.15,
            "petals": 5, "color": "#F2C0CE", "name": "花"}
    item.update(overrides)
    return item


def named(target, word):
    return [item for item in target.commands
            if word in (item["params"].get("name") or "")]


def farthest(items):
    return max(
        math.hypot(point["anchor"][0] - 400.0, point["anchor"][1] - 400.0)
        for item in items
        for point in item["params"]["path"]["subpaths"][0]["knots"]
    )


def test_sprite_draws_one_path():
    target = pen()
    build({"camera": CAMERA, "items": [
        {"shape": "leaf", "center": [0, 0, 0], "facing": [0, 0, -1],
         "radial": [0, 1, 0], "size": 0.2, "width": 0.08, "color": "#6F8F52"}
    ]}, target)
    assert len(target.commands) == 1


def test_blossom_draws_two_layers_and_stamens():
    target = pen()
    build({"camera": CAMERA, "items": [blossom()]}, target)
    assert len(named(target, "内瓣")) == 5
    assert len(named(target, "花丝")) == 9
    assert len(target.commands) == 29


def test_two_layers_add_five_petals():
    single = pen()
    build({"camera": CAMERA, "items": [blossom(layers=1, heart=False)]}, single)
    double = pen()
    build({"camera": CAMERA, "items": [blossom(layers=2, heart=False)]}, double)
    assert len(named(single, "·瓣")) == 5
    assert len(named(double, "·瓣")) == 5
    assert len(named(double, "内瓣")) == 5
    assert len(named(single, "瓣")) + 5 == len(named(double, "瓣"))


def test_inner_diameter_is_058_of_outer():
    target = pen()
    build({"camera": CAMERA, "items": [blossom(heart=False)]}, target)
    outer = farthest(named(target, "·瓣"))
    inner = farthest(named(target, "内瓣"))
    assert abs(inner / outer - 0.58) < 0.01


def test_stamen_count_between_eight_and_ten():
    target = pen()
    build({"camera": CAMERA, "items": [blossom()]}, target)
    stamens = named(target, "花丝")
    assert 8 <= len(stamens) <= 10
    assert len(named(target, "蕊头")) == len(stamens)


def test_layers_one_falls_back_to_single():
    target = pen()
    build({"camera": CAMERA, "items": [blossom(layers=1)]}, target)
    assert not named(target, "内瓣")
    assert len(named(target, "·瓣")) == 5
    assert 8 <= len(named(target, "花丝")) <= 10


def test_inner_color_is_darker_and_stroke_is_not_black():
    target = pen()
    build({"camera": CAMERA, "items": [blossom(heart=False)]}, target)
    outer = named(target, "·瓣")[0]["params"]
    inner = named(target, "内瓣")[0]["params"]

    def channels(color):
        return [int(color[index:index + 2], 16) for index in (1, 3, 5)]

    outer_rgb = channels(outer["fill"])
    inner_rgb = channels(inner["fill"])
    for before, after in zip(outer_rgb, inner_rgb):
        assert 0 < after < before
    stroke = inner["stroke"]["color"]
    assert stroke != "#000000"
    for before, after in zip(inner_rgb, channels(stroke)):
        assert after <= before


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
