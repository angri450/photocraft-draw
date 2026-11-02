# -*- coding: utf-8 -*-
"""人物白模组件的规则测试。"""
import unittest

from photocraft_draw.commands import Pen
from photocraft_draw.components import rig
from photocraft_draw.palette import resolve_palette


def pen():
    return Pen(900, 1200, ref_width=800, palette=resolve_palette("alpine"))


def names(target):
    return [item["params"].get("name", "") for item in target.commands]


class RigTest(unittest.TestCase):
    def test_every_pose_draws(self):
        for pose in rig.POSES:
            target = pen()
            rig.build_figure_rig({"root": [400, 600], "height": 300, "pose": pose}, target)
            self.assertGreaterEqual(len(target.commands), 20, pose)

    def test_all_joints_present(self):
        target = pen()
        rig.build_figure_rig({"root": [400, 600], "height": 300}, target)
        drawn = [name for name in names(target) if name.startswith("关节")]
        self.assertEqual(len(drawn), len(rig.JOINT_SCALE))

    def test_bones_connect_joints(self):
        target = pen()
        rig.build_figure_rig({"root": [400, 600], "height": 300}, target)
        bones = [name for name in names(target) if name.startswith("骨段")]
        self.assertEqual(len(bones), len(rig.BONES))

    def test_height_scales_output(self):
        small = pen()
        rig.build_figure_rig({"root": [400, 600], "height": 200}, small)
        large = pen()
        rig.build_figure_rig({"root": [400, 600], "height": 400}, large)
        small_len = small.commands[0]["params"]
        large_len = large.commands[0]["params"]
        self.assertGreater(abs(large_len["to"][1] - large_len["from"][1]),
                           abs(small_len["to"][1] - small_len["from"][1]))

    def test_flip_mirrors(self):
        normal = pen()
        rig.build_figure_rig({"root": [400, 600], "height": 300, "pose": "point"}, normal)
        flipped = pen()
        rig.build_figure_rig({"root": [400, 600], "height": 300, "pose": "point", "flip": True}, flipped)
        hand_normal = [item for item in normal.commands if item["params"].get("name") == "关节 hand_r"]
        hand_flipped = [item for item in flipped.commands if item["params"].get("name") == "关节 hand_l"]
        self.assertNotEqual(hand_normal[0]["params"]["rect"], hand_flipped[0]["params"]["rect"])

    def test_custom_pose(self):
        table = dict(rig.POSES["stand"])
        table["hand_r"] = (0.5, -0.5)
        target = pen()
        rig.build_figure_rig({"root": [400, 600], "height": 300, "pose": table}, target)
        self.assertGreater(len(target.commands), 20)

    def test_bad_pose_raises(self):
        with self.assertRaises(ValueError):
            rig.build_figure_rig({"root": [400, 600], "height": 300, "pose": "dance"}, pen())

    def test_missing_root_raises(self):
        with self.assertRaises(ValueError):
            rig.build_figure_rig({"height": 300}, pen())

    def test_missing_height_raises(self):
        with self.assertRaises(ValueError):
            rig.build_figure_rig({"root": [400, 600]}, pen())

    def test_custom_pose_missing_joint(self):
        with self.assertRaises(ValueError):
            rig.build_figure_rig({"root": [400, 600], "height": 300,
                                  "pose": {"hip": (0, 0)}}, pen())

    def test_within_budget(self):
        target = pen()
        rig.build_figure_rig({"root": [400, 600], "height": 300}, target)
        self.assertLess(len(target.commands), 40)


if __name__ == "__main__":
    unittest.main()


class PathTest(unittest.TestCase):
    def test_path_command_shape(self):
        target = pen()
        target.path([{"closed": True, "knots": [[10, 20], [30, 20], [20, 40]]}], fill="line")
        item = target.commands[0]
        self.assertEqual(item["command"], "shape.create")
        self.assertEqual(item["params"]["kind"], "path")
        self.assertEqual(len(item["params"]["path"]["subpaths"][0]["knots"]), 3)

    def test_bezier_knots_keep_handles(self):
        target = pen()
        target.path([{"closed": True, "knots": [
            {"anchor": [10, 20], "in": [5, 10], "out": [20, 10]},
            {"anchor": [40, 20], "in": [30, 10], "out": [50, 10]},
        ]}], fill="line")
        knots = target.commands[0]["params"]["path"]["subpaths"][0]["knots"]
        self.assertIn("in", knots[0])
        self.assertIn("out", knots[1])

    def test_custom_shape_component(self):
        from photocraft_draw.components import block
        target = pen()
        block.build_custom_shape({"subpaths": [{"closed": True,
                                                "knots": [[10, 10], [50, 10], [30, 40]]}],
                                  "fill": "line"}, target)
        self.assertEqual(target.commands[0]["params"]["kind"], "path")

    def test_custom_shape_needs_subpaths(self):
        from photocraft_draw.components import block
        with self.assertRaises(ValueError):
            block.build_custom_shape({}, pen())
