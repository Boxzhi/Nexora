"""Pure, bounded query planner. No HA API calls or entity inference."""
from dataclasses import dataclass, replace
import re

from .business_model import BusinessRegistry, PolicyRegistry, QueryKey, PolicyKey, MAX_SCENE_QUERIES
from .natural_language import QueryParser, Frame, TimeSpec, surface
from .menu import parse_parameter

@dataclass(frozen=True)
class Step:
    key: QueryKey
    capability: str
    params: tuple = ()

@dataclass(frozen=True)
class Plan:
    primary: tuple
    supplements: tuple = ()
    stop_on: tuple = ()
    caveat: str = ""
    focus: Frame | None = None

@dataclass(frozen=True)
class PlanningResult:
    plan: Plan | None = None
    message: str = ""

# Never split a control/query compound into an executable read-only plan.
# Every independent part must parse and pass the registry checks.
SEPARATORS=re.compile(r"[，,；;]|以及|另外|顺便|同时|并且|和")
MISSING="当前没有对应的已注册查询能力。"

class QueryPlanner:
    def __init__(self,menu):
        self.menu=menu
        self.registry=BusinessRegistry(menu.capabilities)
        self.policies=PolicyRegistry(self.registry)
        self.parser=QueryParser(menu,self.registry)

    def _step(self,key,params=()):
        item=self.registry.require(key)
        return Step(key,item.capability_id,tuple(sorted(params)))

    def _scene(self,frame,account):
        s=frame.subject
        goal=frame.goal
        if goal=="temperature_unspecified" and s.family=="appliance" and s.target in {"w","p"}:
            return Plan((self._step(QueryKey(s.family,s.target,"temp")),),focus=frame)
        if goal=="overview" and s.family=="appliance" and s.target in {"a","f","b"}:
            return Plan((self._step(QueryKey(s.family,s.target,"status")),),focus=frame)
        rule=self.policies.get(PolicyKey(s.family,s.target,goal,account,frame.time.period))
        if rule is None:
            raise KeyError(goal)
        scene=rule.scene
        return Plan(tuple(self._step(k) for k in scene.primary),
                    tuple(self._step(k) for k in scene.supplements),
                    scene.stop_on,scene.caveat,frame)

    def _utility_period(self,frame,account,today):
        target=frame.subject.target
        time=frame.time
        metric=frame.metric
        if time.period=="invalid":
            raise ValueError("查询日期无效，请检查年月日。")
        if metric=="payment_amount":
            if target=="g" and time==TimeSpec(period="year"):
                return self._step(QueryKey("utility","g","year_pay",account=account))
            raise ValueError("当前未注册该账户及账期的缴费金额查询，不能替换为账单费用。")
        if metric not in {"usage","cost"}:
            if time!=TimeSpec():
                raise ValueError("该指标没有已注册的历史日期查询，不能替换为当前数据。")
            return self._step(QueryKey("utility",target,metric,account=account))
        period=time.period
        parameter=""
        params={}
        month,day=time.month,time.day
        year=time.year
        if time.relative_year is not None:
            year=today.year+time.relative_year
        if month is not None:
            if year is None:
                raise ValueError("请明确该月份属于哪一年。")
            if day is not None:
                if target!="e" or metric!="usage":
                    raise ValueError("当前未注册该单日指标的查询能力。")
                period,parameter="explicit","date"
                params={"year":year,"month":month,"day":day}
                metric="h_day"
            else:
                metric=("history_" if target=="w" else "h_month_")+metric
                if year in {today.year,today.year-1} and time.year is None or target=="w":
                    if year not in {today.year,today.year-1}:
                        raise ValueError("水务月度查询目前仅支持今年或去年。")
                    period="year" if year==today.year else "last_year"
                    parameter="month"
                    params={"month":month}
                else:
                    period,parameter="explicit","year_month"
                    params={"year":year,"month":month}
        elif year is not None:
            metric="h_year_"+metric
            period,parameter="explicit","year"
            params={"year":year}
        elif period in {"today","yesterday","before"}:
            if target!="e" or metric!="usage":
                raise ValueError("当前未注册该单日指标的查询能力。")
            metric="h_day"
        elif period in {"current","previous"}:
            metric=("history_" if target=="w" else "h_month_")+metric
        elif period in {"year","last_year"}:
            metric="h_year_"+metric
        elif not period:
            # A generic usage/cost inquiry without a time is labeled as the
            # latest available bill, never as a real-time meter or unit price.
            metric="latest_"+metric
        else:
            raise ValueError("当前未注册该账期的查询能力。")
        if parameter:
            fields={"month":("month",),"date":("year","month","day"),
                    "year_month":("year","month"),"year":("year",)}[parameter]
            try:
                params=parse_parameter(parameter,"-".join(str(params[k]) for k in fields),today,
                    base_year=today.year-1 if period=="last_year" else today.year)
            except ValueError:
                raise ValueError("查询日期无效或超出当前日期，请检查年月日。") from None
        return self._step(QueryKey("utility",target,metric,period,parameter,account),params.items())

    def frame(self,frame,today):
        s=frame.subject
        account=frame.account
        if s.family=="utility":
            if frame.explicit_account and account=="ambiguous":
                return PlanningResult(message="账户名称存在歧义，请明确查询账户。")
            account=account or "j"
            if account=="l" and (s.target!="e" or not self.menu.settings.get("secondary")):
                return PlanningResult(message="该账户未配置对应查询，不能替换为主账户。")
        elif frame.explicit_account or frame.time!=TimeSpec():
            return PlanningResult(message=MISSING)
        try:
            if frame.goal:
                if frame.time!=TimeSpec():
                    return PlanningResult(message="该场景没有已注册的历史日期查询。")
                plan=self._scene(frame,account)
            elif s.family=="utility":
                plan=Plan((self._utility_period(frame,account,today),),focus=frame)
            else:
                plan=Plan((self._step(QueryKey(s.family,s.target,frame.metric)),),focus=frame)
            return PlanningResult(plan)
        except ValueError as exc:
            return PlanningResult(message=str(exc))
        except KeyError:
            return PlanningResult(message=MISSING)

    def _one(self,frames,today):
        if not frames:
            return PlanningResult()
        results=[self.frame(f,today) for f in frames]
        # Do not use device availability to select a meaning. Identical
        # executable plans may coalesce; genuine ambiguity stays unresolved.
        plans={r.plan for r in results if r.plan is not None}
        if len(plans)==1 and all(r.plan is not None for r in results):
            return PlanningResult(next(iter(plans)))
        if len(results)==1:
            return results[0]
        return PlanningResult(message="查询对象或指标存在多个含义，请明确查询内容。")

    def plan(self,text,today):
        single=self._one(self.parser.parse(text),today)
        if single.plan or single.message:
            return single
        parts=SEPARATORS.split(surface(text))
        if not 2<=len(parts)<=MAX_SCENE_QUERIES or any(not x for x in parts):
            return PlanningResult()
        results=[self._one(self.parser.parse(x),today) for x in parts]
        if any(r.plan is None for r in results):
            return PlanningResult()
        # Explicit multiple reads: every requested primary is retained.
        primary=tuple(dict.fromkeys(step for r in results for step in r.plan.primary))
        supplements=tuple(dict.fromkeys(step for r in results for step in r.plan.supplements if step not in primary))
        if len(primary)+len(supplements)>MAX_SCENE_QUERIES:
            return PlanningResult(message="本次查询项目较多，请缩小查询范围。")
        caveats=tuple(dict.fromkeys(r.plan.caveat for r in results if r.plan.caveat))
        # Mixed scenes cannot share stop predicates or a single follow-up focus.
        return PlanningResult(Plan(primary,supplements,caveat="\n".join(caveats)))
