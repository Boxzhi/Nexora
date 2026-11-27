"""Conservative presentation of known Home intent replies."""
import re
from .reply_format import split_clauses

_ROOM=r"[^：；。，\n]{1,30}"
_TEMP=r"-?\d+(?:\.\d+)?℃"
_HUM=r"\d+(?:\.\d+)?%"
_ENV=re.compile(r"("+_ROOM+r")温度：("+_TEMP+r")，\1湿度：("+_HUM+r")")
_AVG=re.compile(r"(\d+)个有效监测区域平均温度：("+_TEMP+r")。(\d+)个有效监测区域平均湿度：("+_HUM+r")。")
_FIELD=re.compile(r"[^：；。\n]{1,60}：[^；\n]+")

def format_home(metric,value):
    parts=split_clauses(value)
    if not parts or len(parts)<2:
        return value
    if metric=="env":
        rooms=[_ENV.fullmatch(p) for p in parts[:-1]]
        avg=_AVG.fullmatch(parts[-1])
        if avg and all(rooms) and len({m[1] for m in rooms})==len(rooms):
            return "\n".join([m[1]+"："+m[2]+" / "+m[3] for m in rooms]+[
                "", "平均温度："+avg[2]+"（"+avg[1]+"个有效监测区域）",
                "平均湿度："+avg[4]+"（"+avg[3]+"个有效监测区域）"])
        return value
    if metric=="family":
        if (parts[0].startswith("家庭Wi-Fi：") and
                all(re.match(r"(?:\d+位未连接：|未配置：)",p) for p in parts[1:]) and
                parts[-1].endswith("Wi-Fi仅供在家判断参考。")):
            return "\n".join(parts).replace("。Wi-Fi仅供在家判断参考。","。\nWi-Fi仅供在家判断参考。")
        return value
    if metric in {"presence_all","lux_all","water_all","batteries","battery_low","curtains"}:
        if all(_FIELD.fullmatch(p) for p in parts):
            return "\n".join(parts)
    return value


def format_overview(value):
    """Group the known six-part home summary, keeping every source sentence."""
    if not value.startswith("家庭Wi-Fi："):
        return value
    # The boundaries are anchored to sentence endings, not arbitrary substrings.
    pattern=r"(?<=。)\s*(?=入户门锁：|\d+组灯光(?:中，|均已)|已监测家电运行：|\d+个有效监测区域平均温度：|未确认到异常，但部分项目无法核实；)"
    parts=re.split(pattern,value)
    checks=("家庭Wi-Fi：","入户门锁：",r"\d+组灯光(?:中，|均已)","已监测家电运行：",r"\d+个有效监测区域平均温度：","未确认到异常，但部分项目无法核实；")
    if len(parts)!=len(checks) or not all(re.match(p,t) for p,t in zip(checks,parts)):
        return re.sub(pattern,"\n",value)
    labels=("家庭成员","门锁","灯光","家电","室内环境","安全及异常")
    return "\n\n".join(label+"\n"+part for label,part in zip(labels,parts))

def _room_fields(text,pattern):
    result={}
    for line in text.splitlines():
        m=re.fullmatch(pattern,line.removesuffix("。"))
        if not m or m[1] in result:
            return None
        result[m[1]]=m[2]
    return result or None

def presence_overview(rows):
    """Merge two explicitly attributed room lists, without estimating values."""
    metrics={s.key.metric:(kind,text) for s,kind,text in rows
             if s.key.family=="home" and s.key.target=="all"}
    if len(rows)!=4 or set(metrics)!={"presence_all","lux_all","lux_max","lux_min"}:
        return None
    a,b=metrics["presence_all"],metrics["lux_all"]
    if a[0]!="ok" or b[0]!="ok":
        return None
    states=_room_fields(a[1],r"([^：；。\n]+)：(未检测到人体|已检测到人体|检测到人体)")
    lux=_room_fields(b[1],r"([^：；。\n]+)：(\d+(?:\.\d+)?)勒克斯")
    if not states or not lux or set(states)!=set(lux):
        return None
    lines=[room+"："+state+" · "+lux[room]+" lx" for room,state in states.items()]
    lines.extend(("",metrics["lux_max"][1],metrics["lux_min"][1]))
    return lines

def environment_overview(rows):
    """Separate averages from extrema; retain their valid-region qualifiers."""
    metrics=[s.key.metric for s,_,_ in rows]
    if metrics!=["env","temp_max","temp_min","hum_max","hum_min"] or any(
            s.key.family!="home" or s.key.target!="all" for s,_,_ in rows):
        return None
    lines=[rows[0][2],""]
    patterns={
        "temp_max":("温度最高","最高温度"),"temp_min":("温度最低","最低温度"),
        "hum_max":("湿度最高","最高湿度"),"hum_min":("湿度最低","最低湿度"),
    }
    # Only abbreviate the exact known extremum sentence; unknown shapes
    # and data gaps remain untouched.
    for step,kind,text in rows[1:]:
        source,label=patterns[step.key.metric]
        unit=r"℃" if step.key.metric.startswith("temp") else "%"
        m=re.fullmatch(re.escape(source)+r"的有效监测区域：([^。\n]+)，(-?\d+(?:\.\d+)?"+unit+r")。",text)
        if kind=="ok" and m:
            text=label+"（有效区域）："+m[1]+" "+m[2]
        lines.append(text)
    return lines
