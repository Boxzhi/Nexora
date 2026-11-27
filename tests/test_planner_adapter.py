"""Actual adapter integration with synthetic HA handlers and native results."""
import importlib
import json
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from test_agent import load_adapter, Handler, Response
from test_semantic_lexicon import BASE

class PlannerAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.a,self.conv,self.it=load_adapter()
        Menu=importlib.import_module("nexora_adapter_test.menu").Menu
        self.menu=Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],
            settings={"primary_label":"主账户","secondary_label":"第二账户","secondary":"次住所"})
        self.agent=self.a.NexoraAgent(object(),"entry",self.menu,"fallback")
        self.assertIsNotNone(self.agent.planner)
        handlers=[Handler(name) for name in ("LuxeHomeQuery","LuxeLightQuery","LuxeUtilityQuery","LuxeApplianceQuery")]
        self.it.async_get=lambda hass:handlers
        self.agent.resolver.replace_targets("zh-CN",{})
        self.by_sentence={}
        for cap in self.menu.capabilities.values():
            params={k:{"year":2024,"month":3,"day":9}[k] for k in cap.get("parameter_slots",{})}
            query=self.menu._query(cap["id"],params)
            self.by_sentence[query.sentence]=(cap,query.slots)
        async def recognize(u,**kw):
            self.assertTrue(kw.get("strict_intents_only"))
            if u.text not in self.by_sentence:
                return None
            cap,slots=self.by_sentence[u.text]
            return SimpleNamespace(intent=SimpleNamespace(name=cap["intent"]),unmatched_entities=[],
                entities_list=[SimpleNamespace(name=k,value=v) for k,v in slots.items()])
        self.native=SimpleNamespace(_trigger_intents_config={"intents":{}},async_recognize_intent=AsyncMock(side_effect=recognize))
        self.conv.async_get_agent=lambda hass,aid:self.native if aid=="conversation.home_assistant" else object()
        self.conv.async_converse=AsyncMock(side_effect=AssertionError("unexpected fallback"))
        self.speech={
            "utility.gas.basic.balance":"华润燃气燃气账户余额：83.36元。",
            "utility.water.balance":"水务账户余额：93.92元。",
            "utility.gas.tier.tier1_remaining":"第1阶梯剩余气量：377立方米。",
            "utility.gas.tier.tier2_remaining":"第2阶梯：数据不可用。",
            "appliance.ac.master.target":"主卧空调已关闭，无当前运行参数。",
            "appliance.ac.master.temp":"主卧空调已关闭，无当前运行参数。",
            "appliance.ac.secondary.target":"次卧空调设定温度：25℃。",
            "appliance.ac.secondary.temp":"次卧空调室温：20.8℃。",
        }
        self.calls=[]
        async def handle(hass,domain,intent,slots,sentence,*args,**kw):
            cap,expected=self.by_sentence[sentence]
            self.assertEqual(intent,cap["intent"])
            self.assertEqual({k:v["value"] for k,v in slots.items()},expected)
            self.calls.append(cap["id"])
            response=Response("zh-CN")
            response.async_set_speech(self.speech.get(cap["id"],sentence+"：测试数据。"))
            return response
        self.it.async_handle=AsyncMock(side_effect=handle)

    async def ask(self,text,cid="a"):
        u=SimpleNamespace(text=text,conversation_id=cid,context=SimpleNamespace(user_id="u"),device_id=None,
                          satellite_id=None,language="zh-CN",extra_system_prompt=None)
        r=await self.agent.async_process(u)
        self.assertEqual(r.conversation_id,cid)
        return r.response.speech

    async def test_novel_queries_corrected_and_scene_followups(self):
        r=await self.ask("能不能帮我看看家里的天燃气费还剩下多少钱")
        self.assertEqual(r,"华润燃气账户余额：83.36元。")
        self.assertEqual(self.calls,["utility.gas.basic.balance"])
        self.calls.clear()
        r=await self.ask("水费呢")
        self.assertIn("93.92元",r)
        self.assertEqual(self.calls,["utility.water.balance"])
        self.calls.clear()
        r=await self.ask("主卧空调多少度")
        self.assertEqual(r,"主卧空调已关闭，无当前运行参数。")
        self.assertEqual(set(self.calls),{"appliance.ac.master.target","appliance.ac.master.temp"})
        self.calls.clear()
        r=await self.ask("次卧呢？")
        self.assertIn("25℃",r)
        self.assertIn("20.8℃",r)
        self.assertEqual(set(self.calls),{"appliance.ac.secondary.target","appliance.ac.secondary.temp"})
        self.conv.async_converse.assert_not_awaited()

    async def test_physical_quantity_and_batch_results(self):
        r=await self.ask("燃气还剩多少立方米")
        self.assertIn("无法查询实际剩余燃气量",r)
        self.assertIn("377立方米",r)
        self.assertIn("数据不可用",r)
        self.assertNotIn("83.36",r)
        self.calls.clear()
        r=await self.ask("燃气余额和水费余额")
        self.assertIn("83.36元",r)
        self.assertIn("93.92元",r)
        self.assertEqual(set(self.calls),{"utility.gas.basic.balance","utility.water.balance"})
        self.conv.async_converse.assert_not_awaited()

    async def test_boundaries_context_isolation_and_conflict(self):
        await self.ask("主卧空调多少度")
        self.calls.clear()
        r=await self.ask("次卧呢",cid="b")
        self.assertIn("上下文",r)
        self.assertFalse(self.calls)
        for q in ("燃气余额然后关灯","不要查天燃气余额","次住所燃气余额"):
            r=await self.ask(q)
            self.assertTrue(r)
        self.assertFalse(self.calls)
        # A raw native result pointing to another registered capability
        # cannot override the structured subject.
        wrong=self.menu.capabilities["utility.water.balance"]
        original=self.native.async_recognize_intent.side_effect
        async def recognize(u,**kw):
            if u.text=="我想知道天燃气还剩下多少钱":
                return SimpleNamespace(intent=SimpleNamespace(name=wrong["intent"]),unmatched_entities=[],
                   entities_list=[SimpleNamespace(name=k,value=v) for k,v in wrong["slots"].items()])
            return await original(u,**kw)
        self.native.async_recognize_intent=AsyncMock(side_effect=recognize)
        r=await self.ask("我想知道天燃气还剩下多少钱")
        self.assertIn("参数不一致",r)
        self.assertFalse(self.calls)
        self.conv.async_converse.assert_not_awaited()

    async def test_release_audit_mixed_requests_never_delegate(self):
        for q in ("关灯和燃气余额","燃气余额以及关灯","燃气余额，顺便把客厅灯关了","不要帮我查燃气余额"):
            self.calls.clear()
            r=await self.ask(q)
            self.assertTrue("分别发送" in r or "取消" in r,q)
            self.assertFalse(self.calls)
        self.conv.async_converse.assert_not_awaited()

    async def test_release_audit_menu_exit_clears_scene_focus(self):
        await self.ask("主卧空调多少度")
        self.calls.clear()
        r=await self.ask("exit")
        self.assertIn("已退出",r)
        r=await self.ask("次卧呢")
        self.assertIn("上下文",r)
        self.assertFalse(self.calls)
        self.conv.async_converse.assert_not_awaited()

    async def test_canonical_and_structured_speech_use_same_formatter(self):
        cap=self.menu.capabilities["utility.gas.basic.balance"]
        for query in (self.menu._query(cap["id"],{}).sentence,
                      "能不能帮我看看家里的天燃气费还剩下多少钱"):
            self.calls.clear()
            self.assertEqual(await self.ask(query),"华润燃气账户余额：83.36元。")
            self.assertEqual(self.calls,[cap["id"]])
        self.conv.async_converse.assert_not_awaited()

    async def test_quality_diagnostics_separate_from_execution(self):
        self.speech["utility.gas.basic.balance"]="华润燃气账户余额：数据不可用。"
        self.assertIn("数据不可用",await self.ask(self.menu._query("utility.gas.basic.balance",{}).sentence))
        self.assertIn("query_quality:data_gap",self.agent.diagnostics_snapshot())
        self.conv.async_converse.assert_not_awaited()
