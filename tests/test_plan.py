# -*- coding: utf-8 -*-
import unittest

from photocraft_draw.plan import compose_plan, validate_plan


def base_plan():
    return {
        "canvas": [800, 450],
        "ref_width": 800,
        "background": "bg",
        "components": [
            {"component": "indoor_backdrop", "params": {"wall": [0, 0, 800, 450]}}
        ],
    }


class PlanTest(unittest.TestCase):
    def test_valid_plan(self):
        self.assertEqual(validate_plan(base_plan()), [])
        commands, meta = compose_plan(base_plan())
        self.assertGreater(len(commands), 0)
        self.assertEqual(meta["components"], 1)

    def test_bad_canvas(self):
        plan = base_plan()
        plan["canvas"] = [0, 450]
        errors = validate_plan(plan)
        self.assertTrue(any("canvas" in item for item in errors))

    def test_empty_components(self):
        plan = base_plan()
        plan["components"] = []
        errors = validate_plan(plan)
        self.assertTrue(any("components" in item for item in errors))

    def test_unknown_component(self):
        plan = base_plan()
        plan["components"] = [{"component": "no_such", "params": {}}]
        errors = validate_plan(plan)
        self.assertTrue(any("no_such" in item for item in errors))

    def test_bad_params(self):
        plan = base_plan()
        plan["components"] = [{"component": "indoor_backdrop", "params": []}]
        errors = validate_plan(plan)
        self.assertTrue(any("params" in item for item in errors))

    def test_background_is_first(self):
        commands, _ = compose_plan(base_plan())
        first = commands[0]
        self.assertEqual(first["command"], "shape.create")
        self.assertEqual(first["params"]["kind"], "rect")

    def test_caption_adds_text(self):
        plan = base_plan()
        plan["caption"] = "TEST 0.1"
        commands, _ = compose_plan(plan)
        self.assertTrue(any(item["command"] == "type.create" for item in commands))

    def test_canvas_scaling(self):
        plan = base_plan()
        plan["canvas"] = [1600, 900]
        commands, _ = compose_plan(plan)
        first_rect = commands[0]["params"]["rect"]
        self.assertEqual(first_rect, [0, 0, 1600, 900])


if __name__ == "__main__":
    unittest.main()
