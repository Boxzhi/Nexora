"""Independent authored acceptance corpus and end-to-end simulated adapter.

Expected capability IDs/parameters are hand-labeled. No test cases generated
from production grammar. Mock HA values are not real household data.
"""
import importlib
import json
import time
import tracemalloc
from datetime import date
from pathlib import Path
from collections import Counter
import unittest
from unittest.mock import AsyncMock
from types import SimpleNamespace
from test_planner_adapter import PlannerAdapterTests
from test_agent import Response
from test_semantic_lexicon import BASE,PKG,mod

CORPUS=json.loads((Path(__file__).parent/"data"/"v050_independent.json").read_text())
TODAY=date(2026,11,27)
qp=importlib.import_module(PKG+".query_planner")
sem=importlib.import_module(PKG+".semantic")

class IndependentAdapterCorpus(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        PlannerAdapterTests.setUp(self)
        targets={}
        for cap in self.menu.capabilities.values():
            if cap.get("native_slots"):
                entity=targets.setdefault(cap["category"],"light.fixture_"+str(len(targets)))
                sentence=self.menu._query(cap["id"],{}).sentence
                c,slots=self.by_sentence[sentence]
                self.by_sentence[sentence]=(c,{**slots,"luxe_light_id":entity})
        self.agent.resolver.replace_targets("zh-CN",targets)
        for item in CORPUS["positive"]:
            text,ids,*params=item
            for cid in ids:
                cap=self.menu.capabilities[cid]
                q=self.menu._query(cid,params[0] if params else {})
                if cap.get("native_slots"):
                    q.slots["luxe_light_id"]=targets[cap["category"]]
                self.by_sentence[q.sentence]=(cap,q.slots)
    async def ask(self,text,cid):
        return await PlannerAdapterTests.ask(self,text,cid)
    async def test_independent_actual_dispatch(self):
        correct=0
        wrong=[]
        missed=[]
        legacy=sem.SemanticIndex(mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
            settings={"primary_label":"主账户","secondary_label":"第二账户","secondary":"次住所"}))
        novel=0
        for i,(text,expected,*params) in enumerate(CORPUS["positive"]):
            self.calls.clear()
            if legacy.match(text,TODAY) is None:
                novel+=1
            result=await self.ask(text,"independent:"+str(i))
            if Counter(self.calls)==Counter(expected):
                correct+=1
            elif self.calls:
                wrong.append([text,expected,self.calls[:],result])
            else:
                missed.append([text,expected,result])
        print("V050_INDEPENDENT="+json.dumps({"total":len(CORPUS["positive"]),"correct":correct,"novel":novel,
                    "wrong":wrong,"missed":missed},ensure_ascii=False))
        self.assertEqual(wrong,[])
        # A missed supported query is a regression target, not a successful
        # clarification. Keep fixture expectations fixed while correcting code.
        self.assertEqual(missed,[])
        self.conv.async_converse.assert_not_awaited()

    async def test_independent_negative_and_delegate_boundary(self):
        response=Response("zh-CN")
        response.async_set_speech("备用代理测试")
        self.conv.async_converse=AsyncMock(return_value=SimpleNamespace(response=response,conversation_id="ai"))
        for i,text in enumerate(CORPUS["negative"]):
            self.calls.clear()
            await self.ask(text,"negative:"+str(i))
            with self.subTest(text=text):
                self.assertEqual(self.calls,[])
                self.assertIsNone(self.agent.planner.plan(text,TODAY).plan)
        self.conv.async_converse.reset_mock()
        for i,text in enumerate(CORPUS["delegate"]):
            self.calls.clear()
            await self.ask(text,"delegate:"+str(i))
            with self.subTest(text=text):
                self.assertEqual(self.calls,[])
                self.assertEqual(self.conv.async_converse.call_args.kwargs["text"],text)
        self.assertEqual(self.conv.async_converse.await_count,len(CORPUS["delegate"]))
        print("V050_NEGATIVE_CASES="+str(len(CORPUS["negative"])))
        print("V050_DELEGATE_CASES="+str(len(CORPUS["delegate"])))

class LocalPerformance(unittest.TestCase):
    def test_benchmark_planner(self):
        menu=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
             settings={"primary_label":"主账户","secondary_label":"第二账户","secondary":"次住所"})
        tracemalloc.start()
        planner=qp.QueryPlanner(menu)
        current,peak=tracemalloc.get_traced_memory()
        tracemalloc.stop()
        corpus=[x[0] for x in CORPUS["positive"]]+CORPUS["negative"]+CORPUS["delegate"]
        samples=[]
        for _ in range(12):
            for q in corpus:
                start=time.perf_counter_ns()
                planner.plan(q,TODAY)
                samples.append((time.perf_counter_ns()-start)/1_000_000)
        samples.sort()
        p95=samples[int(.95*(len(samples)-1))]
        print("V050_BENCHMARK="+json.dumps({"samples":len(samples),"p95_ms":round(p95,4),
             "median_ms":round(samples[len(samples)//2],4),"max_ms":round(samples[-1],4),
             "index_current_bytes":current,"index_peak_bytes":peak}))
        self.assertLess(p95,10.0)
