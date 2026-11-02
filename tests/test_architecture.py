# -*- coding: utf-8 -*-
import unittest

from photocraft_draw.commands import Pen
from photocraft_draw.components import architecture
from photocraft_draw.palette import resolve_palette


def pen(width: int = 800, height: int = 450):
    return Pen(width, height, ref_width=800, palette=resolve_palette("fresco"))


def shapes(target):
    return [item for item in target.commands if item["command"] == "shape.create"]


class CofferedCeilingTest(unittest.TestCase):
    def test_grid_commands(self):
        target = pen()
        architecture.coffered_ceiling(
            {"ceiling": [0, 0, 800, 104], "columns": 7, "rows": 4}, target
        )
        items = shapes(target)
        self.assertEqual(len(items), 13)
        self.assertEqual(items[0]["params"]["kind"], "rect")
        self.assertEqual(items[0]["params"]["fill"], resolve_palette("fresco")["muted"])

    def test_ribs_converge_to_far_edge(self):
        target = pen()
        architecture.coffered_ceiling({"ceiling": [0, 0, 800, 104]}, target)
        ribs = [item for item in shapes(target) if item["params"].get("name") == "藻井边梁"]
        self.assertEqual(len(ribs), 2)
        self.assertEqual(ribs[0]["params"]["from"], [0, 0])
        self.assertEqual(ribs[0]["params"]["to"], [232, 104])
        self.assertEqual(ribs[1]["params"]["to"], [568, 104])

    def test_vanish_sets_far_edge_width(self):
        target = pen()
        architecture.coffered_ceiling(
            {"ceiling": [0, 0, 800, 104], "vanish": [400, 208]}, target
        )
        ribs = [item for item in shapes(target) if item["params"].get("name") == "藻井边梁"]
        self.assertEqual(ribs[0]["params"]["to"], [200, 104])

    def test_scales_with_canvas(self):
        target = pen(1600, 900)
        architecture.coffered_ceiling({"ceiling": [0, 0, 800, 104]}, target)
        ribs = [item for item in shapes(target) if item["params"].get("name") == "藻井边梁"]
        self.assertEqual(ribs[0]["params"]["to"], [464, 208])

    def test_requires_ceiling(self):
        with self.assertRaises(ValueError):
            architecture.coffered_ceiling({}, pen())

    def test_rejects_flat_vanish(self):
        with self.assertRaises(ValueError):
            architecture.coffered_ceiling(
                {"ceiling": [0, 0, 800, 104], "vanish": [400, 90]}, pen()
            )


class SideDraperyTest(unittest.TestCase):
    def test_two_drapes(self):
        target = pen()
        architecture.side_drapery(
            {"draperies": [[16, 96, 74, 250], [710, 96, 74, 250]]}, target
        )
        items = shapes(target)
        self.assertEqual(len(items), 24)
        names = [item["params"].get("name", "") for item in items]
        self.assertIn("帷幔 1", names)
        self.assertIn("帷幔 2", names)
        self.assertIn("挂杆 1", names)
        self.assertEqual(names.count("帷幔褶"), 10)

    def test_requires_draperies(self):
        with self.assertRaises(ValueError):
            architecture.side_drapery({}, pen())

    def test_rejects_wrong_item(self):
        with self.assertRaises(ValueError):
            architecture.side_drapery({"draperies": [[1, 2, 3]]}, pen())


class WindowGlowTest(unittest.TestCase):
    def test_default_glow(self):
        palette = resolve_palette("fresco")
        target = pen()
        architecture.window_glow({"window": [352, 140, 96, 80]}, target)
        items = shapes(target)
        self.assertEqual(len(items), 4)
        self.assertEqual(items[0]["params"]["fill"], palette["surface"])
        self.assertEqual(items[2]["params"]["fill"], palette["accent"])
        self.assertEqual(items[3]["params"]["name"], "人物背后亮部")
        self.assertEqual(items[3]["params"]["fill"], palette["surface"])

    def test_pool_light(self):
        target = pen()
        architecture.window_glow(
            {"window": [352, 140, 96, 80], "pool": [400, 330, 150, 16]}, target
        )
        items = shapes(target)
        self.assertEqual(len(items), 5)
        self.assertEqual(items[-1]["params"]["name"], "桌面光斑")

    def test_requires_window(self):
        with self.assertRaises(ValueError):
            architecture.window_glow({}, pen())

    def test_rejects_wrong_halo(self):
        with self.assertRaises(ValueError):
            architecture.window_glow({"window": [352, 140, 96, 80], "halo": [400, 200]}, pen())


class SoftVignetteTest(unittest.TestCase):
    def test_corners_and_under_shadow(self):
        target = pen()
        architecture.soft_vignette(
            {"frame": [0, 0, 800, 450], "under_shadow": [400, 356, 300, 18]}, target
        )
        items = shapes(target)
        self.assertEqual(len(items), 14)
        names = [item["params"].get("name", "") for item in items]
        self.assertEqual(names.count("边角老化"), 12)
        self.assertEqual(names.count("桌下暗部"), 2)

    def test_corners_off(self):
        target = pen()
        architecture.soft_vignette(
            {"frame": [0, 0, 800, 450], "corners": False, "under_shadow": [400, 356, 300, 18]},
            target,
        )
        self.assertEqual(len(shapes(target)), 2)

    def test_requires_frame(self):
        with self.assertRaises(ValueError):
            architecture.soft_vignette({}, pen())

    def test_rejects_wrong_under_shadow(self):
        with self.assertRaises(ValueError):
            architecture.soft_vignette(
                {"frame": [0, 0, 800, 450], "under_shadow": [400, 356]}, pen()
            )


class ArchitectureConventionTest(unittest.TestCase):
    def test_no_layer_commands_and_budget(self):
        target = pen()
        architecture.coffered_ceiling({"ceiling": [0, 0, 800, 104]}, target)
        architecture.side_drapery({"draperies": [[16, 96, 40, 200]]}, target)
        architecture.window_glow({"window": [352, 140, 96, 80]}, target)
        architecture.soft_vignette(
            {"frame": [0, 0, 800, 450], "under_shadow": [400, 356, 300, 18]}, target
        )
        self.assertFalse([item for item in target.commands if item["command"].startswith("layer.")])
        self.assertLess(len(target.commands), 120)

    def test_no_pure_black_or_white(self):
        target = pen()
        architecture.coffered_ceiling({"ceiling": [0, 0, 800, 104]}, target)
        architecture.side_drapery({"draperies": [[16, 96, 74, 250]]}, target)
        architecture.window_glow({"window": [352, 140, 96, 80]}, target)
        architecture.soft_vignette(
            {"frame": [0, 0, 800, 450], "under_shadow": [400, 356, 300, 18]}, target
        )
        colors = set()
        for item in shapes(target):
            for value in item["params"].values():
                if isinstance(value, str) and value.startswith("#"):
                    colors.add(value.lower())
        self.assertNotIn("#000000", colors)
        self.assertNotIn("#ffffff", colors)


if __name__ == "__main__":
    unittest.main()
