"""Conservative catalog-based Chinese read-only query matching.

No substring/fuzzy matching, external NLP, or generated entity identifiers.
Fixed queries and bounded registered Utility date parameters only.
"""
from dataclasses import dataclass
from datetime import date
import re
from .menu import Reply, TRANSLATE
from .semantic_lexicon import FAMILIES, describe, patterns
from .semantic_parameters import ParameterIndex
from .context_transitions import Selection

INTENTS = frozenset(FAMILIES)
METRIC = re.compile(r"(?:余额|光照度|温度|湿度|亮度|色温|风速|水温|转速|档位|读数|电量|用电量|用水量|用气量|费用|电费|水费|燃气费|气价|寿命|tds|位置|限位)$")
SUFFIX = re.compile(r"(?:是多少|有多少|多少)$")

def normalize(text):
    if not isinstance(text, str) or len(text) > 256:
        return ""
    value = text.strip().casefold().translate(TRANSLATE).rstrip("？?。！!").strip()
    # Only remove one explicit inquiry wrapper and one sentence-final filler.
    # Never remove a device, account, date, unit, negation or action word.
    for prefix in ("麻烦帮我查一下","请帮我查一下","帮我查一下","麻烦查一下","查一下","请问"):
        if value.startswith(prefix):
            value=value[len(prefix):].lstrip("，,：: ")
            break
    if value.endswith(("啊","呀","呢")):
        value=value[:-1].rstrip()
    return value

@dataclass(frozen=True)
class Match:
    capability: str | None = None
    clarification: str | None = None
    params: tuple = ()
    options: tuple = ()

class SemanticIndex:
    def __init__(self, menu):
        self.menu = menu
        self.exact = {}
        self.aliases = {}
        self.clarifications = {}
        self.profiles = {}
        self.clarification_options={}
        self.parameter_index=ParameterIndex(menu,normalize)
        settings = getattr(menu, "settings", {})
        items = getattr(menu, "items", {})
        for cap in menu.capabilities.values():
            profile=describe(cap)
            if profile is None or not cap.get("sentence"):
                continue
            self.profiles[cap["id"]]=profile
            if profile.parameter:
                continue
            sentence = cap["sentence"]
            if "{secondary}" in sentence and not settings.get("secondary"):
                # Keep the configured secondary label available for a local unavailable
                # message, but do not create an empty target alias.
                continue
            if "{" in sentence.replace("{secondary}", ""):
                continue
            canonical = normalize(sentence.replace("{secondary}", settings.get("secondary", "")))
            cid = cap["id"]
            self._add(self.exact, canonical, cid)
            variants = {canonical}
            item = items.get(cap.get("category"))
            target = normalize(item.name) if item is not None else ""
            if target and canonical.startswith(target) and len(canonical) > len(target) and not canonical[len(target):].startswith("的"):
                variants.add(target + "的" + canonical[len(target):])
            if cap["intent"] == "LuxeUtilityQuery" and cap["slots"].get("utility_kind") == "e":
                prop = cap["slots"].get("luxe_utility_property")
                if prop == "j":
                    label = normalize(settings.get("primary_label", ""))
                    if label:
                        variants.update({label + canonical, label + "的" + canonical})
                elif prop == "l":
                    label = normalize(settings.get("secondary_label", ""))
                    secondary = normalize(settings.get("secondary", ""))
                    if label and secondary and canonical.startswith(secondary + "的"):
                        tail = canonical[len(secondary)+1:]
                        variants.update({label + tail, label + "的" + tail})
            # Metric suffix changes are permitted only for known noun endings.
            for phrase in tuple(variants):
                stem = SUFFIX.sub("", phrase)
                if METRIC.search(stem):
                    variants.update({stem, stem+"多少", stem+"是多少"})
            if cap["intent"] == "LuxeHomeQuery" and canonical.endswith("光照度是多少"):
                room = canonical[:-len("光照度是多少")]
                for prefix in (room,room+"的"):
                    for metric in ("光照度","光照强度","环境光照度","环境亮度"):
                        for suffix in ("","多少","是多少"):
                            variants.add(prefix+metric+suffix)
                for query in (room+"有多亮",room+"亮度",room+"亮度多少",room+"亮度是多少",
                              room+"的亮度",room+"的亮度是多少",room+"的亮度多少",room+"亮不亮"):
                    self.clarifications[query] = "请确认要查询"+room+"的环境光照度，还是某个灯具的亮度？可发送“"+room+"光照度是多少”，或指定灯具名称。"
            if cap["intent"] == "LuxeApplianceQuery" and canonical.endswith("现在状态如何"):
                subject = canonical[:-len("现在状态如何")]
                variants.update({subject+"状态",subject+"状态如何",subject+"现在怎么样",subject+"当前状态"})
            if cid == "appliance.washer.remaining":
                variants.update({"洗衣机还要多久洗完","洗衣机还剩多久","洗衣机什么时候洗完"})
            if cid in {"utility.electric.j.basic.balance","utility.water.balance","utility.gas.basic.balance"}:
                subject={"utility.electric.j.basic.balance":"电费","utility.water.balance":"水费","utility.gas.basic.balance":"燃气费"}[cid]
                variants.update({subject+"还剩多少钱",subject+"还有多少钱",subject+"账户余额"})
            # Shared templates are expanded only for this existing profile.
            # They never generate a capability or alter its original Slots.
            variants.update(patterns(cap,menu))
            for variant in variants:
                self._add(self.aliases,normalize(variant),cid)

        # Curated ambiguities: no device/unit/account is guessed from availability.
        for subject in ("主卧空调","主卧室空调","次卧空调","次卧室空调","浴霸","空调"):
            for suffix in ("多少度","几度","现在多少度","现在几度","温度多少","温度是多少","的温度多少"):
                self.clarifications[subject+suffix]="请确认要查询"+subject+"的设定温度，还是实际检测温度？"
        for phrase in ("大门好了吗","大门好了没","大门安全吗","入户门好了吗","门好了吗"):
            self.clarifications[phrase]="请确认要查询入户门关闭状态、上锁状态，还是反锁状态？"
        for subject in ("燃气","天然气","燃气费"):
            for prefix in ("剩","还剩","还有","剩余"):
                for unit in ("方","立方米","m3","m³","度"):
                    for amount in ("多少","几"):
                        self.clarifications[subject+prefix+amount+unit]="燃气账户余额以元计，当前没有燃气表剩余气量查询。若要查询阶梯剩余额度，请明确第一或第二阶梯。"
        for phrase in ("水费还剩多少吨","水费剩多少吨","水还剩多少吨","电费还剩多少度","电费剩多少度","电还剩多少度"):
            self.clarifications[phrase]="账户余额与剩余实物用量不是同一指标。目前支持账户金额和已用量查询，请明确要查询的项目。"
        for phrase in ("上个月花了多少","上月花了多少","这个月花了多少","本月花了多少","这个月用了多少","上个月用了多少"):
            self.clarifications[phrase]="请明确要查询电费、水费还是燃气费，或相应的用量。"
        for phrase in ("水费要交了吗","电费要交了吗","燃气费要交了吗"):
            self.clarifications[phrase]="请确认要查询是否欠费，还是查询账户余额？"

        # Store only registered choices, never execute on clarification alone.
        def choice(family,target,metric,period="",account=None):
            ids=[p.capability for p in self.profiles.values() if p.family==family and p.target==target
                 and p.metric==metric and p.period==period and not p.parameter
                 and (account is None or p.account==account)]
            return Selection(ids[0]) if len(ids)==1 else None
        for phrase in self.clarifications:
            opts={}
            for name,target in (("主卧空调","m"),("主卧室空调","m"),("次卧空调","s"),("次卧室空调","s"),("浴霸","b")):
                if phrase.startswith(name) and self.clarifications[phrase].endswith("实际检测温度？"):
                    opts={k:choice("appliance",target,metric) for k,metric in
                          (("设定温度","target"),("调的几度","target"),("检测温度","temp"),("实际温度","temp"))}
                    if target in {"m","s"}:
                        opts["室温"]=choice("appliance",target,"temp")
            if phrase in ("大门好了吗","大门好了没","大门安全吗","入户门好了吗","门好了吗"):
                opts={k:choice("home","all",metric) for k,metric in (("关闭状态","door"),("关门状态","door"),("上锁状态","lock"),("反锁状态","deadbolt"))}
            if "环境光照度，还是" in self.clarifications[phrase]:
                for p in self.profiles.values():
                    if p.family=="home" and p.metric=="lux" and phrase.startswith(p.target):
                        opts={"环境光照度":Selection(p.capability),"光照度":Selection(p.capability),"环境亮度":Selection(p.capability)}
            if phrase in ("水费要交了吗","电费要交了吗","燃气费要交了吗"):
                kind={"水":"w","电":"e","燃":"g"}[phrase[0]]
                opts={k:choice("utility",kind,metric,account="j") for k,metric in (("欠费","debt"),("是否欠费","debt"),("余额","balance"),("账户余额","balance"))}
            if self.clarifications[phrase].startswith("燃气账户余额以元计"):
                opts={k:choice("utility","g",metric,account="j") for k,metric in (("第一阶梯","tier1_remaining"),("第二阶梯","tier2_remaining"),("余额","balance"))}
            if phrase in ("上个月花了多少","上月花了多少","这个月花了多少","本月花了多少","这个月用了多少","上个月用了多少"):
                period="previous" if phrase.startswith("上") else "current"
                usage="用了" in phrase
                from .followup import MONTHLY
                opts={label:choice("utility",kind,MONTHLY[kind][0 if usage else 1],period,"j") for label,kind in (("电费","e"),("水费","w"),("燃气费","g"))}
            if opts:
                self.clarification_options[phrase]=tuple(sorted((k,v) for k,v in opts.items() if v is not None))

    @staticmethod
    def _add(index, phrase, cid):
        if phrase:
            index.setdefault(phrase,set()).add(cid)

    def match(self,text,today=None):
        key=normalize(text)
        if not key:
            return None
        # A configured label or extension may introduce a cross-index collision.
        # Do not silently choose an exact phrase over another registered meaning.
        choices=self.exact.get(key,set()) | self.aliases.get(key,set())
        if key in self.clarifications:
            return Match(clarification=self.clarifications[key],options=self.clarification_options.get(key,()))
        if not choices:
            parsed=self.parameter_index.match(key,today or date.today())
            if parsed.invalid:
                return Match(clarification="查询日期无效或超出当前日期，请检查年月日后重试。")
            if len(parsed.choices)==1:
                cid,params=parsed.choices[0]
                return Match(capability=cid,params=params)
            if len(parsed.choices)>1:
                return Match(clarification="该问句对应多个查询，请明确账户和指标。")
            # Recognize unsupported whole date/range expressions without inventing
            # aggregate queries or treating a bill amount as consumption.
            if re.fullmatch(r"(?:最近|过去|近)(?:[0-9]{1,3}|[一二两三四五六七八九十]+)(?:天|个?月|年)(?:电费|水费|燃气费|用电量|用水量|用气量)(?:多少|是多少|花了多少)?",key):
                return Match(clarification="目前未注册该连续时间范围的汇总查询，请指定单日、月份或年度账期。")
            if re.fullmatch(r"(?:[0-9]{4}|[零〇一二三四五六七八九]{4})(?:年|-)(?:[0-9]{1,2}|[一二两三四五六七八九十]{1,3})(?:月份?)?(?:水费(?:是多少|多少|花了多少(?:钱|元)?)|用了(?:多少|几)吨水|用水量多少|用水多少)",key):
                return Match(clarification="指定年份的月度水费目前仅支持今年或去年，请使用“今年3月水费”或“去年3月水费”。")
            if re.fullmatch(r"(?:[0-9]{1,2}|[一二两三四五六七八九十]{1,3})月份?(?:电费|水费|燃气费|用电量|用水量|用气量)(?:多少|是多少|花了多少(?:钱)?)?",key):
                return Match(clarification="请明确查询的是今年、去年还是指定年份的这个月份。")
            return None
        if len(choices)!=1:
            return Match(clarification="该问句对应多个查询，请明确设备、账户或指标，或发送 help。")
        return Match(capability=next(iter(choices)))

    def reply(self,match,visible):
        if match.clarification is not None:
            return Reply(match.clarification)
        if not self.menu._available(match.capability,visible):
            return Reply("该查询当前不可用，请发送 help 查看可用能力。")
        return self.menu._query(match.capability,dict(match.params))
