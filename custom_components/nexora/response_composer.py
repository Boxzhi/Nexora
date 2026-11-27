"""Render actual read-only outcomes; never reconstruct facts from guessed values."""
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Composed:
    text: str
    primary_completed: bool

def normalize_speech(k, speech):
    """Shared formatter for registered read-only speech, not menus or AI."""
    value=speech.strip()
    # Only this known duplicate label at the metric boundary is redundant.
    # Do not rewrite arbitrary text, numeric values or units.
    if (k.family,k.target,k.metric)==("utility","g","balance"):
        value=value.replace("燃气燃气账户余额","燃气账户余额",1)
    if (k.family,k.target,k.metric)==("home","all","overview"):
        # Keep every original sentence and qualification, only add paragraph
        # boundaries at known section starts.
        value=re.sub(r"(?<=。)(?=(?:入户门锁：|\d+组灯光中，|已监测家电运行：|\d+个有效监测区域平均温度：|未确认到异常，但部分项目无法核实；))","\n",value)
    return value

def _clean(outcome):
    return normalize_speech(outcome.step.key,outcome.speech)

def format_response(key,response):
    """Preserve the original IntentResponse and metadata; plain speech only."""
    data=response.as_dict()
    if data.get("response_type")!="action_done":
        return response
    speech=data.get("speech",{})
    if not isinstance(speech,dict) or set(speech)!={"plain"}:
        return response
    plain=speech["plain"]
    if not isinstance(plain,dict) or "speech" not in plain or not set(plain)<={"speech","extra_data"}:
        return response
    value=plain["speech"]
    if isinstance(value,str) and value.strip():
        cleaned=normalize_speech(key,value)
        if cleaned!=value:
            if "extra_data" in plain:
                response.async_set_speech(cleaned,extra_data=plain["extra_data"])
            else:
                response.async_set_speech(cleaned)
    return response


def _scene_text(plan,run):
    """Fuse only exact, complete, correctly scoped known reply contracts.

    A new or partial source reply is rendered verbatim by the ordinary
    composer. Never turn missing readings or a zero count into assurances.
    """
    if plan.focus is None:
        return None
    steps=plan.primary+plan.supplements
    if len(run.outcomes)!=len(steps) or {o.step for o in run.outcomes}!=set(steps):
        return None
    if any(o.kind not in {"ok","state_limit"} or not o.speech.strip() for o in run.outcomes):
        return None
    if any(s.params for s in steps):
        return None
    by_metric={o.step.key.metric:o.speech.strip() for o in run.outcomes}
    keys={(s.key.family,s.key.target,s.key.metric) for s in steps}
    f=plan.focus
    subject=f.subject
    if subject.family=="appliance" and subject.target=="w" and f.goal=="progress" and not plan.caveat and keys=={("appliance","w",m) for m in ("status","phase","remaining")}:
        a=re.fullmatch(r"海尔洗衣机正在运行，程序：([^。；，\n]+)。",by_metric["status"])
        b=re.fullmatch(r"海尔洗衣机洗涤阶段：([^。；，\n]+)。",by_metric["phase"])
        c=re.fullmatch(r"海尔洗衣机正在运行，设备报告剩余时间：(\d+分钟|\d+小时(?:\d+分钟)?)。",by_metric["remaining"])
        if a and b and c:
            return f"海尔洗衣机正在运行{a[1]}程序，目前处于{b[1]}阶段，设备报告剩余{c[1]}。"
    if subject.family=="appliance" and subject.target=="p" and f.goal=="overview" and not plan.caveat and keys=={("appliance","p",m) for m in ("status","filters","replace")}:
        a=re.fullmatch(r"米家净水器：(待机中|制水中)。",by_metric["status"])
        b=re.fullmatch(r"米家净水器PPC滤芯剩余(\d+(?:\.\d+)?)%，RO滤芯剩余(\d+(?:\.\d+)?)%。",by_metric["filters"])
        c=by_metric["replace"]
        if a and b and c=="米家净水器：PPC滤芯当前未达更换提醒阈值；RO滤芯当前未达更换提醒阈值。":
            return f"米家净水器{a[1]}。\nPPC滤芯剩余{b[1]}%，RO滤芯剩余{b[2]}%，均未达到更换提醒阈值。"
    if subject.family=="appliance" and subject.target in {"m","s"} and f.goal=="temperature_unspecified" and not plan.caveat and keys=={("appliance",subject.target,m) for m in ("target","temp")}:
        name={"m":"主卧空调","s":"次卧空调"}[subject.target]
        a=by_metric["target"]
        b=re.fullmatch(re.escape(name)+r"设备报告室温：(-?\d+(?:\.\d+)?)℃（空调已关闭，读数可能未实时刷新）。",by_metric["temp"])
        if a==name+"已关闭，无当前运行参数。" and b:
            return f"{name}已关闭，暂无运行设定温度。最近报告室温{b[1]}℃，读数可能未实时刷新。"
    if subject.family=="home" and subject.target=="阳台" and f.goal=="brightness_unspecified" and keys=={("home","阳台","lux"),("lights","yang_tai","list_on")} and plan.caveat=="环境光照度与灯具开关状态是不同指标。":
        a=re.fullmatch(r"阳台光照度：(\d+(?:\.\d+)?)勒克斯。",by_metric["lux"])
        b=re.fullmatch(r"阳台(\d+)组灯具均已关闭。",by_metric["list_on"])
        if a and b:
            return f"阳台环境光照度为{a[1]}勒克斯，{b[1]}组灯具均已关闭。"
    return None

def compose(plan,run,label):
    if run.superseded:
        return Composed("查询会话已更新，请重新发送。",False)
    fused=_scene_text(plan,run)
    if fused is not None:
        return Composed(fused,True)
    by_step={o.step:o for o in run.outcomes}
    lines=[]
    # Duplicate responses across different subjects, dates or accounts
    # must keep their attribution. Within a scene only an identical
    # state-limit message is safe to collapse across different metrics.
    same={}
    for outcome in run.outcomes:
        if outcome.kind in {"ok","data_gap","state_limit"} and outcome.speech:
            same.setdefault(_clean(outcome),[]).append(outcome)
    # Error messages retain the corresponding registered query label.
    def append(value):
        if value and value not in lines:
            lines.append(value)
    if plan.caveat:
        append(plan.caveat)
    primary_ok=True
    for step in plan.primary+plan.supplements:
        outcome=by_step.get(step)
        if outcome is None or outcome.kind=="error" or outcome.kind=="superseded":
            append(label(step)+"："+(outcome.error if outcome and outcome.error else "查询未完成。"))
            if step in plan.primary:
                primary_ok=False
            continue
        if outcome.kind=="skipped":
            if step in plan.primary:
                append(label(step)+"：查询未完成。")
                primary_ok=False
            continue
        if outcome.kind not in {"ok","data_gap","state_limit"}:
            append(label(step)+"：查询未完成。")
            if step in plan.primary:
                primary_ok=False
            continue
        value=_clean(outcome)
        if not value:
            append(label(step)+"：没有有效回复。")
            if step in plan.primary:
                primary_ok=False
        else:
            duplicates=same.get(value,[])
            scopes={(o.step.key.family,o.step.key.target,o.step.key.account,o.step.key.period,o.step.params) for o in duplicates}
            if len(duplicates)>1 and (len(scopes)>1 or any(o.kind!="state_limit" for o in duplicates)):
                append(label(step)+"："+value)
            else:
                append(value)
    return Composed("\n".join(lines) or "没有可用的查询结果。",primary_ok)
