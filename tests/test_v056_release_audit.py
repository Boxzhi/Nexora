"""Full scoped phrase dispatch audit with the existing HA test doubles."""
import json
import unittest
from collections import Counter
import test_v053_menu_regression as regression

class FullSceneLanguageAudit(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        regression.CompleteSceneAgentTests.setUp(self)
    async def ask(self,q,cid="audit"):
        return await regression.CompleteSceneAgentTests.ask(self,q,cid)

    async def test_all_unambiguous_registered_phrases_dispatch_exact_scene(self):
        seen=set()
        count=0
        members=0
        for phrase,sid in sorted(self.menu.scene_language.exact.items()):
            with self.subTest(phrase=phrase,scene=sid):
                await self.ask("exit")
                self.calls.clear()
                answer=await self.ask(phrase)
                cap=self.menu._parameter_cap(sid)
                if cap.get("parameter"):
                    self.assertIn("请输入",answer)
                    answer=await self.ask(regression.INPUTS[cap["parameter"]])
                self.assertEqual(Counter(self.calls),Counter(self.menu.scenes[sid].members),answer)
                self.assertNotIn("查询未完成",answer)
                count+=1
                members+=len(self.calls)
                seen.add(sid)
        self.assertEqual(len(seen),150)
        self.conv.async_converse.assert_not_awaited()
        print("V056_SCOPED_PHRASE_AUDIT="+json.dumps({"scenes":len(seen),"phrases":count,"members":members}))

    async def test_precise_payment_metrics_remain_independent(self):
        for cid in ("utility.gas.pay.last_pay","utility.gas.pay.last_pay_date","utility.gas.pay.last_pay_channel","utility.gas.pay.year_pay","utility.gas.pay.year_pay_count"):
            await self.ask("exit")
            self.calls.clear()
            phrase=self.menu._query(cid,{}).sentence
            self.assertIsNone(self.menu.scene_language.match(phrase),phrase)
            await self.ask(phrase)
            self.assertEqual(self.calls,[cid],phrase)
        self.conv.async_converse.assert_not_awaited()
