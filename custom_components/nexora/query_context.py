"""Bounded semantic focus for local query plans, without transcript storage.

The existing generation lease is shared by the agent. Only completed,
current turns may write focus; any independent turn consumes old focus.
"""
from dataclasses import dataclass, replace
from .natural_language import Subject, Frame, TimeSpec, surface, unwrap, take_time
from .query_planner import PlanningResult, Plan
from .business_model import QueryKey

@dataclass(frozen=True)
class Focus:
    frame: Frame | None
    anchor: object
    expires: float
    scene: bool = False
    menu_scene: str = ""
    params: tuple = ()

DEFAULT_GOALS={
    "door":"entry_safety","washer":"progress","purifier":"overview",
    "appliance":"overview","light_scope":"overview","light_room":"overview",
    "environment":"environment","family":"family_presence","safety":"alerts",
    "utility":"remaining_unspecified",
}
REPEAT={"再查一次","再查一下","重新查询","再查一遍","现在呢"}
UTILITY_ABSTRACT={
    "daily":"usage","latest_usage":"usage","latest_cost":"cost",
    "h_day":"usage","h_month_usage":"usage","h_month_cost":"cost",
    "history_usage":"usage","history_cost":"cost","h_year_usage":"usage","h_year_cost":"cost",
}
# Preserve specific meanings; not all existing metrics have an abstract
# equivalent. They remain handled by the original follow-up engine.

class QueryContext:
    def __init__(self,planner,clock,ttl=300,max_sessions=256):
        self.planner=planner
        self.clock=clock
        self.ttl=ttl
        self.max_sessions=max_sessions
        self.entries={}

    def clear(self,key):
        self.entries.pop(key,None)

    def consume(self,key):
        now=self.clock()
        for k,v in list(self.entries.items()):
            if v.expires<=now:
                self.entries.pop(k,None)
        return self.entries.pop(key,None)

    def remember(self,key,frame,today,*,scene=False,current=True,menu_scene="",params=()):
        if not current or (frame is None and not menu_scene):
            return False
        self.entries.pop(key,None)
        while len(self.entries)>=self.max_sessions:
            self.entries.pop(min(self.entries,key=lambda k:self.entries[k].expires))
        self.entries[key]=Focus(frame,today,self.clock()+self.ttl,scene,menu_scene,tuple(params))
        return True

    def from_registered(self,capability,params,today):
        item=self.planner.registry.by_id.get(capability)
        if not item:
            return None
        k=item.key
        # Choose a domain by the actual registered metric, not by proximity
        # to an arbitrary alias; home 'all' has several distinct meanings.
        if k.family=="home":
            domain=("door" if k.metric in {"lock","door","deadbolt","childlock"} else
                    "family" if k.metric in {"family","family_count"} else
                    "person" if k.metric=="person" else
                    "curtain" if k.metric in {"curtain","curtain_pos"} else
                    "battery" if k.metric=="battery" else
                    "environment" if k.metric in {"temp","hum","room_env","lux","presence","duration","duration_present","duration_absent","water","env"} else
                    "lid" if k.metric=="lid" else "heater" if k.metric=="heater" else "safety")
        elif k.family=="lights":
            domain="fixture" if k.target.startswith("lights.fixtures.") else "light_scope"
        elif k.family=="appliance":
            domain={"w":"washer","p":"purifier"}.get(k.target,"appliance")
        else:
            domain="utility"
        scope="all" if k.family=="utility" and k.target=="all" and k.period=="all" else ""
        time=TimeSpec(period="" if scope else k.period)
        metric=k.metric
        if k.family=="utility":
            metric=UTILITY_ABSTRACT.get(metric,metric)
            if k.parameter:
                p=dict(params)
                if k.parameter=="month":
                    time=TimeSpec(month=p["month"],relative_year=-1 if k.period=="last_year" else 0)
                elif k.parameter=="month_day":
                    time=TimeSpec(month=p["month"],day=p["day"],relative_year=0)
                else:
                    time=TimeSpec(year=p.get("year"),month=p.get("month"),day=p.get("day"))
            elif k.metric in {"daily","latest_usage","latest_cost"}:
                # Latest-day and latest-bill queries are not identical.
                # Keep the original registered path for same-object repeats.
                metric=k.metric
        return Frame(Subject(k.family,k.target,domain),metric,account=k.account,time=time,
                     explicit_account=bool(k.account),scope=scope)

    def _default(self,sub):
        if sub.domain in {"utility","utility_all"} and sub.target=="all":
            return Frame(replace(sub,domain="utility"),goal="account_health",scope="all" if sub.domain=="utility_all" else "")
        if sub.domain=="fixture":
            return Frame(sub,metric="single_state")
        if sub.domain=="person":
            return Frame(sub,metric="person")
        if sub.domain=="lid":
            return Frame(sub,metric="lid")
        if sub.domain=="heater":
            return Frame(sub,metric="heater")
        if sub.domain=="curtain":
            return Frame(sub,metric="curtain")
        if sub.domain=="battery":
            return Frame(sub,metric="battery")
        goal=DEFAULT_GOALS.get(sub.domain)
        if goal=="environment" and sub.target not in {"主卧","次卧","客餐厅","卫生间","all"}:
            return None
        return Frame(sub,goal=goal) if goal else None

    def _switch(self,old,sub):
        a,b=old.subject,sub
        if a.family==b.family=="utility" and a.target!="all" and b.target!="all":
            if old.goal in {"remaining_unspecified","payment_needed"} or old.metric in {"balance","debt","usage","cost","latest_usage","latest_cost"}:
                # A named secondary electricity account cannot be silently
                # replaced by the primary utility account.
                return replace(old,subject=b,correction=())
            return None
        if a.family==b.family=="appliance" and {a.target,b.target}<={"m","s","ac"}:
            return replace(old,subject=b,correction=())
        if a.family==b.family=="lights" and a.domain!="fixture" and b.domain!="fixture":
            return replace(old,subject=b,correction=())
        if a.family==b.family=="home" and a.domain==b.domain and a.domain in {"environment","person","curtain","battery"}:
            return replace(old,subject=b,correction=())
        # Cross-module switch is allowed only with a specific named subject
        # and an independently registered default, never a borrowed metric.
        return self._default(sub)

    def resolve_menu(self,text,focus,today,visible):
        """Repeat an actual completed scene or explicitly change its period/scope.

        No arbitrary scene switching: unknown follow-ups go to the existing
        single-metric context resolver, not an inferred account or device.
        """
        if focus is None or not focus.menu_scene:
            return PlanningResult()
        value=surface(text)
        target=focus.menu_scene
        params=dict(focus.params)
        tail=value.removesuffix("呢")
        if value in REPEAT:
            pass
        elif value.endswith("呢") and ".monthly." in target and tail in {"本月","这个月","上月","上个月"}:
            target=target.rsplit(".",1)[0]+(".current" if tail in {"本月","这个月"} else ".previous")
            params={}
        elif value.endswith("呢") and ".annual." in target and tail in {"今年","本年","去年","上一年"}:
            target=target.rsplit(".",1)[0]+(".year" if tail in {"今年","本年"} else ".last_year")
            params={}
        elif value.endswith("呢") and target.startswith("scene.utility.summary.") and tail in {"主住所","全部账户","所有账户","全部水电气账户","所有水电气账户"}:
            parts=target.split(".")
            parts[3]="primary" if tail=="主住所" else "all"
            target=".".join(parts)
        else:
            return PlanningResult()
        if focus.anchor!=today:
            return PlanningResult(message="日期已变化，请重新选择菜单查询。")
        try:
            return PlanningResult(plan=self.planner.menu_plan(target,params,visible,self,today))
        except (KeyError,ValueError):
            return PlanningResult(message="该组合查询当前不可用，请发送 help。")

    def resolve(self,text,focus,today):
        if focus is None or focus.frame is None:
            return PlanningResult()
        value=surface(text)
        old=focus.frame
        if value in REPEAT and focus.scene:
            return self._safe(old,focus,today)
        # Use new context only for explicit elliptical turns; complete
        # independent questions and numeric/menu commands retain precedence.
        if value.endswith("呢"):
            raw=value[:-1]
            if old.subject.family=="appliance" and old.subject.target in {"m","s","ac"} and raw in {"主卧","主卧室","次卧","次卧室"}:
                raw=("主卧" if raw.startswith("主") else "次卧")+"空调"
            subjects=() if old.subject.family=="utility" and old.subject.target=="all" and raw in {"所有账户","全部账户","全部水电气账户","所有水电气账户","全部水电气","所有水电气","主住所","主住所水电气"} else self.planner.parser.subject_only(raw)
            if subjects:
                matching=[s for s in subjects if s.family==old.subject.family and (
                    s.domain==old.subject.domain or s.family=="lights" and s.domain in {"light_scope","light_room"} and old.subject.domain in {"light_scope","light_room"})]
                subjects=tuple(matching) if matching else subjects
                if len(subjects)==1:
                    sub=subjects[0]
                    # Preserve legacy same-object/same-family fixed paths
                    # unless it is a cross-module switch or a planned scene.
                    if not focus.scene and old.subject.family==sub.family and old.subject.family!="utility":
                        return PlanningResult()
                    new=self._switch(old,sub)
                    if new:
                        return self._safe(new,focus,today)
                    return PlanningResult(message="该对象没有对应的继承查询。")
        tail=value.removesuffix("呢")
        if old.subject.family=="utility" and old.subject.target=="all":
            # Scope is not a historical period or an electricity account.
            # Only explicit scope switches can widen a completed aggregate.
            if value.endswith("呢") and tail in {"所有账户","全部账户","全部水电气账户","所有水电气账户","全部水电气","所有水电气","主住所","主住所水电气"}:
                scope="" if tail.startswith("主住所") else "all"
                return self._safe(replace(old,scope=scope,correction=()),focus,today)
            options=self.planner.parser._metrics(old.subject,tail)
            if len(options)==1:
                metric,goal=next(iter(options))
                if metric in {"balance","debt","update","balances","debts","low","updates"} or goal in {"remaining_unspecified","payment_needed","account_health"}:
                    return self._safe(replace(old,metric=metric,goal=goal,correction=()),focus,today)
        if old.subject.family=="utility" and old.subject.target!="all" and old.time==TimeSpec():
            options=self.planner.parser._metrics(old.subject,tail)
            if len(options)==1:
                metric,goal=next(iter(options))
                if metric in {"balance","debt","update"} or goal in {"remaining_unspecified","payment_needed"}:
                    return self._safe(replace(old,metric=metric,goal=goal,correction=()),focus,today)
        if old.subject.family=="utility" and old.subject.target=="e" and old.metric in {"year_cost","year_usage"} and tail in {"用量","费用","账单"}:
            return self._safe(replace(old,metric={"用量":"year_usage","费用":"year_cost","账单":"cost"}[tail],
                 time=TimeSpec(period="year"),goal="",correction=()),focus,today)
        if not focus.scene:
            return PlanningResult()
        # Short metric switches are scoped by previous subject; no
        # free-form guessing or conversation transcript reconstruction.
        if tail in {"用量","费用","账单"} and old.subject.family=="utility":
            return self._safe(replace(old,goal="",metric="usage" if tail=="用量" else "cost",correction=()),focus,today)
        time,rest=take_time(tail)
        if not rest and time!=TimeSpec() and old.subject.family=="utility" and old.metric in {"usage","cost"}:
            return self.planner.frame(replace(old,time=time,correction=()),today)
        options=self.planner.parser._metrics(old.subject,tail)
        if len(options)==1:
            metric,goal=next(iter(options))
            return self._safe(replace(old,metric=metric,goal=goal,correction=()),focus,today)
        return PlanningResult()

    def _safe(self,frame,focus,today):
        t=frame.time
        if (t.relative_year is not None and focus.anchor.year!=today.year or
            t.period in {"today","yesterday","before"} and focus.anchor!=today or
            t.period in {"current","previous"} and (focus.anchor.year,focus.anchor.month)!=(today.year,today.month) or
            t.period in {"year","last_year"} and focus.anchor.year!=today.year):
            return PlanningResult(message="原查询的相对账期已变化，请重新指定日期。")
        return self.planner.frame(frame,today)
