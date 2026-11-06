# -*- coding: utf-8 -*-
"""整合验收：组件目录、示例方案和整图合成的一致性。"""
import json
import unittest
from pathlib import Path

from photocraft_draw.commands import Pen
from photocraft_draw.palette import resolve_palette
from photocraft_draw.plan import compose_plan, validate_plan
from photocraft_draw.registry import REGISTRY

PLAN_PATH = Path(__file__).resolve().parents[1] / "plans" / "supper-demo.json"

NEW_COMPONENTS = {
    "seated_figure",
    "leaning_figure",
    "figure_head",
    "figure_hands",
    "figure_row",
    "dinner_plate",
    "bread_loaf",
    "wine_goblet",
    "table_cloth_folds",
    "coffered_ceiling",
    "side_drapery",
    "window_glow",
    "soft_vignette",
}

# figure_row 是批量排人的便利组件，示例里逐人摆姿态，不用它。
DEMO_COMPONENTS = NEW_COMPONENTS - {"figure_row"}


def demo_plan():
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def component_ids(plan):
    return [item["component"] for item in _components(plan)]


def _components(plan):
    for item in plan["layers"]:
        for component in item["components"]:
            yield component


def count(plan, key):
    return component_ids(plan).count(key)


class RegistryTest(unittest.TestCase):
    def test_new_components_registered(self):
        missing = sorted(NEW_COMPONENTS - set(REGISTRY))
        self.assertEqual(missing, [], f"组件目录还缺 {missing}")

    def test_entries_are_documented(self):
        for key, component in REGISTRY.items():
            self.assertEqual(component.id, key)
            self.assertTrue(component.name.strip(), f"{key} 缺中文名")
            self.assertTrue(component.description.strip(), f"{key} 缺说明")
            self.assertTrue(component.params, f"{key} 缺参数说明")
            self.assertTrue(callable(component.build), f"{key} 的 build 不可调用")

    def test_required_params_are_marked(self):
        for key, component in REGISTRY.items():
            texts = list(component.params.values())
            if any("必填" in text for text in texts):
                continue
            # 全部可选也是合法情况：build 自己会对缺参报错。
            # 这类组件至少要有一条参数说明写了默认值，能看出是可选的。
            defaults = [text for text in texts if "默认" in text]
            self.assertTrue(
                defaults,
                f"{key} 的参数说明既没有必填项，也没有任何默认值说明",
            )

    def test_registry_is_searchable(self):
        haystack = " ".join(
            f"{item.id} {item.name} {item.description}" for item in REGISTRY.values()
        )
        for word in ("藻井", "帷幔", "窗光", "手", "盘"):
            self.assertIn(word, haystack)


class DemoPlanTest(unittest.TestCase):
    def test_plan_validates(self):
        self.assertEqual(validate_plan(demo_plan()), [])

    def test_layer_count(self):
        self.assertEqual(len(demo_plan()["layers"]), 10)

    def test_every_new_component_is_used(self):
        used = set(component_ids(demo_plan()))
        self.assertEqual(sorted(DEMO_COMPONENTS - used), [])

    def test_canvas_and_scale(self):
        commands, meta = compose_plan(demo_plan())
        self.assertEqual((meta["width"], meta["height"]), (1600, 900))
        shapes = [item for item in commands if item["command"] == "shape.create"]
        self.assertEqual(shapes[0]["params"]["rect"], [0, 0, 1600, 900])
        self.assertGreater(meta["commands"], 300)

    def test_thirteen_figures(self):
        plan = demo_plan()
        self.assertEqual(count(plan, "seated_figure"), 12)
        self.assertEqual(count(plan, "leaning_figure"), 1)
        self.assertEqual(count(plan, "figure_head"), 13)
        self.assertEqual(count(plan, "figure_hands"), 2)

    def test_table_is_set_for_thirteen(self):
        plan = demo_plan()
        self.assertEqual(count(plan, "dinner_plate"), 8)
        self.assertEqual(count(plan, "bread_loaf"), 6)
        self.assertEqual(count(plan, "wine_goblet"), 5)
        self.assertEqual(count(plan, "table_cloth_folds"), 1)

    def test_paint_order(self):
        names = [item["name"] for item in demo_plan()["layers"]]
        order = {name: index for index, name in enumerate(names)}
        self.assertLess(order["窗光"], order["拱形窗户"])
        self.assertLess(order["拱形窗户"], order["人物躯干"])
        self.assertLess(order["人物躯干"], order["人物头部"])
        self.assertLess(order["人物头部"], order["长条餐桌"])
        self.assertLess(order["长条餐桌"], order["桌面器物"])
        self.assertLess(order["桌面器物"], order["手部"])
        self.assertLess(order["手部"], order["边缘老化"])

    def test_no_pure_black_or_white(self):
        commands, _ = compose_plan(demo_plan())
        bad = []
        for command in commands:
            params = command.get("params") or {}
            for key, value in params.items():
                text = value if isinstance(value, str) else None
                if isinstance(value, dict):
                    text = value.get("color")
                if isinstance(text, str) and text.lower() in ("#000000", "#ffffff"):
                    bad.append((command["command"], key, params.get("name"), text))
        self.assertEqual(bad, [], f"纯黑纯白出现在 {bad}")

    def test_caption_is_text_layer(self):
        commands, _ = compose_plan(demo_plan())
        texts = [item for item in commands if item["command"] == "type.create"]
        self.assertEqual(len(texts), 1)
        self.assertIn("CENACOLO", texts[0]["params"]["text"])

    def test_each_component_stays_within_budget(self):
        palette = resolve_palette("fresco")
        for item in _components(demo_plan()):
            component = REGISTRY[item["component"]]
            target = Pen(800, 450, ref_width=800, palette=palette)
            component.build(item.get("params") or {}, target)
            self.assertLess(
                len(target.commands), 120,
                f"{component.id} 一次调用超过 120 条绘制指令",
            )
            layers = [cmd for cmd in target.commands if cmd["command"].startswith("layer.")]
            self.assertEqual(layers, [], f"{component.id} 自己建了图层")


if __name__ == "__main__":
    unittest.main()
