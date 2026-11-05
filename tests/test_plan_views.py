# -*- coding: utf-8 -*-
"""人物站位和三视图这一层的测试。

覆盖：关节表里的深度、人物落在画面的哪一格、谁腾空谁落地、
两个人是不是同一条水平线、两件兵器在深度上碰不碰得到、
以及站位有没有进画面稿。
"""
from photocraft_draw.brief import build_brief
from photocraft_draw.components.rig import pose_table_3d
from photocraft_draw.plan import validate_plan
from photocraft_draw.views import (
    VIEW_NAMES,
    analyze_plan,
    render_view,
    report,
    scene_3d,
    staging_notes,
)

# 站着的姿态，脚在脚上，手在身侧
STAND_POSE = {
    "hip": (0, 0), "chest": (0, -0.28), "neck": (0, -0.34), "head": (0, -0.41),
    "shoulder_l": (-0.13, -0.31), "shoulder_r": (0.13, -0.31),
    "elbow_l": (-0.15, -0.13), "elbow_r": (0.15, -0.13),
    "hand_l": (-0.16, 0.06), "hand_r": (0.16, 0.06),
    "knee_l": (-0.07, 0.42), "knee_r": (0.07, 0.42),
    "foot_l": (-0.08, 0.84), "foot_r": (0.08, 0.84),
}

# 腾空的姿态：脚收在身下，落在离地一段距离的地方
AIR_POSE = dict(STAND_POSE)
AIR_POSE.update({
    "knee_l": (-0.20, 0.28), "knee_r": (0.18, 0.26),
    "foot_l": (-0.26, 0.48), "foot_r": (0.22, 0.44),
})

# 悟空的层比二郎神靠后一点，两人踩在不同的深度上。z 越大离观众越远。
WK_LAYER_Z = 60.0
EL_LAYER_Z = 0.0


def figure(root, height, name="wukong", pose=None, hand_z=0.0, z=None):
    """一个人物白模。手可以带深度 z。"""
    table = {k: list(v) for k, v in (pose or STAND_POSE).items()}
    for key in ("hand_l", "hand_r"):
        table[key] = list(table[key]) + [hand_z]
    layer = {
        "name": name,
        "describe_zh": "悟空",
        "describe_en": "Wukong",
        "components": [{
            "component": "figure_rig",
            "params": {
                "root": list(root),
                "height": height,
                "pose": table,
                "body": "ink",
                "joint": "line",
                "head": "ink",
            },
        }],
    }
    if z is not None:
        layer["z"] = z
    return layer


def prop(name, points, holder):
    return {
        "name": name,
        "holder": holder,
        "describe_zh": "兵器",
        "describe_en": "weapon",
        "components": [{
            "component": "custom_shape",
            "params": {
                "name": name,
                "subpaths": [{"closed": True, "knots": [list(p) for p in points]}],
                "fill": "accent",
            },
        }],
    }


def build_plan(layers):
    for index, layer in enumerate(layers):
        layer["depth"] = len(layers) - index
    return {
        "name": "站位测试",
        "canvas": [900, 1200],
        "ref_width": 900,
        "palette": "dusk",
        "background": "bg",
        "layers": layers,
    }


def two_figures(cudgel_z=0.0, blade_z=0.0, wk_layer_z=WK_LAYER_Z, el_layer_z=EL_LAYER_Z):
    """两个人和两件兵器。

    cudgel_z 和 blade_z 是两件兵器各自的深度。兵器在持械者的手里，
    所以手的高度要跟着层的深度换算：兵器深度减掉层的深度就是手的深度。
    """
    left = figure([220, 480], 400, name="wukong", pose=AIR_POSE,
                  hand_z=cudgel_z - wk_layer_z, z=wk_layer_z)
    right = figure([680, 800], 400, name="erlang shen",
                   hand_z=blade_z - el_layer_z, z=el_layer_z)
    return build_plan([
        left,
        prop("golden cudgel", [(200, 400), (520, 720)], "wukong"),
        prop("three-pointed blade", [(420, 760), (720, 440)], "erlang shen"),
        right,
    ])


class TestPoseDepth:
    def test_two_numbers_still_work(self):
        table = pose_table_3d({k: list(v) for k, v in STAND_POSE.items()})
        assert table["hip"] == (0.0, 0.0, 0.0)

    def test_three_numbers_keep_the_depth(self):
        table = {k: list(v) for k, v in STAND_POSE.items()}
        table["hand_r"] = [0.16, 0.06, 45.0]
        result = pose_table_3d(table)
        assert result["hand_r"] == (0.16, 0.06, 45.0)

    def test_wrong_point_length_is_rejected(self):
        table = {k: list(v) for k, v in STAND_POSE.items()}
        table["hand_r"] = [0.16]
        try:
            pose_table_3d(table)
        except ValueError as error:
            assert "hand_r" in str(error)
        else:
            raise AssertionError("少写坐标应该报错")


class TestStaging:
    def test_left_third_and_upper_head(self):
        result = analyze_plan(two_figures())
        wukong = result["characters"][0]
        assert wukong["body_band"] == 0
        assert wukong["head_band"] == 0

    def test_airborne_is_measured_against_the_ground(self):
        result = analyze_plan(two_figures())
        wukong, erlang = result["characters"]
        assert wukong["airborne"]
        assert not erlang["airborne"]
        assert wukong["air_gap"] > 100

    def test_upper_and_lower_relationship(self):
        result = analyze_plan(two_figures())
        wukong, erlang = result["characters"]
        assert wukong["level"] == "higher"
        assert erlang["level"] == "lower"

    def test_same_level_is_not_reported_as_higher(self):
        left = figure([220, 700], 400, name="wukong")
        right = figure([680, 700], 400, name="erlang shen")
        result = analyze_plan(build_plan([left, right]))
        assert result["characters"][0]["level"] == "same"

    def test_layer_z_overrides_the_drawing_depth(self):
        result = analyze_plan(two_figures())
        assert result["characters"][0]["z"] == WK_LAYER_Z
        assert result["characters"][1]["z"] == EL_LAYER_Z

    def test_z_is_validated(self):
        plan = two_figures()
        plan["layers"][0]["z"] = "前面"
        errors = validate_plan(plan)
        assert any("z" in text for text in errors)


class TestWeaponContact:
    def test_same_depth_weapons_can_touch(self):
        result = analyze_plan(two_figures(cudgel_z=40, blade_z=40))
        assert result["crossings"]
        assert result["crossings"][0]["touch"]
        assert not result["issues"]

    def test_depth_gap_is_reported(self):
        result = analyze_plan(two_figures(cudgel_z=140, blade_z=0))
        assert result["crossings"]
        assert not result["crossings"][0]["touch"]
        assert any("碰不到" in text for text in result["issues"])

    def test_weapon_depth_comes_from_the_hand(self):
        scene = scene_3d(two_figures(cudgel_z=50, blade_z=50))
        depths = {item["layer"]: item["z"] for item in scene["props"]}
        assert abs(depths["golden cudgel"] - 50.0) < 0.01
        assert abs(depths["three-pointed blade"] - 50.0) < 0.01


class TestViews:
    def test_three_views_render(self):
        plan = two_figures()
        for view in VIEW_NAMES:
            commands, meta = render_view(plan, view)
            assert commands
            assert meta["width"] == 900 and meta["height"] == 1200

    def test_left_view_uses_the_depth_axis(self):
        scene = scene_3d(two_figures(cudgel_z=20))
        hand = scene["figures"][0]["joints"]["hand_r"]
        shoulder = scene["figures"][0]["joints"]["shoulder_r"]
        assert hand[2] < shoulder[2]

    def test_report_mentions_the_crossing(self):
        result = analyze_plan(two_figures(cudgel_z=40, blade_z=40))
        text = report(result)
        assert "兵器交叉" in text
        assert "碰得到" in text


class TestBrief:
    def test_staging_reaches_the_chinese_brief(self):
        info = build_brief(two_figures())
        assert "画面空间关系" in info["zh"]

    def test_staging_reaches_the_english_brief(self):
        info = build_brief(two_figures())
        assert "Staging:" in info["en"]

    def test_position_reaches_the_layer_description(self):
        info = build_brief(two_figures())
        layer = [item for item in info["layers"] if item["name"] == "wukong"][0]
        assert "left third" in layer["en"]
        assert "feet off the ground" in layer["en"]

    def test_notes_are_built_for_every_figure(self):
        notes = staging_notes(two_figures())
        assert set(notes["notes"]) == {"wukong", "erlang shen"}

class TestSlopedWeapon:
    """兵器的深度沿着长度变化的时候，俯视图上是一条斜线。"""

    def sloped(self):
        plan = two_figures()
        plan["layers"][1]["segments"] = [
            {"from": 0.0, "to": 0.5, "depth": 4.0, "z_from": 80.0, "z_to": 0.0},
            {"from": 0.5, "to": 1.0, "depth": 1.0, "z_from": 0.0, "z_to": -80.0},
        ]
        plan["layers"][1]["depth"] = 4.0
        return plan

    def test_the_top_view_shows_a_sloped_line(self):
        commands, _ = render_view(self.sloped(), "top")
        lines = [item["params"] for item in commands
                 if item["params"].get("name", "").startswith("兵器")]
        assert lines
        assert any(abs(item["from"][1] - item["to"][1]) > 1.0 for item in lines)

    def test_a_flat_weapon_stays_horizontal_in_the_top_view(self):
        plan = two_figures()
        plan["layers"][1]["segments"] = [
            {"from": 0.0, "to": 1.0, "depth": 4.0, "z": 20.0},
        ]
        commands, _ = render_view(plan, "top")
        lines = [item["params"] for item in commands
                 if item["params"].get("name", "").startswith("兵器")]
        assert lines
        assert not any(abs(item["from"][1] - item["to"][1]) > 1.0 for item in lines)

class TestViewOrder:
    """三视图里压在谁上头，跟白模里一样。远的先画，近的后画。"""

    def weapon_lines(self, plan, view="front"):
        commands, _ = render_view(plan, view)
        return [item["params"] for item in commands
                if item["params"].get("name", "").startswith("兵器")]

    def test_the_nearer_weapon_is_drawn_later(self):
        plan = two_figures()
        lines = self.weapon_lines(plan)
        assert len(lines) == 2
        # 金箍棒 depth 3，远，先画；长杆 depth 2，近，后画
        assert abs(lines[0]["from"][0] - 200) < 1.0
        assert abs(lines[1]["from"][0] - 420) < 1.0

    def test_a_split_weapon_is_drawn_piece_by_piece(self):
        plan = two_figures()
        plan["layers"][1]["segments"] = [
            {"from": 0.0, "to": 0.5, "depth": 5.0, "z_from": 80.0, "z_to": 40.0},
            {"from": 0.5, "to": 1.0, "depth": 1.0, "z_from": 40.0, "z_to": -20.0},
        ]
        plan["layers"][1]["depth"] = 5.0
        lines = self.weapon_lines(plan)
        assert len(lines) == 3
        # 棒尾 depth 5 最远先画，长杆 depth 2 居中，棒身 depth 1 最近后画
        starts = [round(line["from"][0]) for line in lines]
        assert starts == [200, 420, 360]
