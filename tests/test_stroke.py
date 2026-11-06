# -*- coding: utf-8 -*-
"""变宽笔触的测试：等宽、变宽、闭合环、拐角截断和参数校验。

直接跑测试：

    python3 -m unittest tests.test_stroke

生成演示图（需要本机有 photocraft-cli）：

    python3 -m tests.test_stroke --demo
"""
import math
import sys
import unittest
from pathlib import Path

from photocraft_draw.commands import Pen
from photocraft_draw.palette import resolve_palette
from photocraft_draw.stroke import stroke_path, taper

ROOT = Path(__file__).resolve().parents[1]


def pen():
    return Pen(800, 450, ref_width=800, palette=resolve_palette("fresco"))


def path_command(target):
    commands = [item for item in target.commands if item["params"].get("kind") == "path"]
    assert len(commands) == 1, f"期望一条路径，实际 {len(commands)} 条"
    return commands[0]["params"]


def knots_of(params, index=0):
    return params["path"]["subpaths"][index]["knots"]


class EqualWidthTest(unittest.TestCase):
    def test_straight_line(self):
        target = pen()
        stroke_path(target, [[100, 100], [300, 100]], 10, "ink")
        params = path_command(target)
        self.assertEqual(params["fill"], "#3a2a1e")
        self.assertIsNone(params["stroke"])
        subpaths = params["path"]["subpaths"]
        self.assertEqual(len(subpaths), 1)
        self.assertTrue(subpaths[0]["closed"])
        knots = knots_of(params)
        self.assertEqual(len(knots), 4)
        self.assertEqual(sorted({point[1] for point in knots}), [95, 105])

    def test_scalar_matches_array(self):
        points = [[100, 100], [200, 100], [300, 100]]
        first = pen()
        stroke_path(first, points, 8, "ink")
        second = pen()
        stroke_path(second, points, [8, 8, 8], "ink")
        self.assertEqual(first.commands, second.commands)

    def test_zero_width_makes_a_tip(self):
        target = pen()
        stroke_path(target, [[100, 100], [300, 100]], [10, 0], "ink")
        knots = knots_of(path_command(target))
        self.assertEqual(sorted({point[1] for point in knots}), [95, 100, 105])

    def test_duplicate_points_are_dropped(self):
        target = pen()
        stroke_path(target, [[100, 100], [100, 100], [300, 100]], 6, "ink")
        knots = knots_of(path_command(target))
        self.assertEqual(len(knots), 4)


class VariableWidthTest(unittest.TestCase):
    def test_width_changes_along_line(self):
        target = pen()
        stroke_path(target, [[100, 100], [200, 100], [300, 100]], [12, 6, 2], "ink")
        knots = knots_of(path_command(target))
        self.assertEqual(knots[:3], [[100, 106], [200, 103], [300, 101]])
        self.assertEqual(knots[3:], [[300, 99], [200, 97], [100, 94]])

    def test_variable_width_curve(self):
        points = [[100, 300], [150, 250], [220, 220], [300, 210]]
        target = pen()
        stroke_path(target, points, [12, 8, 4, 2], "ink")
        knots = knots_of(path_command(target))
        # 端点的偏移只跟相邻那一段有关，到中心点的距离正好是半个宽度。
        start = math.hypot(knots[0][0] - 100, knots[0][1] - 300)
        end = math.hypot(knots[3][0] - 300, knots[3][1] - 210)
        self.assertAlmostEqual(start, 6.0, delta=0.6)
        self.assertAlmostEqual(end, 1.0, delta=0.6)
        # 另一侧反向，最后一个点是起点的另一侧，第一个点是终点的另一侧。
        self.assertAlmostEqual(math.hypot(knots[-1][0] - 100, knots[-1][1] - 300), 6.0, delta=0.6)
        self.assertAlmostEqual(math.hypot(knots[4][0] - 300, knots[4][1] - 210), 1.0, delta=0.6)

    def test_taper(self):
        self.assertEqual(taper(1, 12, 2), [12.0])
        self.assertEqual(taper(3, 12, 2), [12.0, 7.0, 2.0])
        self.assertEqual(taper(5, 0, 8), [0.0, 2.0, 4.0, 6.0, 8.0])

    def test_taper_rejects_bad_counts(self):
        with self.assertRaises(ValueError):
            taper(0, 12, 2)
        with self.assertRaises(ValueError):
            taper(3, -1, 2)
        with self.assertRaises(ValueError):
            taper(2.5, 1, 2)


class ClosedLoopTest(unittest.TestCase):
    def square(self):
        return [[200, 200], [300, 200], [300, 300], [200, 300]]

    def test_ring_has_two_subpaths(self):
        target = pen()
        stroke_path(target, self.square(), 8, "ink", closed=True)
        params = path_command(target)
        subpaths = params["path"]["subpaths"]
        self.assertEqual(len(subpaths), 2)
        self.assertTrue(all(item["closed"] for item in subpaths))
        self.assertEqual(len(knots_of(params, 0)), 4)
        self.assertEqual(len(knots_of(params, 1)), 4)

    def test_inner_contour_is_inside(self):
        target = pen()
        stroke_path(target, self.square(), 8, "ink", closed=True)
        params = path_command(target)
        subpaths = params["path"]["subpaths"]
        self.assertEqual(subpaths[0]["op"], "combine")
        self.assertEqual(subpaths[1]["op"], "subtract")
        outer = [point[0] for point in knots_of(params, 0)]
        inner = [point[0] for point in knots_of(params, 1)]
        self.assertGreater(max(outer), max(inner))
        self.assertLess(min(outer), min(inner))

    def test_ring_starts_and_ends_at_same_place(self):
        target = pen()
        ring = [[200, 200], [300, 200], [300, 300], [200, 300], [200, 200]]
        stroke_path(target, ring, 6, "ink", closed=True)
        params = path_command(target)
        self.assertEqual(len(params["path"]["subpaths"]), 2)
        self.assertEqual(len(knots_of(params, 0)), 4)

    def test_ring_works_for_both_windings(self):
        for points in (
            [[200, 200], [300, 200], [300, 300], [200, 300]],
            [[200, 200], [200, 300], [300, 300], [300, 200]],
        ):
            target = pen()
            stroke_path(target, points, 8, "ink", closed=True)
            params = path_command(target)
            outer = [point[0] for point in knots_of(params, 0)]
            inner = [point[0] for point in knots_of(params, 1)]
            self.assertEqual(params["path"]["subpaths"][0]["op"], "combine")
            self.assertEqual(params["path"]["subpaths"][1]["op"], "subtract")
            self.assertGreater(max(outer) - min(outer), max(inner) - min(inner))

    def test_closed_needs_three_points(self):
        with self.assertRaises(ValueError):
            stroke_path(pen(), [[100, 100], [200, 100]], 4, "ink", closed=True)


class MiterTest(unittest.TestCase):
    def corner_distance(self, limit):
        target = pen()
        stroke_path(target, [[100, 100], [200, 100], [200, 200]], 20, "ink",
                    miter_limit=limit)
        corner = knots_of(path_command(target))[1]
        return math.hypot(corner[0] - 200, corner[1] - 100)

    def test_miter_is_clamped_by_width(self):
        # 直角斜接本来要伸出 14.14，按半宽截断后只剩 10。
        self.assertLess(self.corner_distance(1.0), 10.2)
        self.assertGreater(self.corner_distance(1.0), 9.5)

    def test_miter_limit_lets_corner_grow(self):
        self.assertGreater(self.corner_distance(2.0), 13.8)
        self.assertLess(self.corner_distance(2.0), 14.4)


class ValidationTest(unittest.TestCase):
    def test_width_array_length_mismatch(self):
        with self.assertRaises(ValueError):
            stroke_path(pen(), [[0, 0], [10, 0], [20, 0]], [4, 4], "ink")

    def test_too_few_points(self):
        with self.assertRaises(ValueError):
            stroke_path(pen(), [[0, 0]], 4, "ink")
        with self.assertRaises(ValueError):
            stroke_path(pen(), [], 4, "ink")

    def test_bad_point_types(self):
        with self.assertRaises(ValueError):
            stroke_path(pen(), [["0", 0], [10, 0]], 4, "ink")
        with self.assertRaises(ValueError):
            stroke_path(pen(), [[0, 0, 0], [10, 0]], 4, "ink")

    def test_bad_widths(self):
        with self.assertRaises(ValueError):
            stroke_path(pen(), [[0, 0], [10, 0]], -1, "ink")
        with self.assertRaises(ValueError):
            stroke_path(pen(), [[0, 0], [10, 0]], [4, "4"], "ink")
        with self.assertRaises(ValueError):
            stroke_path(pen(), [[0, 0], [10, 0]], None, "ink")

    def test_bad_miter_limit(self):
        with self.assertRaises(ValueError):
            stroke_path(pen(), [[0, 0], [10, 0]], 4, "ink", miter_limit=0)

    def test_no_layers_created(self):
        target = pen()
        stroke_path(target, [[0, 0], [50, 20], [100, 0]], taper(3, 8, 1), "ink")
        self.assertFalse([item for item in target.commands
                          if item["command"].startswith("layer.")])


def _petal_points(cx=590, cy=250, rx=88, ry=120, count=52):
    """圆底圆头的单瓣，底部留一点宽度，接在枝干上。"""
    points = []
    for index in range(count):
        angle = -math.pi + 2 * math.pi * index / count
        radius = 0.28 + 0.72 * math.cos(angle / 2)
        points.append([cx + rx * radius * math.sin(angle),
                       cy - ry * radius * math.cos(angle)])
    return points


def _inward_normal(points, index, center):
    count = len(points)
    previous = points[(index - 1) % count]
    following = points[(index + 1) % count]
    dx = following[0] - previous[0]
    dy = following[1] - previous[1]
    length = math.hypot(dx, dy)
    nx, ny = -dy / length, dx / length
    px, py = points[index]
    if nx * (center[0] - px) + ny * (center[1] - py) < 0:
        nx, ny = -nx, -ny
    return nx, ny


def _fold_strip(points, start, end, width_start, width_end, center=(590, 220)):
    """沿花瓣右边取一段，向里收出一条折边，返回折边多边形和折痕。"""
    outer = points[start:end + 1]
    inner = []
    span = max(1, end - start)
    for step, index in enumerate(range(start, end + 1)):
        depth = width_start + (width_end - width_start) * step / span
        nx, ny = _inward_normal(points, index, center)
        px, py = points[index]
        inner.append([px + nx * depth, py + ny * depth])
    return outer + list(reversed(inner)), inner


def draw_demo(target):
    """演示图：左边一根 12 收到 2 的枝干，右边一片折边翻卷的花瓣。"""
    target.rect(0, 0, 800, 450, fill="bg", name="底")

    branch = [[110, 405], [170, 360], [220, 320], [280, 285],
              [340, 258], [410, 242], [480, 238], [560, 244], [585, 248]]
    stroke_path(target, branch, taper(len(branch), 12, 2), "mid", name="枝干")

    twig = [[300, 278], [332, 256], [366, 244], [398, 240]]
    stroke_path(target, twig, taper(len(twig), 6, 1.4), "mid", name="侧枝")
    target.ellipse(398, 240, 4.0, 5.4, fill="deep",
                   stroke_width=None, stroke=None, name="芽")

    petal = _petal_points()
    target.path([{"closed": True, "knots": petal}], fill="soft",
                stroke_width=None, stroke=None, name="花瓣")

    strip, crease = _fold_strip(petal, 28, 42, 3, 10)
    target.path([{"closed": True, "knots": strip}], fill="mid",
                stroke_width=None, stroke=None, name="花瓣背面")
    target.path([{"closed": False, "knots": crease}], fill=None,
                stroke_width=1.6, stroke="deep", name="折痕")

    stroke_path(target, petal, 1.6, "deep", closed=True, name="花瓣边缘")

    target.text(24, 424, "变宽笔触：枝干 12→2，花瓣边缘折边翻卷", size=12,
                color="muted", name="题字")


def render_demo(path=None):
    """把演示图画成 PNG，返回输出路径。"""
    from photocraft_draw.engine import Engine

    target = Path(path).resolve() if path else (ROOT / "out" / "stroke-demo.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas = Pen(1600, 900, ref_width=800, palette=resolve_palette("fresco"))
    draw_demo(canvas)
    with Engine(read_root=ROOT, write_root=target.parent) as engine:
        engine.new_document(1600, 900, "变宽笔触演示")
        for item in canvas.commands:
            engine.execute(item["command"], item.get("params") or {})
        engine.save(target, "png")
    return target


class DemoTest(unittest.TestCase):
    def test_demo_has_branch_and_petal(self):
        target = pen()
        draw_demo(target)
        names = [item["params"].get("name") for item in target.commands]
        for expected in ("枝干", "侧枝", "花瓣", "花瓣背面", "折痕", "花瓣边缘"):
            self.assertIn(expected, names)
        self.assertLess(len(target.commands), 120)

    def test_petal_edge_is_a_ring(self):
        target = pen()
        draw_demo(target)
        rings = [item for item in target.commands
                 if item["params"].get("name") == "花瓣边缘"]
        self.assertEqual(len(rings), 1)
        self.assertEqual(len(rings[0]["params"]["path"]["subpaths"]), 2)


if __name__ == "__main__":
    if "--demo" in sys.argv:
        print(render_demo())
    else:
        unittest.main()
