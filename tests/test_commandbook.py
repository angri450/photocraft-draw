# -*- coding: utf-8 -*-
import unittest

from photocraft_draw.commandbook import (
    blocked,
    categories,
    describe,
    load_catalog,
    search,
    session_baseline,
)


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


class SessionNoteTest(unittest.TestCase):
    """目录里的会话可用性标注。"""

    def test_every_command_is_annotated(self):
        states = {"可执行", "看上下文", "会话禁用"}
        for item in load_catalog()["commands"]:
            self.assertIn(item["session_state"], states, item["id"])
            self.assertIn(item["session_evidence"], {"实测-调用", "实测-查询", "推断"}, item["id"])

    def test_place_embedded_points_at_doc_place(self):
        item = describe("file.placeEmbedded")
        self.assertEqual(item["session_state"], "会话禁用")
        self.assertEqual(item["session_evidence"], "实测-调用")
        self.assertEqual(item["session_alternative"], "doc.place")
        self.assertIn("center", item["session_alternative_note"])
        self.assertEqual(item["path_params"], "path")
        self.assertEqual(item["path_root"], "读取根")

    def test_queried_baseline_is_marked_as_such(self):
        self.assertEqual(describe("image.adjustments.curves")["session_evidence"], "实测-查询")
        self.assertEqual(describe("file.export.renderVideo")["session_evidence"], "实测-查询")

    def test_save_copy_points_at_doc_save(self):
        item = describe("file.saveACopy")
        self.assertEqual(item["session_alternative"], "doc.save")
        self.assertIn("整份", item["session_alternative_note"])

    def test_print_has_no_alternative(self):
        item = describe("file.print")
        self.assertEqual(item["session_alternative"], "无")
        self.assertIn("一次性模式", item["session_alternative_note"])

    def test_document_path_is_not_a_disk_path(self):
        self.assertIn("文档内路径", describe("shape.create")["path_root"])
        self.assertIn("文档内路径", describe("layer.newAdjustmentLayer.curves")["path_root"])

    def test_scoped_writer_reports_write_root(self):
        item = describe("file.export.renderVideo")
        self.assertEqual(item["session_state"], "可执行")
        self.assertEqual(item["path_root"], "写入根")
        self.assertEqual(item["path_params"], "dir")

    def test_blocked_list_carries_alternatives(self):
        items = blocked()
        self.assertTrue(items)
        self.assertTrue(all(item["session_state"] == "会话禁用" for item in items))
        self.assertTrue(all(item["session_alternative_note"] for item in items))
        ids = {item["id"] for item in items}
        self.assertIn("file.openAs", ids)
        self.assertIn("pattern.import", ids)
        self.assertNotIn("file.export.renderVideo", ids)

    def test_baseline_counts_add_up(self):
        baseline = session_baseline()
        total = baseline["blocked"] + baseline["context"] + baseline["ready"]
        self.assertEqual(total, load_catalog()["count"])

    def test_search_finds_blocked_commands(self):
        ids = [item["id"] for item in search("会话禁用", limit=0)]
        self.assertEqual(len(ids), len(blocked()))
        self.assertIn("file.placeEmbedded", ids)

    def test_search_finds_alternative_method(self):
        ids = [item["id"] for item in search("doc.place", limit=0)]
        self.assertIn("file.placeEmbedded", ids)
        self.assertIn("file.placeLinked", ids)


if __name__ == "__main__":
    unittest.main()
