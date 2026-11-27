"""Independent utterance expectations and full mocked HA adapter regression.

The fixed corpus is authored explicitly, not emitted by the production lexicon.
All 443 capabilities are exercised against synthetic native responses, not
live Home Assistant. No device service or network request is made.
"""
import importlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from test_semantic_lexicon import BASE,PKG,mod
from test_agent import load_adapter,Handler,Response

TODAY=date(2026,11,27)
SET={"primary_label":"甲账户","secondary_label":"乙账户","secondary":"次住所"}
CATALOGS=[json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))]
CORPUS=json.loads((Path(__file__).parent/"data"/"v041_colloquial.json").read_text())

class IndependentCorpusTests(unittest.TestCase):
    def setUp(self):
        self.menu=mod.Menu(CATALOGS,settings=SET)
        self.index=importlib.import_module(PKG+".semantic").SemanticIndex(self.menu)
        self.guard=importlib.import_module(PKG+".fallback").FallbackGuard(self.menu)

    def test_independent_colloquial_corpus(self):
        count=Counter()
        for phrase,cid in CORPUS["query"]:
            with self.subTest(phrase=phrase):
                match=self.index.match(phrase,TODAY)
                self.assertIsNotNone(match)
                self.assertEqual(match.capability,cid)
                count[cid.split(".")[0]]+=1
        self.assertEqual(set(count),{"utility","lights","appliance","home"})
        for phrase in CORPUS["clarify"]:
            with self.subTest(phrase=phrase):
                match=self.index.match(phrase,TODAY)
                self.assertIsNotNone(match)
                self.assertIsNone(match.capability)
                self.assertTrue(match.clarification)
        for phrase in CORPUS["guard"]:
            with self.subTest(phrase=phrase):
                self.assertIsNone(self.index.match(phrase,TODAY))
                self.assertTrue(self.guard.classify(phrase,lambda q:self.index.match(q,TODAY) is not None).reply)
        for phrase in CORPUS["delegate"]:
            with self.subTest(phrase=phrase):
                self.assertIsNone(self.index.match(phrase,TODAY))
                self.assertFalse(self.guard.blocked(phrase))
        print("INDEPENDENT_CORPUS_CASES="+str(sum(map(len,CORPUS.values()))))

    def test_every_catalog_cancel_and_compound_is_not_a_query(self):
        count=0
        for cap in self.menu.capabilities.values():
            params={k:{"year":2024,"month":3,"day":9}[k] for k in cap.get("parameter_slots",{})}
            q=self.menu._query(cap["id"],params).sentence
            for phrase,kind in (("不要查"+q,"cancelled"),(q+"然后关灯","compound")):
                with self.subTest(cid=cap["id"],kind=kind):
                    self.assertIsNone(self.index.match(phrase,TODAY))
                    self.assertEqual(self.guard.classify(phrase,lambda part:self.index.match(part,TODAY) is not None).kind,kind)
                    count+=1
        self.assertEqual(count,886)
        print("NEGATIVE_MUTATION_CASES="+str(count))

    def test_punctuated_followup_and_clarification(self):
        f=self.menu.followups
        f.remember("a","home.env.master.temp_master",{},TODAY)
        self.assertEqual(self.menu.route("a","次卧呢？",today=TODAY).capability,"home.env.secondary.temp_secondary")
        match=self.index.match("主卧空调多少度",TODAY)
        f.remember_clarification("a",f.begin("a"),match.options)
        self.assertEqual(self.menu.route("a","设定温度！",today=TODAY).capability,"appliance.ac.master.target")

class FullAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.a,self.conv,self.it=load_adapter()
        Menu=importlib.import_module("nexora_adapter_test.menu").Menu
        self.menu=Menu(CATALOGS,settings=SET)
        self.agent=self.a.NexoraAgent(object(),"entry",self.menu,"fallback")
        handlers=[Handler(name) for name in ("LuxeUtilityQuery","LuxeLightQuery","LuxeApplianceQuery","LuxeHomeQuery")]
        self.it.async_get=lambda hass:handlers
        self.native_map={}
        self.targets={}
        self.expected={}
        for cap in self.menu.capabilities.values():
            params={k:{"year":2024,"month":3,"day":9}[k] for k in cap.get("parameter_slots",{})}
            # Use original registered data independently of semantic index.
            sentence=cap["sentence"].format(secondary=SET["secondary"],**params)
            slots=dict(cap["slots"])
            slots.update({v:params[k] for k,v in cap.get("parameter_slots",{}).items()})
            if cap.get("native_slots"):
                entity=self.targets.setdefault(cap["category"],"light.fixture_"+str(len(self.targets)))
                slots["luxe_light_id"]=entity
            if sentence in self.native_map:
                raise AssertionError("Duplicate native sentence: "+sentence)
            self.native_map[sentence]=(cap["intent"],slots)
            self.expected[cap["id"]]=(sentence,cap["intent"],slots)
        async def recognize(u,**kw):
            self.assertTrue(kw.get("strict_intents_only"))
            if u.text not in self.native_map:
                return None
            name,slots=self.native_map[u.text]
            return SimpleNamespace(intent=SimpleNamespace(name=name),unmatched_entities=[],
                entities_list=[SimpleNamespace(name=k,value=v) for k,v in slots.items()])
        self.native=SimpleNamespace(_trigger_intents_config={"intents":{}},async_recognize_intent=AsyncMock(side_effect=recognize))
        self.conv.async_get_agent=lambda hass,aid:self.native if aid=="conversation.home_assistant" else object()
        self.conv.async_converse=AsyncMock(side_effect=AssertionError("Unexpected fallback"))
        self.it.async_handle=AsyncMock(return_value=Response("zh-CN"))

    async def test_full_catalog_semantic_dispatch(self):
        count=Counter()
        for index,(cid,(sentence,intent,expected)) in enumerate(self.expected.items()):
            with self.subTest(cid=cid):
                self.it.async_handle.reset_mock()
                u=SimpleNamespace(text="请问"+sentence+"？",conversation_id="case:"+str(index),
                    context=SimpleNamespace(user_id="mock"),device_id=None,satellite_id=None,language="zh-CN",extra_system_prompt=None)
                response=await self.agent.async_process(u)
                self.assertEqual(self.it.async_handle.await_count,1,response.response.speech)
                args=self.it.async_handle.call_args.args
                self.assertEqual(args[2],intent)
                self.assertEqual({k:v["value"] for k,v in args[3].items()},expected)
                self.assertEqual(args[4],sentence)
                count[cid.split(".")[0]]+=1
        self.assertEqual(count,{"utility":136,"lights":144,"appliance":78,"home":85})
        self.conv.async_converse.assert_not_awaited()
        self.assertLessEqual(len(self.menu.followups.contexts),256)
        self.assertLessEqual(len(self.menu.followups.generations),256)
        print("MOCKED_FULL_CATALOG_DISPATCH="+str(sum(count.values())))
