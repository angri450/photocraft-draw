# -*- coding: utf-8 -*-
"""兵器和肢体之间的空间关系这一层的测试。

覆盖：两条线段在空间里的距离、两条线段在画面上交叉没有、
点落不落在两条射线张开的角里、兵器从人物身前扫过去和穿进缝里的区别、
兵器分了段以后白模怎么分层，以及深度和物理深度写岔了会不会被拦下来。
"""
import math

from photocraft_draw.plan import (ordered_layers, ordered_units,
                                   resolve_depths, validate_plan)
from photocraft_draw.relations import (
    analyze,
    in_wedge,
    report,
    seg_seg_cross,
    seg_seg_distance,
    seg_seg_distance_2d,
)
from photocraft_draw.split import axis_of, slice_shape

# 一层写 depth 又写 z，两个要对得上：depth = (z + 120) / 40
UNIT = 40.0
NEAREST_Z = -120.0


def depth_of(z):
    return (z - NEAREST_Z) / UNIT


# ---- 造场景用的零件 ----

def figure(root, height, name, z=0.0, pose=None):
    """一个人物白模。pose 是关节表，写两个数或者三个数都行。"""
    table = {key: list(value) for key, value in (pose or {}).items()}
    return {
        "name": name,
        "z": z,
        "describe_zh": "人物",
        "describe_en": "fighter",
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


def rod(name, holder, start, end, half_width=6.0, z=0.0, segments=None):
    """一根直兵器，从 start 指到 end。"""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    nx, ny = -uy * half_width, ux * half_width
    knots = [
        [start[0] + nx, start[1] + ny],
        [start[0] - nx, start[1] - ny],
        [end[0] - nx, end[1] - ny],
        [end[0] + nx, end[1] + ny],
    ]
    layer = {
        "name": name,
        "holder": holder,
        "z": z,
        "describe_zh": "兵器",
        "describe_en": "weapon",
        "components": [{
            "component": "custom_shape",
            "params": {
                "name": name,
                "subpaths": [{"closed": True, "knots": knots}],
                "fill": "accent",
            },
        }],
    }
    if segments is not None:
        layer["segments"] = segments
    return layer


def build(layers):
    """方案。每层的 depth 按 z 推出来，两边对得上。"""
    for layer in layers:
        layer["depth"] = depth_of(layer.get("z", 0.0))
    return {
        "name": "关系测试",
        "canvas": [900, 1200],
        "ref_width": 900,
        "palette": "dusk",
        "background": "bg",
        "layers": layers,
    }


# 二郎神：右手在 (704, 824) 握住长杆，胳膊往左下伸，肘子在 (576, 780)。
# 杆从他手里往左上斜着上去，手和肘子张开的角就是兵器和胳膊之间的那个缝。
ELBOW = (576, 780)
HAND = (704, 824)
BLADE_TIP = (600, 400)

EL_POSE = {
    "hip": (0, 0), "chest": (0, -0.28), "neck": (0, -0.34), "head": (0, -0.41),
    "shoulder_l": (-0.13, -0.31), "shoulder_r": (0.13, -0.31),
    "elbow_l": (-0.15, -0.13), "elbow_r": (-0.16, -0.05),
    "hand_l": (-0.16, 0.06), "hand_r": (0.16, 0.06),
    "knee_l": (-0.07, 0.42), "knee_r": (0.07, 0.42),
    "foot_l": (-0.08, 0.84), "foot_r": (0.08, 0.84),
}

WK_POSE = {
    "hip": (0, 0), "chest": (0, -0.28), "neck": (0, -0.34), "head": (0, -0.41),
    "shoulder_l": (-0.13, -0.31), "shoulder_r": (0.13, -0.31),
    "elbow_l": (-0.15, -0.13), "elbow_r": (0.15, -0.13),
    "hand_l": (-0.16, 0.06), "hand_r": (0.16, 0.06),
    "knee_l": (-0.07, 0.42), "knee_r": (0.07, 0.42),
    "foot_l": (-0.08, 0.84), "foot_r": (0.08, 0.84),
}


def duel(cudgel_z=0.0):
    """二郎神握杆，金箍棒从兵器和胳膊之间的那个角里穿过去。

    cudgel_z 是金箍棒的深度。跟人物一个深度就是卡在缝里，
    摆到人物前面就是从身前扫过去。
    """
    blade = rod("three-pointed blade", "erlang shen", HAND, BLADE_TIP, z=0.0)
    # 金箍棒斜着穿过那个角，离手边 50 像素，离二郎神的小臂 22 像素
    cudgel = rod("golden cudgel", "wukong", (725.6, 845.6), (612.4, 732.4),
                 half_width=10.0, z=cudgel_z,
                 segments=[{"from": 0.0, "to": 1.0,
                            "depth": depth_of(cudgel_z), "z": cudgel_z}])
    return build([
        figure((100, 300), 400, "wukong", z=60.0, pose=WK_POSE),
        cudgel,
        blade,
        figure((640, 800), 400, "erlang shen", z=0.0, pose=EL_POSE),
    ])


class TestSegmentMath:
    def test_parallel_lines_keep_their_distance(self):
        gap = seg_seg_distance((0, 0, 0), (100, 0, 0), (0, 20, 0), (100, 20, 0))
        assert abs(gap[0] - 20.0) < 0.001

    def test_crossing_lines_touch(self):
        gap = seg_seg_distance((0, 0, 0), (100, 0, 0), (50, -50, 0), (50, 50, 0))
        assert abs(gap[0]) < 0.001

    def test_depth_counts_in_the_distance(self):
        gap = seg_seg_distance((0, 0, 0), (100, 0, 0), (0, 20, 100), (100, 20, 100))
        assert abs(gap[0] - math.hypot(20.0, 100.0)) < 0.001

    def test_picture_distance_ignores_depth(self):
        gap = seg_seg_distance_2d((0, 0, 0), (100, 0, 0), (0, 20, 100), (100, 20, 100))
        assert abs(gap[0] - 20.0) < 0.001

    def test_crossing_point_comes_with_its_ratio(self):
        hit = seg_seg_cross((0, 0, 0), (100, 0, 0), (50, -50, 0), (50, 50, 0))
        assert hit is not None
        point, s, t = hit
        assert abs(point[0] - 50.0) < 0.001 and abs(point[1]) < 0.001
        assert abs(s - 0.5) < 0.001 and abs(t - 0.5) < 0.001

    def test_parallel_lines_do_not_cross(self):
        assert seg_seg_cross((0, 0, 0), (100, 0, 0), (0, 20, 0), (100, 20, 0)) is None

    def test_crossing_outside_the_segments_does_not_count(self):
        assert seg_seg_cross((0, 0, 0), (10, 0, 0), (20, -50, 0), (20, 50, 0)) is None


class TestWedge:
    def test_point_inside_the_angle(self):
        assert in_wedge((0, 0), (0, 10), (10, 0), (3, 3), 100)

    def test_point_on_the_edge_is_not_inside(self):
        assert not in_wedge((0, 0), (0, 10), (10, 0), (0, 5), 100)

    def test_point_too_far_from_the_vertex(self):
        assert not in_wedge((0, 0), (0, 10), (10, 0), (60, 60), 50)

    def test_angle_opening_the_other_way(self):
        assert in_wedge((0, 0), (0, 10), (-10, 0), (-3, 3), 100)


class TestGapAndOverlap:
    def test_cudgel_at_the_same_depth_is_trapped_in_the_gap(self):
        result = analyze(duel(cudgel_z=0.0))
        assert any("缝里穿过去" in text for text in result["issues"])
        assert any("挨得太近" in text for text in result["issues"])

    def test_cudgel_in_front_sweeps_across(self):
        result = analyze(duel(cudgel_z=-60.0))
        assert not any("缝里穿过去" in text for text in result["issues"])
        assert not any("挨得太近" in text for text in result["issues"])
        assert any("前面扫过去" in text for text in result["notes"])
        assert result["gaps"]
        assert not result["gaps"][0]["trapped"]

    def test_cudgel_behind_is_not_trapped_either(self):
        result = analyze(duel(cudgel_z=60.0))
        assert not any("缝里穿过去" in text for text in result["issues"])
        assert any("后面过去" in text for text in result["notes"])

    def test_gap_entry_says_how_far_from_the_hand(self):
        result = analyze(duel(cudgel_z=0.0))
        assert result["gaps"]
        assert result["gaps"][0]["distance"] < 120

    def test_report_mentions_what_was_checked(self):
        text = report(analyze(duel(cudgel_z=-60.0)))
        assert "兵器和肢体之间的空间关系" in text
        assert "看过的几处" in text


class TestPlanSegments:
    def test_segment_bounds_are_checked(self):
        plan = duel()
        plan["layers"][1]["segments"] = [{"from": 0.8, "to": 0.2,
                                           "depth": 1.5, "z": -60}]
        errors = validate_plan(plan)
        assert any("from 要小于 to" in text for text in errors)

    def test_segment_depth_must_be_a_number(self):
        plan = duel()
        plan["layers"][1]["segments"] = [{"from": 0.0, "to": 1.0,
                                           "depth": "前面", "z": -60}]
        errors = validate_plan(plan)
        assert any("depth 必须是数字" in text for text in errors)

    def test_depth_and_z_contradiction_is_reported(self):
        plan = duel()
        plan["layers"][2]["z"] = 200.0
        plan["layers"][2]["depth"] = depth_of(0.0)
        errors = validate_plan(plan)
        assert any("打架" in text for text in errors)

    def test_a_weapon_in_segments_becomes_several_units(self):
        plan = duel()
        plan["layers"][1]["segments"] = [
            {"from": 0.0, "to": 0.4, "depth": 5.0, "z": 80},
            {"from": 0.4, "to": 1.0, "depth": 1.5, "z": -60},
        ]
        plan["layers"][1]["depth"] = 5.0
        units = ordered_units(plan)
        cudgel_units = [item for item in units if "golden cudgel" in item["name"]]
        assert len(cudgel_units) == 2
        assert cudgel_units[0]["depth"] > cudgel_units[1]["depth"]
        assert [item["depth"] for item in units] == sorted(
            [item["depth"] for item in units], reverse=True)

    def test_every_layer_keeps_its_depth_in_the_plan(self):
        plan = duel()
        assert all("depth" in layer for layer in plan["layers"])


class TestDepthFromZ:
    def test_depth_is_derived_from_z(self):
        plan = duel(cudgel_z=-60.0)
        del plan["layers"][1]["depth"]
        resolved = resolve_depths(plan)
        assert "depth" in resolved["layers"][1]
        assert abs(resolved["layers"][1]["depth"] - depth_of(-60.0)) < 0.001

    def test_derived_depth_orders_the_layers(self):
        plan = duel(cudgel_z=-60.0)
        del plan["layers"][1]["depth"]
        layers = ordered_layers(plan)
        assert layers[0]["name"] == "wukong"
        assert layers[-1]["name"] == "golden cudgel"

    def test_depth_and_z_have_to_sit_on_one_line(self):
        plan = duel(cudgel_z=-60.0)
        plan["layers"][3]["z"] = 100.0
        errors = validate_plan(plan)
        assert any("对不上" in text for text in errors)

    def test_a_layer_without_depth_keeps_the_plan_order(self):
        plan = duel()
        del plan["layers"][1]["depth"]
        del plan["layers"][3]["depth"]
        del plan["layers"][3]["z"]
        layers = ordered_layers(plan)
        assert [layer["name"] for layer in layers] == [
            "wukong", "golden cudgel", "three-pointed blade", "erlang shen"]


class TestBriefOrder:
    def test_a_split_weapon_is_listed_at_its_nearest_piece(self):
        from photocraft_draw.brief import build_brief

        plan = duel(cudgel_z=-60.0)
        plan["layers"][1]["segments"] = [
            {"from": 0.0, "to": 0.4, "depth": 5.0, "z": 80},
            {"from": 0.4, "to": 1.0, "depth": 1.5, "z": -60},
        ]
        plan["layers"][1]["depth"] = 5.0
        names = [entry["name"] for entry in build_brief(plan)["layers"]]
        assert names.index("golden cudgel") > names.index("erlang shen")

    def test_a_plain_layer_keeps_its_own_depth(self):
        from photocraft_draw.brief import build_brief

        names = [entry["name"] for entry in build_brief(duel())["layers"]]
        assert names.index("wukong") < names.index("erlang shen")


class TestSplit:
    def test_axis_follows_the_declaration(self):
        components = [{
            "component": "custom_shape",
            "params": {"subpaths": [{"knots": [[0, 0], [10, 10]]}]},
        }]
        axis = axis_of(components, [[1, 2], [3, 4]])
        assert axis == ((1.0, 2.0), (3.0, 4.0))

    def test_axis_comes_from_the_farthest_points(self):
        components = [{
            "component": "custom_shape",
            "params": {"subpaths": [{"knots": [[0, 0], [100, 0], [50, 3]]}]},
        }]
        axis = axis_of(components)
        assert axis == ((0.0, 0.0), (100.0, 0.0))

    def test_slice_keeps_only_the_asked_for_part(self):
        params = {"subpaths": [{"closed": True,
                                "knots": [[0, 0], [100, 0], [100, 20], [0, 20]]}]}
        piece = slice_shape(params, ((0, 0), (100, 0)), 0.25, 0.75)
        xs = [knot[0] for knot in piece["subpaths"][0]["knots"]]
        assert min(xs) >= 24.0 and max(xs) <= 76.0
