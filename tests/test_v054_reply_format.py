import importlib
import unittest
from test_semantic_lexicon import PKG
rf=importlib.import_module(PKG+".reply_format")

class ReplyFormatTests(unittest.TestCase):
    def test_balanced_qualifiers_are_not_split(self):
        self.assertEqual(rf.split_clauses("甲：20元（估算；非账单）；乙：30元。"),("甲：20元（估算；非账单）","乙：30元。"))
        self.assertEqual(rf.split_clauses("甲：[a;b]；乙：{c;d}"),("甲：[a;b]","乙：{c;d}"))

    def test_unknown_structure_is_preserved(self):
        for text in ("甲（未闭合；乙", "甲）；乙", "甲；；乙", "甲；", "甲\n乙"):
            self.assertIsNone(rf.split_clauses(text))
            self.assertEqual(rf.reflow_clauses(text,lambda p:True),text)
        text="甲：20元；未知文本"
        self.assertEqual(rf.reflow_clauses(text,lambda p:"：" in p),text)

    def test_plain_sections_keep_attribution_and_blank_lines(self):
        self.assertEqual(rf.render_section("标题",["甲：数据不可用","","乙：数据不可用"]),"标题\n\n甲：数据不可用\n\n乙：数据不可用")
        self.assertEqual(rf.render_lines([]),"没有可用的查询结果。")
        self.assertEqual(rf.reflow_clauses("甲：20元；乙：30元。",lambda p:"：" in p),"甲：20元\n乙：30元。")
