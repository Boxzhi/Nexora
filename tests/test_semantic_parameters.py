"""Real catalog date/ambiguity tests; no HA I/O."""
import importlib
from datetime import date
from test_semantic_lexicon import BASE, PKG, mod
import json
import unittest

class ParameterTests(unittest.TestCase):
    def setUp(self):
        self.today=date(2026,11,27)
        self.menu=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
            settings={"primary_label":"京华府","secondary_label":"第二账户","secondary":"灵山何家"})
        self.semantic=importlib.import_module(PKG+".semantic")
        self.index=self.semantic.SemanticIndex(self.menu)
    def match(self,q):
        return self.index.match(q,today=self.today)

    def test_all_34_parameterized_canonical_and_spoken(self):
        samples={"year":2024,"month":3,"day":9}
        count=0
        for cap in self.menu.capabilities.values():
            if not cap.get("parameter"):
                continue
            params={field:samples[field] for field in cap["parameter_slots"]}
            canonical=self.menu._query(cap["id"],params)
            spoken=canonical.sentence.replace("2024年","二零二四年").replace("3月","三月份").replace("9日","九号")
            if "九号" in spoken:
                spoken=spoken.replace("三月份","三月")
            for q in (canonical.sentence,spoken,"请问"+spoken+"啊？"):
                with self.subTest(q=q,cid=cap["id"]):
                    match=self.match(q)
                    self.assertIsNotNone(match)
                    self.assertEqual(match.capability,cap["id"])
                    self.assertEqual(dict(match.params),params)
                    reply=self.index.reply(match,lambda c:True)
                    self.assertEqual(reply.sentence,canonical.sentence)
                    self.assertEqual(reply.slots,canonical.slots)
                    count+=1
        self.assertEqual(count,102)

    def test_examples_and_account_boundaries(self):
        cases={
            "去年三月份电费花了多少钱":("utility.electric.j.history.h_month_cost.h_month_cost_last_year",{"month":3}),
            "二零二四年三月九号用了几度电":("utility.electric.j.history.day.h_day_explicit",{"year":2024,"month":3,"day":9}),
            "2024-03-09耗电多少":("utility.electric.j.history.day.h_day_explicit",{"year":2024,"month":3,"day":9}),
            "灵山何家去年三月份电费花了多少钱":("utility.electric.l.history.h_month_cost.h_month_cost_last_year",{"month":3}),
            "第二账户的2024-03用电量多少":("utility.electric.l.history.h_month_usage.h_month_usage_explicit",{"year":2024,"month":3}),
            "今年三月份用了几吨水":("utility.water.history.history_usage.history_usage_year",{"month":3}),
            "去年二月份水费花了多少钱":("utility.water.history.history_cost.history_cost_last_year",{"month":2}),
            "2024年2月份燃气费花了多少钱":("utility.gas.history.h_month_cost.h_month_cost_explicit",{"year":2024,"month":2}),
            "二零二四年账单累计燃气费多少":("utility.gas.history.h_year_cost.h_year_cost_explicit",{"year":2024}),
            "今年三月九号用了几度电":("utility.electric.j.history.day.h_day_year",{"month":3,"day":9}),
        }
        for q,(cid,params) in cases.items():
            with self.subTest(q=q):
                m=self.match(q)
                self.assertEqual(m.capability,cid)
                self.assertEqual(dict(m.params),params)

    def test_invalid_date_future_and_leap_year(self):
        for q in ("2025年2月29日用了多少度电","2026年12月电费是多少",
                  "2026年11月28日用了几度电","去年十三月份水费多少",
                  "2024年0月电费是多少","1999年3月电费是多少",
                  "二零二四年三月三十二号耗电多少","今年十二月用了多少方气",
                  "今年零月份电费多少","今年二十月份电费多少",
                  "2024年三十月电费是多少","2024年三月二零号耗电多少"):
            with self.subTest(q=q):
                m=self.match(q)
                self.assertIsNotNone(m)
                self.assertIsNone(m.capability)
                self.assertIn("日期",m.clarification)
        self.assertEqual(dict(self.match("2024年2月29日用了几度电").params),{"year":2024,"month":2,"day":29})

    def test_ambiguity_and_unsupported_range(self):
        for q in ("主卧空调多少度","次卧空调现在几度","浴霸温度多少","大门好了吗",
                  "阳台有多亮","燃气还剩多少方","燃气还有几立方米","水费还剩多少吨",
                  "上个月花了多少","水费要交了吗","最近7天电费多少",
                  "过去三个月用水量","2024年3月水费是多少"):
            with self.subTest(q=q):
                m=self.match(q)
                self.assertIsNotNone(m)
                self.assertIsNone(m.capability)
                self.assertTrue(m.clarification)

    def test_parameter_does_not_swallow_controls_or_compounds(self):
        for q in ("2024年3月电费多少然后关灯","不要查去年三月电费多少",
                  "把空调调到26度","2024年3月9日用了多少吨水并打开灯",
                  "去年3月电费多少和水费多少","陌生账户去年3月电费多少"):
            with self.subTest(q=q):
                self.assertIsNone(self.match(q))

    def test_duplicate_account_label_and_unconfigured_secondary(self):
        self.menu.settings["primary_label"]="共同账户"
        self.menu.settings["secondary_label"]="共同账户"
        self.index=self.semantic.SemanticIndex(self.menu)
        m=self.match("共同账户去年三月电费多少")
        self.assertIsNone(m.capability)
        self.assertIn("多个",m.clarification)
        self.menu.settings["secondary"]=""
        self.index=self.semantic.SemanticIndex(self.menu)
        self.assertIsNone(self.match("共同账户去年三月电费多少").clarification)
        self.assertIsNone(self.match("第二账户去年三月电费多少"))

    def test_equivalent_calendar_year_and_relative_day(self):
        for q,cid,params in (
            ("2026年3月水费是多少","utility.water.history.history_cost.history_cost_year",{"month":3}),
            ("二零二五年三月份水费花了多少钱","utility.water.history.history_cost.history_cost_last_year",{"month":3}),
            ("2025-03用水量多少","utility.water.history.history_usage.history_usage_last_year",{"month":3}),
            ("去年三月九号用了几度电","utility.electric.j.history.day.h_day_explicit",{"year":2025,"month":3,"day":9}),
            ("灵山何家前年二月二十九号用了几度电","utility.electric.l.history.day.h_day_explicit",{"year":2024,"month":2,"day":29}),
        ):
            with self.subTest(q=q):
                m=self.match(q)
                self.assertEqual(m.capability,cid)
                self.assertEqual(dict(m.params),params)
        for q in ("2026年12月水费多少","2025年2月29日用了几度电","去年二月二十九号用了几度电"):
            self.assertIn("日期",self.match(q).clarification)
        for q in ("2024年3月水费多少","2024-03水费多少","三月份电费多少"):
            self.assertIsNone(self.match(q).capability)
            self.assertTrue(self.match(q).clarification)
