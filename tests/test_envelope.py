# -*- coding: utf-8 -*-
"""包络检查的规则测试。"""
import unittest

from photocraft_draw.envelope import check_envelope, envelope_text


def part(name, box):
    return {"name": name, "bbox": box, "w": box[2] - box[0], "h": box[3] - box[1]}


def person_parts():
    # 以肩部 (400, 400) 为原点，身高 400
    return [
        part("头", [370, 300, 430, 380]),
        part("躯干", [370, 400, 430, 560]),
        part("左臂", [300, 410, 360, 540]),
        part("右臂", [440, 410, 500, 540]),
        part("左腿", [375, 560, 410, 800]),
        part("右腿", [410, 560, 445, 800]),
    ]


class EnvelopeTest(unittest.TestCase):
    def test_normal_person_passes(self):
        result = check_envelope(person_parts(), "person", (400, 400), 400)
        self.assertTrue(result["ok"], envelope_text(result))

    def test_far_part_caught(self):
        parts = person_parts()
        parts.append(part("飘出去的部件", [900, 300, 960, 380]))
        result = check_envelope(parts, "person", (400, 400), 400)
        self.assertFalse(result["ok"])
        self.assertTrue(any("出了外轮廓" in item for item in result["problems"]))

    def test_tiny_shape_caught(self):
        parts = [part(f"小{i}", [395, 415, 405, 435]) for i in range(4)]
        result = check_envelope(parts, "person", (400, 400), 400)
        self.assertFalse(result["ok"])
        self.assertTrue(any("太小" in item for item in result["problems"]))

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            check_envelope(person_parts(), "dragon", (400, 400), 400)


if __name__ == "__main__":
    unittest.main()
