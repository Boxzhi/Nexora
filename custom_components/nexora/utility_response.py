"""Verified utility reply contracts; never derive arrears from a balance."""
import re
from .reply_format import split_clauses

AMOUNT=r"(?:-?\d+(?:\.\d+)?元|数据不可用)"
NAME=r"[^：:。；;，,\n]{1,60}?"
BALANCE=re.compile(r"("+NAME+r")余额[：:]?("+AMOUNT+r")")
COLON_BALANCE=re.compile(r"("+NAME+r")[：:]("+AMOUNT+r")")
FIELD=re.compile(r"("+NAME+r")[：:]([^\n]+)")
LOW=re.compile(r"("+NAME+r")[：:]("+AMOUNT+r")，([^\n]+)")
UPDATE=re.compile(r"[^：:。；;\n]{1,80}(?:更新时间|抓取时间)[：:](?:\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}|数据不可用)")

def _owner(value):
    if value in {"燃气","燃气费"}:
        return "燃气费"
    if value in {"水务","水费"}:
        return "水费"
    if value.endswith("电费") and len(value)>2:
        return value
    return None

def _parts(value):
    if "\n" in value:
        parts=value.splitlines()
        if not parts or any(not p.strip() for p in parts):
            return None
        return tuple(p.strip() for p in parts)
    return split_clauses(value)

def parse_aggregate(metric,value):
    parts=_parts(value)
    if not parts:
        return None
    result={}
    for part in parts:
        raw=part.removesuffix("。")
        if metric=="balances":
            m=BALANCE.fullmatch(raw) or COLON_BALANCE.fullmatch(raw)
        elif metric=="debts":
            m=FIELD.fullmatch(raw)
        elif metric=="low":
            m=LOW.fullmatch(raw)
        else:
            return None
        if not m:
            return None
        name=_owner(m[1])
        if not name or name in result:
            return None
        result[name]=tuple(m.groups()[1:])
    return result

def format_aggregate(metric,value):
    if metric=="updates":
        parts=_parts(value)
        if parts and len(parts)>1 and all(UPDATE.fullmatch(p.removesuffix("。")) for p in parts):
            return "\n".join(parts)
        return value
    data=parse_aggregate(metric,value)
    if not data:
        return value
    return "\n".join(name+"："+"，".join(fields) for name,fields in data.items())

def summary_rows(rows):
    """Merge only complete, consistent account sets from three registered replies."""
    metrics={"balances","debts","low"}
    if len(rows)!=3 or any(kind not in {"ok","partial_data","data_gap"} for _,kind,_ in rows):
        return None
    scopes={(s.key.family,s.key.target,s.key.account,s.key.period,s.params) for s,_,_ in rows}
    if len(scopes)!=1 or next(iter(scopes))[:2]!=("utility","all"):
        return None
    if {s.key.metric for s,_,_ in rows}!=metrics:
        return None
    parsed={s.key.metric:parse_aggregate(s.key.metric,text) for s,_,text in rows}
    if any(not v for v in parsed.values()):
        return None
    balances,debts,low=(parsed[m] for m in ("balances","debts","low"))
    if set(balances)!=set(debts) or set(balances)!=set(low):
        return None
    if any(balances[name][0]!=low[name][0] for name in balances):
        return None
    lines=[]
    for name,(amount,) in balances.items():
        if lines:
            lines.append("")
        lines.extend((name+"："+amount,debts[name][0]+"；"+low[name][1]))
    return lines
