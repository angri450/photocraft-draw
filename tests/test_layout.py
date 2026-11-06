# -*- coding: utf-8 -*-
"""构图检查这一层的测试。

覆盖：三套网格线的位置、规则覆盖、纯色图密度为 0、主体压在黄金分割线
上时偏移接近 0、主体偏左时偏移为正、四象限密度、长轴角度、边距，以及
覆盖图的输出。
"""
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from photocraft_draw.layout import (
    analyze,
    draw_grid,
    grid_lines,
    merge_rules,
    report,
)

BG = (240, 232, 216)
GROUND = (226, 214, 188)
BLOCK = (180, 60, 70)


def make_image(path, size=(200, 100), blocks=(), background=BG, ground=None):
    """做一张纯色底图上放几个方块的测试图。blocks 是 [([x0,y0,x1,y1], 颜色), …]。"""
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    if ground is not None:
        draw.rectangle([0, size[1] // 2, size[0] - 1, size[1] - 1], fill=ground)
    for rect, color in blocks:
        draw.rectangle(rect, fill=color)
    image.save(path)
    return path


class LayoutTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def image(self, name="case.png", **kwargs):
        return make_image(self.root / name, **kwargs)

    # ---- 网格 ----

    def test_golden_positions(self):
        lines = grid_lines(900, 1200)
        vertical = [line["pos"] for line in lines
                    if line["group"] == "golden" and line["kind"] == "vertical"]
        self.assertEqual(len(vertical), 2)
        self.assertAlmostEqual(vertical[0], 900 * 0.382, places=3)
        self.assertAlmostEqual(vertical[1], 900 * 0.618, places=3)
        horizontal = [line["pos"] for line in lines
                      if line["group"] == "golden" and line["kind"] == "horizontal"]
        self.assertAlmostEqual(horizontal[0], 1200 * 0.382, places=3)
        self.assertAlmostEqual(horizontal[1], 1200 * 0.618, places=3)

    def test_three_sets(self):
        lines = grid_lines(900, 1200)
        self.assertEqual(len(lines), 12)
        thirds = [line["pos"] for line in lines
                  if line["group"] == "thirds" and line["kind"] == "vertical"]
        self.assertAlmostEqual(thirds[0], 300, places=3)
        self.assertAlmostEqual(thirds[1], 600, places=3)
        sevens = [line["pos"] for line in lines
                  if line["group"] == "three_seven" and line["kind"] == "vertical"]
        self.assertAlmostEqual(sevens[0], 270, places=3)
        self.assertAlmostEqual(sevens[1], 630, places=3)

    def test_rules_override_only_given(self):
        rules = merge_rules({"golden": [0.25, 0.75]})
        self.assertEqual(rules["golden"], [0.25, 0.75])
        self.assertAlmostEqual(rules["thirds"][0], 1 / 3, places=6)
        self.assertEqual(rules["offset_warn"], 30.0)

    def test_bad_rule_ratio(self):
        with self.assertRaises(ValueError):
            merge_rules({"golden": [0, 1]})
        with self.assertRaises(ValueError):
            merge_rules("黄金分割")

    # ---- 密度 ----

    def test_pure_color_density_is_zero(self):
        path = self.image(blocks=())
        result = analyze(path)
        self.assertEqual(result["subject"]["pixels"], 0)
        self.assertEqual(result["density"]["quadrants"], [0.0, 0.0, 0.0, 0.0])
        self.assertIsNone(result["center_offset"])
        self.assertIsNone(result["axis_angle"])
        self.assertIsNone(result["margin"])

    def test_one_quadrant(self):
        path = self.image(blocks=[([10, 10, 40, 30], BLOCK)])
        result = analyze(path)
        quadrants = result["density"]["quadrants"]
        self.assertGreater(quadrants[0], 0)
        self.assertEqual(quadrants[1], 0.0)
        self.assertEqual(quadrants[2], 0.0)
        self.assertEqual(quadrants[3], 0.0)

    def test_two_background_colors(self):
        path = self.image(blocks=[([10, 60, 30, 80], BLOCK)], ground=GROUND)
        result = analyze(path)
        self.assertEqual(len(result["background"]), 2)
        self.assertEqual(result["subject"]["pixels"], 21 * 21)

    def test_background_is_not_subject(self):
        path = self.image(size=(300, 200), blocks=[([140, 90, 160, 110], BLOCK)],
                          ground=GROUND)
        result = analyze(path)
        self.assertLess(result["subject"]["ratio"], 0.01)

    # ---- 重心偏移 ----

    def test_offset_zero_on_golden_line(self):
        # 200 宽的图，黄金分割横线在 123.6，重心放到 123.5
        path = self.image(blocks=[([114, 52, 133, 71], BLOCK)])
        result = analyze(path)
        offset = result["center_offset"]
        self.assertEqual(offset["line_x"], 0.618)
        self.assertLess(abs(offset["x"]), 1.0)
        self.assertLess(abs(offset["y"]), 1.0)

    def test_left_subject_offset_positive(self):
        path = self.image(blocks=[([5, 52, 24, 71], BLOCK)])
        result = analyze(path)
        self.assertGreater(result["center_offset"]["x"], 0)

    def test_right_subject_offset_negative(self):
        path = self.image(blocks=[([176, 52, 195, 71], BLOCK)])
        result = analyze(path)
        self.assertLess(result["center_offset"]["x"], 0)

    def test_offset_warning_threshold(self):
        path = self.image(blocks=[([5, 52, 24, 71], BLOCK)])
        strict = analyze(path, {"offset_warn": 1})
        loose = analyze(path, {"offset_warn": 1000})
        self.assertTrue(strict["center_offset"]["warn_x"])
        self.assertFalse(loose["center_offset"]["warn_x"])
        self.assertTrue(any("横向" in item for item in strict["issues"]))

    # ---- 长轴 ----

    def test_axis_horizontal(self):
        path = self.image(blocks=[([20, 45, 180, 55], BLOCK)])
        result = analyze(path)
        self.assertLess(abs(result["axis_angle"]), 5)
        self.assertEqual(result["axis_note"], "横向")

    def test_axis_vertical(self):
        path = self.image(blocks=[([95, 10, 105, 90], BLOCK)])
        result = analyze(path)
        self.assertGreater(abs(result["axis_angle"]), 80)
        self.assertEqual(result["axis_note"], "纵向")

    # ---- 边距 ----

    def test_margin(self):
        path = self.image(blocks=[([10, 20, 30, 40], BLOCK)])
        result = analyze(path)
        margin = result["margin"]
        self.assertEqual(margin["left"], 10)
        self.assertEqual(margin["top"], 20)
        self.assertEqual(margin["right"], 200 - 1 - 30)
        self.assertEqual(margin["bottom"], 100 - 1 - 40)
        self.assertEqual(margin["min"], 10)

    # ---- 覆盖图 ----

    def test_draw_grid_writes_png(self):
        path = self.image(size=(400, 300), blocks=[([180, 120, 220, 160], BLOCK)])
        out = self.root / "layout.png"
        data = draw_grid(path, out)
        self.assertTrue(out.is_file())
        self.assertEqual(data["output"], str(out))
        with Image.open(out) as image:
            self.assertEqual(image.size, (400, 300))
            # 0.382 的竖线落在 x=152 上，颜色是黄金分割的红色
            pixel = image.convert("RGB").getpixel((152, 5))
            self.assertGreater(pixel[0], 150)
            self.assertLess(pixel[1], 110)
            self.assertLess(pixel[2], 110)

    def test_draw_grid_keeps_small_image_working(self):
        path = self.image(size=(120, 80), blocks=[([50, 30, 70, 50], BLOCK)])
        out = self.root / "small.png"
        draw_grid(path, out)
        with Image.open(out) as image:
            self.assertEqual(image.size, (120, 80))

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            analyze(self.root / "没有这张图.png")

    # ---- 文字报告 ----

    def test_report_mentions_metrics(self):
        path = self.image(blocks=[([5, 52, 24, 71], BLOCK)])
        text = report(analyze(path))
        for word in ("重心偏移", "疏密", "长轴", "边距", "主体外接框"):
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
