# -*- coding: utf-8 -*-
"""部件分组和配色检查的测试。

分组规则错了，配色检查会把同一个物体的部件当成相邻部件报冲突，
或者把两座不同的山当成一座。这几条是守门。
"""
import unittest

from photocraft_draw.colorize import check_colors, parts_from_commands, report
from photocraft_draw.grouping import group
from photocraft_draw.solver import solve
from photocraft_draw.palette import mix, shade


def _parts(*items):
    """造一组部件。每项是 (名字, 颜色, x, y, 宽, 高)。"""
    return [
        {"name": name, "color": color, "bounds": [x, y, w, h], "group": group_name}
        for name, color, x, y, w, h, group_name in items
    ]


class GroupTest(unittest.TestCase):
    def test_english_trailing_number(self):
        self.assertEqual(group("sky 1"), "sky")
        self.assertEqual(group("sky 24"), "sky")
        self.assertEqual(group("arm 1"), "arm")

    def test_chinese_trailing_number(self):
        self.assertEqual(group("手一"), "手")
        self.assertEqual(group("手二"), "手")
        self.assertEqual(group("袖三"), "袖")

    def test_instance_number_kept(self):
        # 两座不同的山必须分开
        self.assertEqual(group("山 1 脚"), "山 1")
        self.assertEqual(group("山 2 脚"), "山 2")
        self.assertNotEqual(group("山 1 脚"), group("山 2 脚"))

    def test_part_word_stripped(self):
        self.assertEqual(group("山 1 顶"), "山 1")
        self.assertEqual(group("峰 2 雪尖"), "峰 2")

    def test_english_without_number(self):
        self.assertEqual(group("mountains far"), "mountains far")
        self.assertEqual(group("grass slope"), "grass slope")

    def test_declared_group_wins(self):
        # 显式声明优先于名字推断
        self.assertEqual(group("石影 1", "石头 1"), "石头 1")
        self.assertEqual(group("手一", "双手"), "双手")


class CheckColorsTest(unittest.TestCase):
    def test_same_group_not_reported(self):
        parts = _parts(
            ("袖 1", "#7A6248", 0, 0, 100, 100, "袖"),
            ("袖 2", "#7A6248", 0, 0, 100, 100, "袖"),
        )
        result = check_colors(parts)
        self.assertTrue(result["ok"])

    def test_same_color_reported(self):
        # 包围盒要有实际重叠，边界相接不算
        parts = _parts(
            ("天空 1", "#7E9AA8", 0, 0, 900, 320, "天空"),
            ("远山 1", "#7E9AA8", 0, 300, 900, 100, "远山"),
        )
        result = check_colors(parts)
        self.assertFalse(result["ok"])
        self.assertIn("会糊成一块", result["problems"][0])

    def test_small_gap_reported(self):
        parts = _parts(
            ("天空 1", "#7E9AA8", 0, 0, 900, 320, "天空"),
            ("远山 1", "#7E9AA9", 0, 300, 900, 100, "远山"),
        )
        result = check_colors(parts)
        self.assertFalse(result["ok"])

    def test_touching_edges_not_adjacent(self):
        # 边界刚好相接，中间没有重叠，不算挨着
        parts = _parts(
            ("天空 1", "#7E9AA8", 0, 0, 900, 300, "天空"),
            ("远山 1", "#7E9AA8", 0, 300, 900, 100, "远山"),
        )
        self.assertTrue(check_colors(parts)["ok"])

    def test_declared_group_exempt(self):
        parts = _parts(
            ("石影 1", "#211C18", 0, 0, 50, 50, "石头 1"),
            ("石底 1", "#211C18", 0, 0, 50, 50, "石头 1"),
        )
        self.assertTrue(check_colors(parts)["ok"])

    def test_report_status_wording(self):
        # 状态词不能含「通过」两个字，否则子串匹配会误判
        ok = check_colors(_parts(("甲", "#111111", 0, 0, 10, 10, "甲")))
        self.assertIn("检查通过", report(ok))
        self.assertNotIn("不通过", report(ok))
        bad = check_colors(_parts(
            ("甲", "#111111", 0, 0, 10, 10, "甲"),
            ("乙", "#111111", 0, 0, 10, 10, "乙"),
        ))
        self.assertIn("检查未通过", report(bad))


class PaletteTest(unittest.TestCase):
    def test_shade_zero_keeps_color(self):
        self.assertEqual(shade("#5a5f5e", 0).lower(), "#5a5f5e")

    def test_shade_changes_lightness(self):
        self.assertNotEqual(shade("#5a5f5e", 2).lower(), "#5a5f5e")
        self.assertNotEqual(shade("#5a5f5e", -2).lower(), "#5a5f5e")

    def test_shade_keeps_hue(self):
        # 同一色相里调明度，色相不该跑掉。用红绿蓝三通道的比例判断
        base = shade("#5a5f5e", 0)
        lighter = shade("#5a5f5e", 2)
        self.assertNotEqual(base.lower(), lighter.lower())
        # 调亮之后仍然偏冷，绿色通道高于红色通道
        self.assertGreater(int(lighter[3:5], 16), int(lighter[1:3], 16))

    def test_mix_endpoints(self):
        self.assertEqual(mix("#000000", "#ffffff", 0).lower(), "#000000")
        self.assertEqual(mix("#000000", "#ffffff", 1).lower(), "#ffffff")


class SolverTest(unittest.TestCase):
    def test_already_fine_needs_no_change(self):
        parts = _parts(
            ("天空 1", "#7E9AA8", 0, 0, 900, 320, "天空"),
            ("远山 1", "#5E6F66", 0, 300, 900, 100, "远山"),
        )
        result = solve(parts, min_gap=0.12)
        self.assertTrue(result["ok"])
        self.assertFalse(any(item["changed"] for item in result["colors"]))

    def test_collision_gets_separated(self):
        parts = _parts(
            ("天空 1", "#5A5F5E", 0, 0, 900, 320, "天空"),
            ("远山 1", "#5A5F5E", 0, 300, 900, 100, "远山"),
        )
        result = solve(parts, min_gap=0.12)
        self.assertTrue(result["ok"], result)
        self.assertTrue(any(item["changed"] for item in result["colors"]))

    def test_same_group_stays_same_color(self):
        parts = _parts(
            ("袖 1", "#5A5F5E", 0, 0, 100, 100, "袖"),
            ("袖 2", "#5A5F5E", 0, 0, 100, 100, "袖"),
            ("远山 1", "#5A5F5E", 0, 100, 100, 100, "远山"),
        )
        result = solve(parts, min_gap=0.12)
        colors = {item["name"]: item["hex"].lower() for item in result["colors"]}
        self.assertEqual(colors["袖 1"], colors["袖 2"])


if __name__ == "__main__":
    unittest.main()
