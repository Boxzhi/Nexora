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
