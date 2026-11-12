# -*- coding: utf-8 -*-
"""通用 Layout 直接读取实际绘制命令的几何与明确声明。"""
import pytest
from photocraft_draw.layout_tool import export_layout, geometry_scaled
from photocraft_draw.split import axis_of, lerp_point


PERSON = {
    "canvas": [900.0, 1200.0], "ref_width": 900,
    "layers": [
        {"name": "person", "depth": 2, "z": 20,
         "components": [{"component": "figure_rig", "params": {
             "root": [400, 300], "height": 200, "face": "left"}}]},
    ],
}


def test_default_layout_is_actual_geometry():
    doc = export_layout(PERSON, 900, 1200, "single subject")
    assert doc["layout_version"] == "photocraft-layout/v2"
    assert doc["layers"][0]["depth"] == 2
    assert doc["layers"][0]["parts"]
    assert "items" not in doc


def test_semantic_contains_real_joints_and_named_layers():
    doc = export_layout(PERSON, 900, 1200, "single subject", "semantic")
    assert doc["layers"][0]["name"] == "person"
    assert doc["layers"][0]["z"] == 20
    assert doc["skeletons"][0]["joints"]["head"]["xy"] == [400.0, 218.0]
    assert doc["skeletons"][0]["joints"]["hand_l"]["z_offset"] == 0.0
    assert doc["layout_version"] == "photocraft-layout/v2"


def test_components_emits_every_up_to_curve_box_and_actual_depth():
    doc = export_layout(PERSON, 900, 1200, "parts", "components")
    assert doc["components"][0]["name"] == "person"
    assert doc["components"][0]["depth"] == 2
    assert doc["components"][0]["z"] == 20
    assert any(part["kind"] == "ellipse" for part in doc["components"][0]["parts"])
    assert all(len(part["bbox"]) == 4 for part in doc["components"][0]["parts"])
    plan = {
        "canvas": [900, 1200], "ref_width": 900,
        "layers": [{
            "name": "shape", "depth": 0,
            "components": [{
                "component": "custom_shape",
                "params": {"subpaths": [{
                    "closed": True,
                    "knots": [
                        {"anchor": [10, 10], "in": [10, 10], "out": [40, -120]},
                        {"anchor": [110, 50], "out": [110, 50], "in": [140, 10]},
                        {"anchor": [10, 100], "out": [10, 100], "in": [10, 100]},
                    ],
                }]}
            }]
        }]
    }
    data = export_layout(plan, 900, 1200, "curve", "components")
    hand = data["components"][0]["parts"][0]
    assert hand["bbox"][0] >= 0
    assert hand["bbox"][2] <= 1200


def test_empty_plan_is_rejected_instead_of_empty_success():
    bare = {"canvas": [100, 100], "layers": [{"name": "bg", "components": []}]}
    with pytest.raises(ValueError, match="components必须是非空数组"):
        export_layout(bare, 100, 100, "empty", "components")

CURVE_BOX_PLAN = {
    "canvas": [900, 1200], "ref_width": 900,
    "layers": [{"name": "curve", "depth": 1, "components": [{
        "component": "custom_shape", "params": {"subpaths": [{
            "closed": True, "knots": [
                {"anchor": [10, 10], "in": [10, 10], "out": [40, -120]},
                {"anchor": [110, 50], "out": [110, 50], "in": [140, 10]},
                {"anchor": [10, 100], "out": [10, 100], "in": [10, 100]},
            ],
        }]}
    }]}],
}

SEGMENT_PLAN = {
    "canvas": [900, 1200], "ref_width": 900,
    "layers": [{"name": "staff", "depth": 2, "holder": "person",
                "axis": [[100, 100], [500, 500]], "segments": [
                    {"name": "tail", "from": 0, "to": 0.4,
                     "depth": 4, "z_from": 80, "z_to": 20},
                    {"name": "tip", "from": 0.4, "to": 1,
                     "depth": 2, "z_from": 20, "z_to": -60},
                ], "components": [{"component": "custom_shape", "params": {
                    "subpaths": [{"closed": True,
                        "knots": [[100, 100], [500, 400], [500, 500]]}]}}]},
                {"name": "person", "depth": 3,
                 "components": [{"component": "figure_rig", "params": {
                     "root": [600, 700], "height": 300}}]}],
}


def test_curve_geometry_contains_more_than_anchor_box():
    layer = geometry_scaled(CURVE_BOX_PLAN, 450, 600)[0]
    part = layer["parts"][0]
    assert part["bbox_source"] == "fill_polygon"
    assert part["bbox"][1] < 5
    assert 0 <= part["bbox"][0] < part["bbox"][2] <= 450
    assert 0 <= part["bbox"][1] < part["bbox"][3] <= 600


def test_joints_scale_once_from_quantized_canvas_coordinates():
    full = export_layout(PERSON, 900, 1200, "person", "semantic")
    small = export_layout(PERSON, 450, 600, "person", "semantic")
    for name, joint in full["skeletons"][0]["joints"].items():
        assert small["skeletons"][0]["joints"][name]["xy"] == [
            value / 2 for value in joint["xy"]]


def test_segment_geometry_and_axes_keep_matching_declared_depth():
    doc = export_layout(SEGMENT_PLAN, 900, 1200, "fight", "geometry")
    actual = [layer for layer in doc["layers"] if layer["name"].startswith("staff ")]
    expected = {segment["name"]: segment for segment in SEGMENT_PLAN["layers"][0]["segments"]}
    assert len(actual) == 2
    for layer in actual:
        segment = expected[layer["name"].split(" ", 1)[1]]
        assert layer["depth"] == segment["depth"]
        assert [layer["z_from"], layer["z_to"]] == [segment["z_from"], segment["z_to"]]
    source = SEGMENT_PLAN["layers"][0]
    for segment in doc["axes"][0]["segments"]:
        declaration = expected[segment["name"]]
        assert segment["depth"] == declaration["depth"]
        assert segment["z_from"] == declaration["z_from"]
        for point, ratio in zip(segment["axis"], segment["ratio"]):
            expected_point = lerp_point(axis_of(source["components"], source["axis"]), ratio)
            assert point == [round(value, 2) for value in expected_point]


def test_tree_exports_actual_drawing_shapes():
    plan = {"canvas": [900, 1200], "ref_width": 900,
            "layers": [{"name": "tree", "components": [{
                "component": "crabapple_tree",
                "params": {"root": [400, 900], "height": 600}}]}]}
    doc = export_layout(plan, 900, 1200, "tree")
    assert doc["layers"][0]["name"] == "tree"
    assert doc["layers"][0]["parts"]
    assert "items" not in doc


def test_reference_responsibilities_remain_in_semantic_not_geometry(tmp_path):
    reference = tmp_path / "character.png"
    reference.write_bytes(b"test fixture, not a generated artwork")
    plan = {**PERSON, "details": {"subjects": [{"target": "person", "priority": "primary",
            "aspects": {"costume": "layered linen robe"}}], "references": [{
            "path": str(reference), "targets": ["person"], "roles": ["costume"],
            "instruction": "retain robe", "avoid": ["new pose"]}]}}
    semantic = export_layout(plan, 900, 1200, "person", "semantic")
    assert semantic["references"][0]["targets"] == ["person"]
    assert semantic["references"][0]["avoid"] == ["new pose"]
    assert "references" not in export_layout(plan, 900, 1200, "person", "geometry")


def test_unnamed_segments_keep_their_declared_depths():
    plan = {"canvas": [900, 1200], "ref_width": 900, "layers": [
        {"name": "person", "depth": 1, "components": PERSON["layers"][0]["components"]},
        {"name": "staff", "depth": 2, "holder": "person",
         "axis": [[100, 100], [500, 500]], "segments": [
             {"from": 0, "to": 0.5, "depth": 5, "z_from": 80, "z_to": 20},
             {"from": 0.5, "to": 1, "depth": 1, "z_from": 20, "z_to": -60},
         ], "components": [{"component": "custom_shape", "params": {
             "subpaths": [{"knots": [[100, 100], [500, 400], [500, 500]]}]}}]},
    ]}
    actual = [x for x in geometry_scaled(plan, 900, 1200) if x["name"] == "staff"]
    assert [x["depth"] for x in actual] == [5, 1]
    assert [[x["z_from"], x["z_to"]] for x in actual] == [[80, 20], [20, -60]]


def test_text_only_plan_keeps_text_and_ignores_empty_shape_layers():
    plan = {"canvas": [800, 800], "ref_width": 800,
            "layers": [{"name": "label", "components": [{
                "component": "grove_label", "params": {"title": "TEST", "features": []}}]}]}
    doc = export_layout(plan, 800, 800, "label", "semantic")
    assert doc["layers"][0]["name"] == "label"
    assert {x["text"] for x in doc["annotations"]} >= {"TEST", "固体饮料"}
    assert all(x["bbox_source"] == "font_estimate" for x in doc["annotations"])
    assert export_layout(plan, 800, 800, "label")["layers"][0]["parts"] == []
