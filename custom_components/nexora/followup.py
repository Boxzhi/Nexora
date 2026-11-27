"""Small deterministic, read-only context; no LLM or conversation transcript."""
from dataclasses import dataclass

PERIODS={"这个月呢":"current","本月呢":"current","上个月呢":"previous","上月呢":"previous","今天呢":"today","昨天呢":"yesterday","前天呢":"before","今年呢":"year","去年呢":"last_year"}
MONTHLY={"e":("h_month_usage","h_month_cost"),"w":("history_usage","history_cost"),"g":("h_month_usage","h_month_cost")}
USAGE={"用量","用水量","用电量","用气量"}
COST={"费用","水费","电费","燃气费","账单"}
USAGE_PHRASES={"这个月用了多少度":"current","上个月用了多少度":"previous","这个月用了多少水":"current","上个月用了多少水":"previous","这个月用了多少气":"current","上个月用了多少气":"previous"}

@dataclass
class Context:
    capability:str
    expires:float
    pending_period:str|None=None

class Followups:
    def __init__(self,menu,clock,ttl=300,max_sessions=256):
        self.menu,self.clock,self.ttl,self.max_sessions=menu,clock,ttl,max_sessions
        self.contexts={}
    def clear(self,key):
        self.contexts.pop(key,None)
    def prune(self):
        for key,c in list(self.contexts.items()):
            if c.expires<=self.clock():
                self.clear(key)
    def remember(self,key,capability):
        self.prune()
        cap=self.menu.capabilities.get(capability)
        if not cap or cap["intent"]!="LuxeUtilityQuery" or cap.get("parameter"):
            self.clear(key)
            return
        if key not in self.contexts and len(self.contexts)>=self.max_sessions:
            self.clear(min(self.contexts,key=lambda k:self.contexts[k].expires))
        self.contexts[key]=Context(capability,self.clock()+self.ttl)

    def _find(self,slots,available):
        choices=[c["id"] for c in self.menu.capabilities.values() if c["intent"]=="LuxeUtilityQuery" and c["slots"]==slots and not c.get("parameter") and self.menu._available(c["id"],available)]
        return choices[0] if len(choices)==1 else "当前没有对应的本地查询，请发送 help。"

    def route(self,key,text,available):
        self.prune()
        c=self.contexts.get(key)
        labels={self.menu.settings["primary_label"]:"j",self.menu.settings["secondary_label"]:"l"}
        if self.menu.settings["secondary"]:
            labels[self.menu.settings["secondary"]]="l"
        targets={label.casefold()+"呢":prop for label,prop in labels.items() if label}
        if not c:
            if text in PERIODS or text in targets or text in USAGE_PHRASES:
                return "查询上下文已失效，请补充查询对象，或发送 help。"
            return None
        slots=dict(self.menu.capabilities[c.capability]["slots"])
        kind=slots.get("utility_kind")
        metric=slots.get("utility_metric")
        if c.pending_period and text in USAGE|COST:
            if kind not in MONTHLY:
                return "请发送 help 重新选择查询。"
            slots["utility_metric"]=MONTHLY[kind][0 if text in USAGE else 1]
            slots["utility_period"]=c.pending_period
            c.pending_period=None
            return self._find(slots,available)
        if text in targets and kind=="e":
            slots["luxe_utility_property"]=targets[text]
            return self._find(slots,available)
        if text in USAGE_PHRASES and kind in MONTHLY:
            # Do not reinterpret a unit from another utility.
            if not (kind=="e" and text.endswith("度") or kind=="w" and text.endswith("水") or kind=="g" and text.endswith("气")):
                return None
            slots["utility_metric"]=MONTHLY[kind][0]
            slots["utility_period"]=USAGE_PHRASES[text]
            return self._find(slots,available)
        if text not in PERIODS:
            return None
        period=PERIODS[text]
        if kind not in MONTHLY:
            return "请补充需要查询的具体项目，或发送 help。"
        monthly=MONTHLY[kind]
        if period in {"current","previous"}:
            if metric in monthly:
                slots["utility_period"]=period
            elif metric in {"latest_usage","latest_cost"}:
                slots["utility_metric"]=monthly[0 if metric=="latest_usage" else 1]
                slots["utility_period"]=period
            elif metric=="balance":
                c.pending_period=period
                return "请问要查询用量还是费用？回复“用量”或“费用”。"
            else:
                return "请补充需要查询的具体项目，或发送 help。"
        elif period in {"today","yesterday","before"} and kind=="e" and metric in {"h_day","daily"}:
            slots["utility_metric"]="h_day"
            slots["utility_period"]=period
        elif period in {"year","last_year"} and metric in {"h_year_usage","h_year_cost","year_usage","year_cost"}:
            slots["utility_metric"]="h_year_usage" if metric.endswith("usage") else "h_year_cost"
            slots["utility_period"]=period
        else:
            return "当前查询无法直接切换到该账期，请发送 help。"
        return self._find(slots,available)
