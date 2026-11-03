# -*- coding: utf-8 -*-
"""depth 字段测试：层序由 depth 决定，方案声明和成品层序要能对照。"""
import unittest

from photocraft_draw.depth import declared_depths, depth_conflicts, depth_values
from photocraft_draw.plan import compose_plan, ordered_layers, validate_plan


def layer(name, depth=None):
    item = {"name": name, "components": [
        {"component": "indoor_backdrop",
         "params": {"wall": [0, 0, 800, 450]}}]}
    if depth is not None:
        item["depth"] = depth
    return item


def plan_with(layers):
    return {"canvas": [800, 450], "ref_width": 800, "layers": layers}


class OrderedLayersTest(unittest.TestCase):
    """层序由 depth 决定：depth 大的更远，先画。"""

    def test_no_depth_keeps_plan_order(self):
        layers = [layer("远"), layer("近")]
        self.assertEqual([item["name"] for item in ordered_layers(plan_with(layers))],
                         ["远", "近"])

    def test_depth_sorts_far_to_near(self):
        layers = [layer("近", 0), layer("远", 3)]
        result = [item["name"] for item in ordered_layers(plan_with(layers))]
        self.assertEqual(result, ["远", "近"])

    def test_plan_order_does_not_matter(self):
        first = plan_with([layer("远", 3), layer("近", 0)])
        second = plan_with([layer("近", 0), layer("远", 3)])
        self.assertEqual([item["name"] for item in ordered_layers(first)],
                         [item["name"] for item in ordered_layers(second)])

    def test_equal_depth_keeps_plan_order(self):
        layers = [layer("甲", 1), layer("乙", 1)]
        result = [item["name"] for item in ordered_layers(plan_with(layers))]
        self.assertEqual(result, ["甲", "乙"])


class DepthValidationTest(unittest.TestCase):
    """depth 的写法校验。"""

    def test_depth_must_be_number(self):
        plan = plan_with([layer("甲", "远"), layer("乙", 1)])
        errors = validate_plan(plan)
        self.assertTrue(any("depth" in item for item in errors))

    def test_all_or_nothing(self):
        plan = plan_with([layer("甲", 1), layer("乙")])
        errors = validate_plan(plan)
        self.assertTrue(any("depth" in item for item in errors))

    def test_depth_must_be_finite(self):
        plan = plan_with([layer("甲", float("inf")), layer("乙", 1)])
        errors = validate_plan(plan)
        self.assertTrue(any("有限" in item for item in errors))

    def test_valid_depth_passes(self):
        plan = plan_with([layer("甲", 0), layer("乙", 2)])
        self.assertEqual(validate_plan(plan), [])


class ComposeWithDepthTest(unittest.TestCase):
    """depth 决定绘制顺序。"""

    def stage_names(self, plan):
        commands, _ = compose_plan(plan)
        names = [item["params"]["name"] for item in commands
                 if item["command"] == "layer.new.group"]
        return [name for name in names if name in ("远", "近")]

    def test_depth_drives_draw_order(self):
        plan = plan_with([layer("近", 0), layer("远", 3)])
        self.assertEqual(self.stage_names(plan), ["远", "近"])

    def test_same_plan_reversed_gives_same_commands(self):
        first = plan_with([layer("远", 3), layer("近", 0)])
        second = plan_with([layer("近", 0), layer("远", 3)])
        commands_a, _ = compose_plan(first)
        commands_b, _ = compose_plan(second)
        self.assertEqual(commands_a, commands_b)


class DepthValuesTest(unittest.TestCase):
    """深度取值和冲突判断。"""

    def test_declared_depths_reads_plan(self):
        plan = plan_with([layer("甲", 2), layer("乙")])
        self.assertEqual(declared_depths(plan), {"甲": 2.0})

    def test_declared_value_used(self):
        values = depth_values(["甲", "乙"], {"甲": 0.0, "乙": 4.0}, 1.0)
        self.assertEqual(values, [0.0, 4.0])

    def test_unit_scales_declared_value(self):
        values = depth_values(["甲"], {"甲": 3.0}, 2.0)
        self.assertEqual(values, [6.0])

    def test_undeclared_layer_interpolates(self):
        values = depth_values(["甲", "底色", "乙"], {"甲": 0.0, "乙": 4.0}, 1.0)
        self.assertEqual(values, [0.0, 2.0, 4.0])

    def test_undeclared_at_front_goes_nearer(self):
        values = depth_values(["文字层", "甲"], {"甲": 2.0}, 1.0)
        self.assertEqual(values, [1.0, 2.0])

    def test_conflict_when_front_is_declared_farther(self):
        conflicts = depth_conflicts(["甲", "乙"], {"甲": 5.0, "乙": 1.0})
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["front"], "甲")
        self.assertEqual(conflicts[0]["back"], "乙")

    def test_no_conflict_when_order_matches(self):
        conflicts = depth_conflicts(["甲", "乙"], {"甲": 1.0, "乙": 5.0})
        self.assertEqual(conflicts, [])


if __name__ == "__main__":
    unittest.main()
