"""Execute only strictly validated, registered speech-only intents.

The HA API objects are supplied by the adapter; this layer does not route,
manage conversations, or fall back to another agent.
"""
import asyncio
import re
from dataclasses import dataclass
from typing import Any


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

@dataclass(frozen=True)
class ExecutionResult:
    response: Any = None
    error: str | None = None


async def execute_readonly(*, hass, conversation_api, intent_api, handler_for,
                           resolver, cap, reply, u, get_state, logger, current=lambda:True):
    """Validate the installed handler and slots immediately before dispatch."""
    handler = handler_for(cap["intent"])
    if handler is None:
        return ExecutionResult(error="只读查询配置不可用，请检查意图库。")
    try:
        async with asyncio.timeout(5):
            # Fail closed if HA recognition APIs or sentence-trigger registry differ.
            native = conversation_api.async_get_agent(hass, "conversation.home_assistant")
            recognize = getattr(native, "async_recognize_intent", None)
            triggers = getattr(native, "_trigger_intents_config", None)
            if not callable(recognize) or not isinstance(triggers, dict) or triggers.get("intents"):
                return ExecutionResult(error="本地严格识别不可用，请检查 HA 版本或句式触发器。")
            probe = conversation_api.ConversationInput(text=reply.sentence, context=u.context, conversation_id=None, device_id=u.device_id, satellite_id=u.satellite_id, language=u.language, agent_id="conversation.home_assistant")
            result = await recognize(probe, strict_intents_only=True)
            if result is None or result.unmatched_entities or result.intent.name != cap["intent"]:
                return ExecutionResult(error="该问句与已安装意图库不匹配，请检查版本。")
            recognized = {item.name: item.value for item in result.entities_list}
            if len(recognized)!=len(result.entities_list):
                return ExecutionResult(error="查询参数重复，请检查已安装意图库。")
            expected = reply.slots
            if not _slots_match(recognized, expected, cap.get("native_slots", {})) or handler_for(cap["intent"]) is not handler:
                return ExecutionResult(error="查询参数与已安装意图库不一致，请检查版本。")
            if cap.get("native_slots"):
                mapped=resolver.targets.get(cap["category"])
                if mapped is not None and mapped!=recognized["luxe_light_id"]:
                    resolver.invalidate()
                    return ExecutionResult(error="该查询目标已变化，请发送 help 刷新菜单。")
            if resolver.status(cap,get_state)=="hidden":
                return ExecutionResult(error="该查询已不可用，请发送 help 刷新菜单。")
            if not current():
                return ExecutionResult(error="查询会话已更新。")
            # No await between handler identity validation and dispatch.
            response = await intent_api.async_handle(hass, "conversation", cap["intent"], {k:{"value":v,"text":str(v)} for k,v in recognized.items()}, reply.sentence, u.context, u.language, assistant="conversation", conversation_agent_id="conversation.home_assistant")
    except Exception:
        logger.debug("Nexora local query failed", exc_info=True)
        return ExecutionResult(error="本地查询暂时失败，请稍后重试。")
    try:
        if not isinstance(response.as_dict(),dict):
            return ExecutionResult(error="本地查询未返回有效回复，请稍后重试。")
    except Exception:
        return ExecutionResult(error="本地查询未返回有效回复，请稍后重试。")
    return ExecutionResult(response=response)
