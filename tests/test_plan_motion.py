# -*- coding: utf-8 -*-
"""动作状态这一层的测试。

覆盖：意图向量与动作词的关系、兵器主轴与意图的关系、
持械一致性、两个交战角色的夹角，以及方案校验对 motion 的拦截。
"""
import math

import pytest

from photocraft_draw.motion import ACTION_RULES, analyze_plan, report
from photocraft_draw.plan import validate_plan

WK_ROOT, WK_H = [300, 700], 440
EL_ROOT, EL_H = [600, 690], 430

# 举过头顶的姿势：双臂朝上，用来验证持械判据不误报
WK_RAISED = {
    "hip": (0, 0), "chest": (-0.03, -0.27), "neck": (-0.07, -0.33), "head": (-0.10, -0.40),
    "shoulder_l": (-0.13, -0.31), "shoulder_r": (0.11, -0.31),
    "elbow_l": (0.0785, -0.4479), "hand_l": (0.3044, -0.5550),
    "elbow_r": (0.3088, -0.4616), "hand_r": (0.25, -0.7045),
    "knee_l": (-0.21, 0.40), "knee_r": (0.17, 0.42),
    "foot_l": (-0.34, 0.84), "foot_r": (0.21, 0.84),
}

EL_RAISED = {
    "hip": (0, 0), "chest": (-0.13, -0.26), "neck": (-0.16, -0.32), "head": (-0.18, -0.39),
    "shoulder_l": (-0.01, -0.30), "shoulder_r": (-0.25, -0.30),
    "elbow_l": (-0.1219, -0.5235), "hand_l": (-0.3430, -0.4069),
    "elbow_r": (-0.0060, -0.2454), "hand_r": (-0.2558, -0.2558),
    "knee_l": (-0.23, 0.38), "knee_r": (0.18, 0.42),
    "foot_l": (-0.16, 0.84), "foot_r": (0.32, 0.84),
}


def _figure(pose, root, height, body="ink"):
    return {
        "component": "figure_rig",
        "params": {
            "root": list(root),
            "height": height,
            "pose": {k: list(v) for k, v in pose.items()},
            "body": body,
            "joint": "line",
            "head": body,
        },
    }


def _rod(name, p1, p2, width=18):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    nx, ny = -uy * width / 2, ux * width / 2
    return {
        "component": "custom_shape",
        "params": {
            "name": name,
            "fill": "deep",
            "subpaths": [{
                "closed": True,
                "knots": [
                    [p1[0] + nx, p1[1] + ny],
                    [p2[0] + nx, p2[1] + ny],
                    [p2[0] - nx, p2[1] - ny],
                    [p1[0] - nx, p1[1] - ny],
                ],
            }],
        },
    }


def build_plan(wukong_motion=None, erlang_motion=None,
               wukong_weapon=None, erlang_weapon=None,
               wukong_pose=None, erlang_pose=None):
    """造一份带两个角色和两件兵器的方案。

    兵器给两个端点：(起点, 终点)。
    """
    wukong_weapon = wukong_weapon or ((410, 390), (537, 705))
    erlang_weapon = erlang_weapon or ((490, 580), (360, 355))
    wukong_motion = wukong_motion or {"action": "press_down", "angle": 65}
    erlang_motion = erlang_motion or {"action": "lift_up", "angle": 245}
    return {
        "name": "动作测试",
        "canvas": [900, 1200],
        "ref_width": 900,
        "palette": "dusk",
        "background": "bg",
        "layers": [
            {
                "name": "wukong",
                "depth": 2,
                "motion": wukong_motion,
                "components": [_figure(wukong_pose or WK_RAISED, WK_ROOT, WK_H)],
            },
            {
                "name": "erlang shen",
                "depth": 1,
                "motion": erlang_motion,
                "components": [_figure(erlang_pose or EL_RAISED, EL_ROOT, EL_H, "muted")],
            },
            {
                "name": "wukong weapon",
                "depth": 3,
                "holder": "wukong",
                "components": [_rod("golden cudgel", wukong_weapon[0], wukong_weapon[1])],
            },
            {
                "name": "erlang weapon",
                "depth": 4,
                "holder": "erlang shen",
                "components": [_rod("three-pointed blade", erlang_weapon[0], erlang_weapon[1])],
            },
        ],
    }


def read(plan):
    """跑一次分析，返回按层名索引的角色表和完整结果。"""
    result = analyze_plan(plan)
    actors = {item["layer"]: item for item in result["actors"]}
    props = {item["layer"]: item for item in result["props"]}
    return actors, props, result


class TestIntentVector:
    def test_angle_zero_points_right(self):
        plan = build_plan(
            wukong_motion={"action": "push_out", "angle": 0},
            erlang_motion={"action": "pull_in", "angle": 180},
        )
        actors, _, _ = read(plan)
        assert actors["wukong"]["angle"] == 0.0
        assert actors["erlang shen"]["angle"] == 180.0

    def test_angle_normalized_to_360(self):
        plan = build_plan(
            wukong_motion={"action": "lift_up", "angle": 270},
            erlang_motion={"action": "press_down", "angle": 90},
        )
        actors, _, _ = read(plan)
        assert actors["wukong"]["angle"] == 270.0
        assert actors["erlang shen"]["angle"] == 90.0

    def test_opposite_intent_gives_wide_duel(self):
        plan = build_plan(
            wukong_motion={"action": "press_down", "angle": 65, "opponents": ["erlang shen"]},
            erlang_motion={"action": "lift_up", "angle": 245, "opponents": ["wukong"]},
        )
        _, _, result = read(plan)
        duel = result["duels"][0]
        assert duel["gap"] == pytest.approx(180.0, abs=1.0)
        assert "issue" not in duel

    def test_same_intent_gives_narrow_duel_and_issue(self):
        plan = build_plan(
            wukong_motion={"action": "press_down", "angle": 90, "opponents": ["erlang shen"]},
            erlang_motion={"action": "press_down", "angle": 90, "opponents": ["wukong"]},
        )
        _, _, result = read(plan)
        duel = result["duels"][0]
        assert duel["gap"] < 60.0
        assert "issue" in duel
        assert "对抗读不出来" in duel["issue"]


class TestWeaponAxis:
    def test_weapon_along_intent_has_no_issue(self):
        plan = build_plan()
        _, props, _ = read(plan)
        assert props["wukong weapon"]["gap"] < 50.0
        assert not props["wukong weapon"]["issues"]
        assert not props["erlang weapon"]["issues"]

    def test_weapon_against_intent_is_reported(self):
        # 兵器往右上，意图是往下压
        plan = build_plan(
            wukong_weapon=((410, 390), (700, 200)),
        )
        _, props, _ = read(plan)
        assert props["wukong weapon"]["gap"] > 50.0
        assert any(item["kind"] == "prop_misaligned"
                   for item in props["wukong weapon"]["issues"])

    def test_weapon_without_holder_is_reported(self):
        plan = build_plan()
        plan["layers"][2].pop("holder")
        _, props, _ = read(plan)
        assert any(item["kind"] == "prop_no_holder"
                   for item in props["wukong weapon"]["issues"])


class TestHoldConsistency:
    def test_raised_arms_are_not_reported_as_off_weapon(self):
        # 举过头顶准备劈砍，手臂朝上是正常的，手还在兵器上
        plan = build_plan()
        actors, _, _ = read(plan)
        wukong = actors["wukong"]
        assert not any(item["kind"] == "hand_off_weapon"
                       for item in wukong["issues"])
        # 手臂方向和意图差得很远，但手没有离开兵器，所以不报
        gaps = wukong["arm_gaps"]
        assert max(gaps.values()) > 90.0
        assert max(wukong["hold_gaps"].values()) < 75.0

    def test_hand_away_from_weapon_is_reported(self):
        # 手甩到右边，兵器在左下，手离兵器老远
        pose = dict(WK_RAISED)
        pose["elbow_r"] = (0.40, -0.30)
        pose["hand_r"] = (0.62, -0.34)
        plan = build_plan(wukong_pose=pose)
        actors, _, _ = read(plan)
        wukong = actors["wukong"]
        assert any(item["kind"] == "hand_off_weapon"
                   for item in wukong["issues"])
        assert wukong["hold_gaps"]["arm_r_fore"] > 75.0

    def test_hold_check_runs_without_motion_declaration(self):
        # 没写 motion 的角色，手离兵器太远照样要报
        plan = build_plan()
        plan["layers"][0].pop("motion")
        actors, _, _ = read(plan)
        assert actors["wukong"]["hold_gaps"]
        assert not any(item["kind"] == "hand_off_weapon"
                       for item in actors["wukong"]["issues"])


class TestUndeclared:
    def test_layer_without_motion_is_listed_as_undeclared(self):
        plan = build_plan()
        plan["layers"][1].pop("motion")
        _, _, result = read(plan)
        assert "erlang shen" in result["undeclared"]
        assert "wukong" not in result["undeclared"]

    def test_missing_opponent_layer_is_reported(self):
        plan = build_plan(
            wukong_motion={"action": "press_down", "angle": 65, "opponents": ["不存在的人"]},
        )
        actors, _, _ = read(plan)
        assert any(item["kind"] == "opponent_missing"
                   for item in actors["wukong"]["issues"])


class TestPlanValidation:
    def test_valid_motion_passes(self):
        assert validate_plan(build_plan()) == []

    def test_unknown_action_is_rejected(self):
        plan = build_plan(
            wukong_motion={"action": "fly_to_moon", "angle": 65},
        )
        errors = validate_plan(plan)
        assert any("不在动作词表里" in item for item in errors)

    def test_angle_outside_action_sector_is_rejected(self):
        plan = build_plan(
            wukong_motion={"action": "press_down", "angle": 10},
        )
        errors = validate_plan(plan)
        assert any("对不上" in item for item in errors)

    def test_missing_angle_is_rejected(self):
        plan = build_plan(
            wukong_motion={"action": "press_down"},
        )
        errors = validate_plan(plan)
        assert any("缺少 angle" in item for item in errors)

    def test_angle_must_be_number(self):
        plan = build_plan(
            wukong_motion={"action": "press_down", "angle": "65"},
        )
        errors = validate_plan(plan)
        assert any("缺少 angle" in item for item in errors)

    def test_holder_must_exist(self):
        plan = build_plan()
        plan["layers"][2]["holder"] = "nobody"
        errors = validate_plan(plan)
        assert any("holder" in item for item in errors)

    def test_opponent_must_exist(self):
        plan = build_plan(
            wukong_motion={"action": "press_down", "angle": 65, "opponents": ["nobody"]},
        )
        errors = validate_plan(plan)
        assert any("opponents" in item for item in errors)

    def test_action_rules_cover_every_action(self):
        for name in ACTION_RULES:
            assert len(ACTION_RULES[name]) == 3


class TestReport:
    def test_report_mentions_both_actors_and_duel(self):
        plan = build_plan(
            wukong_motion={"action": "press_down", "angle": 65, "opponents": ["erlang shen"]},
            erlang_motion={"action": "lift_up", "angle": 245, "opponents": ["wukong"]},
        )
        text = report(analyze_plan(plan))
        assert "wukong" in text
        assert "erlang shen" in text
        assert "交战方向" in text
        assert "兵器主轴" in text

    def test_report_lists_segment_directions(self):
        text = report(analyze_plan(build_plan()))
        assert "躯干" in text
        assert "左上臂" in text

    def test_report_shows_arm_gap_to_intent_and_hold_distance(self):
        text = report(analyze_plan(build_plan()))
        assert "与意图差" in text
        assert "离兵器" in text