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
                engine.new_document(meta["width"], meta["height"], "测试")
                for item in commands:
                    engine.execute(item["command"], item.get("params") or {})
                engine.save(root / "test.png", "png")
                engine.save(root / "test.psd", "psd")
            self.assertGreater((root / "test.png").stat().st_size, 0)
            self.assertGreater((root / "test.psd").stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
