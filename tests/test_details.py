# -*- coding: utf-8 -*-
import json
from pathlib import Path
import pytest
from photocraft_draw.details import build_details, combine_brief, prepare_request, validate_details
from photocraft_draw.plan import validate_plan


def plan():
    return {"canvas": [900, 1200], "layers": [
        {"name": "person", "components": [{"component": "block_figure", "params": {"root": [300, 500]}}]},
    ]}


def test_no_details_is_noop():
    assert combine_brief("old", plan()) == "old"


def test_many_kind_of_details_and_white_models(tmp_path):
    first=tmp_path/"all-pose.png"; first.write_bytes(b"x")
    second=tmp_path/"left-contact.png"; second.write_bytes(b"x")
    third=tmp_path/"cloth-piece.png"; third.write_bytes(b"x")
    p=plan()
    p["_plan_dir"]=str(tmp_path)
    p["details"]={
        "subjects": [
            {"target":"person", "priority":"primary", "aspects":{
                "identity":["known monkey King",
                              "coherent character identity"],
                "costume":["full traditional armour", "movable cuffs"],
                "material":["woven cloth", "brushed metal", "pliable leather"],
                "pattern":["legible hand drawn motifs"]},
                "reject":["shiny plastic"], "acceptance":["recognisable at thumbnail"]},
        ],
        "references":[
            {"path":"all-pose.png","roles":["layout","anatomy","contact"],
             "targets":["*"],"instruction":"Only geometry, no appearance."},
            {"path":"left-contact.png","roles":["contact"],"targets":["person"],
             "priority":"primary","avoid":["overlapping duplicate limbs"]},
            {"path":"cloth-piece.png","roles":["costume","material"],
             "targets":["person"],"priority":"preserve"},
        ],
    }
    assert validate_plan(p)==[]
    req=prepare_request(p)
    refs=req["_reference_sources"]
    assert len(refs)==3
    assert refs[0]["priority"]=="support"
    assert refs[1]["priority"]=="primary"
    assert "known monkey King" in req["prompt"]
    assert "Reference image 3" in req["prompt"]
    assert "Do not imitate: overlapping duplicate limbs" in req["prompt"]
    assert all(Path(r["url"]).exists() for r in refs)


def test_declares_reference_sources_and_brief(tmp_path):
    for name in ("layout.png", "identity.jpg"):
        (tmp_path/name).write_bytes(b"x")
    p = plan()
    p["_plan_dir"] = str(tmp_path)
    p["details"] = {"references": [
        {"path": "layout.png", "source": "whitebox", "roles": ["geometry"], "avoid": ["block hands"]},
        {"path": "identity.jpg", "source": "character-sheet", "roles": ["identity", "costume"]},
    ]}
    assert validate_details(p) == []
    from photocraft_draw.details import detail_brief
    text = detail_brief(p, "zh")
    assert "几何白模" in text
    assert "角色造型卡" in text
    p["details"]["references"][0]["source"] = "made-up"
    assert any(".source" in error for error in validate_plan(p))


def test_reference_target_and_appearance_schema(tmp_path):
    p=plan(); p["_plan_dir"]=str(tmp_path)
    p["details"]={"subjects":[{"target":"not-there","aspects":{}}]}
    assert any("不在已有图层" in err for err in validate_details(p))
    assert any("target" in err for err in validate_plan(p))


def test_one_white_model_for_one_detail(tmp_path):
    (tmp_path/"bite.png").write_bytes(b"x")
    p=plan()
    p["_plan_dir"]=str(tmp_path)
    p["details"]={"subjects":[{"target":"person","aspects":{"appearance":[]}}],
                  "references":[{"path":"bite.png","roles":["contact"],"targets":["person"]}]}
    assert len(build_details(p)["references"])==1
