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
    def as_dict(self):
        return {"response_type":"action_done"}

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
    base=Path(__file__).resolve().parents[1]/"custom_components/nexora"
    pkg=ModuleType("nexora_adapter_test")
    pkg.__path__=[str(base)]
    sys.modules[pkg.__name__]=pkg
    spec=importlib.util.spec_from_file_location("nexora_adapter_test.agent",base/"agent.py")
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
        self.menu=SimpleNamespace(aliases={},followups=SimpleNamespace(clear=lambda *a:None,remember=lambda *a:None),capabilities={"water":{"id":"water","intent":"LuxeUtilityQuery"}},route=lambda *a,**kw:SimpleNamespace(capability="water",sentence="水费余额是多少",slots=self.slots,text=""))
        self.agent=self.a.NexoraAgent(object(),"entry",self.menu,"fallback")
        self.u=SimpleNamespace(text="1",conversation_id="test",context=SimpleNamespace(user_id="u"),device_id=None,satellite_id=None,language="zh-CN",extra_system_prompt="p")
        self.agent.resolver.replace_targets("zh-CN",{})
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

    def test_native_light_slots(self):
        expected={"light_query":"single_state"}
        native={"luxe_light_id":"light"}
        self.assertTrue(self.a._slots_match({**expected,"luxe_light_id":"light.example"},expected,native))
        self.assertFalse(self.a._slots_match({**expected,"luxe_light_id":"switch.example"},expected,native))
        self.assertFalse(self.a._slots_match({**expected,"luxe_light_id":"light.example","unexpected":"x"},expected,native))
        self.assertFalse(self.a._slots_match({"light_query":"brightness","luxe_light_id":"light.example"},expected,native))
        self.assertFalse(self.a._slots_match(expected,expected,native))
    async def test_native_light_dispatch(self):
        self.h=Handler("LuxeLightQuery")
        self.menu.capabilities["water"]={"id":"water","category":"lights.fixture","intent":"LuxeLightQuery","native_slots":{"luxe_light_id":"light"}}
        self.slots={"light_query":"single_state"}
        self.result.intent.name="LuxeLightQuery"
        self.result.entities_list=[SimpleNamespace(name="light_query",value="single_state"),SimpleNamespace(name="luxe_light_id",value="light.example")]
        await self.agent.async_process(self.u)
        self.it.async_handle.assert_awaited_once()
        self.assertEqual(self.it.async_handle.call_args.args[3]["luxe_light_id"]["value"],"light.example")

    async def test_context_remember_only_success(self):
        remembered=[]
        self.menu.followups.remember=lambda *args:remembered.append(args)
        await self.agent.async_process(self.u)
        self.assertEqual(len(remembered),1)
        self.it.async_handle.return_value=SimpleNamespace(as_dict=lambda:{"response_type":"error"})
        await self.agent.async_process(self.u)
        self.assertEqual(len(remembered),1)
    async def test_changed_native_target_blocks(self):
        self.h=Handler("LuxeLightQuery")
        self.menu.capabilities["water"]={"id":"water","category":"lights.fixture","intent":"LuxeLightQuery","native_slots":{"luxe_light_id":"light"}}
        self.slots={"light_query":"single_state"}
        self.result.intent.name="LuxeLightQuery"
        self.result.entities_list=[SimpleNamespace(name="light_query",value="single_state"),SimpleNamespace(name="luxe_light_id",value="light.new")]
        self.agent.resolver.replace_targets("zh-CN",{"lights.fixture":"light.old"})
        r=await self.agent.async_process(self.u)
        self.assertIn("目标已变化",r.response.speech)
        self.it.async_handle.assert_not_awaited()

    async def test_lazy_mapping_only_recognizes(self):
        cap={"id":"fixture","category":"lights.fixture","intent":"LuxeLightQuery","sentence":"测试灯状态如何","slots":{"light_query":"single_state"},"native_slots":{"luxe_light_id":"light"}}
        self.menu.capabilities={"fixture":cap}
        self.result.intent.name="LuxeLightQuery"
        self.result.entities_list=[SimpleNamespace(name="light_query",value="single_state"),SimpleNamespace(name="luxe_light_id",value="light.example")]
        self.agent.resolver.invalidate()
        await self.agent._prepare_capabilities(self.u,{"LuxeLightQuery"})
        self.assertEqual(self.agent.resolver.targets,{"lights.fixture":"light.example"})
        self.it.async_handle.assert_not_awaited()
        await self.agent._prepare_capabilities(self.u,{"LuxeLightQuery"})
        self.native.async_recognize_intent.assert_awaited_once()

    async def test_local_reply_does_not_execute_or_fallback(self):
        self.menu.route=lambda *a,**kw:SimpleNamespace(capability=None,text="菜单")
        r=await self.agent.async_process(self.u)
        self.assertEqual(r.response.speech,"菜单")
        self.it.async_handle.assert_not_awaited()
        self.conv.async_converse.assert_not_awaited()

    async def test_local_execution_exception_never_falls_back(self):
        self.it.async_handle.side_effect=RuntimeError("test")
        r=await self.agent.async_process(self.u)
        self.assertIn("本地查询暂时失败",r.response.speech)
        self.it.async_handle.assert_awaited_once()
        self.conv.async_converse.assert_not_awaited()

    async def test_fallback_only_on_unmatched_route(self):
        self.menu.route=lambda *a,**kw:None
        self.conv.async_converse=AsyncMock(return_value="fallback")
        self.assertEqual(await self.agent.async_process(self.u),"fallback")
        self.conv.async_converse.assert_awaited_once()
        self.it.async_handle.assert_not_awaited()

    async def test_native_data_gap_is_terminal(self):
        response=Response("zh-CN")
        response.async_set_speech("数据不可用")
        self.it.async_handle.return_value=response
        r=await self.agent.async_process(self.u)
        self.assertEqual(r.response.speech,"数据不可用")
        self.it.async_handle.assert_awaited_once()
        self.conv.async_converse.assert_not_awaited()
