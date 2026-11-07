# -*- coding: utf-8 -*-
"""回归基线与性能基准这一层的测试。

覆盖：纯色图没有前景时交并比为 0、同一张图交并比为 1、低于阈值判失败、
基线缺失报错、尺寸不一致报错。
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("regression", ROOT / "tools" / "regression.py")
regression = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(regression)

BG = (240, 232, 216)
BLOCK = (180, 60, 70)


def make_image(path, blocks=(), size=(120, 80), background=BG):
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    for rect, color in blocks:
        draw.rectangle(rect, fill=color)
    image.save(path)
    return path


class RegressionTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def test_pure_color_iou_is_zero(self):
        blank = make_image(self.root / "blank.png")
        block = make_image(self.root / "block.png", [([10, 10, 60, 60], BLOCK)])
        self.assertEqual(regression.iou(blank, block), 0.0)

    def test_same_image_iou_is_one(self):
        block = make_image(self.root / "block.png", [([10, 10, 60, 60], BLOCK)])
        self.assertAlmostEqual(regression.iou(block, block), 1.0, places=6)

    def test_below_threshold_fails(self):
        baseline = make_image(self.root / "a.png", [([5, 5, 50, 50], BLOCK)])
        current = make_image(self.root / "b.png", [([60, 30, 110, 75], BLOCK)])
        result = regression.compare(baseline, current, threshold=0.97)
        self.assertFalse(result["ok"])
        self.assertLess(result["iou"], 0.5)
        self.assertEqual(result["threshold"], 0.97)

    def test_above_threshold_passes(self):
        baseline = make_image(self.root / "a.png", [([5, 5, 60, 60], BLOCK)])
        current = make_image(self.root / "b.png", [([6, 6, 60, 60], BLOCK)])
        result = regression.compare(baseline, current, threshold=0.9)
        self.assertTrue(result["ok"])

    def test_missing_baseline_raises(self):
        current = make_image(self.root / "b.png", [([5, 5, 50, 50], BLOCK)])
        with self.assertRaises(FileNotFoundError):
            regression.compare(self.root / "没有基线.png", current)

    def test_size_mismatch_raises(self):
        first = make_image(self.root / "a.png", size=(120, 80))
        second = make_image(self.root / "b.png", size=(80, 60))
        with self.assertRaises(ValueError):
            regression.iou(first, second)

    def test_compare_image_is_side_by_side(self):
        first = make_image(self.root / "a.png", [([5, 5, 50, 50], BLOCK)])
        second = make_image(self.root / "b.png", [([5, 5, 50, 50], BLOCK)])
        out = self.root / "compare.png"
        regression.build_compare(first, second, out, 1.0)
        with Image.open(out) as image:
            self.assertEqual(image.size, (120 * 2 + regression.GAP, 80))


if __name__ == "__main__":
    unittest.main()
