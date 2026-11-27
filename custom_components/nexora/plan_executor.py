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
GAP=re.compile(r"(?:数据不可用|数据尚未获取|状态无法确认|状态未知|暂无该月正式账单|暂无该年正式账单|无法获取数据)[。.]?$")

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
    if STATE_LIMIT.fullmatch(speech) or (step.key.family=="appliance" and step.key.target=="w" and speech.rstrip("。.")=="海尔洗衣机已关机，无法确认当前数据"):
        return Outcome(step,"state_limit",speech)
    if GAP.search(speech):
        return Outcome(step,"data_gap",speech)
    return Outcome(step,"ok",speech)

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
