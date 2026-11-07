# -*- coding: utf-8 -*-
"""正交投影与三视图的测试。

覆盖：三个轴向各取哪两个坐标、不除以深度、比例尺三个视图共用、
同一个 x 在正视图和俯视图里落在同一列、同一个 y 在正视图和左视图里落在
同一行、空点集和空网格报错、尺寸线在投影退化的视图里跳过。
"""
import math

import pytest

from photocraft_draw.ortho import (
    AXES,
    build_views,
    demo_meshes,
    make_blossom,
    ortho_project,
    project_panel,
)


def box_mesh(width=1.8, height=2.2, depth=1.1, x=0.0, z=0.0):
    """一个轴对齐的方块，用来量三个视角的宽高。"""
    half_w, half_d = width / 2.0, depth / 2.0
    vertices = [
        [x - half_w, 0.0, z - half_d], [x + half_w, 0.0, z - half_d],
        [x + half_w, 0.0, z + half_d], [x - half_w, 0.0, z + half_d],
        [x - half_w, height, z - half_d], [x + half_w, height, z - half_d],
        [x + half_w, height, z + half_d], [x - half_w, height, z + half_d],
    ]
    faces = [
        [0, 1, 2, 3], [4, 7, 6, 5],
        [3, 2, 6, 7], [0, 4, 5, 1],
        [0, 3, 7, 4], [1, 5, 6, 2],
    ]
    return {"vertices": vertices, "faces": faces, "color": "#B08A5E", "name": "方块"}


def extents(points):
    """一组二维点的宽和高。"""
    us = [point[0] for point in points]
    vs = [point[1] for point in points]
    return max(us) - min(us), max(vs) - min(vs)


class TestOrthoProject:
    def test_front_takes_x_and_y(self):
        assert ortho_project([[1, 2, 3]], "front", 1.0) == [[1, 2]]

    def test_left_takes_z_and_y(self):
        assert ortho_project([[1, 2, 3]], "left", 1.0) == [[3, 2]]

    def test_top_takes_x_and_z(self):
        assert ortho_project([[1, 2, 3]], "top", 1.0) == [[1, 3]]

    def test_scale_multiplies_both_axes(self):
        assert ortho_project([[1, 2, 3]], "front", 10.0) == [[10, 20]]

    def test_depth_is_not_divided(self):
        near = ortho_project([[1, 2, 0]], "front", 1.0)
        far = ortho_project([[1, 2, 1000]], "front", 1.0)
        assert near == far == [[1, 2]]

    def test_tuple_points_are_accepted(self):
        assert ortho_project([(1, 2, 3)], "top", 2.0) == [[2, 6]]

    def test_empty_points_raise(self):
        with pytest.raises(ValueError, match="空点集"):
            ortho_project([], "front", 1.0)

    def test_unknown_axis_raises(self):
        with pytest.raises(ValueError, match="投影轴向"):
            ortho_project([[1, 2, 3]], "side", 1.0)

    def test_short_point_raises(self):
        with pytest.raises(ValueError, match="\\[x, y, z\\]"):
            ortho_project([[1, 2]], "front", 1.0)

    def test_zero_scale_raises(self):
        with pytest.raises(ValueError, match="比例尺"):
            ortho_project([[1, 2, 3]], "front", 0.0)


class TestViewScale:
    def test_three_views_differ_in_width_and_height(self):
        mesh = box_mesh(1.8, 2.2, 1.1)
        front = extents(ortho_project(mesh["vertices"], "front"))
        left = extents(ortho_project(mesh["vertices"], "left"))
        top = extents(ortho_project(mesh["vertices"], "top"))
        assert front == pytest.approx((1.8, 2.2))
        assert left == pytest.approx((1.1, 2.2))
        assert top == pytest.approx((1.8, 1.1))

    def test_one_scale_for_all_three_panels(self):
        _, meta = build_views([box_mesh()], width=900, height=1200)
        assert meta["scale"] > 0
        assert len(meta["panels"]) == 3
        assert [panel["view"] for panel in meta["panels"]] == list(AXES)

    def test_unit_length_maps_to_the_same_pixels(self):
        _, meta = build_views([box_mesh()], width=900, height=1200)
        front_a = project_panel([0, 0, 0], "front", meta)
        front_b = project_panel([1, 0, 0], "front", meta)
        top_a = project_panel([0, 0, 0], "top", meta)
        top_b = project_panel([1, 0, 0], "top", meta)
        assert front_b[0] - front_a[0] == pytest.approx(meta["scale"])
        assert top_b[0] - top_a[0] == pytest.approx(meta["scale"])

    def test_same_x_lands_in_the_same_column(self):
        _, meta = build_views([box_mesh()], width=900, height=1200)
        front_panel = meta["panels"][AXES.index("front")]
        top_panel = meta["panels"][AXES.index("top")]
        for x in (-1.2, 0.0, 1.4):
            front = project_panel([x, 0, 0], "front", meta)
            top = project_panel([x, 0, 0], "top", meta)
            assert (front[0] - front_panel["left"]) == pytest.approx(
                top[0] - top_panel["left"])

    def test_same_y_lands_in_the_same_row(self):
        _, meta = build_views([box_mesh()], width=900, height=1200)
        for y in (0.0, 1.1, 2.2):
            front = project_panel([0, y, 0], "front", meta)
            left = project_panel([0, y, 0], "left", meta)
            assert front[1] == pytest.approx(left[1])

    def test_canvas_is_three_panels_wide(self):
        _, meta = build_views([box_mesh()], width=720, height=900)
        assert meta["width"] == 2160
        assert meta["height"] == 900


class TestMeshInput:
    def test_dict_mesh_renders_faces(self):
        commands, meta = build_views([box_mesh()])
        assert meta["faces"] == 3
        assert commands

    def test_object_mesh_is_accepted(self):
        class Mesh:
            def __init__(self):
                data = box_mesh()
                self.vertices = data["vertices"]
                self.faces = data["faces"]
                self.color = "mid"

        _, meta = build_views([Mesh()])
        assert meta["faces"] == 3

    def test_empty_mesh_list_raises(self):
        with pytest.raises(ValueError, match="至少一个网格"):
            build_views([])

    def test_mesh_without_vertices_raises(self):
        with pytest.raises(ValueError, match="vertices"):
            build_views([{"faces": [[0, 1, 2]]}])

    def test_mesh_without_faces_raises(self):
        with pytest.raises(ValueError, match="faces"):
            build_views([{"vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]]}])

    def test_face_with_unknown_vertex_raises(self):
        with pytest.raises(ValueError, match="不存在"):
            build_views([{"vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                          "faces": [[0, 1, 7]]}])

    def test_commands_stay_flat(self):
        commands, _ = build_views([box_mesh()])
        allowed = {"shape.create", "type.create"}
        assert {item["command"] for item in commands} <= allowed

    def test_demo_primitives_render(self):
        from photocraft_draw.ortho import demo_meshes

        commands, meta = build_views(demo_meshes(), width=800, height=700)
        assert meta["meshes"] == 4
        assert meta["faces"] > 100
        assert commands


class TestDimensions:
    def test_degenerate_dimension_is_skipped(self):
        # 沿 z 的尺寸在正视图里压成一个点，画不出来，应该跳过。
        dimensions = [{"from": [0, 0, 0], "to": [0, 0, 1.5], "label": "深 1.5"}]
        commands, meta = build_views([box_mesh()], dimensions=dimensions)
        assert meta["dimensions"] == 2
        lines = [item for item in commands
                 if item["params"].get("name", "").startswith("尺寸线")]
        assert len(lines) == 2

    def test_dimension_is_drawn_in_every_useful_view(self):
        dimensions = [{"from": [-1, 0, 0], "to": [1, 0, 0], "label": "宽 2"}]
        commands, meta = build_views([box_mesh()], dimensions=dimensions)
        assert meta["dimensions"] == 2
        texts = [item for item in commands if item["command"] == "type.create"]
        assert any(item["params"]["text"] == "宽 2" for item in texts)

    def test_views_can_be_limited(self):
        dimensions = [{"from": [-1, 0, 0], "to": [1, 0, 0], "label": "宽 2",
                       "views": ["front"]}]
        _, meta = build_views([box_mesh()], dimensions=dimensions)
        assert meta["dimensions"] == 1

    def test_unknown_dimension_view_raises(self):
        dimensions = [{"from": [0, 0, 0], "to": [1, 0, 0], "views": ["back"]}]
        with pytest.raises(ValueError, match="不认识的视图"):
            build_views([box_mesh()], dimensions=dimensions)

    def test_short_dimension_point_raises(self):
        with pytest.raises(ValueError, match="\\[x, y, z\\]"):
            build_views([box_mesh()], dimensions=[{"from": [0, 0], "to": [1, 0, 0]}])


class TestPerViewCenter:
    """每个视图按自身内容竖向居中，默认关闭，比例尺始终不变。"""

    def test_default_keeps_the_shared_center(self):
        _, meta = build_views(demo_meshes(), width=800, height=700)
        assert meta["center_per_view"] is False
        for view in AXES:
            assert meta["v_centers"][view] == pytest.approx(meta["v_center"])

    def test_switch_uses_each_view_content_center(self):
        _, meta = build_views(demo_meshes(), width=800, height=700,
                              center_per_view=True)
        assert meta["center_per_view"] is True
        assert meta["v_centers"]["front"] == pytest.approx(1.1)
        assert meta["v_centers"]["left"] == pytest.approx(1.1)
        assert meta["v_centers"]["top"] == pytest.approx(0.25)

    def test_each_view_keeps_its_own_range(self):
        _, meta = build_views(demo_meshes(), width=800, height=700,
                              center_per_view=True)
        assert meta["v_ranges"]["front"] == pytest.approx([0.0, 2.2])
        assert meta["v_ranges"]["left"] == pytest.approx([0.0, 2.2])
        assert meta["v_ranges"]["top"] == pytest.approx([-2.0, 2.5])

    def test_scale_does_not_change(self):
        _, plain = build_views(demo_meshes(), width=800, height=700)
        _, centered = build_views(demo_meshes(), width=800, height=700,
                                  center_per_view=True)
        assert centered["scale"] == pytest.approx(plain["scale"])

    def test_content_midpoint_lands_on_panel_middle(self):
        _, meta = build_views(demo_meshes(), width=800, height=700,
                              center_per_view=True)
        cases = {
            "front": ([0.0, 0.0, 0.0], [0.0, 2.2, 0.0]),
            "left": ([0.0, 0.0, 0.0], [0.0, 2.2, 0.0]),
            "top": ([0.0, 0.0, -2.0], [0.0, 0.0, 2.5]),
        }
        for view, (low, high) in cases.items():
            panel = meta["panels"][AXES.index(view)]
            middle = panel["top"] + panel["height"] / 2.0
            first = project_panel(low, view, meta)
            second = project_panel(high, view, meta)
            assert (first[1] + second[1]) / 2.0 == pytest.approx(middle)

    def test_horizontal_alignment_survives(self):
        _, meta = build_views(demo_meshes(), width=800, height=700,
                              center_per_view=True)
        front_panel = meta["panels"][AXES.index("front")]
        top_panel = meta["panels"][AXES.index("top")]
        for x in (-3.0, 0.0, 3.0):
            front = project_panel([x, 0.0, 0.0], "front", meta)
            top = project_panel([x, 0.0, 0.0], "top", meta)
            assert (front[0] - front_panel["left"]) == pytest.approx(
                top[0] - top_panel["left"])

    def test_centering_moves_the_front_view_to_the_middle(self):
        _, plain = build_views(demo_meshes(), width=800, height=700)
        _, centered = build_views(demo_meshes(), width=800, height=700,
                                  center_per_view=True)
        panel = centered["panels"][AXES.index("front")]
        middle = panel["top"] + panel["height"] / 2.0
        low = project_panel([0.0, 0.0, 0.0], "front", centered)
        high = project_panel([0.0, 2.2, 0.0], "front", centered)
        assert (low[1] + high[1]) / 2.0 == pytest.approx(middle)
        # 默认模式下内容中点不落在画板中点
        low_plain = project_panel([0.0, 0.0, 0.0], "front", plain)
        high_plain = project_panel([0.0, 2.2, 0.0], "front", plain)
        assert abs((low_plain[1] + high_plain[1]) / 2.0 - middle) > 1.0


class TestBlossom:
    """薄片花形：五瓣、自带标记、不按法向剔除、侧视压扁。"""

    def flower(self, **kwargs):
        options = {"center": [0.0, 0.0, 0.0], "diameter": 1.0,
                   "facing": [0.0, 0.0, 1.0]}
        options.update(kwargs)
        return make_blossom(**options)

    def test_mesh_has_five_petals_and_a_flag(self):
        flower = self.flower()
        assert flower["shape"] == "blossom"
        assert flower["petals"] == 5
        assert len(flower["faces"]) == 5
        # 每瓣一圈轮廓点，瓣数固定，点数随轮廓加密可增
        first = len(flower["faces"][0])
        assert all(len(face) == first for face in flower["faces"])
        assert len(flower["vertices"]) == len(flower["faces"]) * first

    def test_front_view_shows_five_petals(self):
        _, meta = build_views([self.flower()], width=800, height=700)
        assert meta["view_faces"]["front"] == 5

    def test_side_view_uses_one_lens_instead_of_petals(self):
        commands, _ = build_views([self.flower()], width=800, height=700)
        petals = [item for item in commands
                  if item["params"].get("name", "").startswith("花·花瓣")]
        lenses = [item for item in commands
                  if item["params"].get("name", "").startswith("花·侧视")]
        # 正视是五瓣；左视和俯视接近侧视，按杯状截面画成一个扁椭圆，
        # 不再让花瓣尖拉出长刺。
        assert len(petals) == 5
        assert len(lenses) == 2

    def test_side_view_is_flatter_than_the_front(self):
        flower = self.flower()
        front = extents(ortho_project(flower["vertices"], "front"))[0]
        left = extents(ortho_project(flower["vertices"], "left"))[0]
        assert 0.9 <= front <= 1.0
        assert left == pytest.approx(0.0, abs=1e-9)

    def test_scale_matches_the_other_objects(self):
        flower = self.flower()
        box = box_mesh(1.8, 2.2, 1.1)
        _, meta = build_views([box, flower], width=800, height=700)
        for mesh in (box, flower):
            world = extents(ortho_project(mesh["vertices"], "front"))[0]
            screen = extents([project_panel(point, "front", meta)
                              for point in mesh["vertices"]])[0]
            assert screen == pytest.approx(world * meta["scale"])

    def test_petals_are_stroked_with_their_own_fill(self):
        commands, _ = build_views([self.flower()], width=800, height=700)
        petals = [item["params"] for item in commands
                  if item["params"].get("name", "").startswith("花·花瓣")]
        assert petals
        for params in petals:
            assert params["stroke"]["color"] == params["fill"]

    def test_petals_field_alone_marks_a_blossom(self):
        flower = self.flower()
        flower.pop("shape")
        commands, meta = build_views([flower], width=800, height=700)
        lenses = [item for item in commands
                  if item["params"].get("name", "").startswith("花·侧视")]
        assert len(lenses) == 2
        assert meta["view_faces"]["left"] == 1

    def test_flower_turned_toward_a_view_keeps_its_petals(self):
        # 花面朝 +X 时，左视图是正视，应当画五瓣而不是扁椭圆
        flower = self.flower(facing=[1.0, 0.0, 0.0])
        commands, _ = build_views([flower], width=800, height=700)
        petals = [item for item in commands
                  if item["params"].get("name", "").startswith("花·花瓣")]
        lenses = [item for item in commands
                  if item["params"].get("name", "").startswith("花·侧视")]
        assert len(petals) == 5
        assert lenses

    def test_empty_parameters_raise(self):
        with pytest.raises(ValueError, match="center"):
            make_blossom()
        with pytest.raises(ValueError, match="diameter"):
            make_blossom([0, 0, 0], 0)
        with pytest.raises(ValueError, match="petals"):
            make_blossom([0, 0, 0], 1.0, petals=2)
        with pytest.raises(ValueError, match="facing|零向量"):
            make_blossom([0, 0, 0], 1.0, facing=[0, 0, 0])
