"""Typed local Chinese query parsing, independent of runtime dispatch.

Subject, metric and time are recognized separately. The grammar must consume
the full input; unknown/negative/control fragments are never discarded.
"""
from dataclasses import dataclass, replace
from collections import defaultdict
import re
import unicodedata

from .semantic_lexicon import ROOMS, DEVICES, UTILITIES, HOME, LIGHT, APPLIANCE, COMMON_APPLIANCE, UTILITY
from .semantic_parameters import number, YEAR, SMALL

@dataclass(frozen=True, order=True)
class Subject:
    family: str
    target: str
    domain: str

@dataclass(frozen=True)
class TimeSpec:
    period: str = ""
    year: int | None = None
    month: int | None = None
    day: int | None = None
    relative_year: int | None = None

@dataclass(frozen=True)
class Frame:
    subject: Subject
    metric: str = ""
    goal: str = ""
    account: str = ""
    time: TimeSpec = TimeSpec()
    explicit_account: bool = False
    correction: tuple = ()

def surface(text):
    if not isinstance(text,str) or len(text)>256:
        return ""
    return unicodedata.normalize("NFKC",text).casefold().strip().rstrip("?。!？！").strip()

WRAPPERS=tuple(sorted({
    "能不能帮我看看","能不能帮我查一下","能否帮我查询","能不能告诉我",
    "麻烦帮我看看","麻烦帮我查一下","请帮我查一下","请帮我看看",
    "我想知道","我想了解","想知道","我想问一下","帮我看一下","帮我查一下",
    "帮我看看","帮我查查","帮我查询","帮我查","麻烦查一下","麻烦看看",
    "请问","请告诉我","告诉我","查一下","查查","查一查","查询","看看",
},key=lambda s:(-len(s),s)))
# These modifiers are only allowed at documented grammar boundaries.
LEADING=("现在","目前","当前","此刻","我家的","家里的","家中的","我家")
BETWEEN=("的","那台","这台","目前","当前","现在","此刻","到底","实际上","一共","总共")
TRAILING=("啊","呀","呢")
PERIODS={"今天":"today","今日":"today","昨天":"yesterday","昨日":"yesterday","前天":"before",
         "这个月":"current","本月":"current","上个月":"previous","上月":"previous",
         "今年":"year","本年":"year","去年":"last_year","上一年":"last_year"}
DATE_RE=re.compile(r"(?:(?P<year>"+YEAR+r")年|(?P<relative>今年|本年|去年|上一年|前年))?"
                   r"(?P<month>"+SMALL+r")月(?:份)?(?:(?P<day>"+SMALL+r")(?:日|号))?")
ISO_RE=re.compile(r"(?P<year>[0-9]{4})-(?P<month>[0-9]{1,2})(?:-(?P<day>[0-9]{1,2}))?")
YEAR_RE=re.compile(r"(?P<year>"+YEAR+r")年")

def take_time(value):
    for pattern in (ISO_RE,DATE_RE,YEAR_RE):
        m=pattern.match(value)
        if m:
            g=m.groupdict()
            try:
                spec=TimeSpec(year=number(g["year"],year=True) if g.get("year") else None,
                    month=number(g["month"]) if g.get("month") else None,
                    day=number(g["day"]) if g.get("day") else None,
                    relative_year={"今年":0,"本年":0,"去年":-1,"上一年":-1,"前年":-2}.get(g.get("relative")))
            except (ValueError,KeyError):
                # Recognized malformed date must not turn into a current query.
                spec=TimeSpec(period="invalid")
            return spec,value[m.end():]
    for word in sorted(PERIODS,key=lambda x:-len(x)):
        if value.startswith(word):
            return TimeSpec(period=PERIODS[word]),value[len(word):]
    return TimeSpec(),value

def unwrap(value):
    for _ in range(3):
        word=next((x for x in WRAPPERS if value.startswith(x)),None)
        if not word:
            break
        value=value[len(word):].lstrip(" ,，:：")
    if value.endswith(TRAILING):
        value=value[:-1].rstrip()
    return value

def modifiers(value,words=BETWEEN):
    # Bounded grammar, not a global stop-word filter.
    for _ in range(4):
        word=next((x for x in sorted(words,key=lambda x:-len(x)) if value.startswith(x)),None)
        if not word:
            break
        value=value[len(word):].lstrip()
    return value

class PrefixIndex:
    def __init__(self):
        self.root={}
    def add(self,word,value):
        if not word:
            return
        node=self.root
        for char in word:
            node=node.setdefault(char,{})
        node.setdefault(None,set()).add(value)
    def prefixes(self,text):
        node=self.root
        matches=[]
        for i,char in enumerate(text):
            node=node.get(char)
            if node is None:
                break
            if None in node:
                matches.append((i+1,node[None]))
        return tuple(reversed(matches))

# Independently authored metric fragments: not whole query sentences.
UTILITY_RULES=(
    (r"(?:账户)?(?:余额|剩余金额|可用余额)(?:还有多少|还剩多少|是多少|多少|有多少)?","balance",""),
    (r"(?:账户(?:里|内)?)?(?:还)?(?:剩(?:下)?|有)(?:多少|几)(?:块钱|块|元|钱)?","","remaining_unspecified"),
    (r"(?:还)?(?:剩(?:下)?|有)(?:多少|几)(?:方|立方米|m3|m³)","","remaining_physical"),
    (r"(?:还)?(?:剩(?:下)?|有)(?:多少|几)(?:度|吨)","","remaining_physical"),
    (r"(?:是不是|是否|有没有|有无)?欠费(?:了)?(?:吗|没|没有|多少)?","debt",""),
    (r"(?:还)?(?:要|需要|该)(?:交费|缴费|交钱|交了|交|充值)(?:了)?(?:吗|没|没有)?|够不够用","","payment_needed"),
    (r"(?:账户)?(?:情况|健康|怎么样|如何)","","account_health"),
    (r"(?:累计|总计)?(?:用量|用电量|耗电量|用水量|用气量|耗电|用电|用水|用气)(?:是|有|为)?(?:多少|几)?","usage",""),
    (r"(?:累计|总计)?(?:用了|消耗了)(?:多少|几)(?:度电|吨水|方气|立方米|度|吨|方)?","usage",""),
    (r"(?:账单)?(?:费用|金额|花了|花了多少|花了多少钱|花了多少元|多少钱|多少块钱|多少元|多少|是多少)(?:多少)?","cost",""),
    (r"(?:余额|数据)?(?:更新|刷新)(?:时间|了没|了吗|了没有|于何时|是什么时候|什么时候)","update",""),
)
LIGHT_RULES=(
    (r"(?:还)?(?:亮着|开着)(?:吗|没|没有)|(?:都|全)?关(?:好|了)(?:吗|没|没有)|(?:有没有|还有没有)(?:开着|亮着|没关)的?灯?(?:具)?","","any_lights_on"),
    (r"(?:还有|有|开了|亮着|还亮着|还开着)?(?:多少|几)(?:组|盏|个)灯?(?:具)?(?:是)?(?:开着|亮着|没关)(?:的)?|(?:开着|亮着|开了|还亮着)(?:多少|几)(?:组|盏|个)灯?(?:具)?","count_on",""),
    (r"(?:还)?(?:有)?(?:哪些|什么)灯?(?:具)?(?:是)?(?:亮着|开着|没关)(?:的)?|(?:开着|亮着)(?:的)?(?:有)?哪些","list_on",""),
    (r"(?:情况|概况|怎么样|如何|状态)","","overview"),
    (r"(?:亮度|亮度百分比)(?:是|有|为)?(?:多少|几)?","brightness",""),
    (r"(?:色温)(?:是|有|为)?(?:多少|几k)?","temperature",""),
)
APPLIANCE_RULES=(
    (r"(?:设定|设置|设|调)(?:的|是|了|的是|定在)?(?:温度|多少度|几度)(?:是多少|多少|几度)?","target",""),
    (r"(?:实际|检测|测得|测到|室内|室)(?:的)?(?:温度|多少度|几度)(?:是多少|多少|几度)?","temp",""),
    (r"(?:温度|多少度|几度)(?:是多少|多少)?","","temperature_unspecified"),
    (r"(?:现在)?(?:怎么样|如何|情况|状态)","","overview"),
    (r"(?:还)?(?:在)?(?:运行|工作|开着|开机|开启)(?:了吗|吗|没|没有)|(?:开了|关了)(?:吗|没|没有)","status",""),
)
HOME_ENV_RULES=(
    (r"(?:室内|环境|室)?(?:温度|多少度|几度)(?:是多少|多少)?","temp",""),
    (r"(?:空气|环境)?湿度(?:是多少|多少)?","hum",""),
    (r"(?:环境|温湿度)(?:怎么样|如何|是多少|多少)?","","environment"),
    (r"(?:环境)?(?:光照度|光照强度|光照|环境亮度)(?:是多少|多少)?","lux",""),
    (r"(?:亮不亮|有多亮|亮度怎么样)","","brightness_unspecified"),
    (r"(?:现在)?(?:有|有没有|是否有|是不是有)人(?:吗|没|没有)?|有人没有","presence",""),
)
SPECIAL_RULES={
    "washer":((r"(?:洗(?:好|完)(?:了)?(?:吗|没|没有)|还在洗吗)","status",""),
              (r"(?:还(?:有|要)?|剩)?(?:多久|多少分钟)(?:才能|能|才)?(?:洗完|洗好|完成|结束)?","remaining",""),
              (r"洗到(?:哪|哪儿|哪里|哪一步)(?:了)?|洗衣进度|运行阶段","phase",""),
              (r"(?:洗衣)?进度(?:怎么样|如何)?","","progress"),
              (r"(?:怎么样|如何|情况|状态)","","progress")),
    "purifier":((r"(?:滤芯|滤芯寿命)(?:怎么样|还剩多少|剩多少|如何|寿命多少)?","filters",""),
                (r"滤芯(?:该|要|需要)(?:更换|换)(?:了)?(?:吗|没)?","","maintenance")),
    "door":((r"(?:关好|关严)(?:了)?(?:吗|没|没有)|(?:好|安全)(?:了)?(?:吗|没|没有)|(?:状态|情况|怎么样)","","entry_safety"),
             (r"(?:反锁)(?:了)?(?:吗|没|没有|状态)","deadbolt",""),
             (r"(?:上锁|锁好|锁)(?:了)?(?:吗|没|没有|状态)","lock",""),
             (r"(?:关着|关闭|关)(?:了)?(?:吗|没|没有|状态)","door","")),
    "family":((r"(?:现在)?(?:都)?(?:有)?(?:哪些人|什么人|些什么人|谁)(?:在家|在)?|(?:有没有|有)人(?:吗|没|没有)?","","family_presence"),
              (r"(?:现在)?(?:有)?(?:多少|几)(?:个)?人(?:在家|在)?","family_count","")),
    "person":((r"(?:现在)?(?:在家|回家|到家|在不在家)(?:了)?(?:吗|没|没有)?","person",""),),
    "battery":((r"(?:电池)?(?:电量|剩余电量|还有多少电|还剩多少电)(?:多少|是多少)?","battery",""),),
    "curtain":((r"(?:开着|关着|打开|关闭)(?:了)?(?:吗|没|没有|状态)","curtain",""),
               (r"(?:打开|开)(?:了)?(?:多少|百分之多少)|位置(?:多少|是多少)?","curtain_pos","")),
    "lid":((r"(?:盖上|合上|打开|关着|开着)(?:了)?(?:吗|没|没有|状态)","lid",""),),
    "heater":((r"(?:开着|工作|运行)(?:吗|没|没有)?","heater",""),),
    "safety":((r"(?:异常|提醒|问题|警报|告警)(?:有哪些|多少|吗)?","","alerts"),),
}

# Only reviewed, high-certainty lexical substitutions. No edit-distance
# guessing over room names, accounts, dates, units or control commands.
CORRECTIONS = {
    "天燃气": "天然气", "天燃气费": "天然气费", "洗衣鸡": "洗衣机",
    "净水气": "净水器", "主卧空条": "主卧空调", "次卧空条": "次卧空调",
    "空条": "空调", "客厅登": "客厅灯",
}

def valid_utility_fragment(target,tail,metric,goal):
    # The same numeral/unit may mean a different metric; a mismatched unit
    # invalidates the frame rather than being discarded or guessed.
    if goal=="remaining_physical":
        return target=="g" and bool(re.search(r"(?:方|立方米|m3)$",tail))
    if metric=="usage":
        if re.search(r"度电|耗电|用电|度$",tail):
            return target=="e"
        if re.search(r"吨水|用水|吨$",tail):
            return target=="w"
        if re.search(r"方气|用气|立方米|方$",tail):
            return target=="g"
    return True

class QueryParser:
    def __init__(self,menu,registry):
        self.menu=menu
        self.registry=registry
        self.subjects=PrefixIndex()
        self.accounts=PrefixIndex()
        self.fragments=defaultdict(set)
        self.rules={}
        self.aliases=defaultdict(set)
        def add(f,t,d,words):
            for w in words:
                w=surface(w)
                if w:
                    sub=Subject(f,t,d)
                    self.subjects.add(w,sub)
                    self.aliases[w].add(sub)
        for t,words in UTILITIES.items():
            add("utility",t,"utility",words)
        for t,words in DEVICES.items():
            d={"w":"washer","p":"purifier"}.get(t,"appliance")
            add("appliance",t,d,words+({"ac":("空调","两台空调"),"w":("衣服","洗衣服")}.get(t,())))
            if t in {"m","s"}:
                room="主卧" if t=="m" else "次卧"
                add("appliance",t,d,tuple(a+b+"空调" for a in ROOMS.get(room,(room,)) for b in ("那台","这台","的","的那台","的这台")))
        # Rooms and individual fixtures use actual registered targets.
        for k,item in registry.by_key.items():
            cap=menu.capabilities[item.capability_id]
            name=getattr(menu.items.get(cap["category"]),"name","")
            if k.family=="lights":
                if k.target=="all":
                    add("lights",k.target,"light_scope",("全屋灯光","全屋灯","家里的灯","家里灯","灯光","灯具","灯"))
                elif k.target.startswith("lights.fixtures."):
                    add("lights",k.target,"fixture",(name,))
                else:
                    add("lights",k.target,"light_scope",tuple(a+b for a in ROOMS.get(name,(name,)) for b in ("灯光","灯具","灯")))
                    add("lights",k.target,"light_room",ROOMS.get(name,(name,)))
            if k.family=="home":
                if k.metric in {"temp","hum","room_env","presence","lux","duration","duration_present","duration_absent","water"}:
                    add("home",k.target,"environment",ROOMS.get(k.target,(k.target,)))
                elif k.metric=="person":
                    add("home",k.target,"person",(k.target,))
                elif k.metric=="battery":
                    add("home",k.target,"battery",(k.target,))
                elif k.metric in {"curtain","curtain_pos"}:
                    add("home",k.target,"curtain",tuple(a+"窗帘" for a in ROOMS.get(k.target,(k.target,))))
                # Fragments from existing vocabulary remain scoped by semantic
                # subject; no full question expansion or arbitrary token deletion.
            if k.family=="appliance":
                templates=APPLIANCE.get(k.target,{}).get(k.metric,COMMON_APPLIANCE.get(k.metric,()))
                if k.target!="ac":
                    for w in templates:
                        self.fragments[(k.family,k.target)].add((surface(w),k.metric))
            elif k.family=="home":
                for w in HOME.get(k.metric,()):
                    if w.startswith("{s}"):
                        self.fragments[(k.family,k.target)].add((surface(w[3:]),k.metric))
            elif k.family=="lights":
                for w in LIGHT.get(k.metric,()):
                    if w.startswith("{s}"):
                        self.fragments[(k.family,k.target)].add((surface(w[3:]),k.metric))
        add("home","all","door",("入户门","大门","门锁","门"))
        add("home","all","family",("家里","家中","家庭成员","家人"))
        add("home","all","safety",("全屋","家里","家中"))
        add("home","all","lid",("马桶盖",))
        add("home","all","heater",("燃气热水器","热水器"))
        add("home","all","environment",("全屋环境","家里环境"))
        for key,account in (("primary_label","j"),("secondary_label","l"),("secondary","l")):
            word=surface(menu.settings.get(key,""))
            if word:
                self.accounts.add(word,account)
        for domain in ("utility","light_scope","light_room","fixture","appliance","washer","purifier","environment",
                       "door","family","person","battery","curtain","lid","heater","safety"):
            common=UTILITY_RULES if domain=="utility" else LIGHT_RULES if domain in {"light_scope","light_room","fixture"} else (
                APPLIANCE_RULES if domain in {"appliance","washer","purifier"} else HOME_ENV_RULES if domain=="environment" else ())
            self.rules[domain]=tuple((re.compile(p),m,g) for p,m,g in SPECIAL_RULES.get(domain,())+common)

    def _account(self,value):
        matches=self.accounts.prefixes(value)
        if not matches:
            return "",False,value
        n,accounts=matches[0]
        return next(iter(accounts)) if len(accounts)==1 else "ambiguous",True,value[n:].removeprefix("的").lstrip()

    def _metrics(self,sub,tail):
        out=set()
        if sub.domain=="light_room" and not re.search(r"灯|灯具|灯光",tail):
            return out
        # Domain rules take precedence over legacy fragment aliases. This is
        # essential for broad status queries and temperature ambiguity.
        for pattern,metric,goal in self.rules[sub.domain]:
            if pattern.fullmatch(tail):
                if sub.family=="utility" and not valid_utility_fragment(sub.target,tail,metric,goal):
                    continue
                if sub.family=="utility" and goal=="account_health" and sub.target!="all":
                    goal="payment_needed"
                if sub.domain=="fixture" and goal=="any_lights_on":
                    metric,goal="single_state",""
                if sub.domain=="fixture" and goal=="overview":
                    metric,goal="single_state",""
                out.add((metric,goal))
        if sub.domain=="washer" and ("","progress") in out:
            return {("","progress")}
        if out:
            return out
        # Explicit metric fragments are only legal for the corresponding
        # subject class; e.g. a room temperature cannot apply to a door.
        allowed={"environment":{"temp","hum","room_env","presence","lux","duration","duration_present","duration_absent","water"},
                 "person":{"person"},"battery":{"battery"},"curtain":{"curtain","curtain_pos"},
                 "door":{"door","lock","deadbolt","childlock"},"lid":{"lid"},"heater":{"heater"},
                 "family":{"family","family_count"},"safety":{"alerts","safety","faults","overview"}}.get(sub.domain)
        return {(m,"") for phrase,m in self.fragments[(sub.family,sub.target)]
                if phrase==tail and (allowed is None or m in allowed)}

    def parse(self,text):
        value=unwrap(surface(text))
        if not value or len(value)>256:
            return ()
        # Leading time/account/scope may occur in either order, each at most once.
        time=TimeSpec()
        account=""
        explicit=False
        for _ in range(3):
            value=modifiers(value,LEADING)
            a,e,rest=self._account(value)
            if e and not explicit:
                account,explicit,value=a,e,rest
                continue
            ts,rest=take_time(value)
            if ts!=TimeSpec() and time==TimeSpec():
                time,value=ts,rest
                continue
            break
        value=value.lstrip()
        matches=self.subjects.prefixes(value)
        correction=()
        if not matches:
            for typo,word in sorted(CORRECTIONS.items(),key=lambda x:-len(x[0])):
                if value.startswith(typo):
                    corrected=word+value[len(typo):]
                    candidate=self.subjects.prefixes(corrected)
                    if candidate and candidate[0][0]>=len(word):
                        value,matches,correction=corrected,candidate,(typo,word)
                    break
        result=set()
        # Prefer longest known subject. Do not reinterpret a failed specific
        # target as a shorter one, e.g. "燃气热水器" -> "燃气".
        if matches:
            n,subjects=matches[0]
            tail=modifiers(value[n:].lstrip())
            ts,rest=take_time(tail)
            if ts!=TimeSpec():
                if time!=TimeSpec():
                    return ()
                time,tail=ts,modifiers(rest)
            for sub in subjects:
                if (explicit or time!=TimeSpec()) and sub.family!="utility":
                    continue
                for metric,goal in self._metrics(sub,tail):
                    result.add(Frame(sub,metric,goal,account,time,explicit,correction))
        # Object-last form, with exact independent metric fragment and a known
        # target at the end, no unconstrained text deletion.
        if not matches:
            for word,subjects in self.aliases.items():
                if len(value)<=len(word) or not value.endswith(word):
                    continue
                head=value[:-len(word)].removesuffix("的").rstrip()
                for sub in subjects:
                    if (explicit or time!=TimeSpec()) and sub.family!="utility":
                        continue
                    for metric,goal in self._metrics(sub,head):
                        result.add(Frame(sub,metric,goal,account,time,explicit))
        return tuple(sorted(result,key=repr))

    def subject_only(self,text):
        value=unwrap(surface(text))
        return tuple(sorted(self.aliases.get(value,())))
