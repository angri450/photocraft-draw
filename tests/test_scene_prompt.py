# -*- coding: utf-8 -*-
"""场景转提示词：整体描述与 Layout 包围盒。"""
import pytest

from photocraft_draw.scene_prompt import caption_from_plan, layout_from_plan

CAMERA = {"position": [0, 0, -1], "target": [0, 0, 0], "up": [0, 1, 0],
          "focal": 600, "frame": [800, 800], "center": [400, 400],
          "projection": "perspective"}

PLAN = {
    "canvas": [800, 800],
    "layers": [{"components": [
        {"component": "organic_layer", "params": {"camera": CAMERA, "items": [
            {"center": [0, 0, 0], "facing": [0, 0, -1], "size": 0.2, "petals": 5},
            {"shape": "bud", "center": [0.3, 0, 0], "facing": [0, 0, -1],
             "radial": [0, 1, 0], "size": 0.05, "width": 0.03},
            {"shape": "leaf", "center": [-0.3, 0, 0], "facing": [0, 0, -1],
             "radial": [0, 1, 0], "size": 0.2, "width": 0.08},
        ]}},
    ]}],
}


def test_caption_counts_subjects():
    text = caption_from_plan(PLAN)
    assert "1 open blossoms" in text
    assert "1 closed buds" in text
    assert "1 narrow leaves" in text


def test_layout_has_one_item_per_shape():
    draft = layout_from_plan(PLAN, 800, 800, "test")
    assert len(draft["items"]) == 3
    assert draft["bbox_coord_space"] == "abs"
    assert draft["bbox_format"] == "xyxy"


def test_boxes_stay_inside_canvas():
    draft = layout_from_plan(PLAN, 800, 800, "test")
    for item in draft["items"]:
        x0, y0, x1, y1 = item["bbox"]
        assert 0 <= x0 < x1 <= 800
        assert 0 <= y0 < y1 <= 800


def test_missing_camera_raises():
    with pytest.raises(ValueError, match="相机"):
        layout_from_plan({"layers": [{"components": []}]}, 800, 800, "x")
