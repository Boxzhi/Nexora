"""Shared plain-text presentation; no facts, thresholds or device inference."""
import re

_BRACKETS={"（":"）","(":")","[":"]","【":"】","{":"}"}
_CLOSERS=frozenset(_BRACKETS.values())

def split_clauses(value,separators="；;"):
    """Split only top-level delimiters, or reject an unfamiliar structure."""
    if not isinstance(value,str) or not value.strip() or "\n" in value:
        return None
    stack=[]
    parts=[]
    start=0
    for i,ch in enumerate(value):
        if ch in _BRACKETS:
            stack.append(_BRACKETS[ch])
        elif ch in _CLOSERS:
            if not stack or stack.pop()!=ch:
                return None
        elif ch in separators and not stack:
            part=value[start:i].strip()
            if not part:
                return None
            parts.append(part)
            start=i+1
    final=value[start:].strip()
    if stack or not final:
        return None
    return tuple(parts+[final])

def reflow_clauses(value,accept,separators="；;"):
    """Reflow only when every clause satisfies the same explicit contract."""
    parts=split_clauses(value,separators)
    if not parts or len(parts)<2 or not all(accept(p) for p in parts):
        return value
    return "\n".join(parts)

def render_lines(lines,empty="没有可用的查询结果。"):
    # Keep intentional blank lines and do not globally deduplicate.
    rows=list(lines)
    return "\n".join(rows) if rows else empty

def render_section(title,lines):
    return title+"\n\n"+render_lines(lines)

def format_known(key,value):
    """Dispatch verified multi-field contracts; unrecognized speech is unchanged."""
    if (key.family,key.target)==("utility","all") and key.metric in {"balances","debts","low","updates"}:
        from .utility_response import format_aggregate
        return format_aggregate(key.metric,value)
    if (key.family,key.target)==("appliance","ac") and key.metric in {"status","temp","target"}:
        m=re.fullmatch(r"(主卧空调[^。\n]+。)(次卧空调[^。\n]+。)",value)
        if m:
            return "\n".join(m.groups())
    if key.family=="home" and key.metric in {"lux","lux_all","lux_max","lux_min"}:
        from .home_response import format_home, format_lux
        if key.target=="all" and key.metric=="lux_all":
            value=format_home(key.metric,value)
        return format_lux(key.metric,value)
    if key.family=="home" and key.target=="all" and key.metric in {"env","family","presence_all","water_all","batteries","battery_low","curtains"}:
        from .home_response import format_home
        return format_home(key.metric,value)
    if (key.family,key.target,key.metric)==("home","all","overview"):
        from .home_response import format_overview
        return format_overview(value)
    return value
