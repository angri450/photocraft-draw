# -*- coding: utf-8 -*-
from pathlib import Path
from photocraft_draw.details import build_details, combine_brief, detail_brief, validate_details, visual_handoff
from photocraft_draw.plan import validate_plan


def plan():
    return {"canvas": [900, 1200], "layers": [
        {"name": "person", "components": [{"component": "block_figure", "params": {"root": [300, 500]}}]},
    ]}


def test_no_details_is_noop():
    assert combine_brief("old", plan()) == "old"


def test_handoff_has_multiple_references_without_model_or_upload(tmp_path):
    for name in ("all-pose.png", "left-contact.png", "cloth-piece.png"):
        (tmp_path / name).write_bytes(b"x")
    p = plan()
    p["_plan_dir"] = str(tmp_path)
    p["details"] = {
        "scene": "A compact confrontation in open air.",
        "subjects": [{"target": "person", "priority": "primary", "aspects": {
            "identity": ["recognisable subject"],
            "costume": ["traditional outfit"],
            "material": ["woven cloth"],
            "pattern": ["hand drawn motifs"],
            "acceptance": ["清晰可辨"]},
            "reject": ["shiny plastic"]}],
        "references": [
            {"path": "all-pose.png", "roles": ["layout", "anatomy", "contact"], "targets": ["*"], "instruction": "Only geometry, no appearance."},
            {"path": "left-contact.png", "roles": ["contact"], "targets": ["person"], "priority": "primary", "avoid": ["overlapping duplicate limbs"]},
            {"path": "cloth-piece.png", "roles": ["costume", "material"], "targets": ["person"], "priority": "preserve"},
        ],
    }
    p["details"]["subjects"][0]["aspects"]["acceptance"] = "流程内部条件"
    assert validate_plan(p) == []
    handoff = visual_handoff(p)
    assert list(handoff) == ["description", "canvas", "references"]
    assert handoff["canvas"] == [900, 1200]
    assert len(handoff["references"]) == 3
    assert handoff["references"][1]["priority"] == "primary"
    assert all(Path(ref["url"]).is_file() for ref in handoff["references"])
    assert "recognisable subject" in handoff["description"]
    assert "Reference image 3" in handoff["description"]
    assert "Exclude overlapping duplicate limbs." in handoff["description"]
    for text in ("A compact confrontation in open air.", "shiny plastic"):
        assert text in handoff["description"]
    for text in ("Upload this file", "current main conflict", "primary):", "acceptance", "流程内部条件", "scene is built in"):
        assert text not in handoff["description"]


def test_declares_reference_source_and_chinese_brief(tmp_path):
    for name in ("layout.png", "identity.jpg"):
        (tmp_path / name).write_bytes(b"x")
    p = plan()
    p["_plan_dir"] = str(tmp_path)
    p["details"] = {"subjects": [{"target": "person", "aspects": {"identity": ["恒定的身份"]}}],
        "references": [
            {"path": "layout.png", "source": "whitebox", "roles": ["geometry"], "avoid": ["block hands"]},
            {"path": "identity.jpg", "source": "character-sheet", "roles": ["identity", "costume"]}]}
    assert validate_details(p) == []
    text = detail_brief(p, "zh")
    assert "构图、透视、布局、留白与镜头" in text
    assert "主体身份" in text
    assert "几何白模" not in text
    p["details"]["references"][0]["source"] = "made-up"
    assert any(".source" in error for error in validate_plan(p))


def test_reference_target_and_appearance_schema(tmp_path):
    p = plan()
    p["details"] = {"subjects": [{"target": "not-there", "aspects": {}}]}
    assert any("不在已有图层" in err for err in validate_details(p))
    assert any("target" in err for err in validate_plan(p))


def test_one_white_model_for_one_detail(tmp_path):
    (tmp_path / "bite.png").write_bytes(b"x")
    p = plan()
    p["_plan_dir"] = str(tmp_path)
    p["details"] = {"subjects": [{"target": "person", "aspects": {"appearance": ["自然"]}}],
                  "references": [{"path": "bite.png", "roles": ["contact"], "targets": ["person"]}]}
    assert len(build_details(p)["references"]) == 1
