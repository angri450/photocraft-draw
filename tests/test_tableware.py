# -*- coding: utf-8 -*-
import unittest

from photocraft_draw.commands import Pen
from photocraft_draw.components import tableware
from photocraft_draw.palette import resolve_palette


def pen():
    return Pen(800, 450, ref_width=800, palette=resolve_palette("fresco"))


def shapes(target):
    return [item for item in target.commands if item["command"] == "shape.create"]


def names(target):
    return [item["params"].get("name", "") for item in target.commands]


def colors(target):
    for item in target.commands:
        params = item["params"]
        for key in ("fill", "color"):
            value = params.get(key)
            if isinstance(value, str):
                yield value
        stroke = params.get("stroke")
        if isinstance(stroke, dict) and isinstance(stroke.get("color"), str):
            yield stroke["color"]


class DinnerPlateTest(unittest.TestCase):
    def test_plate(self):
        target = pen()
        tableware.build_dinner_plate({"center": [120, 330], "size": 26}, target)
        self.assertEqual(len(shapes(target)), 3)
        self.assertEqual(names(target), ["盘影", "盘沿", "盘面"])

    def test_plate_without_shadow(self):
        target = pen()
        tableware.build_dinner_plate({"center": [120, 330], "shadow": False}, target)
        self.assertEqual(len(shapes(target)), 2)
        self.assertNotIn("盘影", names(target))

    def test_plate_requires_center(self):
        with self.assertRaises(ValueError):
            tableware.build_dinner_plate({}, pen())

    def test_plate_rejects_bad_center(self):
        with self.assertRaises(ValueError):
            tableware.build_dinner_plate({"center": [120]}, pen())
        with self.assertRaises(ValueError):
            tableware.build_dinner_plate({"center": ["120", 330]}, pen())

    def test_plate_rejects_bad_size(self):
        with self.assertRaises(ValueError):
            tableware.build_dinner_plate({"center": [120, 330], "size": 0}, pen())


class BreadLoafTest(unittest.TestCase):
    def test_bread(self):
        target = pen()
        tableware.build_bread_loaf({"center": [160, 322], "size": 14}, target)
        self.assertEqual(len(shapes(target)), 4)
        self.assertEqual(names(target), ["面包影", "面包", "面包顶", "面包割口"])

    def test_bread_cut(self):
        target = pen()
        tableware.build_bread_loaf({"center": [160, 322], "size": 14, "cut": True}, target)
        self.assertEqual(len(shapes(target)), 6)
        self.assertIn("面包切面", names(target))
        self.assertEqual(names(target).count("面包割口"), 2)

    def test_bread_requires_center(self):
        with self.assertRaises(ValueError):
            tableware.build_bread_loaf({}, pen())

    def test_bread_rejects_bad_size(self):
        with self.assertRaises(ValueError):
            tableware.build_bread_loaf({"center": [160, 322], "size": -4}, pen())


class WineGobletTest(unittest.TestCase):
    def test_goblet(self):
        target = pen()
        tableware.build_wine_goblet({"center": [150, 332], "height": 22}, target)
        self.assertEqual(len(shapes(target)), 7)
        self.assertEqual(names(target), ["杯影", "杯脚", "杯颈", "杯身", "杯光", "杯口", "酒"])

    def test_goblet_plain(self):
        target = pen()
        tableware.build_wine_goblet(
            {"center": [150, 332], "height": 22, "wine": False, "glint": False}, target
        )
        self.assertEqual(len(shapes(target)), 5)
        self.assertNotIn("酒", names(target))
        self.assertNotIn("杯光", names(target))

    def test_goblet_requires_center(self):
        with self.assertRaises(ValueError):
            tableware.build_wine_goblet({}, pen())

    def test_goblet_rejects_bad_height(self):
        with self.assertRaises(ValueError):
            tableware.build_wine_goblet({"center": [150, 332], "height": 0}, pen())


class TableClothFoldsTest(unittest.TestCase):
    def test_cloth_folds(self):
        target = pen()
        tableware.build_table_cloth_folds({"area": [40, 340, 720, 38], "folds": 4}, target)
        self.assertEqual(len(shapes(target)), 11)
        self.assertEqual(names(target).count("布褶 1"), 1)
        self.assertIn("布边", names(target))
        self.assertIn("桌沿阴影", names(target))

    def test_cloth_folds_by_fraction(self):
        target = pen()
        tableware.build_table_cloth_folds({"area": [40, 340, 720, 38], "folds": [0.3, 0.6]}, target)
        self.assertEqual(len(shapes(target)), 1 + 1 + 4 + 1)

    def test_cloth_folds_without_trim(self):
        target = pen()
        tableware.build_table_cloth_folds(
            {"area": [40, 340, 720, 38], "folds": 2, "top_shade": False, "hem": False}, target
        )
        self.assertEqual(len(shapes(target)), 1 + 4)

    def test_cloth_requires_area(self):
        with self.assertRaises(ValueError):
            tableware.build_table_cloth_folds({}, pen())

    def test_cloth_rejects_bad_area(self):
        with self.assertRaises(ValueError):
            tableware.build_table_cloth_folds({"area": [40, 340, 0, 38]}, pen())

    def test_cloth_rejects_bad_folds(self):
        with self.assertRaises(ValueError):
            tableware.build_table_cloth_folds({"area": [40, 340, 720, 38], "folds": 0}, pen())
        with self.assertRaises(ValueError):
            tableware.build_table_cloth_folds({"area": [40, 340, 720, 38], "folds": [1.2]}, pen())


class TablewareRulesTest(unittest.TestCase):
    def test_component_catalog_shape(self):
        self.assertEqual(
            set(tableware.COMPONENTS),
            {"dinner_plate", "bread_loaf", "wine_goblet", "table_cloth_folds"},
        )
        for key, item in tableware.COMPONENTS.items():
            self.assertEqual(key, key.strip())
            self.assertTrue(item["name"])
            self.assertTrue(item["description"])
            self.assertTrue(item["params"])
            self.assertTrue(callable(item["build"]))

    def test_no_pure_black_or_white(self):
        target = pen()
        tableware.build_dinner_plate({"center": [120, 330]}, target)
        tableware.build_bread_loaf({"center": [160, 322], "cut": True}, target)
        tableware.build_wine_goblet({"center": [150, 332]}, target)
        tableware.build_table_cloth_folds({"area": [40, 340, 720, 38], "folds": 4}, target)
        for value in colors(target):
            self.assertNotIn(value.lower(), ("#000000", "#ffffff"))

    def test_demo_row_within_command_budget(self):
        target = pen()
        for index, cx in enumerate((120, 200, 285, 400, 505, 590, 660, 725), 1):
            tableware.build_dinner_plate({"center": [cx, 330], "size": 22 + index}, target)
        for cx in (160, 245, 350, 455, 560, 640):
            tableware.build_bread_loaf({"center": [cx, 322], "size": 14, "cut": cx % 3 == 0}, target)
        for cx in (150, 300, 380, 480, 610):
            tableware.build_wine_goblet({"center": [cx, 332], "height": 22}, target)
        self.assertLessEqual(len(target.commands), 120)


if __name__ == "__main__":
    unittest.main()
