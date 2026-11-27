"""Route menu commands locally and preserve the existing conversation fallback."""
import asyncio
import logging
from uuid import uuid4
from .capability import Resolver
from .binding_extractor import BindingExtractor
from .executor import _slot_equal, _slots_match, execute_readonly
from .router import Route, RouteDecision, decide, from_reply
from .semantic import SemanticIndex
from .fallback import AIConversations, FallbackGuard, AI_PROMPT
from .diagnostics import RouteDiagnostics

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
        self.fallback_guard = FallbackGuard(menu)
        self.ai_sessions = AIConversations()
        self.route_diagnostics = RouteDiagnostics()
        self.ai_timeout = 60

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
        # Menu or recognized light queries trigger a lazy mapping refresh. Never execute
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

    def _record(self,route,status,started):
        elapsed=self.route_diagnostics.record(route,status,started)
        _LOGGER.debug("Nexora route=%s status=%s elapsed_ms=%d",route,status,elapsed)

    def diagnostics_snapshot(self):
        return self.route_diagnostics.snapshot()

    async def _async_fallback(self,u,cid,key,started):
        boundary=self.fallback_guard.classify(u.text)
        if boundary.reply:
            self._record("guard","blocked",started)
            return self._reply(u,cid,boundary.reply)
        try:
            agent=conversation.async_get_agent(self.hass,self.fallback)
        except (KeyError,ValueError):
            agent=None
        if agent is None or agent is self or self.fallback==self.entry_id:
            self._record("ai","unavailable",started)
            return self._reply(u,cid,"备用对话代理配置错误。")
        reserved,ai_cid=self.ai_sessions.reserve(key)
        if not reserved:
            self._record("ai","busy",started)
            return self._reply(u,cid,"AI 对话正在处理，请稍后重试。")
        try:
            prompt="\n".join(filter(None,(u.extra_system_prompt,AI_PROMPT)))
            async with asyncio.timeout(self.ai_timeout):
                result=await conversation.async_converse(
                    self.hass,text=u.text,conversation_id=ai_cid,context=u.context,
                    language=u.language,agent_id=self.fallback,device_id=u.device_id,
                    satellite_id=u.satellite_id,extra_system_prompt=prompt)
            response=getattr(result,"response",None)
            if response is None:
                self.ai_sessions.fail(key)
                self._record("ai","invalid_response",started)
                return self._reply(u,cid,"AI 未返回有效回复，请稍后重试。")
            if response.as_dict().get("response_type")=="error":
                self.ai_sessions.fail(key)
                self._record("ai","error",started)
                return self._reply(u,cid,"AI 对话暂时不可用，请稍后重试。")
            returned_id=getattr(result,"conversation_id",None)
            self.ai_sessions.complete(key,returned_id if returned_id!=cid else None)
            self._record("ai","completed",started)
            return conversation.ConversationResult(response=response,conversation_id=cid,
                                                   continue_conversation=getattr(result,"continue_conversation",False))
        except TimeoutError:
            self.ai_sessions.fail(key)
            self._record("ai","timeout",started)
            return self._reply(u,cid,"AI 对话超时，请稍后重试。")
        except asyncio.CancelledError:
            self.ai_sessions.fail(key)
            self._record("ai","cancelled",started)
            raise
        except Exception:
            self.ai_sessions.fail(key)
            self._record("ai","error",started)
            return self._reply(u,cid,"AI 对话暂时不可用，请稍后重试。")
        finally:
            self.ai_sessions.release(key)

    async def _native_registered_query(self,u,visible,today,available):
        """Preserve exact registered native queries, without executing actions.

        Native recognition follows explicit menu and context handling.
        The result must uniquely identify a registered capability, and the
        canonical query is independently validated by the read-only executor.
        """
        from .menu import PARAMETERS, parse_parameter
        # Fixed-slot native synonyms must not regress when AI fallback is guarded.
        from .semantic import INTENTS
        candidates=[c for c in self.menu.capabilities.values()
                    if c.get("intent") in INTENTS and c.get("sentence")
                    and (not c.get("parameter") or
                         (c.get("parameter") in PARAMETERS and c.get("intent")=="LuxeUtilityQuery"))]
        if not candidates:
            return None
        try:
            native=conversation.async_get_agent(self.hass,"conversation.home_assistant")
            recognize=getattr(native,"async_recognize_intent",None)
            triggers=getattr(native,"_trigger_intents_config",None)
            if not callable(recognize) or not isinstance(triggers,dict) or triggers.get("intents"):
                return None
            probe=conversation.ConversationInput(text=u.text,context=u.context,conversation_id=None,
                device_id=u.device_id,satellite_id=u.satellite_id,language=u.language,agent_id="conversation.home_assistant")
            async with asyncio.timeout(3):
                result=await recognize(probe,strict_intents_only=True)
            if result is None or result.unmatched_entities or result.intent.name not in INTENTS:
                return None
            slots={item.name:item.value for item in result.entities_list}
            if result.intent.name=="LuxeLightQuery" and "luxe_light_id" in slots:
                await self._prepare_capabilities(u,available)
            matches=[]
            for cap in candidates:
                if cap["intent"]!=result.intent.name:
                    continue
                if not cap.get("parameter"):
                    if not _slots_match(slots,cap["slots"],cap.get("native_slots",{})):
                        continue
                    if cap.get("native_slots"):
                        # Match the original recognized entity, not merely its domain.
                        if self.resolver.targets.get(cap["category"])!=slots.get("luxe_light_id"):
                            continue
                    matches.append((cap,{}))
                    continue
                fields=PARAMETERS[cap["parameter"]]
                mapping=cap["parameter_slots"]
                values=[]
                for field in fields:
                    value=slots.get(mapping[field])
                    if type(value) is int:
                        values.append(str(value))
                    elif type(value) is str and value.isascii() and value.isdigit():
                        values.append(value)
                    else:
                        break
                if len(values)!=len(fields):
                    continue
                try:
                    params=parse_parameter(cap["parameter"],"-".join(values),today,
                        base_year=today.year-1 if cap.get("parameter_year_offset")==-1 else today.year)
                except ValueError:
                    continue
                expected={**cap["slots"],**{mapping[k]:v for k,v in params.items()}}
                if _slots_match(slots,expected,cap.get("native_slots",{})):
                    matches.append((cap,params))
            if len(matches)!=1:
                return None
            cap,params=matches[0]
            if not self.menu._available(cap["id"],visible):
                from .menu import Reply
                return RouteDecision(Route.LOCAL_REPLY,Reply("该查询当前不可用，请发送 help。"),"local_native")
            return RouteDecision(Route.LOCAL_QUERY,self.menu._query(cap["id"],params),"local_native")
        except Exception:
            return None

    async def async_process(self,u):
        """Standard HA Conversation Agent entry; no transport-specific protocols."""
        started=self.route_diagnostics.clock()
        cid=u.conversation_id or uuid4().hex
        key=(u.context.user_id,u.device_id,u.satellite_id,cid)
        generation=self.menu.followups.begin(key)
        handlers=[h for h in intent.async_get(self.hass)
                  if type(h) is ScriptIntentHandler and "speech" in h.config
                  and not any(k in h.config for k in ("action","reprompt","card"))]
        available={h.intent_type for h in handlers}
        changed=self.resolver.extractor.refresh(handlers)
        if "LuxeLightQuery" in changed:
            self.resolver.targets.clear()
            self.resolver.modes.clear()
            self.resolver.invalidate()
        from .menu import HELP,BACK,NEXT,PREV,TRANSLATE,PATH_RE
        text=u.text.strip().casefold().translate(TRANSLATE)
        if text in HELP|BACK|NEXT|PREV or text in self.menu.aliases or PATH_RE.fullmatch(text) or self.menu.followups.is_followup_message(text):
            await self._prepare_capabilities(u,available)
        get_state=getattr(getattr(self.hass,"states",None),"get",lambda _:None)
        def visible(cap):
            # Re-evaluate after a lazy light mapping refresh.
            return cap["intent"] in available and self.resolver.status(cap,get_state)!="hidden"
        if not self.menu.followups.is_current(key,generation):
            return self._reply(u,cid,"查询会话已更新，请重新发送。")
        # Always visit the menu state machine: independent messages cancel old
        # parameter prompts and clear stale business context before any await.
        today=dt_util.now().date()
        decision=decide(self.menu,key,u.text,visible,today=today)
        if decision.route is Route.FALLBACK:
            boundary=self.fallback_guard.classify(u.text)
            # Do not pass cancelled reads or compound query/control requests to
            # either native recognition or an action-capable fallback.
            if boundary.kind in {"cancelled","compound"}:
                self.menu.followups.clear(key)
                self._record("guard","blocked",started)
                return self._reply(u,cid,boundary.reply)
            match=self.semantic.match(u.text,today=today)
            if match is None and boundary.kind=="control":
                self.menu.followups.clear(key)
                return await self._async_fallback(u,cid,key,started)
            # Explicit ambiguity / invalid date is a local terminal reply even
            # if the native recognizer would otherwise pick an interpretation.
            if match is not None and match.clarification is not None:
                decision=from_reply(self.semantic.reply(match,visible),"local_semantic")
                if match.options:
                    self.menu.followups.remember_clarification(key,generation,match.options)
            else:
                native=await self._native_registered_query(u,visible,today,available)
                if not self.menu.followups.is_current(key,generation):
                    return self._reply(u,cid,"查询会话已更新，请重新发送。")
                if native is not None:
                    if (match is not None and native.route is Route.LOCAL_QUERY
                            and (native.reply.capability!=match.capability or
                                 native.reply.slots!=self.menu._query(match.capability,dict(match.params)).slots)):
                        # Native still has priority when the registered
                        # meaning agrees; conflicting meanings never execute.
                        from .menu import Reply
                        decision=from_reply(Reply("原生识别与查询对象、指标或日期参数不一致，请明确查询内容。"),"local_semantic")
                    else:
                        decision=native
                elif match is not None:
                    if match.capability and self.menu.capabilities[match.capability].get("native_slots"):
                        await self._prepare_capabilities(u,available)
                    if not self.menu.followups.is_current(key,generation):
                        return self._reply(u,cid,"查询会话已更新，请重新发送。")
                    decision=from_reply(self.semantic.reply(match,visible),"local_semantic")
        if decision.route is Route.FALLBACK:
            self.menu.followups.clear(key)
            # No local-state writes after this await; late AI replies cannot
            # restore old prompts or business context.
            return await self._async_fallback(u,cid,key,started)
        reply = decision.reply
        route=decision.source
        if decision.route is Route.LOCAL_REPLY:
            self._record(route,"reply",started)
            return self._reply(u, cid, reply.text)
        self.menu.followups.clear(key)
        cap = self.menu.capabilities[reply.capability]
        execution = await execute_readonly(
            hass=self.hass, conversation_api=conversation, intent_api=intent,
            handler_for=self._handler, resolver=self.resolver, cap=cap,
            reply=reply, u=u, get_state=get_state, logger=_LOGGER,
        )
        if execution.error is not None:
            self._record(route,"error",started)
            return self._reply(u, cid, execution.error)
        response = execution.response
        ok=response.as_dict().get("response_type")=="action_done"
        if ok:
            if cap.get("parameter"):
                params={k:reply.slots[v] for k,v in cap["parameter_slots"].items()}
                self.menu.followups.complete(key,generation,reply.capability,params,today)
            else:
                self.menu.followups.complete(key,generation,reply.capability)
        self._record(route,"completed" if ok else "error",started)
        return conversation.ConversationResult(response=response, conversation_id=cid)
