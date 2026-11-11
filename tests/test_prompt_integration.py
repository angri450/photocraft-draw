# -*- coding: utf-8 -*-
"""MOSS Prompt Enhancer 的定位、保留与接入集成测试。"""
from pathlib import Path

import pytest

from photocraft_draw.prompt_compiler import compile_layout
from photocraft_draw.scene_prompt import caption_from_plan, layout_from_plan


def test_official_compiler_handles_photocraft_layout():
    plan = {"canvas": [896, 1152], "ref_width": 900,
            "layers": [{"name": "树", "components": [
                {"component": "crabapple_tree", "params": {
                    "root": [400, 900], "height": 600}}]}]}
    draft = layout_from_plan(plan, 896, 1152, "a flowering tree")
    prompt = compile_layout(draft)
    assert '"bbox_coord_space":"abs_centralized"' in prompt
    assert '"bbox_format":"yxyx"' in prompt
    assert '"width"' not in prompt


def test_layout_text_keeps_exact_copy_and_caption_identity():
    command = {"command": "type.create", "params": {
        "x": 400, "y": 150, "text": "冰红茶",
        "font": "Microsoft YaHei", "size": 54, "color": "#6B2F24",
        "align": "center", "weight": 700}}
    plan = {"canvas": [800, 800], "ref_width": 800, "caption": "a study",
            "layers": [{"name": "字", "depth": 0, "components": [
                {"component": "grove_label", "params": {"title": "冰红茶",
                    "subtitle": "净含量：500mL", "features": []}}]}]}
    draft = layout_from_plan(plan, 800, 800, "a poster")
    texts = [item for item in draft["items"] if item["label"] == "text"]
    assert {item["text"] for item in texts} == {"冰红茶", "净含量：500mL", "a study"}
    assert all(item["caption"] for item in texts)


def test_caption_field_stays_drawing_caption():
    # 方案 caption 是的小字标题；自动整体描述从零生成，不被这个标题吞掉。
    plan = {"caption": "画面左下角的小字", "canvas": [800, 800],
            "layers": [{"components": []}]}
    assert caption_from_plan(plan) != "画面左下角的小字"
    plan["scene_caption"] = "独立的整体场景描述"
    assert caption_from_plan(plan) == "独立的整体场景描述"


def test_missing_compiler_is_explicit(tmp_path):
    with pytest.raises(FileNotFoundError, match="compile_prompt.py"):
        compile_layout({"caption": "test"}, custom_home=tmp_path)
