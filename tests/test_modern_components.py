# -*- coding: utf-8 -*-
"""现代题材组件：形状、参数和注册。"""
import unittest

from photocraft_draw.commands import Pen
from photocraft_draw.components import modern
from photocraft_draw.palette import resolve_palette
from photocraft_draw.registry import get_component


def pen():
    return Pen(900, 1200, ref_width=900, palette=resolve_palette("fresco"))


def names(target):
    return [item["params"].get("name", "") for item in target.commands
            if item["command"] == "shape.create"]


def fills(target):
    return [item["params"].get("fill") for item in target.commands
            if item["command"] == "shape.create"]


class ModernComponentTest(unittest.TestCase):
    def test_bottle_draws_all_parts(self):
        target = pen()
        modern.build_bottle({"base": [450, 900], "height": 400}, target)
        text = " ".join(names(target))
        for part in ("瓶身", "高光", "茶液", "标签", "圆标", "瓶盖"):
            self.assertIn(part, text)

    def test_bottle_colors_dict_wins(self):
        target = pen()
        modern.build_bottle({"base": [450, 900], "height": 400,
                             "body": "#111111",
                             "colors": {"body": "#B4694F"}}, target)
        self.assertIn("#B4694F", fills(target))
        self.assertNotIn("#111111", fills(target))

    def test_apple_bite_adds_notch(self):
        target = pen()
        modern.build_apple({"center": [450, 600], "radius": 120, "bite": True}, target)
        self.assertTrue(any("缺口" in name for name in names(target)))

    def test_apple_without_bite_has_no_notch(self):
        target = pen()
        modern.build_apple({"center": [450, 600], "radius": 120}, target)
        self.assertFalse(any("缺口" in name for name in names(target)))

    def test_tree_fruit_and_blossom(self):
        target = pen()
        modern.build_apple_tree({"root": [300, 900], "fruit": True}, target)
        self.assertTrue(any("果子" in name for name in names(target)))
        other = pen()
        modern.build_apple_tree({"root": [300, 900], "blossom": True}, other)
        self.assertTrue(any("花" in name for name in names(other)))
        coloured = pen()
        modern.build_apple_tree({"root": [300, 900], "fruit": True,
                                 "colors": {"fruit_color": "#123456"}}, coloured)
        self.assertIn("#123456", fills(coloured))

    def test_truck_has_two_wheels(self):
        target = pen()
        modern.build_truck({"origin": [95, 565]}, target)
        text = " ".join(names(target))
        self.assertIn("左轮", text)
        self.assertIn("右轮", text)

    def test_display_stand_apples(self):
        target = pen()
        modern.build_display_stand({"frame": [110, 760, 680, 280]}, target)
        self.assertTrue(any("果堆" in name for name in names(target)))
        other = pen()
        modern.build_display_stand({"frame": [110, 760, 680, 280],
                                    "apples": False}, other)
        self.assertFalse(any("果堆" in name for name in names(other)))

    def test_hand_has_palm_and_fingers(self):
        target = pen()
        modern.build_holding_hand({"center": [600, 900]}, target)
        text = " ".join(names(target))
        self.assertIn("手掌", text)
        self.assertIn("手指", text)

    def test_missing_required_params_raise(self):
        for build in (modern.build_bottle, modern.build_apple,
                      modern.build_apple_tree, modern.build_truck,
                      modern.build_display_stand, modern.build_holding_hand):
            with self.assertRaises(ValueError):
                build({}, pen())

    def test_registry_exposes_new_components(self):
        for key in ("bottle", "apple", "apple_tree", "truck",
                    "display_stand", "holding_hand"):
            self.assertEqual(get_component(key).id, key)


if __name__ == "__main__":
    unittest.main()
