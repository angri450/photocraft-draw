"""Layout 的结构和文字来自实际绘制命令。"""
from types import SimpleNamespace
from photocraft_draw.cli import cmd_prompt
from photocraft_draw.scene_prompt import caption_from_plan


def test_text_annotation_uses_exact_drawing_text():
    from photocraft_draw.plan import load_plan
    from photocraft_draw.layout_tool import text_annotations
    from pathlib import Path
    plan=load_plan(Path(__file__).resolve().parents[1]/"plans"/"spray.json")
    plan["caption"]="a study"
    annotations=text_annotations(plan,896,1200)
    assert annotations == [{"label":"text","text":"a study",
                           "bbox":annotations[0]["bbox"],"bbox_source":"font_estimate",
                           "font":"DejaVu Sans Mono","size":annotations[0]["size"],
                           "color":annotations[0]["color"],"weight":None,"align":"left"}]
    text_plan={"canvas":[800,800],"ref_width":800,
               "layers":[{"name":"label","components":[
                   {"component":"grove_label","params":{"title":"TEST","features":[]}}]}]}
    from photocraft_draw.layout_tool import export_layout
    doc=export_layout(text_plan,800,800,"poster")
    assert doc["layers"][0]["parts"] == []
    assert {x["text"] for x in doc["annotations"]} >= {"TEST", "固体饮料"}


def test_default_command_exports_uniform_geometry(tmp_path):
    from photocraft_draw.layout_tool import export_layout
    from photocraft_draw.scene_prompt import caption_from_plan
    source=tmp_path/"tree.json"
    import json
    plan={"canvas":[900,1200],"ref_width":900,"scene_caption":"a flowering tree",
          "layers":[{"name":"tree","components":[{"component":"crabapple_tree",
              "params":{"root":[400,900],"height":600}}]}]}
    source.write_text(json.dumps(plan),encoding="utf-8")
    target=tmp_path/"layout.json"
    code=cmd_prompt(SimpleNamespace(plan=str(source),out=str(target),width=900,
                                  height=1200,caption_only=False,detail="geometry"))
    assert code==0
    doc=json.loads(target.read_text(encoding="utf-8"))
    assert doc["layout_version"]=="photocraft-layout/v2"
    assert doc["layers"][0]["name"]=="tree"
    assert doc["layers"][0]["parts"]


def test_scene_description_does_not_use_small_drawing_caption():
    plan={"caption":"画面左下角的小字","layers":[]}
    assert caption_from_plan(plan) != "画面左下角的小字"
    plan["scene_caption"]="独立的整体场景描述"
    assert caption_from_plan(plan) == "独立的整体场景描述"
