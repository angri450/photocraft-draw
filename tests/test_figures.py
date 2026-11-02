# -*- coding: utf-8 -*-
"""人物组件的规则测试。"""
import unittest

from photocraft_draw.commands import Pen
from photocraft_draw.components import figures
from photocraft_draw.palette import resolve_palette


def Recorder():
    """只记录指令，不换算出图。"""
    return Pen(800, 450, ref_width=800, palette=resolve_palette("fresco"))


class FiguresTest(unittest.TestCase):
    def test_seated_figure_emits_shapes(self):
        pen = Recorder()
        figures.build_seated_figure({"seat": [100, 180, 50, 128], "pose": "front"}, pen)
        self.assertGreaterEqual(len(pen.commands), 8)
        self.assertTrue(all(item["command"] == "shape.create" for item in pen.commands))

    def test_five_poses_all_draw(self):
        counts = {}
        for pose in figures.POSES:
            pen = Recorder()
            figures.build_seated_figure({"seat": [100, 180, 50, 128], "pose": pose}, pen)
            counts[pose] = len(pen.commands)
        self.assertEqual(len(counts), len(figures.POSES))
        for pose, count in counts.items():
            self.assertGreaterEqual(count, 8, pose)

    def test_pose_changes_silhouette(self):
        front = Recorder()
        figures.build_seated_figure({"seat": [100, 180, 50, 128], "pose": "front"}, front)
        point = Recorder()
        figures.build_seated_figure({"seat": [100, 180, 50, 128], "pose": "point"}, point)
        self.assertNotEqual(front.commands, point.commands)

    def test_bad_pose_raises(self):
        with self.assertRaises(ValueError):
            figures.build_seated_figure({"seat": [100, 180, 50, 128], "pose": "dance"}, Recorder())

    def test_missing_seat_raises(self):
        with self.assertRaises(ValueError):
            figures.build_seated_figure({"pose": "front"}, Recorder())

    def test_zero_size_seat_raises(self):
        with self.assertRaises(ValueError):
            figures.build_seated_figure({"seat": [100, 180, 0, 128]}, Recorder())

    def test_leaner_needs_elbow(self):
        with self.assertRaises(ValueError):
            figures.build_leaning_figure({"seat": [200, 180, 56, 124]}, Recorder())

    def test_leaner_draws(self):
        pen = Recorder()
        figures.build_leaning_figure(
            {"seat": [200, 180, 56, 124], "elbow": [258, 300], "robe": "mid"}, pen)
        self.assertGreaterEqual(len(pen.commands), 7)

    def test_head_each_turn(self):
        for turn in figures.TURNS:
            pen = Recorder()
            figures.build_figure_head({"center": [400, 150], "size": 44, "turn": turn}, pen)
            self.assertGreater(len(pen.commands), 6, turn)

    def test_head_beard_adds_shapes(self):
        bare = Recorder()
        figures.build_figure_head({"center": [400, 150], "size": 44}, bare)
        bearded = Recorder()
        figures.build_figure_head({"center": [400, 150], "size": 44, "beard": True}, bearded)
        self.assertGreater(len(bearded.commands), len(bare.commands))

    def test_bad_turn_raises(self):
        with self.assertRaises(ValueError):
            figures.build_figure_head({"center": [400, 150], "turn": "up"}, Recorder())

    def test_hands_need_list(self):
        with self.assertRaises(ValueError):
            figures.build_figure_hands({}, Recorder())

    def test_hands_four_kinds(self):
        for kind in figures.HAND_KINDS:
            pen = Recorder()
            figures.build_figure_hands({"hands": [[400, 316, kind]], "size": 14}, pen)
            self.assertGreaterEqual(len(pen.commands), 3, kind)

    def test_bad_hand_kind_raises(self):
        with self.assertRaises(ValueError):
            figures.build_figure_hands({"hands": [[400, 316, "wave"]]}, Recorder())

    def test_row_repeats_poses(self):
        pen = Recorder()
        figures.build_figure_row(
            {"row": [60, 178, 50, 128], "count": 6, "poses": ["side", "front"]}, pen)
        self.assertGreaterEqual(len(pen.commands), 48)

    def test_row_needs_count(self):
        with self.assertRaises(ValueError):
            figures.build_figure_row({"row": [60, 178, 50, 128]}, Recorder())

    def test_no_pure_black_or_white(self):
        pen = Pen(1600, 900, ref_width=800, palette=resolve_palette("fresco"))
        figures.build_seated_figure({"seat": [100, 180, 50, 128], "pose": "open"}, pen)
        figures.build_figure_head({"center": [100, 150], "size": 42}, pen)
        for item in pen.commands:
            fill = str(item["params"].get("fill", "")).upper()
            self.assertNotIn(fill, ("#000000", "#FFFFFF", "BLACK", "WHITE"))

    def test_single_figure_within_budget(self):
        pen = Recorder()
        figures.build_seated_figure({"seat": [100, 180, 50, 128], "pose": "point"}, pen)
        figures.build_figure_head({"center": [125, 150], "size": 42}, pen)
        figures.build_figure_hands({"hands": [[110, 316, "open"], [140, 316, "rest"]]}, pen)
        self.assertLess(len(pen.commands), 120)


if __name__ == "__main__":
    unittest.main()
