"""Fixed de-identified response-contract replay based on user-supplied HA logs.

This is not a new live HA test. The replay covers selected response formats from the
420-query run (synthetic labels and readings) and tests lossless formatting, classification and execution.
The new wording corpus is manually labeled, not generated from the grammar.
"""
import importlib
import json
from pathlib import Path
from datetime import date
import unittest
from collections import Counter
import test_planner_adapter as adapter
from test_semantic_lexicon import BASE,PKG,mod

data=json.loads((Path(__file__).parent/"data"/"v051_replay.json").read_text())
bm=importlib.import_module(PKG+".business_model")
pe=importlib.import_module(PKG+".plan_executor")
rc=importlib.import_module(PKG+".response_composer")
qp=importlib.import_module(PKG+".query_planner")
di=importlib.import_module(PKG+".diagnostic_ids")

class V051ReplayTests(unittest.TestCase):
    def setUp(self):
        self.menu=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
            settings={"primary_label":"主账户","secondary_label":"第二账户","secondary":"次住所"})
        self.registry=bm.BusinessRegistry(self.menu.capabilities)
    def test_actual_speech_replay(self):
        for cid,source,expected,quality in data["replies"]:
            with self.subTest(cid=cid):
                key=self.registry.by_id[cid].key
                self.assertEqual(rc.normalize_speech(key,source),source if expected is None else expected)
                self.assertEqual(pe.classify_speech(key,source),quality)
        print("V051_FORMAT_REPLAY="+str(len(data["replies"])))
    def test_diagnostics_whitelist_matches_all_original_catalog_ids(self):
        self.assertEqual(di.BUILTIN_IDS,set(self.registry.by_id))
        self.assertEqual(len(di.BUILTIN_IDS),443)

class V051IndependentAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        adapter.PlannerAdapterTests.setUp(self)
    async def ask(self,q,cid):
        return await adapter.PlannerAdapterTests.ask(self,q,cid)
    async def test_independent_readings(self):
        wrong=[]
        for i,(q,expected) in enumerate(data["positive"]):
            self.calls.clear()
            r=await self.ask(q,"v051:"+str(i))
            if Counter(self.calls)!=Counter(expected):
                wrong.append([q,expected,self.calls[:],r])
        print("V051_INDEPENDENT="+json.dumps({"total":len(data["positive"]),"correct":len(data["positive"])-len(wrong),"wrong":wrong},ensure_ascii=False))
        self.assertEqual(wrong,[])
        self.conv.async_converse.assert_not_awaited()
    async def test_independent_negative_requests(self):
        for i,q in enumerate(data["negative"]):
            self.calls.clear()
            r=await self.ask(q,"v051neg:"+str(i))
            with self.subTest(q=q):
                self.assertFalse(self.calls)
                self.assertTrue(r)
        self.conv.async_converse.assert_not_awaited()
        print("V051_NEGATIVE="+str(len(data["negative"])))
