"""Conservative household fallback guard and isolated AI conversation state.

The classifier is not a permissions boundary for a third-party agent.
No device IDs, state values or local chat history are forwarded by this layer.
"""
from dataclasses import dataclass
from time import monotonic
import re

from .semantic_lexicon import ROOMS as ROOM_ALIASES, DEVICES, UTILITIES, describe

# These are recognition hints for unmatched queries, not an authorization layer.
HOUSEHOLD = {
    "家里","家中","我家","全屋","家电","智能家居","家庭成员","在家","回家",
    "入户门","大门","门锁","窗帘","马桶盖","水浸","漏水","燃气","天然气","电费","水费","电表","水表","燃气表",
    "用电","用水","用气","度电","吨水","多少气","多少水","多少电","爸爸","妈妈","爷爷","奶奶",
    "灯具","灯光","吸顶灯","筒灯","射灯","灯带","空调","洗衣机","滤芯","洗衣液","柔顺剂",
    "浴霸","晾衣机","晾衣架","净水器","热水器","摄像头","传感器","路由器","光照度","风扇","吊扇",
    "home assistant","homeassistant","hass","smart home","my house","my home",
}
ROOMS={"客厅","餐厅","主卧","次卧","阳台","厨房","玄关","卫生间","儿童房","过道","客餐厅"}
LIVE = re.compile(r"现在|当前|实时|今天|昨天|前天|刚才|本月|上月|这个月|上个月|今年|去年|前年|余额|欠费|剩余|(?:还)?剩(?:下)?(?:多少|几|钱)|还有多少|多少钱|多少度|几度|几档|几组|几盏|多少方|多少吨|用量|费用|耗电|光照(?:度|强度)?|亮度|温度|湿度|电量|状态|多久|在家|有人|没人|开着|关着|亮着|关了|开了|锁了|坏了|故障|报错|可用|在线|离线|掉线|是不是|是否|有没有|有多亮|洗好|洗完|洗到|该换|要换|还在|工作吗|运行吗|有没有|多少|(?:吗|没|没有|不|呢)[？?。！!]*$")
QUESTION = re.compile(r"多少|几(?:度|档|组|盏|个|台|人|次|天|方|吨|元|块|钱)|多久|什么时候|为何|为什么|怎么|如何|是不是|是否|有没有|(?:吗|没|没有|不|呢)[？?。！!]*$")
INQUIRY = re.compile(r"^(?:请|麻烦|帮我|请帮我)?(?:查查|查询|查一下|查一查|查看|看看|看一下|告诉我|请问)")
NEGATED_READ = re.compile(r"^(?:请|麻烦|帮我|请帮我)?(?:不要|不用|别|不必|无需|停止)(?:再)?(?:查询|查|查看|看一下|读取)")
EDUCATION = re.compile(r"^(?:请问|请|帮我|给我|请帮我)?(?:介绍|解释|科普|讲解|什么是|如何|怎么|怎样|为什么|写|编写|设计|制定|推荐|比较|分析一下.*原理)")
HOWTO = re.compile(r"(?:怎么|如何|怎样)(?:清洁|保养|省电|使用|安装|配置|设置|维修|工作|缴费|交费|交|充值|选购|挑选|换滤芯|换电池|计算|接入|连接)")
# An interrogative state ("灯关了吗") must not be mistaken for a command.
STATUS_QUESTION = re.compile(r"(?:了没|了吗|了没有|开着没|关着没|亮着没|开着吗|关着吗|亮着吗|没开|没关|是否|是不是|有没有|多少|几度|几档|多久)")
CONTROL = re.compile(r"^(?:(?:请|帮我|麻烦|能不能|可以|给我|你能|一下|不要|别|不用)\s*)*(?:打开|关闭|开启|关掉|开灯|关灯|启动|停止|暂停|恢复|设置|调节|调整|调高|调低|解锁|上锁|反锁|执行|控制|turn on|turn off|unlock|lock |set )")
OBJECT_CONTROL = re.compile(r"^(?:请|麻烦|帮我|请帮我)?(?:把|将).+(?:打开|关闭|开启|关掉|关上|启动|停止|暂停|恢复|设置|调到|调节|调整|调高|调低|解锁|上锁|反锁)(?:.*)?$")
ENTITY = re.compile(r"(?:switch|light|sensor|binary_sensor|climate|cover|lock|camera)\.[a-z0-9_]+",re.I)
MISSING_CONTEXT = {"还剩多少","剩多少","还有多少钱","余额呢","多少钱","多少度","几度","调的几度","设了几度","现在屋里几度","还有多久","还要多久","设定温度","实际温度","检测温度","环境光照度","关闭状态","上锁状态","反锁状态","第一阶梯","第二阶梯","用量呢","费用呢"}
# Explicit query+action composition is not an implicit authorization to run either.
SEPARATOR = re.compile(r"然后|接着|同时|顺便|并且|再(?:帮我)?(?=查|关|开|调|设|启|停|锁|解)|[，,；;]")
GUARD_REPLY = "这条家庭实时查询尚未匹配已注册的查询能力，无法确认实际数据。请明确设备、账户和查询项目，或发送 help。"
AI_PROMPT = ("涉及家庭实时数据时，仅依据可验证的数据来源回答；无法验证时请明确说明，"
             "不要推测设备是否存在或实际状态，不要将未验证结果当成真实数据。其他任务遵循原有代理配置及权限。")

@dataclass(frozen=True)
class BoundaryDecision:
    kind: str
    reply: str = ""

class FallbackGuard:
    def __init__(self, menu):
        terms=set(HOUSEHOLD)|ROOMS
        terms.update(alias for aliases in ROOM_ALIASES.values() for alias in aliases)
        terms.update(alias for aliases in DEVICES.values() for alias in aliases)
        terms.update(alias for aliases in UTILITIES.values() for alias in aliases)
        settings=getattr(menu,"settings",{})
        for key in ("primary_label","secondary_label","secondary"):
            value=settings.get(key)
            if isinstance(value,str) and len(value.strip())>=2:
                terms.add(value.strip().casefold())
        # Use only typed registry subjects, not arbitrary descriptions or entity IDs.
        for cap in getattr(menu,"capabilities",{}).values():
            p=describe(cap)
            if not p:
                continue
            if p.family=="home" and p.target!="all" and len(p.target)>=2:
                terms.add(p.target.casefold())
            if p.family=="lights" and p.target.startswith("lights.fixtures."):
                item=getattr(menu,"items",{}).get(cap.get("category"))
                name=getattr(item,"name","")
                if len(name)>=2:
                    terms.add(name.casefold())
        self.terms=tuple(sorted({re.sub(r"\s+","",x.casefold()) for x in terms if x},key=lambda v:(-len(v),v)))

    def _household(self,text):
        return (any(term in text for term in self.terms)
                or ENTITY.search(text) is not None
                or re.search(r"(?:灯|门|窗|电|水|气)(?:开着|关着|亮着|关了|开了|锁了|还剩|剩多少|够用)",text) is not None)

    @staticmethod
    def _command(value):
        # State questions and read requests take precedence over imperative verbs.
        if INQUIRY.search(value):
            return False
        if STATUS_QUESTION.search(value) and not re.search(r"(?:调到|设置为|设为|调至)\d",value):
            return False
        if HOWTO.search(value) or EDUCATION.search(value):
            return False
        return bool(CONTROL.search(value) or OBJECT_CONTROL.search(value))

    def _query(self,value):
        return self._household(value) and (LIVE.search(value) is not None or INQUIRY.search(value) is not None or QUESTION.search(value) is not None or re.search(r"怎么样|哪了|够不够|够用|几天",value) is not None)

    def classify(self,text):
        value=text.strip().casefold() if isinstance(text,str) else ""
        if not value:
            return BoundaryDecision("delegate")
        # Preserve word boundaries for English controls, compact Chinese whitespace.
        compact=re.sub(r"\s+","",value).rstrip("？?。！!")
        if NEGATED_READ.search(compact):
            return BoundaryDecision("cancelled","已取消本次查询，不执行查询。")
        parts=[p for p in SEPARATOR.split(compact) if p]
        if len(parts)>1 and any(self._command(p) for p in parts) and any(self._query(p) and not self._command(p) for p in parts):
            return BoundaryDecision("compound","检测到查询与设备控制混合在同一条消息中，请分别发送查询和控制指令。")
        if compact in MISSING_CONTEXT or compact.removesuffix("呢") in MISSING_CONTEXT:
            return BoundaryDecision("missing_context","请补充查询对象或账期，当前没有足够的本地查询上下文。")
        if self._command(value) or self._command(compact):
            return BoundaryDecision("control")
        # General educational or writing requests retain the configured Agent.
        if (EDUCATION.search(compact) or HOWTO.search(compact)) and not re.search(r"当前|实时|刚才|现在(?:是|有|多少|几|没|不)|今天(?:用了|还有|剩|交了)|为什么.*(?:没开|没关|报错|故障)",compact):
            return BoundaryDecision("delegate")
        if ENTITY.fullmatch(value) or self._query(compact):
            return BoundaryDecision("live",GUARD_REPLY)
        return BoundaryDecision("delegate")

    def blocked(self,text):
        return bool(self.classify(text).reply)

@dataclass
class Session:
    cid: str | None
    expires: float

class AIConversations:
    """Bounded, ephemeral AI session IDs, separate from local conversation IDs."""
    def __init__(self,clock=monotonic,ttl=1800,max_sessions=256,max_active=2):
        self.clock,self.ttl,self.max_sessions=clock,ttl,max_sessions
        self.max_active=max_active
        self.sessions={}
        self.active=set()
        self.rejected_ids={}

    def reserve(self,key):
        now=self.clock()
        for cid,expiry in list(self.rejected_ids.items()):
            if expiry<=now:
                self.rejected_ids.pop(cid,None)
        for k,s in list(self.sessions.items()):
            if s.expires<=now and k not in self.active:
                self.sessions.pop(k,None)
        if key in self.active or len(self.active)>=self.max_active:
            return False,None
        self.active.add(key)
        session=self.sessions.get(key)
        return True,session.cid if session and session.expires>now else None

    def complete(self,key,cid):
        if not isinstance(cid,str) or not cid or len(cid)>512:
            self.sessions.pop(key,None)
            return
        owners=[other for other,s in self.sessions.items() if other!=key and s.cid==cid]
        if owners or cid in self.rejected_ids:
            # Never reuse a conversation returned for different local scopes.
            for other in owners:
                self.sessions.pop(other,None)
            self.sessions.pop(key,None)
            self.rejected_ids[cid]=self.clock()+self.ttl
            while len(self.rejected_ids)>self.max_sessions:
                self.rejected_ids.pop(next(iter(self.rejected_ids)))
            return
        self.sessions.pop(key,None)
        while len(self.sessions)>=self.max_sessions:
            self.sessions.pop(next(iter(self.sessions)))
        self.sessions[key]=Session(cid,self.clock()+self.ttl)

    def fail(self,key):
        # Never reuse a potentially partially written AI chat after timeout.
        self.sessions.pop(key,None)

    def release(self,key):
        self.active.discard(key)
