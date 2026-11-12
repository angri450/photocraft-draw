"""整体描述使用作者对实际画面的说明，不从花种或网格类型猜内容。"""
from photocraft_draw.scene_prompt import caption_from_plan


def test_explicit_description_has_priority():
    assert caption_from_plan({"scene_caption":"two fighters crossing polearms",
                              "caption":"small printed title"}) == "two fighters crossing polearms"


def test_brief_and_layer_descriptions_suppress_default_flower_caption():
    plan={"brief_en":{"subject":"two figures in combat","style":"clear white model"},
          "layers":[{"name":"person","describe_en":"fighter with a staff"}]}
    assert caption_from_plan(plan) == "two figures in combat, clear white model"
    del plan["brief_en"]
    assert caption_from_plan(plan) == "fighter with a staff"
    assert "crabapple" not in caption_from_plan(plan)
