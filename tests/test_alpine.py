# -*- coding: utf-8 -*-
"""高山场景组件的规则测试。"""
import unittest

from photocraft_draw.commands import Pen
from photocraft_draw.components import alpine
from photocraft_draw.palette import resolve_palette


def pen():
    return Pen(800, 450, ref_width=800, palette=resolve_palette("alpine"))


def names(target):
    return [item["params"].get("name", "") for item in target.commands]


class SkyTest(unittest.TestCase):
    def test_bands_cover_area(self):
        target = pen()
        alpine.build_alpine_sky({"area": [0, 0, 800, 300], "bands": 10}, target)
        self.assertEqual(len(target.commands), 10)

    def test_bands_top_to_bottom(self):
        target = pen()
        alpine.build_alpine_sky({"area": [0, 0, 800, 300], "bands": 6}, target)
        tops = [item["params"]["rect"][1] for item in target.commands]
        self.assertEqual(tops, sorted(tops))

    def test_bands_gradient_is_smooth(self):
        target = pen()
        alpine.build_alpine_sky({"area": [0, 0, 800, 300], "bands": 6}, target)
        fills = [item["params"]["fill"] for item in target.commands]
        self.assertEqual(len(set(fills)), len(fills))

    def test_too_many_bands_raises(self):
        with self.assertRaises(ValueError):
            alpine.build_alpine_sky({"area": [0, 0, 800, 300], "bands": 30}, pen())

    def test_clouds_add_shapes(self):
        plain = pen()
        alpine.build_alpine_sky({"area": [0, 0, 800, 300], "bands": 6}, plain)
        cloudy = pen()
        alpine.build_alpine_sky({"area": [0, 0, 800, 300], "bands": 6,
                                 "clouds": [[200, 90, 80, 20]]}, cloudy)
        self.assertGreater(len(cloudy.commands), len(plain.commands))

    def test_missing_area_raises(self):
        with self.assertRaises(ValueError):
            alpine.build_alpine_sky({"bands": 8}, pen())


class PeaksTest(unittest.TestCase):
    def test_peak_draws_body_and_snow(self):
        target = pen()
        alpine.build_alpine_peaks({"peaks": [[200, 320, 120, 180]], "snow": True}, target)
        self.assertTrue(any("雪" in name for name in names(target)))
        self.assertEqual(len([n for n in names(target) if "山 1" in n]), 5)

    def test_snow_off_by_default(self):
        target = pen()
        alpine.build_alpine_peaks({"peaks": [[200, 320, 120, 180]]}, target)
        self.assertFalse(any("雪" in name for name in names(target)))

    def test_snow_off_removes_snow(self):
        bare = pen()
        alpine.build_alpine_peaks({"peaks": [[200, 320, 120, 180]], "snow": False}, bare)
        self.assertFalse(any("雪" in name for name in names(bare)))

    def test_body_widths_shrink_upward(self):
        target = pen()
        alpine.build_alpine_peaks({"peaks": [[200, 320, 120, 180]], "snow": False}, target)
        widths = [item["params"]["rect"][2] for item in target.commands
                  if item["params"].get("kind") == "ellipse"]
        self.assertEqual(widths, sorted(widths, reverse=True))

    def test_empty_peaks_raises(self):
        with self.assertRaises(ValueError):
            alpine.build_alpine_peaks({"peaks": []}, pen())

    def test_missing_peaks_raises(self):
        with self.assertRaises(ValueError):
            alpine.build_alpine_peaks({}, pen())


class GroundTest(unittest.TestCase):
    def test_ground_base(self):
        target = pen()
        alpine.build_rocky_ground({"area": [0, 300, 800, 150]}, target)
        self.assertGreaterEqual(len(target.commands), 2)

    def test_rocks_added(self):
        target = pen()
        alpine.build_rocky_ground({"area": [0, 300, 800, 150],
                                   "rocks": [[120, 380, 60, 22], [640, 400, 80, 26]]}, target)
        self.assertEqual(sum(1 for name in names(target) if name.startswith("石头")), 2)

    def test_bad_tone_raises(self):
        with self.assertRaises(ValueError):
            alpine.build_rocky_ground({"area": [0, 300, 800, 150], "tone": "light"}, pen())

    def test_missing_area_raises(self):
        with self.assertRaises(ValueError):
            alpine.build_rocky_ground({}, pen())


class PaletteTest(unittest.TestCase):
    def test_no_pure_black_or_white(self):
        target = pen()
        alpine.build_alpine_sky({"area": [0, 0, 800, 300], "bands": 8,
                                 "clouds": [[200, 90, 80, 20]]}, target)
        alpine.build_alpine_peaks({"peaks": [[200, 320, 120, 180], [500, 320, 160, 220]]}, target)
        alpine.build_rocky_ground({"area": [0, 300, 800, 150],
                                   "rocks": [[120, 380, 60, 22]]}, target)
        for item in target.commands:
            fill = str(item["params"].get("fill", "")).upper()
            self.assertNotIn(fill, ("#000000", "#FFFFFF", "BLACK", "WHITE"))

    def test_scene_within_budget(self):
        target = pen()
        alpine.build_alpine_sky({"area": [0, 0, 800, 310], "bands": 14,
                                 "clouds": [[160, 80, 70, 18], [600, 110, 90, 22]]}, target)
        before = len(target.commands)
        alpine.build_alpine_peaks({"peaks": [[120, 330, 140, 200]]}, target)
        single = len(target.commands) - before
        self.assertLess(single, 12)


if __name__ == "__main__":
    unittest.main()
