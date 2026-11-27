import importlib
import json
import unittest
from test_semantic_lexicon import BASE,PKG,mod

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.m=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
                        settings={"primary_label":"甲账户","secondary_label":"乙账户","secondary":"次住所"})
        self.guard=importlib.import_module(PKG+".fallback").FallbackGuard(self.m)

    def test_unmatched_queries_are_local(self):
        for q in ("燃气剩多少","天然气还剩几方","水费够不够用","灯亮着没","主卧空调开着没","次卧窗帘关了没",
                  "洗衣机洗好没","洗衣液还剩多少","滤芯还剩多少天","浴霸暖风开了没","摄像头掉线了没",
                  "晾衣架升到哪了","餐厅吊扇现在几档","家里有哪些设备坏了","玄关现在有没有人",
                  "甲账户电费怎么样","乙账户还剩多少钱","sensor.example","查看客厅空调","关闭客厅灯了吗"):
            with self.subTest(q=q):
                self.assertEqual(self.guard.classify(q).kind,"live")

    def test_normal_questions_preserve_delegate(self):
        for q in ("你好","讲个故事","洗衣机怎么清洁","空调如何省电","我家空调怎么省电",
                  "介绍一下 Home Assistant","给爸爸写一段生日祝福","帮我设置一个学习计划",
                  "什么是光照度","水费怎么交","如何配置传感器","推荐一款空调","为什么海水是咸的",
                  "如何把灯具接入 Home Assistant","今天天气怎么样","新加坡现在多少度"):
            with self.subTest(q=q):
                self.assertFalse(self.guard.blocked(q))

    def test_controls_and_query_control_boundary(self):
        for q in ("关闭客厅灯","把主卧空调调到26度","打开阳台灯","turn on kitchen light","不要开灯"):
            with self.subTest(q=q):
                self.assertEqual(self.guard.classify(q).kind,"control")
        for q in ("燃气余额多少然后关灯","关掉客厅灯再查燃气余额","查一下主卧温度，打开空调"):
            with self.subTest(q=q):
                self.assertEqual(self.guard.classify(q).kind,"compound")
        for q in ("不要查燃气剩多少","请别再查询水费"):
            self.assertEqual(self.guard.classify(q).kind,"cancelled")
        for q in ("调的几度","还有多久","上锁状态","余额呢"):
            self.assertEqual(self.guard.classify(q).kind,"missing_context")

    def test_unknown_real_time_not_education(self):
        for q in ("我家空调为什么现在没开","为什么空调现在报错","家里今天用了多少电","查一下乙账户的电费"):
            self.assertEqual(self.guard.classify(q).kind,"live")

    def test_mixed_request_with_short_conjunction(self):
        self.assertEqual(self.guard.classify("燃气余额多少并关灯").kind,"compound")

    def test_release_audit_mixed_and_cancelled(self):
        for q in ("关灯和燃气余额","燃气余额以及关灯","燃气余额，顺便把客厅灯关了","关灯另外查询水费"):
            self.assertEqual(self.guard.classify(q).kind,"compound",q)
        self.assertEqual(self.guard.classify("不要帮我查燃气余额").kind,"cancelled")
        self.assertEqual(self.guard.classify("燃气余额和水费余额").kind,"live")
