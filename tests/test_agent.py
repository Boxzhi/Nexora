"""Adapter contract tests with minimal Home Assistant doubles, not runtime tests."""
import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
import sys
from datetime import datetime

class Handler:
    def __init__(self, name="LuxeUtilityQuery", config=None):
        self.intent_type=name
        self.config={"speech":{}} if config is None else config

class Response:
    def __init__(self,language):
        self.speech=""
    def async_set_speech(self,text):
        self.speech=text

def load_adapter():
    modules={n:ModuleType(n) for n in ("homeassistant","homeassistant.components","homeassistant.components.conversation","homeassistant.components.intent_script","homeassistant.components.intent_script.helpers","homeassistant.helpers","homeassistant.helpers.intent","homeassistant.util","homeassistant.util.dt")}
    conv=modules["homeassistant.components.conversation"]
    conv.AbstractConversationAgent=object
    conv.ConversationInput=lambda **kw:SimpleNamespace(**kw)
    conv.ConversationResult=lambda **kw:SimpleNamespace(**kw)
    conv.async_get_agent=lambda *a:None
    conv.async_converse=AsyncMock()
    it=modules["homeassistant.helpers.intent"]
    it.async_get=lambda hass:[]
    it.IntentResponse=Response
    it.async_handle=AsyncMock()
    modules["homeassistant.components.intent_script.helpers"].ScriptIntentHandler=Handler
    modules["homeassistant.util.dt"].now=lambda:datetime(2026,11,27)
    for n,m in modules.items():
        if "." in n:
            parent,key=n.rsplit(".",1)
            setattr(modules[parent],key,m)
    spec=importlib.util.spec_from_file_location("nexora_test_adapter",Path(__file__).resolve().parents[1]/"custom_components/nexora/agent.py")
    adapter=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,modules):
        spec.loader.exec_module(adapter)
    return adapter,conv,it

class Tests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.a,self.conv,self.it=load_adapter()
        self.h=Handler()
        self.it.async_get=lambda hass:[self.h]
        self.it.async_handle=AsyncMock(return_value=Response("zh-CN"))
        self.slots={"utility_kind":"w","utility_metric":"balance","luxe_utility_property":"j"}
        self.result=SimpleNamespace(intent=SimpleNamespace(name="LuxeUtilityQuery"),unmatched_entities=[],entities_list=[SimpleNamespace(name=k,value=v) for k,v in self.slots.items()])
        self.native=SimpleNamespace(_trigger_intents_config={"intents":{}},async_recognize_intent=AsyncMock(return_value=self.result))
        self.fallback=object()
        self.conv.async_get_agent=lambda hass,aid:self.native if aid=="conversation.home_assistant" else self.fallback
        self.menu=SimpleNamespace(capabilities={"water":{"intent":"LuxeUtilityQuery"}},route=lambda *a,**kw:SimpleNamespace(capability="water",sentence="水费余额是多少",slots=self.slots,text=""))
        self.agent=self.a.NexoraAgent(object(),"entry",self.menu,"fallback")
        self.u=SimpleNamespace(text="1",conversation_id="test",context=SimpleNamespace(user_id="u"),device_id=None,satellite_id=None,language="zh-CN",extra_system_prompt="p")
    async def test_matching_read_only_query(self):
        r=await self.agent.async_process(self.u)
        self.it.async_handle.assert_awaited_once()
        self.conv.async_converse.assert_not_awaited()
        self.assertEqual(r.conversation_id,"test")
    async def test_mismatched_slots_never_execute(self):
        self.result.entities_list[0].value="g"
        r=await self.agent.async_process(self.u)
        self.assertIn("不一致",r.response.speech)
        self.it.async_handle.assert_not_awaited()
        self.conv.async_converse.assert_not_awaited()
    async def test_trigger_registry_blocks(self):
        self.native._trigger_intents_config={"intents":{"trigger":{}}}
        r=await self.agent.async_process(self.u)
        self.assertIn("严格识别不可用",r.response.speech)
        self.it.async_handle.assert_not_awaited()
    async def test_action_handler_blocks(self):
        self.h.config["action"]={}
        r=await self.agent.async_process(self.u)
        self.assertIn("不可用",r.response.speech)
        self.it.async_handle.assert_not_awaited()
    async def test_changed_handler_blocks(self):
        async def recognize(*a,**kw):
            self.h=Handler()
            return self.result
        self.native.async_recognize_intent=recognize
        r=await self.agent.async_process(self.u)
        self.assertIn("不一致",r.response.speech)
        self.it.async_handle.assert_not_awaited()
    async def test_fallback_context(self):
        self.menu.route=lambda *a,**kw:None
        self.conv.async_converse=AsyncMock(return_value="fallback response")
        self.assertEqual(await self.agent.async_process(self.u),"fallback response")
        self.assertEqual(self.conv.async_converse.call_args.kwargs["conversation_id"],"test")
        self.assertEqual(self.conv.async_converse.call_args.kwargs["extra_system_prompt"],"p")
    def test_numeric_slots(self):
        self.assertTrue(self.a._slot_equal(2024.0,2024))
        self.assertFalse(self.a._slot_equal(True,1))
        self.assertFalse(self.a._slot_equal("l","j"))
