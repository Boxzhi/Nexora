"""Route menu commands locally and preserve the existing conversation fallback."""
import asyncio
import logging
from uuid import uuid4
from .capability import Resolver
from .binding_extractor import BindingExtractor
from .executor import _slot_equal, _slots_match, execute_readonly, ExecutionResult
from .router import Route, RouteDecision, decide, from_reply
from .semantic import SemanticIndex, normalize
from .semantic_lexicon import describe
from .business_model import QueryKey
from .query_planner import QueryPlanner
from .query_context import QueryContext
from .plan_executor import run_plan, response_quality
from .response_composer import compose, format_response
from .transport_format import format_query_text, format_query_response
from .menu import Menu, PARAMETERS, parse_parameter
from .fallback import AIConversations, FallbackGuard, AI_PROMPT
from .diagnostics import RouteDiagnostics
from .diagnostic_ids import BUILTIN_IDS

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
        self.planner = self.query_context = None
        if isinstance(menu,Menu):
            try:
                self.planner=QueryPlanner(menu)
                self.query_context=QueryContext(self.planner,menu.clock,max_sessions=menu.max_sessions)
            except (ValueError,KeyError):
                # Invalid or incomplete custom registry must not prevent the
                # compatible legacy path from loading.
                self.planner=self.query_context=None
                _LOGGER.warning("Nexora structured query registry unavailable; retaining legacy routes",exc_info=True)

    @property
    def supported_languages(self):
        return "*"

    def _reply(self, u, cid, text, *, query=False):
        r = intent.IntentResponse(language=u.language)
        r.async_set_speech(format_query_text(cid,text) if query else text)
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
                                if len(slots)==len(result.entities_list) and _slots_match(slots,cap["slots"],cap["native_slots"]):
                                    targets[cap["category"]]=slots["luxe_light_id"]
            except Exception:
                _LOGGER.debug("Nexora capability mapping deferred",exc_info=True)
            self.resolver.replace_targets(u.language,targets)

    def _record(self,route,status,started):
        elapsed=self.route_diagnostics.record(route,status,started)
        _LOGGER.debug("Nexora route=%s status=%s elapsed_ms=%d",route,status,elapsed)

    def diagnostics_snapshot(self):
        return self.route_diagnostics.snapshot()

    def capability_snapshot(self):
        """Administrator diagnostic: no entity IDs, state values or templates.

        Native mappings are those from the last normal query/menu refresh.
        Downloading diagnostics itself does not recognize or execute intents.
        """
        available={h.intent_type for h in intent.async_get(self.hass)
                   if type(h) is ScriptIntentHandler and "speech" in h.config
                   and not any(k in h.config for k in ("action","reprompt","card"))}
        get_state=getattr(getattr(self.hass,"states",None),"get",lambda _:None)
        counts={"visible":0,"temporary":0,"hidden":0}
        details=[]
        for cid,cap in self.menu.capabilities.items():
            result=(self.resolver.assess(cap,get_state) if cap["intent"] in available
                else {"status":"hidden","reasons":[{"code":"intent_not_registered_readonly"}]})
            counts[result["status"]]+=1
            if result["status"]!="visible" or result["reasons"]:
                # Only built-in semantic IDs; omit user-provided catalog
                # labels and entity IDs. Custom IDs are not included.
                if cid in BUILTIN_IDS:
                    details.append({"capability":cid,**result})
                else:
                    details.append(result)
        return {"registered":sum(counts.values()),"counts":counts,
                "native_mapping_initialized":self.resolver.language is not None,
                "native_mapping_refresh_needed":self.resolver.needs_refresh(self.resolver.language),
                "template_schema_verified":sorted(self.resolver.extractor.data),
                "details":details}

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
            if result is None or result.intent.name not in INTENTS:
                return None
            from .menu import Reply
            def unresolved():
                return RouteDecision(Route.LOCAL_REPLY,Reply("已识别为本地查询，但查询参数不一致或未唯一注册，无法确认实际数据。请明确查询对象和指标，或发送 help。"),"local_native")
            if result.unmatched_entities:
                return unresolved()
            slots={item.name:item.value for item in result.entities_list}
            if len(slots)!=len(result.entities_list):
                return unresolved()
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
                return unresolved()
            cap,params=matches[0]
            if not self.menu._available(cap["id"],visible):
                from .menu import Reply
                return RouteDecision(Route.LOCAL_REPLY,Reply("该查询当前不可用，请发送 help。"),"local_native")
            return RouteDecision(Route.LOCAL_QUERY,self.menu._query(cap["id"],params),"local_native")
        except Exception:
            return None

    def _boundary(self,text,today):
        def known(q):
            index=getattr(self.menu,"scene_language",None)
            if index and index.match(q):
                return True
            if self.semantic.match(q,today=today) is not None:
                return True
            return bool(self.planner and self.planner.plan(q,today).plan)
        return self.fallback_guard.classify(text,known)

    def _structured(self,text,match,today):
        """Keep canonical/fixed/dynamic compatibility; widen broad aliases
        and explicit ambiguities only when a registered plan resolves them."""
        if self.planner is None:
            return None
        if match is not None and match.capability and (
                match.params or normalize(text) in self.semantic.exact):
            return None
        candidate=self.planner.plan(text,today)
        if match is None:
            return candidate
        if candidate.plan is None:
            return None
        if match.clarification is not None:
            # Only a recognized semantic scene can replace a legacy
            # clarification. Never suppress invalid-date/account warnings.
            if candidate.plan.focus and candidate.plan.focus.goal:
                return candidate
            return None
        plan=candidate.plan
        if (plan.focus and plan.focus.goal and len(plan.primary+plan.supplements)>1
                and match.capability in {step.capability for step in plan.primary}):
            return candidate
        return None

    async def _execute_query_plan(self,plan,u,cid,key,generation,today,available,visible,get_state,started):
        self.menu.followups.clear(key)
        members=plan.primary+plan.supplements
        current=lambda:self.menu.followups.is_current(key,generation)
        if any(self.menu.capabilities.get(step.capability,{}).get("native_slots") for step in members):
            await self._prepare_capabilities(u,available)
        async def dispatch(step):
            if not current():
                return ExecutionResult(error="查询会话已更新。")
            cap=self.menu.capabilities.get(step.capability)
            p=describe(cap) if cap else None
            if p is None or QueryKey(p.family,p.target,p.metric,p.period,p.parameter,p.account)!=step.key:
                return ExecutionResult(error="查询能力配置已变化。")
            if not self.menu._available(step.capability,visible):
                return ExecutionResult(error="该查询当前不可用。")
            params=dict(step.params)
            fields=PARAMETERS.get(p.parameter,())
            if len(params)!=len(step.params) or set(params)!=set(fields) or set(params)!=set(cap.get("parameter_slots",{})) or any(type(v) is not int for v in params.values()):
                return ExecutionResult(error="查询日期参数不一致。")
            if fields:
                try:
                    base_year=today.year+cap.get("parameter_year_offset",0)
                    validated=parse_parameter(p.parameter,"-".join(str(params[k]) for k in fields),today,base_year=base_year)
                    if validated!=params:
                        return ExecutionResult(error="查询日期参数不一致。")
                except (ValueError,KeyError,TypeError):
                    return ExecutionResult(error="查询日期无效。")
            reply=self.menu._query(step.capability,params)
            return await execute_readonly(hass=self.hass,conversation_api=conversation,intent_api=intent,
                handler_for=self._handler,resolver=self.resolver,cap=cap,reply=reply,u=u,
                get_state=get_state,logger=_LOGGER,current=current)
        run=await run_plan(plan,dispatch,current)
        def label(step):
            try:
                return self.menu._query(step.capability,dict(step.params)).sentence
            except (ValueError,KeyError):
                return "注册查询"
        composed=compose(plan,run,label)
        if not run.superseded:
            for outcome in run.outcomes:
                self._record("query_quality",outcome.kind,started)
        if composed.primary_completed and current():
            # A multi-metric scene retains its semantic goal, not an
            # arbitrary last result. For single steps preserve the legacy
            # follow-up engine as well.
            if len(members)==1:
                self.menu.followups.complete(key,generation,members[0].capability,dict(members[0].params),today)
            if self.query_context:
                self.query_context.remember(key,plan.focus,today,scene=True,current=current(),
                    menu_scene=plan.menu_scene,params=members[0].params if plan.menu_scene else ())
        self._record("local_menu_scene" if plan.title else "local_planner","completed" if composed.primary_completed else "error",started)
        return self._reply(u,cid,composed.text,query=True)

    async def async_process(self,u):
        """Standard HA Conversation Agent entry; no transport-specific protocols."""
        started=self.route_diagnostics.clock()
        cid=u.conversation_id or uuid4().hex
        key=(u.context.user_id,u.device_id,u.satellite_id,cid)
        generation=self.menu.followups.begin(key)
        prior=self.query_context.consume(key) if self.query_context else None
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
        alias=text in self.menu.aliases or text in getattr(self.menu,"scene_aliases",{})
        index=getattr(self.menu,"scene_language",None)
        scene_id=index.match(u.text) if index else None
        if text in HELP|BACK|NEXT|PREV or alias or scene_id or PATH_RE.fullmatch(text) or self.menu.followups.is_followup_message(text.rstrip("？?。！!").strip()):
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
        if prior and self.query_context:
            session=self.menu.sessions.get(key)
            from .menu import EXIT
            if not (session and session.pending) and text not in HELP|EXIT|BACK|NEXT|PREV and not text.isdecimal() and not alias and not scene_id and not PATH_RE.fullmatch(text):
                boundary=self._boundary(u.text,today)
                if boundary.kind not in {"cancelled","compound","control"}:
                    if prior.menu_scene:
                        await self._prepare_capabilities(u,available)
                        if not self.menu.followups.is_current(key,generation):
                            return self._reply(u,cid,"查询会话已更新，请重新发送。")
                    inherited=self.query_context.resolve_menu(u.text,prior,today,visible)
                    if not inherited.plan and not inherited.message:
                        inherited=self.query_context.resolve(u.text,prior,today)
                    if inherited.plan:
                        return await self._execute_query_plan(inherited.plan,u,cid,key,generation,today,available,visible,get_state,started)
                    if inherited.message:
                        self.menu.followups.clear(key)
                        self._record("local_planner","reply",started)
                        return self._reply(u,cid,inherited.message)
        # Only an exact, registered, fully scoped scene can override a
        # legacy single-metric match. All other input retains the old path.
        if scene_id and self._boundary(u.text,today).kind not in {"cancelled","compound","control"}:
            decision=from_reply(self.menu.select_scene(key,scene_id,visible),"local_scene_language")
        else:
            decision=decide(self.menu,key,u.text,visible,today=today)
        if decision.route is Route.LOCAL_SCENE:
            if self.planner is None:
                return self._reply(u,cid,"组合查询暂不可用，请发送 help 或直接查询具体指标。")
            try:
                plan=self.planner.menu_plan(decision.reply.scene,dict(decision.reply.params),visible,
                    self.query_context,today)
            except (ValueError,KeyError):
                self._record("local_menu_scene","error",started)
                return self._reply(u,cid,"组合查询当前不可用，请发送 help。")
            return await self._execute_query_plan(plan,u,cid,key,generation,today,available,visible,get_state,started)
        if decision.route is Route.FALLBACK:
            boundary=self._boundary(u.text,today)
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
            candidate=self._structured(u.text,match,today) if boundary.kind!="control" else None
            if candidate and candidate.plan:
                plan=candidate.plan
                native=await self._native_registered_query(u,visible,today,available)
                if not self.menu.followups.is_current(key,generation):
                    return self._reply(u,cid,"查询会话已更新，请重新发送。")
                if native is not None:
                    if native.route is Route.LOCAL_REPLY:
                        self._record("local_native","reply",started)
                        return self._reply(u,cid,native.reply.text)
                    compatible=any(native.reply.capability==step.capability and
                        native.reply.slots==self.menu._query(step.capability,dict(step.params)).slots
                        for step in plan.primary+plan.supplements)
                    if not compatible:
                        self._record("local_planner","reply",started)
                        return self._reply(u,cid,"原生识别与查询对象、指标或日期参数不一致，请明确查询内容。")
                return await self._execute_query_plan(plan,u,cid,key,generation,today,available,visible,get_state,started)
            if candidate and candidate.message:
                self.menu.followups.clear(key)
                self._record("local_planner","reply",started)
                return self._reply(u,cid,candidate.message)
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
        if ok and self.query_context and self.menu.followups.is_current(key,generation):
            params={k:reply.slots[v] for k,v in cap.get("parameter_slots",{}).items()}
            focus=self.query_context.from_registered(reply.capability,params,today)
            self.query_context.remember(key,focus,today,scene=False)
        if ok:
            p=describe(cap)
            if p is not None:
                semantic_key=QueryKey(p.family,p.target,p.metric,p.period,p.parameter,p.account)
                self._record("query_quality",response_quality(semantic_key,response),started)
                response=format_response(semantic_key,response)
        if ok:
            response=format_query_response(cid,response)
        self._record(route,"completed" if ok else "error",started)
        return conversation.ConversationResult(response=response, conversation_id=cid)
