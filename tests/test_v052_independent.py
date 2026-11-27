"""Independent, synthetic-response conversation cases. No private data or real HA calls."""
import json
import unittest
from pathlib import Path
from collections import Counter
import test_planner_adapter as adapter

DATA=json.loads((Path(__file__).parent/"data"/"v052_independent.json").read_text())

class V052ConversationCorpus(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        adapter.PlannerAdapterTests.setUp(self)

    async def ask(self,q,cid):
        return await adapter.PlannerAdapterTests.ask(self,q,cid)

    async def test_independent_single_turn(self):
        wrong=[]
        for i,(q,expected) in enumerate(DATA["positive"]):
            self.calls.clear()
            speech=await self.ask(q,"v052:single:"+str(i))
            if Counter(self.calls)!=Counter(expected):
                wrong.append([q,expected,self.calls[:],speech])
        print("V052_INDEPENDENT="+json.dumps({"total":len(DATA["positive"]),"correct":len(DATA["positive"])-len(wrong),"wrong":wrong},ensure_ascii=False))
        self.assertEqual(wrong,[])
        self.conv.async_converse.assert_not_awaited()

    async def test_independent_sequences(self):
        wrong=[]
        total=0
        for i,sequence in enumerate(DATA["sequences"]):
            for q,expected in sequence:
                total+=1
                self.calls.clear()
                speech=await self.ask(q,"v052:session:"+str(i))
                if Counter(self.calls)!=Counter(expected):
                    wrong.append([q,expected,self.calls[:],speech])
        print("V052_SEQUENCES="+json.dumps({"sessions":len(DATA["sequences"]),"turns":total,"correct":total-len(wrong),"wrong":wrong},ensure_ascii=False))
        self.assertEqual(wrong,[])
        self.conv.async_converse.assert_not_awaited()

    async def test_independent_orphan_and_mixed_boundaries(self):
        for i,q in enumerate(DATA["negative"]):
            with self.subTest(q=q):
                self.calls.clear()
                speech=await self.ask(q,"v052:negative:"+str(i))
                self.assertTrue(speech)
                self.assertFalse(self.calls)
        self.conv.async_converse.assert_not_awaited()
        print("V052_NEGATIVE="+str(len(DATA["negative"])))
