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
    if (key.family,key.target,key.metric)==("home","all","overview"):
        return re.sub(r"(?<=。)(?=(?:入户门锁：|\d+组灯光中，|已监测家电运行：|\d+个有效监测区域平均温度：|未确认到异常，但部分项目无法核实；))","\n",value)
    return value
