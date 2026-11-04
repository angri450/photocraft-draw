# -*- coding: utf-8 -*-
"""演出朝向这一层的测试。

覆盖：声明的朝向和关节表对不对得上、背对观众的提示、
没声明朝向的角色怎么算、以及朝向有没有进画面稿。
"""
from photocraft_draw.brief import build_brief
from photocraft_draw.facing import FACE_WORDS, analyze_plan, report
from photocraft_draw.plan import validate_plan

# 正面朝向的站姿：两肩展开，头在身体中线上，脖子不拧
FRONT_POSE = {
    "hip": (0, 0), "chest": (0, -0.28), "neck": (0, -0.34), "head": (0, -0.41),
    "shoulder_l": (-0.13, -0.31), "shoulder_r": (0.13, -0.31),
    "elbow_l": (-0.15, -0.13), "elbow_r": (0.15, -0.13),
    "hand_l": (-0.16, 0.06), "hand_r": (0.16, 0.06),
    "knee_l": (-0.07, 0.42), "knee_r": (0.07, 0.42),
    "foot_l": (-0.08, 0.84), "foot_r": (0.08, 0.84),
}

# 侧身：两肩叠在一起，头甩到一边
SIDE_POSE = {
    "hip": (0, 0), "chest": (-0.03, -0.27), "neck": (-0.07, -0.33),
    "head": (-0.16, -0.39),
    "shoulder_l": (-0.05, -0.31), "shoulder_r": (0.05, -0.31),
    "elbow_l": (-0.15, -0.13), "elbow_r": (0.15, -0.13),
    "hand_l": (-0.16, 0.06), "hand_r": (0.16, 0.06),
    "knee_l": (-0.07, 0.42), "knee_r": (0.07, 0.42),
    "foot_l": (-0.08, 0.84), "foot_r": (0.08, 0.84),
}


def build_plan(pose=None, face="front"):
    params = {
        "root": [300, 700],
        "height": 440,
        "pose": {k: list(v) for k, v in (pose or FRONT_POSE).items()},
        "body": "ink",
        "joint": "line",
        "head": "ink",
    }
    if face is not None:
        params["face"] = face
    return {
        "name": "朝向测试",
        "canvas": [900, 1200],
        "ref_width": 900,
        "palette": "dusk",
        "background": "bg",
        "layers": [
            {
                "name": "wukong",
                "describe_zh": "悟空在左",
                "describe_en": "Wukong at left",
                "components": [
                    {"component": "figure_rig", "params": params},
                ],
            },
        ],
    }


def read(plan):
    result = analyze_plan(plan)
    return result["characters"][0], result


class TestFacingDeclaration:
    def test_front_pose_passes(self):
        character, _ = read(build_plan())
        assert character["face"] == "front"
        assert not character["issues"]

    def test_unknown_facing_word_is_reported(self):
        character, _ = read(build_plan(face="sideways"))
        assert any(item["kind"] == "facing_unknown"
                   for item in character["issues"])

    def test_back_facing_is_reported(self):
        character, _ = read(build_plan(face="back"))
        assert any(item["kind"] == "facing_back"
                   for item in character["issues"])

    def test_missing_facing_is_listed_as_undeclared(self):
        character, result = read(build_plan(face=None))
        assert character["face"] is None
        assert result["undeclared"] == ["wukong"]


class TestFacingGeometry:
    def test_narrow_shoulders_read_as_side_view(self):
        pose = dict(FRONT_POSE)
        pose["shoulder_l"] = (-0.05, -0.31)
        pose["shoulder_r"] = (0.05, -0.31)
        character, _ = read(build_plan(pose=pose))
        assert any(item["kind"] == "facing_span"
                   for item in character["issues"])

    def test_head_off_center_reads_as_turned_head(self):
        pose = dict(FRONT_POSE)
        pose["head"] = (-0.14, -0.41)
        character, _ = read(build_plan(pose=pose))
        assert any(item["kind"] == "facing_head"
                   for item in character["issues"])

    def test_twisted_neck_reads_as_turned_body(self):
        pose = dict(FRONT_POSE)
        pose["neck"] = (-0.10, -0.34)
        pose["head"] = (-0.18, -0.41)
        character, _ = read(build_plan(pose=pose))
        assert any(item["kind"] == "facing_twist"
                   for item in character["issues"])

    def test_tilted_torso_reads_as_turned_body(self):
        pose = dict(FRONT_POSE)
        pose["chest"] = (-0.12, -0.27)
        pose["neck"] = (-0.02, -0.33)
        pose["head"] = (0.0, -0.41)
        character, _ = read(build_plan(pose=pose))
        assert any(item["kind"] == "facing_torso"
                   for item in character["issues"])

    def test_uneven_shoulders_read_as_turned_body(self):
        pose = dict(FRONT_POSE)
        pose["shoulder_r"] = (0.13, -0.24)
        character, _ = read(build_plan(pose=pose))
        assert any(item["kind"] == "facing_shoulder"
                   for item in character["issues"])

    def test_side_pose_declared_side_has_no_issue(self):
        character, _ = read(build_plan(pose=SIDE_POSE, face="left"))
        assert not character["issues"]


class TestBrief:
    def test_facing_reaches_chinese_brief(self):
        info = build_brief(build_plan())
        assert "正面朝观众" in info["zh"]

    def test_facing_reaches_english_brief(self):
        info = build_brief(build_plan())
        assert "facing the audience" in info["en"]

    def test_undeclared_facing_stays_out_of_brief(self):
        info = build_brief(build_plan(face=None))
        assert "facing the audience" not in info["en"]


class TestPlanValidation:
    def test_valid_facing_passes(self):
        assert validate_plan(build_plan()) == []

    def test_missing_facing_is_allowed(self):
        assert validate_plan(build_plan(face=None)) == []


class TestReport:
    def test_report_mentions_facing_section(self):
        text = report(analyze_plan(build_plan()))
        assert "角色朝向" in text
        assert "正面朝观众" in text

    def test_report_lists_back_facing_issue(self):
        text = report(analyze_plan(build_plan(face="back")))
        assert "禁止背场" in text

    def test_face_words_cover_four_orientations(self):
        assert len(FACE_WORDS) == 4
