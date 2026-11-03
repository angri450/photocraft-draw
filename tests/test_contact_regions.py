

# -*- coding: utf-8 -*-
"""头部和脖子区域的判断测试：不碰引擎，只测纯函数。"""
import unittest

import numpy as np

from photocraft_draw import contact


def blank(height=100, width=100):
    return np.zeros((height, width), dtype=bool)


def fill(mask, x0, y0, x1, y1):
    mask[y0:y1, x0:x1] = True
    return mask


class RegionTest(unittest.TestCase):
    """头部和脖子区域的判断：覆盖比例和断开。"""

    def region(self, x=50, y=50, rx=20, ry=20):
        return {"layer": "hero", "label": "hero", "part": "head",
                "x": x, "y": y, "rx": rx, "ry": ry}

    def test_empty_mask_covers_nothing(self):
        hit = contact._region_hit(self.region(), blank())
        self.assertEqual(hit["coverage"], 0.0)
        self.assertFalse(hit["cut"])

    def test_band_across_middle_cuts_region(self):
        mask = fill(blank(), 0, 45, 100, 55)
        hit = contact._region_hit(self.region(), mask)
        self.assertTrue(hit["cut"])

    def test_edge_bite_is_not_a_cut(self):
        mask = fill(blank(), 0, 30, 100, 38)
        hit = contact._region_hit(self.region(), mask)
        self.assertFalse(hit["cut"])

    def test_full_cover_is_not_a_cut(self):
        mask = fill(blank(), 0, 0, 100, 100)
        hit = contact._region_hit(self.region(), mask)
        self.assertAlmostEqual(hit["coverage"], 1.0, delta=0.01)
        self.assertFalse(hit["cut"])


class PlanRegionTest(unittest.TestCase):
    """保护区从方案里反算：头部椭圆和脖子圆盘。"""

    def plan(self):
        rig = {"component": "figure_rig",
               "params": {"root": [50, 50], "height": 100,
                          "pose": {name: [0, 0] for name in contact.JOINT_NAMES}}}
        return {"ref_width": 100,
                "layers": [{"name": "hero", "components": [rig]}]}

    def test_gives_head_and_neck(self):
        regions = contact._plan_regions(self.plan(), 100)
        parts = {region["part"] for region in regions}
        self.assertEqual(parts, {"head", "neck"})

    def test_head_radius_follows_height(self):
        regions = contact._plan_regions(self.plan(), 100)
        head = [r for r in regions if r["part"] == "head"][0]
        self.assertAlmostEqual(head["ry"], 0.075 * 100, places=3)
        self.assertAlmostEqual(head["rx"], 0.075 * 100 * 0.86, places=3)

    def test_neck_radius_follows_height(self):
        regions = contact._plan_regions(self.plan(), 100)
        neck = [r for r in regions if r["part"] == "neck"][0]
        self.assertAlmostEqual(neck["rx"], 0.045 * 100, places=3)


class PlanPropsTest(unittest.TestCase):
    """每层的道具名字，以及道具排在身体后面没有。"""

    def rig(self):
        return {"component": "figure_rig", "params": {}}

    def prop(self, name):
        return {"component": "custom_shape", "params": {"name": name}}

    def test_prop_after_body_is_in_front(self):
        plan = {"layers": [{"name": "hero",
                           "components": [self.rig(), self.prop("长戟")]}]}
        props = contact._plan_props(plan)
        self.assertEqual(props["hero"]["names"], {"长戟"})
        self.assertTrue(props["hero"]["after_body"])

    def test_prop_before_body_is_behind(self):
        plan = {"layers": [{"name": "hero",
                           "components": [self.prop("长戟"), self.rig()]}]}
        props = contact._plan_props(plan)
        self.assertFalse(props["hero"]["after_body"])


class BoundsOverlapTest(unittest.TestCase):
    def test_overlapping_bounds(self):
        region = {"x": 50, "y": 50, "rx": 10, "ry": 10}
        self.assertTrue(contact._bounds_overlap([40, 40, 20, 20], region))

    def test_far_bounds(self):
        region = {"x": 50, "y": 50, "rx": 10, "ry": 10}
        self.assertFalse(contact._bounds_overlap([80, 80, 20, 20], region))

    def test_missing_bounds(self):
        region = {"x": 50, "y": 50, "rx": 10, "ry": 10}
        self.assertFalse(contact._bounds_overlap(None, region))