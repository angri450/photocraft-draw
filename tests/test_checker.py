# -*- coding: utf-8 -*-
"""检验器的规则测试。"""
import unittest

from photocraft_draw.checker import check_commands, parts_of, report_text


def shape(kind, name, **params):
    body = {"kind": kind, "name": name, **params}
    return {"command": "shape.create", "params": body}


class PartsTest(unittest.TestCase):
    def test_rect_bbox(self):
        parts = parts_of([shape("rect", "躯干", rect=[10, 20, 30, 40])])
        self.assertEqual(parts[0]["bbox"], [10, 20, 40, 60])

    def test_line_bbox(self):
        parts = parts_of([shape("line", "线", **{"from": [30, 10], "to": [10, 50]})])
        self.assertEqual(parts[0]["bbox"], [10, 10, 30, 50])

    def test_path_bbox(self):
        parts = parts_of([shape("path", "路径",
                                path={"subpaths": [{"closed": True, "knots": [[5, 5], [50, 20], [20, 60]]}]})])
        self.assertEqual(parts[0]["bbox"], [5, 5, 50, 60])


class CheckTest(unittest.TestCase):
    def person(self, extra_arm_x=0):
        return [
            shape("rect", "头", rect=[90, 10, 20, 20]),
            shape("rect", "躯干", rect=[85, 30, 30, 60]),
            shape("rect", "左臂", rect=[70, 32, 12, 55]),
            shape("rect", "右臂", rect=[118 + extra_arm_x, 32, 12, 55]),
            shape("rect", "左腿", rect=[88, 90, 12, 55]),
            shape("rect", "右腿", rect=[100, 90, 12, 55]),
        ]

    def test_good_person_passes(self):
        result = check_commands(self.person(), (900, 1200), expect="person")
        self.assertTrue(result["ok"], report_text(result))

    def test_out_of_canvas_caught(self):
        result = check_commands(self.person(extra_arm_x=800), (900, 1200), expect="person")
        self.assertFalse(result["ok"])
        self.assertTrue(any("超出画布" in item for item in result["problems"]))

    def test_missing_part_caught(self):
        parts = [item for item in self.person() if item["params"]["name"] != "左腿"]
        result = check_commands(parts, (900, 1200), expect="person")
        self.assertFalse(result["ok"])
        self.assertTrue(any("缺少部件" in item for item in result["problems"]))

    def test_head_below_torso_caught(self):
        parts = self.person()
        parts[0] = shape("rect", "头", rect=[90, 120, 20, 20])
        result = check_commands(parts, (900, 1200), expect="person")
        self.assertFalse(result["ok"])
        self.assertTrue(any("头在躯干下方" in item for item in result["problems"]))

    def test_arm_crossed_caught(self):
        parts = self.person()
        parts[2] = shape("rect", "左臂", rect=[130, 32, 12, 55])
        result = check_commands(parts, (900, 1200), expect="person")
        self.assertFalse(result["ok"])
        self.assertTrue(any("左臂长到" in item for item in result["problems"]))

    def test_empty_caught(self):
        result = check_commands([], (900, 1200))
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
