# -*- coding: utf-8 -*-
import unittest

from photocraft_draw.commands import Pen
from photocraft_draw.components import arched_windows, indoor_backdrop, long_table
from photocraft_draw.palette import resolve_palette


def pen():
    return Pen(800, 450, ref_width=800, palette=resolve_palette("fresco"))


class ComponentTest(unittest.TestCase):
    def test_indoor_backdrop(self):
        target = pen()
        indoor_backdrop.build(
            {
                "wall": [0, 0, 800, 450],
                "floor": [0, 355, 800, 95],
                "ceiling": [90, 30, 620, 70],
                "tapestries": [[18, 110, 70, 230], [712, 110, 70, 230]],
            },
            target,
        )
        shapes = [item for item in target.commands if item["command"] == "shape.create"]
        self.assertGreater(len(shapes), 10)
        self.assertEqual(shapes[0]["command"], "shape.create")

    def test_indoor_backdrop_requires_wall(self):
        with self.assertRaises(ValueError):
            indoor_backdrop.build({}, pen())

    def test_arched_windows(self):
        target = pen()
        arched_windows.build({"windows": [[330, 140, 90, 150], [520, 140, 90, 150]]}, target)
        shapes = [item for item in target.commands if item["command"] == "shape.create"]
        self.assertEqual(len(shapes), 8)

    def test_arched_windows_requires_windows(self):
        with self.assertRaises(ValueError):
            arched_windows.build({}, pen())

    def test_long_table(self):
        target = pen()
        long_table.build(
            {
                "table": [50, 300, 700, 40],
                "plates": [140, 230, 320, 395],
                "plate_y": 320,
                "cup_x": 465,
            },
            target,
        )
        shapes = [item for item in target.commands if item["command"] == "shape.create"]
        self.assertGreaterEqual(len(shapes), 8)
        names = [item["params"].get("name", "") for item in shapes]
        self.assertTrue(any("盘子" in name for name in names))
        self.assertTrue(any("酒杯" in name for name in names))

    def test_long_table_requires_table(self):
        with self.assertRaises(ValueError):
            long_table.build({}, pen())


if __name__ == "__main__":
    unittest.main()
