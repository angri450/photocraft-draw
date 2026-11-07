# -*- coding: utf-8 -*-
"""逐朵匹配布局评估的测试。

覆盖：纯色图零匹配、两个粉色方块全中、整体平移后交并比为零、多余连通域
被记数、面积过小的噪点被忽略、计划框按画布缩放，以及命令行退出码和 JSON。
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("eval_layout", ROOT / "tools" / "eval_layout.py")
eval_layout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval_layout)

BG = (240, 232, 216)
PINK = (230, 150, 170)


def make_draft(boxes, width=200, height=100):
    return {
        "width": width,
        "height": height,
        "items": [{"caption": "a pale rose-pink blossom", "bbox": list(box)}
                  for box in boxes],
    }


def make_image(path, rects=(), size=(200, 100), background=BG):
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    for box in rects:
        draw.rectangle([box[0], box[1], box[2] - 1, box[3] - 1], fill=PINK)
    image.save(path)
    return path


class EvalLayoutTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def test_pure_color_has_no_match(self):
        image = make_image(self.root / "blank.png")
        result = eval_layout.evaluate(make_draft([[10, 10, 60, 60]]), image)
        self.assertEqual(result["summary"]["matched"], 0)
        self.assertEqual(result["summary"]["mean_iou"], 0.0)
        self.assertFalse(result["summary"]["ok"])

    def test_two_squares_all_match(self):
        boxes = [[10, 10, 60, 60], [80, 10, 130, 60]]
        image = make_image(self.root / "two.png", boxes)
        result = eval_layout.evaluate(make_draft(boxes), image)
        self.assertEqual(result["summary"]["matched"], 2)
        self.assertAlmostEqual(result["summary"]["mean_iou"], 1.0, places=3)
        self.assertEqual(result["summary"]["extras"], 0)
        self.assertTrue(result["summary"]["ok"])

    def test_global_shift_has_zero_iou(self):
        image = make_image(self.root / "shift.png", [[100, 10, 150, 60]])
        result = eval_layout.evaluate(make_draft([[10, 10, 60, 60]]), image)
        self.assertEqual(result["rows"][0]["iou"], 0.0)
        self.assertFalse(result["rows"][0]["matched"])

    def test_extra_component_is_counted(self):
        image = make_image(self.root / "extra.png",
                           [[10, 10, 60, 60], [80, 10, 130, 60], [150, 10, 190, 60]])
        result = eval_layout.evaluate(make_draft([[10, 10, 60, 60], [80, 10, 130, 60]]), image)
        self.assertEqual(result["summary"]["extras"], 1)

    def test_tiny_noise_is_ignored(self):
        image = make_image(self.root / "noise.png",
                           [[10, 10, 60, 60], [80, 10, 130, 60], [5, 5, 7, 7]])
        result = eval_layout.evaluate(make_draft([[10, 10, 60, 60], [80, 10, 130, 60]]), image)
        self.assertEqual(result["summary"]["extras"], 0)
        self.assertEqual(result["summary"]["matched"], 2)

    def test_planned_boxes_are_scaled(self):
        draft = make_draft([[10, 10, 40, 40]], width=100, height=50)
        image = make_image(self.root / "scaled.png", [[20, 20, 80, 80]], size=(200, 100))
        result = eval_layout.evaluate(draft, image)
        self.assertAlmostEqual(result["rows"][0]["iou"], 1.0, places=3)

    def test_main_exit_code_and_json(self):
        image = make_image(self.root / "blank.png")
        draft = self.root / "draft.json"
        draft.write_text(json.dumps(make_draft([[10, 10, 60, 60]])), encoding="utf-8")
        out = self.root / "eval.json"
        code = eval_layout.main([str(draft), str(image), "--json", str(out)])
        self.assertEqual(code, 1)
        self.assertTrue(out.is_file())
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["planned_count"], 1)
        self.assertIn("summary", data)

    def test_no_blossom_raises(self):
        draft = {"width": 200, "height": 100, "items": [{"caption": "a twig", "bbox": [0, 0, 10, 10]}]}
        image = make_image(self.root / "blank.png")
        with self.assertRaises(ValueError):
            eval_layout.evaluate(draft, image)

    def test_tangent_circles_are_split(self):
        image = Image.new("RGB", (200, 100), BG)
        draw = ImageDraw.Draw(image)
        for cx in (50, 90):
            draw.ellipse([cx - 20, 30, cx + 19, 69], fill=PINK)
        path = self.root / "circles.png"
        image.save(path)
        pixels = np.asarray(Image.open(path).convert("RGB"), dtype=int)
        blobs = eval_layout.components(eval_layout.pink_mask(pixels), 10,
                                       restore=eval_layout.ERODE_RADIUS)
        self.assertEqual(len(blobs), 2)

    def test_one_to_one_does_not_reuse_a_blob(self):
        image = make_image(self.root / "pair.png", [[10, 10, 60, 60], [70, 10, 120, 60]])
        draft = make_draft([[10, 10, 60, 60], [50, 10, 100, 60]])
        result = eval_layout.evaluate(draft, image)
        actuals = [tuple(row["actual"]) for row in result["rows"] if row["actual"]]
        self.assertEqual(len(actuals), 2)
        self.assertEqual(len(set(actuals)), 2)
        self.assertTrue(all(row["matched"] for row in result["rows"]))

    def test_area_ratio_is_reported(self):
        image = make_image(self.root / "small.png", [[10, 10, 35, 60]])
        result = eval_layout.evaluate(make_draft([[10, 10, 60, 60]]), image)
        row = result["rows"][0]
        self.assertAlmostEqual(row["area_ratio"], 0.5, places=2)
        self.assertEqual(row["size"], "偏小")
        self.assertEqual(row["actual_area"], 25 * 50)

    def test_extras_after_one_to_one(self):
        image = make_image(self.root / "extra.png",
                           [[10, 10, 60, 60], [80, 10, 130, 60], [150, 10, 190, 60]])
        result = eval_layout.evaluate(make_draft([[10, 10, 60, 60], [80, 10, 130, 60]]), image)
        self.assertEqual(result["summary"]["extras"], 1)
        self.assertEqual(result["summary"]["matched"], 2)


if __name__ == "__main__":
    unittest.main()
