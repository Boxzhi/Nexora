"""Pure route classification; no intent execution or fallback side effects."""
from dataclasses import dataclass
import re
from .menu import RESERVED, TRANSLATE
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


def is_menu_message(menu, text):
    """Classify reserved menu syntax without reading or mutating sessions.

    Numeric inputs, paths and date-like parameters are reserved menu input.
    A queued parameter may arrive before its preceding prompt is executed.
    Free-form questions and follow-ups remain on the ordinary route.
    """
    if not isinstance(text, str):
        return False
    t = text.strip().casefold().translate(TRANSLATE)
    return (t in RESERVED or t in menu.aliases
            or re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", t) is not None
            or re.fullmatch(r"[0-9]{1,4}(?:-[0-9]{1,2}){1,2}", t) is not None)
