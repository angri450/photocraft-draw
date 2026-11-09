# -*- coding: utf-8 -*-
"""分组声明和几何判据的测试。

分组错了，配色检查会把同一个物体的部件当成相邻部件报冲突，
或者把两座不同的山当成一座。这些是守门。
"""
import unittest

from photocraft_draw.colorize import check_colors
from photocraft_draw.geometry import polygons_of, shapes_intersect
from photocraft_draw.grouping import group, subject_of


def _command(name, kind, fill="#888888", **extra):
    params = {"kind": kind, "fill": fill, "name": name}
    params.update(extra)
    return {"command": "shape.create", "params": params}


def _rect(x, y, w, h):
    return {"kind": "rect", "rect": [x, y, w, h]}


class SubjectTest(unittest.TestCase):
    def test_subject_strips_number(self):
        self.assertEqual(subject_of("树冠 423"), "树冠")
        self.assertEqual(subject_of("陶瓶 44"), "陶瓶")
        self.assertEqual(subject_of("近灯罩 3"), "近灯罩")

    def test_subject_keeps_chinese_number(self):
        # 果一、果二、果三是三种不同的果子
        self.assertEqual(subject_of("果二 238"), "果二")
        self.assertEqual(subject_of("果一 12"), "果一")

    def test_subject_of_plain_name(self):
        self.assertEqual(subject_of("水面"), "水面")
        self.assertEqual(subject_of("躯干"), "躯干")


class GroupByTest(unittest.TestCase):
    def test_same_subject_same_group(self):
        self.assertEqual(group("树冠 1", "树冠"), "树冠")
        self.assertEqual(group("树冠 2", "树冠"), "树冠")

    def test_declared_group_wins(self):
        self.assertEqual(group("石影 1", "石头 1"), "石头 1")


class GeometryTest(unittest.TestCase):
    def test_overlapping_rects_intersect(self):
        a = _command("甲", "rect", rect=[0, 0, 100, 100])
        b = _command("乙", "rect", rect=[50, 50, 100, 100])
        self.assertTrue(shapes_intersect(a, b))

    def test_edge_touching_counts_as_touching(self):
        # 边界正好相接，两个部件在画面上真的贴在一起，要报出来
        a = _command("甲", "rect", rect=[0, 0, 100, 100])
        b = _command("乙", "rect", rect=[100, 0, 100, 100])
        self.assertTrue(shapes_intersect(a, b))

    def test_distant_rects_do_not_intersect(self):
        a = _command("甲", "rect", rect=[0, 0, 100, 100])
        b = _command("乙", "rect", rect=[500, 500, 100, 100])
        self.assertFalse(shapes_intersect(a, b))

    def test_ellipse_inside_rect(self):
        a = _command("椭圆", "ellipse", rect=[40, 40, 20, 20])
        b = _command("框", "rect", rect=[0, 0, 100, 100])
        self.assertTrue(shapes_intersect(a, b))

    def test_polygon_of_path(self):
        command = {
            "command": "shape.create",
            "params": {
                "kind": "path",
                "fill": "#888888",
                "name": "块",
                "path": {"subpaths": [{"closed": True, "knots": [
                    {"anchor": [0, 0], "in": [0, 0], "out": [100, 0]},
                    {"anchor": [100, 0], "in": [100, 0], "out": [100, 100]},
                    {"anchor": [100, 100], "in": [100, 100], "out": [0, 100]},
                    {"anchor": [0, 100], "in": [0, 100], "out": [0, 0]},
                ]}]},
            },
        }
        polygons = polygons_of(command)
        self.assertEqual(1, len(polygons))
        self.assertTrue(len(polygons[0]) >= 4)

    def test_bounding_boxes_are_prefiltered(self):
        # 天空横贯全画布，包围盒和任何东西都相交，形状却不交
        sky = _command("天空", "rect", rect=[0, 0, 900, 320])
        grass = _command("草坡", "rect", rect=[0, 540, 900, 100])
        self.assertFalse(shapes_intersect(sky, grass))


class LayerExemptTest(unittest.TestCase):
    def test_same_layer_skipped(self):
        parts = [
            {"name": "天空 1", "color": "#A9BFB2", "bounds": [0, 0, 900, 320],
             "layer": "sky"},
            {"name": "天空 2", "color": "#A9BFB2", "bounds": [0, 290, 900, 140],
             "layer": "sky"},
        ]
        self.assertTrue(check_colors(parts)["ok"])

    def test_different_layer_still_checked(self):
        parts = [
            {"name": "天空 1", "color": "#A9BFB2", "bounds": [0, 0, 900, 320],
             "layer": "sky"},
            {"name": "远山 1", "color": "#A9BFB2", "bounds": [0, 300, 900, 100],
             "layer": "mountains"},
        ]
        self.assertFalse(check_colors(parts)["ok"])


if __name__ == "__main__":
    unittest.main()
