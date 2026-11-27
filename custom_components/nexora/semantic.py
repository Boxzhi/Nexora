"""Conservative catalog-based Chinese read-only query matching.

No substring/fuzzy matching, external NLP, or generated entity identifiers.
Only fixed capabilities of the four known intent families are indexed.
"""
from dataclasses import dataclass
import re
from .menu import Reply, TRANSLATE
from .semantic_lexicon import FAMILIES, describe, patterns

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

class SemanticIndex:
    def __init__(self, menu):
        self.menu = menu
        self.exact = {}
        self.aliases = {}
        self.clarifications = {}
        self.profiles = {}
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
                              room+"的亮度",room+"的亮度是多少",room+"的亮度多少"):
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

    @staticmethod
    def _add(index, phrase, cid):
        if phrase:
            index.setdefault(phrase,set()).add(cid)

    def match(self,text):
        key=normalize(text)
        if not key:
            return None
        # A configured label or extension may introduce a cross-index collision.
        # Do not silently choose an exact phrase over another registered meaning.
        choices=self.exact.get(key,set()) | self.aliases.get(key,set())
        if key in self.clarifications:
            return Match(clarification=self.clarifications[key])
        if not choices:
            return None
        if len(choices)!=1:
            return Match(clarification="该问句对应多个查询，请明确设备、账户或指标，或发送 help。")
        return Match(capability=next(iter(choices)))

    def reply(self,match,visible):
        if match.clarification is not None:
            return Reply(match.clarification)
        if not self.menu._available(match.capability,visible):
            return Reply("该查询当前不可用，请发送 help 查看可用能力。")
        return self.menu._query(match.capability,{})
