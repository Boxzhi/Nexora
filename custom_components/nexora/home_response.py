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
