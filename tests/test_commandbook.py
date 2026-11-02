# -*- coding: utf-8 -*-
import unittest

from photocraft_draw.commandbook import categories, describe, load_catalog, search


class CommandBookTest(unittest.TestCase):
    def test_catalog_count(self):
        self.assertEqual(load_catalog()["count"], 953)

    def test_categories(self):
        names = {item["name"] for item in categories()}
        self.assertIn("图层操作", names)
        self.assertIn("滤镜效果", names)

    def test_chinese_search(self):
        ids = [item["id"] for item in search("曲线")]
        self.assertIn("image.adjustments.curves", ids)

    def test_search_sharpen(self):
        ids = [item["id"] for item in search("锐化", limit=20)]
        self.assertIn("filter.sharpen.unsharpMask", ids)

    def test_category_filter(self):
        found = search(category="滤镜效果", limit=20)
        self.assertTrue(found)
        self.assertTrue(all(item["category"] == "filter" for item in found))

    def test_describe(self):
        item = describe("image.adjustments.curves")
        self.assertIn("points", item["params"])
        self.assertEqual(item["category_name"], "图像调整")

    def test_unknown_command(self):
        with self.assertRaises(KeyError):
            describe("no.such.command")


if __name__ == "__main__":
    unittest.main()
