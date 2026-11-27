"""Small deterministic, read-only context; no LLM or conversation transcript."""
from dataclasses import dataclass

PERIODS={"这个月呢":"current","本月呢":"current","上个月呢":"previous","上月呢":"previous","今天呢":"today","昨天呢":"yesterday","前天呢":"before","今年呢":"year","去年呢":"last_year"}
MONTHLY={"e":("h_month_usage","h_month_cost"),"w":("history_usage","history_cost"),"g":("h_month_usage","h_month_cost")}
USAGE={"用量","用水量","用电量","用气量"}
COST={"费用","水费","电费","燃气费","账单"}
METRIC_SWITCH={"费用呢":"cost","用量呢":"usage","用电量呢":"usage","用水量呢":"usage","用气量呢":"usage","电费呢":"cost","水费呢":"cost","燃气费呢":"cost"}
OTHER_ACCOUNT={"另一个账户呢","另一个账号呢","第二个账户呢"}
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
        self.generations={}
    def begin(self,key):
        """Reserve a turn without letting a late result overwrite a newer turn."""
        token=object()
        self.generations.pop(key,None)
        self.generations[key]=token
        while len(self.generations)>self.max_sessions:
            self.generations.pop(next(iter(self.generations)))
        return token
    def is_current(self,key,token):
        return self.generations.get(key) is token
    def complete(self,key,token,capability):
        if self.is_current(key,token):
            self.remember(key,capability)
            return True
        return False
    def is_followup_message(self,text):
        labels=[self.menu.settings["primary_label"]]
        if self.menu.settings["secondary"]:
            labels.extend([self.menu.settings["secondary_label"],self.menu.settings["secondary"]])
        return (text in PERIODS or text in USAGE_PHRASES or text in METRIC_SWITCH
                or text in OTHER_ACCOUNT or text in USAGE | COST
                or any(label and text==label.casefold()+"呢" for label in labels))
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
        labels=[(self.menu.settings["primary_label"],"j")]
        if self.menu.settings["secondary"]:
            labels.extend([(self.menu.settings["secondary_label"],"l"),(self.menu.settings["secondary"],"l")])
        options={}
        for label,prop in labels:
            if label:
                options.setdefault(label.casefold()+"呢",set()).add(prop)
        targets={label:next(iter(props)) for label,props in options.items() if len(props)==1}
        if not c:
            if self.is_followup_message(text):
                return "查询上下文已失效，请补充查询对象，或发送 help。"
            return None
        slots=dict(self.menu.capabilities[c.capability]["slots"])
        kind=slots.get("utility_kind")
        metric=slots.get("utility_metric")
        if c.pending_period and text in USAGE|COST:
            if text in {"用水量","用电量","用气量","水费","电费","燃气费"} and text not in {"w":{"用水量","水费"},"e":{"用电量","电费"},"g":{"用气量","燃气费"}}.get(kind,set()):
                return "请选择当前账户的用量或费用，或发送 help。"
            if kind not in MONTHLY:
                return "请发送 help 重新选择查询。"
            slots["utility_metric"]=MONTHLY[kind][0 if text in USAGE else 1]
            slots["utility_period"]=c.pending_period
            c.pending_period=None
            return self._find(slots,available)
        if text in OTHER_ACCOUNT:
            if kind!="e" or not self.menu.settings["secondary"] or slots.get("luxe_utility_property") not in {"j","l"}:
                return "当前没有可切换的电费账户，请发送 help。"
            slots["luxe_utility_property"]="l" if slots["luxe_utility_property"]=="j" else "j"
            return self._find(slots,available)
        metric_switch_text=text if text in METRIC_SWITCH else text+"呢"
        if metric_switch_text in METRIC_SWITCH:
            text=metric_switch_text
            if kind not in MONTHLY:
                return "请补充需要查询的具体项目，或发送 help。"
            if text not in {"费用呢","用量呢"} and text not in {"w":{"用水量呢","水费呢"},"e":{"用电量呢","电费呢"},"g":{"用气量呢","燃气费呢"}}[kind]:
                return "请补充需要查询的账户或设备。"
            pair=MONTHLY[kind]
            if metric in pair and slots.get("utility_period") in {"current","previous"}:
                slots["utility_metric"]=pair[0 if METRIC_SWITCH[text]=="usage" else 1]
                return self._find(slots,available)
            if metric in {"h_year_usage","h_year_cost"}:
                slots["utility_metric"]="h_year_usage" if METRIC_SWITCH[text]=="usage" else "h_year_cost"
                return self._find(slots,available)
            return "请补充需要查询的账期，或发送 help。"
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
