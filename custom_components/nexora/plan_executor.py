"""Bounded async execution of registered, read-only plans.

The caller supplies the existing strict executor. This layer does not call
HA services, parse numeric values into facts, or authorize device control.
"""
import asyncio
from dataclasses import dataclass
import re

from .business_model import MAX_SCENE_QUERIES, STOP_CONDITIONS

@dataclass(frozen=True)
class Outcome:
    step: object
    kind: str
    speech: str = ""
    error: str = ""

@dataclass(frozen=True)
class PlanRun:
    outcomes: tuple
    superseded: bool = False

# The Intent Script contract returns text, not typed device state. Only exact,
# affirmative state messages can suppress optional work; unknown states cannot.
AC_NAMES={"m":"主卧空调","s":"次卧空调"}
LIGHT_NAMES={"all":"全屋","ke_ting":"客厅","can_ting":"餐厅","zhu_wo":"主卧","ci_wo":"次卧","er_tong_fang":"儿童房","xuan_guan":"玄关","guo_dao":"过道","chu_fang":"厨房","wei_sheng_jian":"卫生间","yang_tai":"阳台"}
STATE_LIMIT=re.compile(r"^(?:主卧空调|次卧空调|餐厅风扇|洗衣机)(?:：|:)?(?:已关闭|已关机)，无当前运行参数[。.]?$")
GAP=re.compile(r"数据不可用|数据尚未获取|状态无法确认|状态未知|欠费情况暂无法确认|暂无(?:该月|该年|有效|该月正式|该年正式)账单(?:数据)?|无法获取数据|超出每日历史覆盖范围|缺失或异常月份|本月暂无账单|部分项目无法核实")
YEAR_PARTIAL=re.compile(r"^[^。；\n]{1,80}\d{4}年账单累计(?:用电量|电费|用水量|水费|用气量|燃气费)：-?\d+(?:\.\d+)?(?:度|元|吨|立方米)（[1-9]\d*期有效账单；(?:本月暂无账单|缺失或异常月份：[^。；\n]+，仅为已知账单合计)）。$")
PHYSICAL_STATE_LIMIT=re.compile(r"^(?:[^。；\n]{1,40}当前已关闭，无法获取实时(?:亮度|色温)|(?:主卧|次卧)空调设备报告室温：-?\d+(?:\.\d+)?℃（空调已关闭，读数可能未实时刷新）)[。.]?$")
CAPABILITY_LIMIT=re.compile(r"未配置：[^。；\n]+|未监测窗户、实时烟雾和燃气泄漏")
VALID_AGGREGATE=re.compile(r"(?:余额-?\d+(?:\.\d+)?元|余额：-?\d+(?:\.\d+)?元|[：:]-?\d+(?:\.\d+)?元，余额正常|当前无欠费|[1-9]\d*组灯光中，|[1-9]\d*个有效监测区域平均(?:温度|湿度)：|\d+位成员的设备已连接)")

def classify_speech(key,speech):
    """Conservative quality annotation for actual registered speech.

    This annotation is not a device fact, an authorization, or a reason
    to substitute data. Unknown text is retained; only verified contracts
    are classified as partial results.
    """
    text=speech.strip()
    if key.family=="utility" and key.metric in {"h_year_usage","h_year_cost"} and YEAR_PARTIAL.fullmatch(text):
        return "partial_data"
    if GAP.search(text):
        if ((key.family=="utility" and key.target=="all") or
            (key.family=="home" and key.metric=="overview")) and VALID_AGGREGATE.search(text):
            return "partial_data"
        return "data_gap"
    if STATE_LIMIT.fullmatch(text) or PHYSICAL_STATE_LIMIT.fullmatch(text):
        return "state_limit"
    if key.family=="appliance":
        if key.target=="w" and text.rstrip("。.")=="海尔洗衣机已关机，无法确认当前数据":
            return "state_limit"
        if key.target=="ac" and text=="主卧空调已关闭，无当前运行参数。次卧空调已关闭，无当前运行参数。":
            return "state_limit"
        if key.target=="b" and text in {"米家浴霸暖风档位：未运行。","米家浴霸换气档位：未运行。","米家浴霸吹风档位：未运行。","米家浴霸取暖设定温度：暖风未开启。","米家浴霸杀菌剩余时间：当前未在杀菌。"}:
            return "state_limit"
    if CAPABILITY_LIMIT.search(text):
        return "capability_limit"
    return "ok"

def response_quality(key,response):
    """Use the same classification for the single-query route."""
    speech=response.as_dict().get("speech",{}).get("plain",{}).get("speech")
    return classify_speech(key,speech) if isinstance(speech,str) and speech.strip() else "unclassified"

def unpack(step,result):
    if result.error is not None:
        return Outcome(step,"error",error=result.error)
    try:
        data=result.response.as_dict()
        if data.get("response_type")!="action_done":
            return Outcome(step,"error",error="本地查询未正常完成。")
        speech=data.get("speech",{}).get("plain",{}).get("speech")
        if not isinstance(speech,str) or not speech.strip():
            return Outcome(step,"error",error="本地查询未返回有效文字。")
        speech=speech.strip()
    except (AttributeError,TypeError,KeyError):
        return Outcome(step,"error",error="本地查询未返回有效回复。")
    return Outcome(step,classify_speech(step.key,speech),speech)

def stop_supplements(plan,outcomes):
    for outcome in outcomes:
        k=outcome.step.key
        s=outcome.speech.rstrip("。.")
        if outcome.kind not in {"ok","state_limit"}:
            continue
        if "no_lights_on" in plan.stop_on and k.family=="lights" and k.metric=="count_on":
            room=LIGHT_NAMES.get(k.target)
            if room and s==room+"当前有0组灯具开启":
                return True
        if k.family!="appliance" or k.metric!="status":
            continue
        name=AC_NAMES.get(k.target,"洗衣机" if k.target=="w" else "")
        if "device_off" in plan.stop_on and name and s in {
            name+"已关闭",name+"：已关闭",name+"已关机",name+"：已关机",
            name+"已关闭，无当前运行参数",name+"已关机，无当前运行参数",
        }:
            return True
        if "device_off" in plan.stop_on and k.target=="w" and s in {"海尔洗衣机已关机","海尔洗衣机：已关机"}:
            return True
        if "cycle_not_running" in plan.stop_on and k.target=="w" and s in {
            "洗衣机当前未运行","洗衣机：未运行","洗衣机未在洗衣",
        }:
            return True
        if "all_devices_off" in plan.stop_on and k.target=="ac" and s in {
            "两台空调均已关闭","全屋空调均已关闭","两台空调均已关机",
        }:
            return True
    return False

async def run_plan(plan,dispatch,current,*,timeout=12,concurrency=2):
    """Retain order and partial results; cancel all work before returning.

    A stale generation prevents additional dispatch and context updates.
    Primary queries always execute; only explicit stop rules can skip
    supplements. Timeout and failed members are not forwarded to AI.
    """
    members=plan.primary+plan.supplements
    if (not plan.primary or len(members)>MAX_SCENE_QUERIES or len(set(members))!=len(members)
            or not set(plan.stop_on)<=STOP_CONDITIONS or not 1<=concurrency<=2 or timeout<=0):
        raise ValueError("Invalid read-only plan")
    results={}
    async def one(step):
        if not current():
            results[step]=Outcome(step,"superseded")
            return
        try:
            result=await dispatch(step)
            results[step]=unpack(step,result)
        except asyncio.CancelledError:
            raise
        except Exception:
            results[step]=Outcome(step,"error",error="本地查询暂时失败。")

    async def group(steps):
        for start in range(0,len(steps),concurrency):
            if not current():
                return
            # TaskGroup owns every child and waits for cancellation.
            async with asyncio.TaskGroup() as tasks:
                for step in steps[start:start+concurrency]:
                    tasks.create_task(one(step))
    try:
        async with asyncio.timeout(timeout):
            await group(plan.primary)
            if current():
                if stop_supplements(plan,tuple(results[s] for s in plan.primary if s in results)):
                    for step in plan.supplements:
                        results[step]=Outcome(step,"skipped")
                else:
                    await group(plan.supplements)
    except TimeoutError:
        for step in members:
            results.setdefault(step,Outcome(step,"error",error="本次组合查询超时。"))
    if not current():
        return PlanRun(tuple(results[s] for s in members if s in results),True)
    return PlanRun(tuple(results.get(s,Outcome(s,"error",error="查询未完成。")) for s in members))
