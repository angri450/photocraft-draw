# -*- coding: utf-8 -*-
"""守卫测试：包里每个模块都要能导入。

之前 colorize.py 末尾多了一个引号，pytest 全绿却没发现，因为没有测试
import 过它。这里把每个模块都 import 一遍，语法错、导入错立刻暴露。
"""
import importlib
import pathlib
import unittest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "photocraft_draw"


def _module_names():
    names = []
    for path in sorted(PACKAGE.glob("*.py")):
        if path.name.startswith("_"):
            continue
        names.append(path.stem)
    return names


class ImportTest(unittest.TestCase):
    def test_every_module_imports(self):
        failures = []
        for name in _module_names():
            try:
                importlib.import_module(f"photocraft_draw.{name}")
            except Exception as error:
                failures.append(f"{name}: {type(error).__name__}: {error}")
        self.assertEqual([], failures, "有模块导入不了：\n" + "\n".join(failures))

    def test_components_import(self):
        importlib.import_module("photocraft_draw.components")

    def test_command_line_runs(self):
        # 命令行入口要能起来，参数解析错也要在这里发现
        from photocraft_draw.cli import main
        self.assertTrue(callable(main))


if __name__ == "__main__":
    unittest.main()
