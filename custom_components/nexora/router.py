"""Classify local replies and queries without executing intents."""
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
    source: str = "local_menu"

def from_reply(reply,source="local_menu"):
    if reply is None:
        return RouteDecision(Route.FALLBACK)
    return RouteDecision(Route.LOCAL_REPLY if reply.capability is None else Route.LOCAL_QUERY,reply,source)

def decide(menu,key,text,visible,*,today):
    """Menu, parameter and follow-up handling always precedes native recognition."""
    return from_reply(menu.route(key,text,visible,today=today))
