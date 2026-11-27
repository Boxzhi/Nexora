"""Route menu commands locally and preserve the existing conversation fallback."""
import asyncio
import logging
import re
from uuid import uuid4
from .capability import Resolver
from .binding_extractor import BindingExtractor
from .executor import _slot_equal, _slots_match, execute_readonly
from .router import Route, decide, is_menu_message
from .semantic import SemanticIndex

from homeassistant.components import conversation
from homeassistant.components.intent_script.helpers import ScriptIntentHandler
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

class NexoraAgent(conversation.AbstractConversationAgent):
    def __init__(self, hass, entry_id, menu, fallback, bindings=None):
        self.hass, self.entry_id, self.menu, self.fallback = hass, entry_id, menu, fallback
        self.resolver = Resolver(bindings)
        self.resolver.extractor = BindingExtractor()
        self._resolve_lock = asyncio.Lock()
        self.semantic = SemanticIndex(menu)

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

    menu_protocol_version = 1
    context_protocol_version = 1
    semantic_protocol_version = 1

    def is_semantic_message(self, text):
        return self.semantic.match(text) is not None

    async def async_process_semantic(self, u):
        if not self.is_semantic_message(u.text):
            return self._reply(u, u.conversation_id or uuid4().hex, "查询能力已变化，请发送 help。")
        return await self._async_process(u, menu_only=True)

    def is_menu_message(self, text):
        if is_menu_message(self.menu, text):
            return True
        if not isinstance(text, str):
            return False
        return self.menu.followups.is_followup_message(text.strip().casefold())

    def begin_fast_context(self, conversation_id):
        """Reserve a transport query for a non-user HA Context() session."""
        key=(None,None,None,conversation_id)
        token=self.menu.followups.begin(key)
        self.menu.followups.clear(key)
        return token

    def finish_fast_context(self, conversation_id, token, intent_type, slots):
        """Capture only an exact registered, available fixed utility capability.

        Called by a trusted transport only after a successful strict native query.
        No response text is parsed and no intent is executed here.
        """
        key=(None,None,None,conversation_id)
        if not self.menu.followups.is_current(key,token) or intent_type!="LuxeUtilityQuery":
            return False
        if self._handler(intent_type) is None:
            return False
        candidates=[cap for cap in self.menu.capabilities.values()
                    if cap["intent"]==intent_type and not cap.get("parameter")
                    and _slots_match(slots,cap["slots"],cap.get("native_slots",{}))
                    and self.menu._available(cap["id"],lambda c:True)]
        if len(candidates)!=1:
            return False
        return self.menu.followups.complete(key,token,candidates[0]["id"])

    async def async_process_menu(self, u):
        """Local-only entrypoint for an ordered transport menu lane."""
        if not self.is_menu_message(u.text):
            return self._reply(u, u.conversation_id or uuid4().hex, "非菜单指令，请重新发送 help。")
        return await self._async_process(u, menu_only=True)

    async def async_process(self, u):
        return await self._async_process(u)

    async def _async_process(self, u, *, menu_only=False):
        cid = u.conversation_id or uuid4().hex
        key = (u.context.user_id, u.device_id, u.satellite_id, cid)
        generation = self.menu.followups.begin(key)
        handlers = [h for h in intent.async_get(self.hass) if type(h) is ScriptIntentHandler and "speech" in h.config and not any(k in h.config for k in ("action", "reprompt", "card"))]
        available = {h.intent_type for h in handlers}
        changed = self.resolver.extractor.refresh(handlers)
        if "LuxeLightQuery" in changed:
            self.resolver.targets.clear()
            self.resolver.modes.clear()
            self.resolver.invalidate()
        from .menu import HELP, BACK, NEXT, PREV, TRANSLATE
        t=u.text.strip().casefold().translate(TRANSLATE)
        semantic_match = self.semantic.match(u.text)
        needs_native = (semantic_match is not None and semantic_match.capability is not None
                        and self.menu.capabilities[semantic_match.capability].get("native_slots"))
        if needs_native or t in HELP|BACK|NEXT|PREV or t in self.menu.aliases or re.fullmatch(r"[1-8](?:\.[1-8])*",t):
            await self._prepare_capabilities(u,available)
        get_state=getattr(getattr(self.hass,"states",None),"get",lambda _:None)
        statuses={}
        def visible(cap):
            cid=cap["id"]
            if cid not in statuses:
                statuses[cid]=cap["intent"] in available and self.resolver.status(cap,get_state)!="hidden"
            return statuses[cid]
        if not self.menu.followups.is_current(key,generation):
            return self._reply(u,cid,"查询会话已更新，请重新发送。")
        decision = decide(self.menu, key, u.text, visible, today=dt_util.now().date(),
                          semantic=self.semantic, semantic_match=semantic_match)
        if decision.route is Route.FALLBACK:
            if menu_only:
                return self._reply(u, cid, "当前没有待输入的菜单参数，请发送 help。")
            self.menu.followups.clear(key)
            try:
                agent = conversation.async_get_agent(self.hass, self.fallback)
            except (KeyError, ValueError):
                agent = None
            if agent is None or agent is self or self.fallback == self.entry_id:
                return self._reply(u, cid, "备用对话代理配置错误。")
            return await conversation.async_converse(self.hass, text=u.text, conversation_id=u.conversation_id, context=u.context, language=u.language, agent_id=self.fallback, device_id=u.device_id, satellite_id=u.satellite_id, extra_system_prompt=u.extra_system_prompt)
        reply = decision.reply
        if decision.route is Route.LOCAL_REPLY:
            return self._reply(u, cid, reply.text)
        self.menu.followups.clear(key)
        cap = self.menu.capabilities[reply.capability]
        execution = await execute_readonly(
            hass=self.hass, conversation_api=conversation, intent_api=intent,
            handler_for=self._handler, resolver=self.resolver, cap=cap,
            reply=reply, u=u, get_state=get_state, logger=_LOGGER,
        )
        if execution.error is not None:
            return self._reply(u, cid, execution.error)
        response = execution.response
        if response.as_dict().get("response_type")=="action_done":
            self.menu.followups.complete(key,generation,reply.capability)
        return conversation.ConversationResult(response=response, conversation_id=cid)
