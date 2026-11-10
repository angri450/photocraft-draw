# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from photocraft_draw.engine import Engine, EngineError, find_engine
from photocraft_draw.plan import compose_plan


def engine_available() -> bool:
    try:
        find_engine()
        return True
    except EngineError:
        return False


@unittest.skipUnless(engine_available(), "本机没有 photocraft-cli")
class EngineTest(unittest.TestCase):
    def test_draw_and_save(self):
        plan = {
            "canvas": [320, 180],
            "ref_width": 320,
            "background": "bg",
            "components": [
                {"component": "indoor_backdrop", "params": {"wall": [0, 0, 320, 180]}}
            ],
        }
        commands, meta = compose_plan(plan)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Engine(read_root=root, write_root=root) as engine:
                engine.new_document(
                    meta["width"], meta["height"], "测试",
                    background=meta.get("document_background"),
                )
                for item in commands:
                    engine.execute(item["command"], item.get("params") or {})
                info = engine.inspect()
                self.assertEqual(info["width"], 320)
                self.assertGreaterEqual(info["layers"], 1)
                engine.save(root / "test.png", "png")
                engine.save(root / "test.psd", "psd")
                engine.render_to(root / "preview.png", max_side=100)
                engine.open_document(root / "test.psd")
                reopened = engine.inspect()
                self.assertEqual(reopened["width"], 320)
                placed = engine.place(root / "preview.png", scale=20)
                self.assertIsNotNone(placed["layer"])
                self.assertEqual(engine.jobs(), [])
                self.assertEqual(engine.cancel_job("nope").get("cancelled", 0), 0)
            self.assertGreater((root / "test.png").stat().st_size, 0)
            self.assertGreater((root / "test.psd").stat().st_size, 0)
            self.assertGreater((root / "preview.png").stat().st_size, 0)


@unittest.skipUnless(engine_available(), "本机没有 photocraft-cli")
class RunOnceTest(unittest.TestCase):
    def test_validates_arguments(self):
        with self.assertRaises(ValueError):
            Engine().run_once([], Path("/tmp/run-once.png"))
        with self.assertRaises(ValueError):
            Engine().run_once([], Path("/tmp/run-once.png"),
                              new={"width": 10, "height": 10},
                              source=Path("/tmp/source.png"))
        with self.assertRaises(ValueError):
            Engine().run_once((), Path("/tmp/run-once.png"),
                              new={"width": 10, "height": 10})
        with self.assertRaises(ValueError):
            Engine().run_once([{"params": {}}], Path("/tmp/run-once.png"),
                              new={"width": 10, "height": 10})
        with self.assertRaises(ValueError):
            Engine().run_once([("shape.create", {})], Path("/tmp/run-once.png"),
                              new=[1, 2])

    def test_command_failure_raises(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(EngineError) as caught:
                Engine().run_once([("no.such.command", {})],
                                  Path(folder) / "bad.png",
                                  new={"width": 100, "height": 100})
            self.assertIn("退出码", str(caught.exception))
            self.assertIn("no.such.command", str(caught.exception))

    def test_timeout_raises(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(EngineError) as caught:
                Engine().run_once([("shape.create", {})],
                                  Path(folder) / "slow.png",
                                  new={"width": 100, "height": 100},
                                  timeout=0.000001)
            self.assertIn("超时", str(caught.exception))

    def test_places_svg_at_requested_center(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            svg = root / "badge.svg"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">'
                '<rect width="120" height="80" fill="#6b2f24"/></svg>',
                encoding="utf-8",
            )
            result = Engine().run_once(
                [("file.placeEmbedded", {"path": str(svg), "center": [100, 80],
                                         "smartObject": True})],
                root / "placed.png",
                new={"width": 400, "height": 300, "name": "place"},
            )
            placed = result["entries"][0]["result"]
            self.assertEqual(placed["bounds"], [40.0, 40.0, 160.0, 120.0])
            self.assertTrue(placed["smartObject"])
            self.assertTrue((root / "placed.png").is_file())


if __name__ == "__main__":
    unittest.main()
