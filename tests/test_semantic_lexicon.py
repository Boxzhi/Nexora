"""Audit the vocabulary against the unchanged built-in catalogs."""
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from collections import Counter, defaultdict

BASE=Path(__file__).resolve().parents[1]/"custom_components/nexora"
PKG="nexora_lexicon_test"
package=ModuleType(PKG)
package.__path__=[str(BASE)]
sys.modules[PKG]=package
mod=importlib.import_module(PKG+".menu")
lex=importlib.import_module(PKG+".semantic_lexicon")

class VocabularyTests(unittest.TestCase):
    def setUp(self):
        self.menu=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
                           settings={"primary_label":"主账户","secondary_label":"第二账户","secondary":"次住所"})
    def test_every_catalog_capability_classified(self):
        profiles=[lex.describe(c) for c in self.menu.capabilities.values()]
        self.assertNotIn(None,profiles)
        self.assertEqual(Counter(p.family for p in profiles),{"home":85,"lights":144,"appliance":78,"utility":136})
        self.assertEqual(sum(bool(p.parameter) for p in profiles),34)
        self.assertEqual(len({(p.family,p.target,p.metric,p.period,p.parameter,p.account) for p in profiles}),443)
    def test_every_fixed_capability_has_curated_patterns(self):
        for c in self.menu.capabilities.values():
            with self.subTest(capability=c["id"]):
                phrases=lex.patterns(c,self.menu)
                if c.get("parameter"):
                    self.assertFalse(phrases)
                else:
                    self.assertGreaterEqual(len(phrases),2)
    def test_account_and_metric_separation(self):
        caps=self.menu.capabilities
        p=lambda cid:lex.patterns(caps[cid],self.menu)
        self.assertIn("燃气剩多少",p("utility.gas.basic.balance"))
        self.assertNotIn("燃气还剩多少方",p("utility.gas.basic.balance"))
        self.assertIn("次住所的电费剩多少",p("utility.electric.l.basic.balance"))
        self.assertNotIn("电费剩多少",p("utility.electric.l.basic.balance"))
        self.assertFalse(p("appliance.ac.master.temp")&p("appliance.ac.master.target"))
        self.assertIn("晾衣架灯开着没",p("lights.fixtures.airer.single_state"))
        self.assertNotIn("晾衣架灯开着没",p("appliance.airer.light"))
        self.assertIn("餐厅风扇灯开着没",p("lights.fixtures.dining_fan.single_state"))
        self.assertNotIn("餐厅风扇灯开着没",p("appliance.fan.light"))
        self.assertFalse(p("home.access.door.lock_all")&p("home.access.door.door_all"))
        self.assertFalse(p("utility.summary.primary.balances")&p("utility.summary.all.balances_all"))
        self.menu.settings["secondary"]=""
        self.assertFalse(p("utility.electric.l.basic.balance"))
    def test_vocab_collision_audit(self):
        index=defaultdict(set)
        for c in self.menu.capabilities.values():
            for phrase in lex.patterns(c,self.menu):
                index[phrase].add(c["id"])
        collisions={q:sorted(ids) for q,ids in index.items() if len(ids)>1}
        self.assertEqual(collisions,{})
        self.assertGreater(len(index),1000)

class ComposedMatcherTests(VocabularyTests):
    def setUp(self):
        super().setUp()
        self.semantic=importlib.import_module(PKG+".semantic")
        self.index=self.semantic.SemanticIndex(self.menu)
    def test_all_expanded_phrases_and_wrappers(self):
        total=0
        for c in self.menu.capabilities.values():
            for phrase in lex.patterns(c,self.menu):
                for text in (phrase, "请问"+phrase+"？", "帮我查一下"+phrase+"啊"):
                    with self.subTest(text=text,capability=c["id"]):
                        result=self.index.match(text)
                        self.assertIsNotNone(result)
                        self.assertEqual(result.capability,c["id"])
                        total+=1
        print(f"COMPOSED_CORPUS_CASES={total}")
        self.assertGreater(total,3000)
    def test_all_canonical_fixed_queries(self):
        for c in self.menu.capabilities.values():
            if c.get("parameter"):
                continue
            query=self.menu._query(c["id"],{})
            with self.subTest(capability=c["id"]):
                self.assertEqual(self.index.match(query.sentence).capability,c["id"])
    def test_combined_index_collision_audit(self):
        collisions={q:sorted(ids) for q,ids in self.index.aliases.items() if len(ids|self.index.exact.get(q,set()))>1}
        self.assertEqual(collisions,{})
        print(f"COMBINED_UNIQUE_PHRASES={len(set(self.index.aliases)|set(self.index.exact))}")
    def test_spoken_examples(self):
        for phrase,cid in {
            "燃气剩多少":"utility.gas.basic.balance",
            "燃气还剩多少":"utility.gas.basic.balance",
            "电费剩多少":"utility.electric.j.basic.balance",
            "水费还剩多少":"utility.water.balance",
            "昨天用了几度电":"utility.electric.j.history.day.h_day_yesterday",
            "上月水费花了多少":"utility.water.history.history_cost.history_cost_previous",
            "家里哪些灯还亮着":"lights.all.list_on",
            "哪些灯没关":"lights.all.list_on",
            "有没有灯掉线了":"lights.abnormal.offline",
            "主卧吸顶灯亮着没":"lights.fixtures.master_ceiling.single_state",
            "衣服洗好了吗":"appliance.washer.status",
            "洗到哪了":"appliance.washer.phase",
            "还有多久洗好":"appliance.washer.remaining",
            "主卧空调现在调的几度啊":"appliance.ac.master.target",
            "主卧空调测到几度":"appliance.ac.master.temp",
            "家里都有谁":"home.family.family_all",
            "主卧现在几度":"home.env.master.temp_master",
            "大门锁好了吗":"home.access.door.lock_all",
            "大门关严了吗":"home.access.door.door_all",
        }.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(self.index.match(phrase).capability,cid)
    def test_no_control_unit_or_time_guessing(self):
        for phrase in ("帮我打开客厅灯","主卧空调调到26度","请问关闭浴霸",
                       "把洗衣机停一下","燃气还剩多少方","燃气剩多少度","水费还剩多少吨",
                       "昨天主卧现在几度","不要查燃气剩多少","燃气剩多少然后关灯",
                       "未知房间现在几度","2024年3月电费是多少"):
            with self.subTest(phrase=phrase):
                self.assertIsNone(self.index.match(phrase))
    def test_account_alias_collision_is_local_clarification(self):
        self.menu.settings["primary_label"]="共同账户"
        self.menu.settings["secondary_label"]="共同账户"
        index=self.semantic.SemanticIndex(self.menu)
        match=index.match("共同账户电费剩多少")
        self.assertIsNotNone(match)
        self.assertIsNone(match.capability)
        self.assertIn("多个查询",match.clarification)
    def test_no_secondary_query_when_not_configured(self):
        self.menu.settings["secondary"]=""
        index=self.semantic.SemanticIndex(self.menu)
        self.assertIsNone(index.match("第二账户电费剩多少"))
        self.assertEqual(index.match("电费剩多少").capability,"utility.electric.j.basic.balance")
