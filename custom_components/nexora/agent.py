"""Route menu commands locally and preserve the existing conversation fallback."""
import asyncio
import logging
import re
from uuid import uuid4
from .capability import Resolver
from .binding_extractor import BindingExtractor

from homeassistant.components import conversation
from homeassistant.components.intent_script.helpers import ScriptIntentHandler
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

def _slot_equal(actual, expected):
    if type(expected) is int:
        return (type(actual) in (int, float) and actual == expected) or (type(actual) is str and actual == str(expected))
    return type(actual) is str and actual == expected

def _slots_match(recognized, expected, native_slots):
    if set(recognized) != set(expected) | set(native_slots):
        return False
    if any(not _slot_equal(recognized[k], v) for k, v in expected.items()):
        return False
    # The target is resolved by the locally installed, strict native sentence
    # lists, not by menu input or an LLM. Never accept another domain.
    for key, domain in native_slots.items():
        value = recognized[key]
        if domain != "light" or key != "luxe_light_id" or type(value) is not str or not re.fullmatch(r"light\.[a-z0-9_]+", value):
            return False
    return True

class NexoraAgent(conversation.AbstractConversationAgent):
    def __init__(self, hass, entry_id, menu, fallback, bindings=None):
        self.hass, self.entry_id, self.menu, self.fallback = hass, entry_id, menu, fallback
        self.resolver = Resolver(bindings)
        self.resolver.extractor = BindingExtractor()
        self._resolve_lock = asyncio.Lock()

    @property
    def supported_languages(self):
        return "*"

    def _reply(self, u, cid, text):
        r = intent.IntentResponse(language=u.language)
        r.async_set_speech(text)
        return conversation.ConversationResult(response=r, conversation_id=cid)

    def _handler(self, name):
        for h in intent.async_get(self.hass):
            if h.intent_type == name and type(h) is ScriptIntentHandler and "speech" in h.config and not any(k in h.config for k in ("action", "reprompt", "card")):
                return h
        return None

    async def _prepare_capabilities(self, u, available):
        # Only menu interaction triggers a lazy mapping refresh. Never execute
        # intent scripts for capability detection, or perform supplier I/O.
        if not self.resolver.needs_refresh(u.language):
            return
        async with self._resolve_lock:
            if not self.resolver.needs_refresh(u.language):
                return
            targets={}
            try:
                native=conversation.async_get_agent(self.hass,"conversation.home_assistant")
                recognize=getattr(native,"async_recognize_intent",None)
                triggers=getattr(native,"_trigger_intents_config",None)
                if callable(recognize) and isinstance(triggers,dict) and not triggers.get("intents"):
                    async with asyncio.timeout(3):
                        for cap in self.menu.capabilities.values():
                            if cap["intent"] not in available or cap.get("native_slots")!={"luxe_light_id":"light"} or cap["slots"].get("light_query")!="single_state":
                                continue
                            probe=conversation.ConversationInput(text=cap["sentence"],context=u.context,conversation_id=None,device_id=u.device_id,satellite_id=u.satellite_id,language=u.language,agent_id="conversation.home_assistant")
                            result=await recognize(probe,strict_intents_only=True)
                            if result is not None and not result.unmatched_entities and result.intent.name==cap["intent"]:
                                slots={x.name:x.value for x in result.entities_list}
                                if _slots_match(slots,cap["slots"],cap["native_slots"]):
                                    targets[cap["category"]]=slots["luxe_light_id"]
            except Exception:
                _LOGGER.debug("Nexora capability mapping deferred",exc_info=True)
            self.resolver.replace_targets(u.language,targets)

    async def async_process(self, u):
        cid = u.conversation_id or uuid4().hex
        key = (u.context.user_id, u.device_id, u.satellite_id, cid)
        handlers = [h for h in intent.async_get(self.hass) if type(h) is ScriptIntentHandler and "speech" in h.config and not any(k in h.config for k in ("action", "reprompt", "card"))]
        available = {h.intent_type for h in handlers}
        changed = self.resolver.extractor.refresh(handlers)
        if "LuxeLightQuery" in changed:
            self.resolver.targets.clear()
            self.resolver.modes.clear()
            self.resolver.invalidate()
        from .menu import HELP, BACK, NEXT, PREV, TRANSLATE
        t=u.text.strip().casefold().translate(TRANSLATE)
        if t in HELP|BACK|NEXT|PREV or t in self.menu.aliases or re.fullmatch(r"[1-8](?:\.[1-8])*",t):
            await self._prepare_capabilities(u,available)
        get_state=getattr(getattr(self.hass,"states",None),"get",lambda _:None)
        statuses={}
        def visible(cap):
            cid=cap["id"]
            if cid not in statuses:
                statuses[cid]=cap["intent"] in available and self.resolver.status(cap,get_state)!="hidden"
            return statuses[cid]
        reply = self.menu.route(key, u.text, visible, today=dt_util.now().date())
        if reply is None:
            self.menu.followups.clear(key)
            try:
                agent = conversation.async_get_agent(self.hass, self.fallback)
            except (KeyError, ValueError):
                agent = None
            if agent is None or agent is self or self.fallback == self.entry_id:
                return self._reply(u, cid, "备用对话代理配置错误。")
            return await conversation.async_converse(self.hass, text=u.text, conversation_id=u.conversation_id, context=u.context, language=u.language, agent_id=self.fallback, device_id=u.device_id, satellite_id=u.satellite_id, extra_system_prompt=u.extra_system_prompt)
        if reply.capability is None:
            return self._reply(u, cid, reply.text)
        self.menu.followups.clear(key)
        cap = self.menu.capabilities[reply.capability]
        handler = self._handler(cap["intent"])
        if handler is None:
            return self._reply(u, cid, "只读查询配置不可用，请检查意图库。")
        try:
            async with asyncio.timeout(5):
                # Fail closed if HA recognition APIs or sentence-trigger registry differ.
                native = conversation.async_get_agent(self.hass, "conversation.home_assistant")
                recognize = getattr(native, "async_recognize_intent", None)
                triggers = getattr(native, "_trigger_intents_config", None)
                if not callable(recognize) or not isinstance(triggers, dict) or triggers.get("intents"):
                    return self._reply(u, cid, "本地严格识别不可用，请检查 HA 版本或句式触发器。")
                probe = conversation.ConversationInput(text=reply.sentence, context=u.context, conversation_id=None, device_id=u.device_id, satellite_id=u.satellite_id, language=u.language, agent_id="conversation.home_assistant")
                result = await recognize(probe, strict_intents_only=True)
                if result is None or result.unmatched_entities or result.intent.name != cap["intent"]:
                    return self._reply(u, cid, "该问句与已安装意图库不匹配，请检查版本。")
                recognized = {item.name: item.value for item in result.entities_list}
                expected = reply.slots
                if not _slots_match(recognized, expected, cap.get("native_slots", {})) or self._handler(cap["intent"]) is not handler:
                    return self._reply(u, cid, "查询参数与已安装意图库不一致，请检查版本。")
                if cap.get("native_slots"):
                    mapped=self.resolver.targets.get(cap["category"])
                    if mapped is not None and mapped!=recognized["luxe_light_id"]:
                        self.resolver.invalidate()
                        return self._reply(u,cid,"该查询目标已变化，请发送 help 刷新菜单。")
                if self.resolver.status(cap,get_state)=="hidden":
                    return self._reply(u,cid,"该查询已不可用，请发送 help 刷新菜单。")
                # No await between handler identity validation and dispatch.
                response = await intent.async_handle(self.hass, "conversation", cap["intent"], {k:{"value":v,"text":str(v)} for k,v in recognized.items()}, reply.sentence, u.context, u.language, assistant="conversation", conversation_agent_id="conversation.home_assistant")
        except Exception:
            _LOGGER.debug("Nexora local query failed", exc_info=True)
            return self._reply(u, cid, "本地查询暂时失败，请稍后重试。")
        if response.as_dict().get("response_type")=="action_done":
            self.menu.followups.remember(key,reply.capability)
        return conversation.ConversationResult(response=response, conversation_id=cid)
