# -*- coding: utf-8 -*-
"""三维盒子投影的测试。"""
import unittest

from photocraft_draw.commands import Pen
from photocraft_draw.components import box3d
from photocraft_draw.palette import resolve_palette


def pen():
    return Pen(900, 1200, ref_width=800, palette=resolve_palette("dawn"))


class Box3DTest(unittest.TestCase):
    def test_far_drawn_first(self):
        target = pen()
        box3d.build_box3d_scene({"boxes": [
            [100, 100, 0, 80, 80, 10],
            [100, 100, 60, 80, 80, 10],
        ], "colors": ["deep", "muted"]}, target)
        names = [item["params"]["name"] for item in target.commands]
        self.assertEqual(names[0], "盒 2")  # z=60 的先画
        self.assertEqual(names[1], "盒 1")

    def test_skew_shifts_x(self):
        target = pen()
        box3d.build_box3d_scene({"boxes": [[0, 0, 100, 50, 50, 10]], "skew_x": 0.5}, target)
        x, y, w, h = target.commands[0]["params"]["rect"]
        self.assertGreater(x, 0)

    def test_missing_boxes_raises(self):
        with self.assertRaises(ValueError):
            box3d.build_box3d_scene({}, pen())

    def test_bad_box_raises(self):
        with self.assertRaises(ValueError):
            box3d.build_box3d_scene({"boxes": [[1, 2, 3]]}, pen())

    def test_within_budget(self):
        target = pen()
        box3d.build_box3d_scene({"boxes": [[i * 10, 0, i, 40, 40, 10] for i in range(20)]}, target)
        self.assertEqual(len(target.commands), 20)


if __name__ == "__main__":
    unittest.main()
