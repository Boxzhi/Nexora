"""Pure route classification; no intent execution or fallback side effects."""
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Route(str, Enum):
    LOCAL_REPLY = "local_reply"
    LOCAL_QUERY = "local_query"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    reply: Any = None


def decide(menu, key, text, visible, *, today):
    """Preserve the existing menu/follow-up precedence and state transitions."""
    reply = menu.route(key, text, visible, today=today)
    if reply is None:
        return RouteDecision(Route.FALLBACK)
    if reply.capability is None:
        return RouteDecision(Route.LOCAL_REPLY, reply)
    return RouteDecision(Route.LOCAL_QUERY, reply)
