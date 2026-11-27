"""Bounded spoken date grammar over registered Utility parameter capabilities.

Full matches only. No new intent, slot or date-range aggregation is invented.
Use the same menu parameter validator and the HA-local date supplied by the agent.
"""
from dataclasses import dataclass
from itertools import product
import re
from .menu import PARAMETERS, parse_parameter
from .semantic_lexicon import describe, UTILITY

DIGITS = {"零":0,"〇":0,"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,
          "六":6,"七":7,"八":8,"九":9}
YEAR = r"(?:[0-9]{4}|[零〇一二三四五六七八九]{4})"
SMALL = r"(?:[0-9]{1,2}|[零〇一二两三四五六七八九十]{1,3})"

def number(text,year=False):
    if text.isascii() and text.isdecimal():
        return int(text)
    if year:
        return int("".join(str(DIGITS[x]) for x in text))
    if text in DIGITS:
        return DIGITS[text]
    if text.startswith("十") and (len(text)==1 or len(text)==2 and text[1] in DIGITS and DIGITS[text[1]]>0):
        return 10+(DIGITS[text[1]] if len(text)==2 else 0)
    if len(text) in (2,3) and text[0] in ("二","三") and text[1]=="十":
        if len(text)==3 and (text[2] not in DIGITS or not DIGITS[text[2]]):
            raise ValueError("invalid number")
        return DIGITS[text[0]]*10+(DIGITS[text[2]] if len(text)==3 else 0)
    raise ValueError("invalid number")

def _field(name):
    return "(?P<"+name+">"+(YEAR if name=="year" else SMALL)+")"

def _date_patterns(kind,period):
    y,m,d=(_field(n) for n in ("year","month","day"))
    if kind=="date":
        return (y+"年"+m+"月"+d+"(?:日|号)",y+"-"+m+"-"+d)
    if kind=="month_day":
        return ("(?:今年|本年)?"+m+"月"+d+"(?:日|号)",)
    if kind=="year_month":
        return (y+"年"+m+"月(?:份)?",y+"-"+m)
    if kind=="month":
        prefix="(?:去年|上一年)" if period=="last_year" else "(?:今年|本年)"
        return (prefix+m+"月(?:份)?",)
    if kind=="year":
        return (y+"年",)
    return ()

def _account_prefixes(profile,settings):
    if profile.target!="e":
        return ("",)
    if profile.account=="l":
        secondary=settings.get("secondary","")
        if not secondary:
            return ()
        labels={secondary,settings.get("secondary_label","")} - {""}
        return tuple(sorted({label+sep for label,sep in product(labels,("","的"))}))
    if profile.account=="j":
        label=settings.get("primary_label","")
        return ("",label,label+"的") if label else ("",)
    return ()

@dataclass(frozen=True)
class DynamicResult:
    choices: tuple = ()
    invalid: bool = False

class ParameterIndex:
    def __init__(self,menu,normalize):
        self.rules=[]
        settings=getattr(menu,"settings",{})
        for cap in menu.capabilities.values():
            p=describe(cap)
            if p is None or p.family!="utility" or p.parameter not in PARAMETERS:
                continue
            sentence=cap["sentence"].replace("{secondary}的","")
            # The original templates have the time phrase before the query.
            last=sentence.rfind("}")
            if last<0:
                continue
            tail=sentence[last+1:]
            for marker in ("月份","月","年","日","号"):
                if tail.startswith(marker):
                    tail=tail[len(marker):]
                    break
            if not tail or "{" in tail:
                continue
            suffixes={tail}
            suffixes.update(q.removeprefix("{p}") for q in UTILITY.get(p.target,{}).get(p.metric,()) if q.startswith("{p}"))
            # The catalog annual metric is explicitly cumulative bills, not payments.
            if p.metric=="h_month_cost" or p.metric=="history_cost":
                cost={"e":"电费","w":"水费","g":"燃气费"}[p.target]
                suffixes.update({cost+"花了多少钱",cost+"花了多少元"})
            for prefix, date_pattern, suffix in product(_account_prefixes(p,settings),_date_patterns(p.parameter,p.period),suffixes):
                expr=re.escape(normalize(prefix))+date_pattern+re.escape(normalize(suffix))
                self.rules.append((re.compile(expr),cap))

    def match(self,key,today):
        choices=set()
        invalid=False
        for regex,cap in self.rules:
            match=regex.fullmatch(key)
            if not match:
                continue
            try:
                fields=PARAMETERS[cap["parameter"]]
                values=[str(number(match.group(f),year=f=="year")) for f in fields]
                params=parse_parameter(cap["parameter"],"-".join(values),today,
                    base_year=today.year-1 if cap.get("parameter_year_offset")==-1 else today.year)
            except (ValueError,KeyError):
                invalid=True
                continue
            choices.add((cap["id"],tuple(sorted(params.items()))))
        return DynamicResult(tuple(sorted(choices)),invalid)
