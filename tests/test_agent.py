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
        self.menu=SimpleNamespace(aliases={},followups=SimpleNamespace(clear=lambda *a:None,remember=lambda *a:None,begin=lambda *a:object(),is_current=lambda *a:True,is_followup_message=lambda text:False),capabilities={"water":{"id":"water","intent":"LuxeUtilityQuery"}},route=lambda *a,**kw:SimpleNamespace(capability="water",sentence="水费余额是多少",slots=self.slots,text=""))
        self.menu.followups.complete=lambda key,token,cap: self.menu.followups.remember(key,cap)
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
        self.u.text="你好"
        response=Response("zh-CN")
        response.async_set_speech("你好")
        self.conv.async_converse=AsyncMock(return_value=SimpleNamespace(response=response,conversation_id="ai-session"))
        r=await self.agent.async_process(self.u)
        self.assertEqual(r.conversation_id,"test")
        self.assertIsNone(self.conv.async_converse.call_args.kwargs["conversation_id"])
        self.assertIn("p",self.conv.async_converse.call_args.kwargs["extra_system_prompt"])
        self.assertIn("不要推测",self.conv.async_converse.call_args.kwargs["extra_system_prompt"])
        await self.agent.async_process(self.u)
        self.assertEqual(self.conv.async_converse.call_args.kwargs["conversation_id"],"ai-session")
        self.u.conversation_id="other"
        await self.agent.async_process(self.u)
        self.assertIsNone(self.conv.async_converse.call_args.kwargs["conversation_id"])
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
        self.u.text="你好"
        response=Response("zh-CN")
        response.async_set_speech("fallback")
        self.conv.async_converse=AsyncMock(return_value=SimpleNamespace(response=response,conversation_id="ai"))
        self.assertEqual((await self.agent.async_process(self.u)).response.speech,"fallback")
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

    async def test_semantic_query_uses_strict_executor_and_no_fallback(self):
        from importlib import import_module
        SemanticIndex=import_module("nexora_adapter_test.semantic").SemanticIndex
        self.menu.capabilities["water"].update(sentence="水费余额是多少",slots=self.slots)
        self.menu._available=lambda cid,visible:visible(self.menu.capabilities[cid])
        self.menu._query=lambda cid,p:SimpleNamespace(capability=cid,sentence="水费余额是多少",slots=self.slots)
        self.menu.route=lambda *a,**kw:None
        self.agent.semantic=SemanticIndex(self.menu)
        self.u.text="请问水费余额？"
        self.assertIsNotNone(self.agent.semantic.match(self.u.text))
        original=self.native.async_recognize_intent
        async def recognize(u,**kw):
            return None if u.text==self.u.text else await original(u,**kw)
        self.native.async_recognize_intent=recognize
        await self.agent.async_process(self.u)
        self.it.async_handle.assert_awaited_once()
        self.conv.async_converse.assert_not_awaited()

    async def test_semantic_hidden_or_missing_handler_is_terminal(self):
        from importlib import import_module
        SemanticIndex=import_module("nexora_adapter_test.semantic").SemanticIndex
        self.menu.capabilities["water"].update(sentence="水费余额是多少",slots=self.slots)
        self.menu._available=lambda cid,visible:visible(self.menu.capabilities[cid])
        self.menu.route=lambda *a,**kw:None
        self.agent.semantic=SemanticIndex(self.menu)
        self.u.text="水费余额"
        self.h.config["action"]={}
        r=await self.agent.async_process(self.u)
        self.assertIn("不可用",r.response.speech)
        self.it.async_handle.assert_not_awaited()
        self.conv.async_converse.assert_not_awaited()

    async def test_unmatched_live_queries_blocked_before_ai(self):
        self.menu.route=lambda *a,**kw:None
        for text in ("阳台光照传感器是不是坏了","我家还剩多少钱","sensor.foo","主卧空调当前状态","爸爸现在在家吗"):
            self.u.text=text
            r=await self.agent.async_process(self.u)
            self.assertIn("无法确认",r.response.speech)
        self.conv.async_converse.assert_not_awaited()
        self.it.async_handle.assert_not_awaited()
        self.assertEqual(self.agent.diagnostics_snapshot()["guard:blocked"]["count"],5)

    async def test_ai_timeout_releases_session_and_never_retries(self):
        self.menu.route=lambda *a,**kw:None
        self.u.text="讲个故事"
        self.agent.ai_timeout=0.01
        async def slow(*args,**kw):
            await asyncio.sleep(10)
        self.conv.async_converse=AsyncMock(side_effect=slow)
        r=await self.agent.async_process(self.u)
        self.assertIn("超时",r.response.speech)
        self.conv.async_converse.assert_awaited_once()
        self.assertFalse(self.agent.ai_sessions.active)
        self.assertFalse(self.agent.ai_sessions.sessions)
        self.assertEqual(self.agent.diagnostics_snapshot()["ai:timeout"]["count"],1)

    async def test_ai_error_never_replays(self):
        self.menu.route=lambda *a,**kw:None
        self.u.text="讲个故事"
        self.conv.async_converse=AsyncMock(side_effect=RuntimeError("test"))
        r=await self.agent.async_process(self.u)
        self.assertIn("暂时不可用",r.response.speech)
        self.conv.async_converse.assert_awaited_once()
        self.assertFalse(self.agent.ai_sessions.active)

    async def test_ai_busy_does_not_block_menu_or_overwrite_local_context(self):
        self.menu.route=lambda *a,**kw:None if a[1]=="讲个故事" else SimpleNamespace(capability="water",sentence="水费余额是多少",slots=self.slots,text="")
        self.u.text="讲个故事"
        started=asyncio.Event()
        release=asyncio.Event()
        async def slow(*args,**kw):
            started.set()
            await release.wait()
            return SimpleNamespace(response=Response("zh-CN"),conversation_id="ai")
        self.conv.async_converse=AsyncMock(side_effect=slow)
        task=asyncio.create_task(self.agent.async_process(self.u))
        await started.wait()
        try:
            r=await self.agent.async_process(self.u)
            self.assertIn("正在处理",r.response.speech)
            self.u.text="1"
            remembered=[]
            self.menu.followups.remember=lambda *args:remembered.append(args)
            await self.agent.async_process(self.u)
            self.assertEqual(len(remembered),1)
        finally:
            release.set()
            await task
        self.assertEqual(len(remembered),1)
        self.conv.async_converse.assert_awaited_once()

    async def test_guard_preserves_registered_exact_parameter_query(self):
        self.menu.route=lambda *a,**kw:None
        self.u.text="2024年3月1日用了多少度电"
        cap={"id":"water","intent":"LuxeUtilityQuery","sentence":"{year}年{month}月{day}日用了多少度电","parameter":"date",
             "parameter_slots":{"year":"y","month":"m","day":"d"},
             "slots":{"utility_kind":"e","utility_metric":"h_day"}}
        self.menu.capabilities={"water":cap}
        self.slots={**cap["slots"],"y":2024,"m":3,"d":1}
        self.result.entities_list=[SimpleNamespace(name=k,value=v) for k,v in self.slots.items()]
        self.menu._available=lambda cid,visible:visible(cap)
        self.menu._query=lambda cid,p:SimpleNamespace(capability=cid,sentence=self.u.text,slots=self.slots)
        await self.agent.async_process(self.u)
        self.it.async_handle.assert_awaited_once()
        self.conv.async_converse.assert_not_awaited()

    async def test_guard_preserves_native_fixed_slot_synonym(self):
        self.menu.route=lambda *a,**kw:None
        self.u.text="想查一下家里的水费余额"
        cap={"id":"water","intent":"LuxeUtilityQuery","sentence":"水费余额是多少","slots":self.slots}
        self.menu.capabilities={"water":cap}
        self.menu._available=lambda cid,visible:visible(cap)
        self.menu._query=lambda cid,p:SimpleNamespace(capability=cid,sentence=cap["sentence"],slots=self.slots)
        await self.agent.async_process(self.u)
        self.it.async_handle.assert_awaited_once()
        self.conv.async_converse.assert_not_awaited()

    def test_ai_duplicate_backend_session_id_is_not_reused(self):
        from importlib import import_module
        AIConversations=import_module("nexora_adapter_test.fallback").AIConversations
        now=[0]
        sessions=AIConversations(clock=lambda:now[0],ttl=30,max_sessions=2)
        sessions.complete("a","same")
        sessions.complete("b","same")
        self.assertFalse(sessions.sessions)
        sessions.complete("c","same")
        self.assertFalse(sessions.sessions)
        self.assertEqual(sessions.reserve("a"),(True,None))
        sessions.release("a")
        now[0]=31
        self.assertEqual(sessions.reserve("b"),(True,None))
        self.assertFalse(sessions.rejected_ids)
        sessions.release("b")

    def test_no_transport_private_protocol(self):
        for name in ("menu_protocol_version","context_protocol_version","semantic_protocol_version",
                     "guard_protocol_version","begin_fast_context","finish_fast_context",
                     "async_process_menu","async_process_semantic","async_process_guarded"):
            self.assertFalse(hasattr(self.agent,name),name)
        self.assertTrue(callable(self.agent.async_process))

    async def test_general_questions_and_controls_delegate_without_local_execution(self):
        self.menu.route=lambda *a,**kw:None
        self.native.async_recognize_intent.return_value=None
        self.conv.async_converse=AsyncMock(return_value=SimpleNamespace(response=Response("zh-CN"),conversation_id="ai"))
        for text in ("洗衣机怎么清洁","空调如何省电","介绍一下 Home Assistant",
                     "给爸爸写一段生日祝福","帮我设置一个学习计划","关闭客厅灯","什么是光照度"):
            with self.subTest(text=text):
                self.u.text=text
                await self.agent.async_process(self.u)
        self.assertEqual(self.conv.async_converse.await_count,7)
        self.it.async_handle.assert_not_awaited()

    async def test_native_priority_over_semantic_alias(self):
        from importlib import import_module
        SemanticIndex=import_module("nexora_adapter_test.semantic").SemanticIndex
        self.menu.route=lambda *a,**kw:None
        other={**self.slots,"utility_kind":"g"}
        self.menu.capabilities={
            "water":{"id":"water","intent":"LuxeUtilityQuery","sentence":"水费余额是多少","slots":self.slots},
            "gas":{"id":"gas","intent":"LuxeUtilityQuery","sentence":"燃气费余额是多少","slots":other}}
        self.menu._available=lambda cid,visible:visible(self.menu.capabilities[cid])
        self.menu._query=lambda cid,p:SimpleNamespace(capability=cid,sentence=self.menu.capabilities[cid]["sentence"],slots=self.menu.capabilities[cid]["slots"])
        self.agent.semantic=SemanticIndex(self.menu)
        self.u.text="水费余额"
        self.result.entities_list=[SimpleNamespace(name=k,value=v) for k,v in other.items()]
        await self.agent.async_process(self.u)
        self.assertEqual(self.it.async_handle.call_args.args[3]["utility_kind"]["value"],"g")
        self.conv.async_converse.assert_not_awaited()
        self.assertEqual(self.agent.diagnostics_snapshot()["local_native:completed"]["count"],1)

    async def test_native_non_household_synonym_is_not_sent_to_ai(self):
        self.menu.route=lambda *a,**kw:None
        self.u.text="查一下余额"
        cap={"id":"water","intent":"LuxeUtilityQuery","sentence":"水费余额是多少","slots":self.slots}
        self.menu.capabilities={"water":cap}
        self.menu._available=lambda cid,visible:visible(cap)
        self.menu._query=lambda cid,p:SimpleNamespace(capability=cid,sentence=cap["sentence"],slots=self.slots)
        await self.agent.async_process(self.u)
        self.it.async_handle.assert_awaited_once()
        self.conv.async_converse.assert_not_awaited()

    async def test_native_light_synonym_initializes_mapping(self):
        self.menu.route=lambda *a,**kw:None
        self.h=Handler("LuxeLightQuery")
        self.u.text="那盏灯亮着没"
        slots={"light_query":"single_state"}
        cap={"id":"fixture","category":"lights.fixture","intent":"LuxeLightQuery","sentence":"测试灯状态如何","slots":slots,"native_slots":{"luxe_light_id":"light"}}
        self.menu.capabilities={"fixture":cap}
        self.result.intent.name="LuxeLightQuery"
        self.result.entities_list=[SimpleNamespace(name=k,value=v) for k,v in {**slots,"luxe_light_id":"light.example"}.items()]
        self.menu._available=lambda cid,visible:visible(cap)
        self.menu._query=lambda cid,p:SimpleNamespace(capability=cid,sentence=cap["sentence"],slots=slots)
        self.agent.resolver.invalidate()
        await self.agent.async_process(self.u)
        self.assertEqual(self.agent.resolver.targets["lights.fixture"],"light.example")
        self.it.async_handle.assert_awaited_once()
        self.conv.async_converse.assert_not_awaited()

    async def test_independent_dialog_cancels_pending_date_prompt(self):
        import json
        from importlib import import_module
        Menu=import_module("nexora_adapter_test.menu").Menu
        directory=Path(__file__).resolve().parents[1]/"custom_components/nexora/catalogs"
        menu=Menu([json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))])
        self.agent=self.a.NexoraAgent(object(),"entry",menu,"fallback")
        key=("u",None,None,"test")
        menu.route(key,"help")
        menu.route(key,"1.1.1.2.1.4")
        self.assertIsNotNone(menu.sessions[key].pending)
        self.native.async_recognize_intent.return_value=None
        self.u.text="讲个故事"
        self.conv.async_converse=AsyncMock(return_value=SimpleNamespace(response=Response("zh-CN"),conversation_id="ai"))
        await self.agent.async_process(self.u)
        self.assertIsNone(menu.sessions[key].pending)
        self.conv.async_converse.assert_awaited_once()
        self.it.async_handle.assert_not_awaited()
