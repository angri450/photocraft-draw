# -*- coding: utf-8 -*-
"""接触点分析的规则测试：不碰引擎，只测纯函数和判断标准。"""
import unittest

import numpy as np

from photocraft_draw import contact


def blank(height=100, width=100):
    return np.zeros((height, width), dtype=bool)


def fill(mask, x0, y0, x1, y1):
    mask[y0:y1, x0:x1] = True
    return mask


def hand(layer="hero", joint="hand_r", x=50, y=50, radius=6):
    return {"layer": layer, "figure": 1, "label": layer,
            "joint": joint, "x": float(x), "y": float(y),
            "radius": float(radius), "hits": []}


class BlobTest(unittest.TestCase):
    def test_splits_two_areas(self):
        mask = blank()
        fill(mask, 10, 10, 20, 20)
        fill(mask, 60, 60, 70, 70)
        blobs = contact._blobs(mask, min_area=4)
        self.assertEqual(len(blobs), 2)
        self.assertEqual(blobs[0]["area"], 100)
        self.assertAlmostEqual(blobs[0]["x"], 14.5, places=1)

    def test_drops_small_areas(self):
        mask = blank()
        fill(mask, 10, 10, 20, 20)
        fill(mask, 50, 50, 52, 52)
        blobs = contact._blobs(mask, min_area=10)
        self.assertEqual(len(blobs), 1)

    def test_empty_mask(self):
        self.assertEqual(contact._blobs(blank()), [])


class PoseTableTest(unittest.TestCase):
    def test_named_pose(self):
        table = contact._pose_table("stand")
        self.assertIn("hand_r", table)

    def test_bad_name_raises(self):
        with self.assertRaises(ValueError):
            contact._pose_table("dance")

    def test_missing_joint_raises(self):
        with self.assertRaises(ValueError):
            contact._pose_table({"hip": [0, 0]})

    def test_dict_needs_pairs(self):
        table = contact._pose_table({name: [0, 0] for name in contact.JOINT_NAMES})
        self.assertEqual(table["hip"], (0.0, 0.0))


class PlanJointTest(unittest.TestCase):
    def plan(self, rigs):
        return {"ref_width": 100, "layers": [{"name": "hero", "components": rigs}]}

    def rig(self, root):
        return {"component": "figure_rig",
                "params": {"root": root, "height": 100,
                           "pose": {name: [0, 0] for name in contact.JOINT_NAMES}}}

    def test_scales_to_canvas(self):
        joints = contact._plan_joints(self.plan([self.rig([50, 50])]), 200)
        self.assertAlmostEqual(joints[0]["x"], 100.0, places=3)

    def test_numbers_figures_in_one_layer(self):
        joints = contact._plan_joints(
            self.plan([self.rig([10, 10]), self.rig([60, 60])]), 100)
        labels = {joint["label"] for joint in joints}
        self.assertEqual(labels, {"hero第1个", "hero第2个"})

    def test_single_figure_keeps_layer_name(self):
        joints = contact._plan_joints(self.plan([self.rig([10, 10])]), 100)
        self.assertEqual(joints[0]["label"], "hero")


class JointHitTest(unittest.TestCase):
    def test_sides_and_coverage(self):
        order = ["blade", "hero", "ground"]
        masks = {
            "blade": fill(blank(), 40, 40, 60, 60),
            "hero": fill(blank(), 45, 45, 55, 55),
            "ground": fill(blank(), 30, 30, 70, 70),
        }
        joints = contact._joint_hits([hand()], masks, order)
        sides = {hit["part"]: hit["side"] for hit in joints[0]["hits"]}
        self.assertEqual(sides["blade"], "front")
        self.assertEqual(sides["hero"], "own")
        self.assertEqual(sides["ground"], "back")

    def test_half_covered_joint(self):
        order = ["blade", "hero"]
        masks = {
            "blade": fill(blank(), 50, 40, 70, 60),
            "hero": fill(blank(), 44, 44, 56, 56),
        }
        joints = contact._joint_hits([hand()], masks, order)
        blade = [hit for hit in joints[0]["hits"] if hit["part"] == "blade"][0]
        self.assertAlmostEqual(blade["coverage"], 0.5, delta=0.1)


class HazardTest(unittest.TestCase):
    def build(self, order, masks, joints, contacts=None, layers=None):
        joints = contact._joint_hits(joints, masks, order)
        return contact._hazards(joints, masks, contacts or [], layers or order, 100 * 100)

    def kinds(self, notes):
        return [note["kind"] for note in notes]

    def test_hand_under_two_front_parts(self):
        order = ["blade", "rod", "hero"]
        masks = {
            "blade": fill(blank(), 40, 40, 60, 60),
            "rod": fill(blank(), 40, 40, 60, 60),
            "hero": fill(blank(), 44, 44, 56, 56),
        }
        notes = self.build(order, masks, [hand()])
        self.assertIn("夹手", self.kinds(notes))

    def test_hand_under_one_front_part_is_quiet(self):
        order = ["blade", "hero"]
        masks = {
            "blade": fill(blank(), 40, 40, 60, 60),
            "hero": fill(blank(), 44, 44, 56, 56),
        }
        notes = self.build(order, masks, [hand()])
        self.assertNotIn("夹手", self.kinds(notes))

    def test_hand_shape_layer_does_not_count(self):
        order = ["blade", "hero gripping hand", "hero"]
        masks = {
            "blade": fill(blank(), 40, 40, 60, 60),
            "hero gripping hand": fill(blank(), 40, 40, 60, 60),
            "hero": fill(blank(), 44, 44, 56, 56),
        }
        notes = self.build(order, masks, [hand()])
        self.assertNotIn("夹手", self.kinds(notes))

    def test_two_hands_on_same_front_part(self):
        order = ["rod", "hero"]
        masks = {
            "rod": fill(blank(), 0, 44, 100, 56),
            "hero": fill(blank(), 24, 44, 56, 56),
        }
        joints = [hand(joint="hand_l", x=30, y=50), hand(joint="hand_r", x=50, y=50)]
        notes = self.build(order, masks, joints)
        self.assertIn("疑似穿手", self.kinds(notes))

    def test_two_hands_on_part_behind_character_is_quiet(self):
        order = ["hero", "rod"]
        masks = {
            "rod": fill(blank(), 0, 44, 100, 56),
            "hero": fill(blank(), 24, 44, 56, 56),
        }
        joints = [hand(joint="hand_l", x=30, y=50), hand(joint="hand_r", x=50, y=50)]
        notes = self.build(order, masks, joints)
        self.assertNotIn("疑似穿手", self.kinds(notes))

    def test_two_hands_far_apart_is_quiet(self):
        order = ["rod", "hero"]
        masks = {
            "rod": fill(blank(), 0, 44, 100, 56),
            "hero": fill(blank(), 4, 44, 96, 56),
        }
        joints = [hand(joint="hand_l", x=10, y=50), hand(joint="hand_r", x=90, y=50)]
        notes = self.build(order, masks, joints)
        self.assertNotIn("疑似穿手", self.kinds(notes))

    def test_three_parts_in_one_place(self):
        order = ["a", "b", "c", "ground"]
        masks = {"a": fill(blank(), 40, 40, 60, 60),
                 "b": fill(blank(), 40, 40, 60, 60),
                 "c": fill(blank(), 40, 40, 60, 60),
                 "ground": fill(blank(), 0, 0, 100, 100)}
        spot = {"number": 1, "x": 50, "y": 50, "area": 400, "bbox": [40, 40, 20, 20]}
        contacts = [
            {"upper": "a", "lower": "b", "spots": [spot]},
            {"upper": "b", "lower": "c", "spots": [dict(spot, number=2)]},
            {"upper": "a", "lower": "c", "spots": [dict(spot, number=3)]},
        ]
        notes = contact._hazards([], {}, contacts, order, 100 * 100)
        self.assertIn("挤在一处", self.kinds(notes))

    def test_backdrop_does_not_count_as_crowd(self):
        order = ["a", "b", "ground"]
        masks = {"a": fill(blank(), 40, 40, 60, 60),
                 "b": fill(blank(), 40, 40, 60, 60),
                 "ground": fill(blank(), 0, 0, 100, 100)}
        spot = {"number": 1, "x": 50, "y": 50, "area": 400, "bbox": [40, 40, 20, 20]}
        contacts = [
            {"upper": "a", "lower": "b", "spots": [spot]},
            {"upper": "a", "lower": "ground", "spots": [dict(spot, number=2)]},
            {"upper": "b", "lower": "ground", "spots": [dict(spot, number=3)]},
        ]
        notes = contact._hazards([], {}, contacts, order, 100 * 100)
        self.assertNotIn("挤在一处", self.kinds(notes))


class BackgroundTest(unittest.TestCase):
    def test_full_canvas_layer_is_background(self):
        masks = {"底色": np.ones((100, 100), dtype=bool),
                 "hero": fill(blank(), 10, 10, 20, 20)}
        found = contact._background_layers(masks, 100, 100)
        self.assertEqual(found, {"底色"})


class PublicTest(unittest.TestCase):
    def test_strips_internal_keys(self):
        data = {"canvas": [10, 10], "_masks": {}, "contacts": []}
        self.assertEqual(sorted(contact.public(data)), ["canvas", "contacts"])


if __name__ == "__main__":
    unittest.main()
