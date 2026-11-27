"""Conservative household fallback guard and isolated AI conversation state.

The classifier is not a permissions boundary for a third-party agent.
No device IDs, state values or local chat history are forwarded by this layer.
"""
import asyncio
from dataclasses import dataclass
from time import monotonic
import re

# Explicit household vocabulary; not generic isolated words such as 温度.
HOUSEHOLD = {
    "家里","家中","我家","全屋","家电","智能家居","家庭成员","在家","回家",
    "入户门","门锁","窗帘","马桶盖","水浸","漏水","燃气","电费","水费","电表","水表",
    "用电","用水","用气","度电","吨水","多少气","多少水","多少电","爸爸","妈妈","爷爷","奶奶","灯具","灯光","吸顶灯","筒灯","射灯","灯带","空调","洗衣机",
    "浴霸","晾衣机","晾衣架","净水器","热水器","摄像头","传感器","路由器","光照度",
    "home assistant","homeassistant","hass","smart home","my house","my home",
    "switch.","light.","sensor.","binary_sensor.","climate.","cover.","lock.","camera.",
}
ROOMS = {"客厅","餐厅","主卧","次卧","阳台","厨房","玄关","卫生间","儿童房","过道","客餐厅"}
# Unknown commands or referential follow-ups cannot safely infer a local target.
COMMAND = re.compile(r"^(?:请|帮我|麻烦|能不能|可以|给我|把|将|给)?(?:打开|关闭|开启|关掉|开灯|关灯|启动|停止|暂停|恢复|设置|调节|调整|调高|调低|解锁|上锁|反锁|执行|控制|turn on|turn off|unlock|lock |set )")
REFERENTIAL = re.compile(r"^(?:那|这)?(?:它|他|她|那个|这个|上一|刚才|其他|另一个|还有|多少|现在呢|呢)")
GUARD_REPLY = "这条家庭查询或控制指令尚未匹配已注册的只读能力，无法确认实时状态。请明确设备、账户和查询项目，或发送 help。"
AI_PROMPT = ("本通道用于普通问答。不得执行家庭设备控制、自动化或服务调用；"
             "不得推测家庭实时数据、设备是否存在或设备状态。涉及家庭实时数据时，"
             "请说明本通道无法验证，并建议通过 Nexora 本地查询。")

class FallbackGuard:
    def __init__(self, menu):
        terms=set(HOUSEHOLD)|ROOMS
        settings=getattr(menu,"settings",{})
        for key in ("primary_label","secondary_label","secondary"):
            value=settings.get(key)
            if isinstance(value,str) and len(value.strip())>=2:
                terms.add(value.strip().casefold())
        self.terms=tuple(sorted(terms,key=lambda v:(-len(v),v)))

    def blocked(self,text):
        value=text.strip().casefold() if isinstance(text,str) else ""
        if not value:
            return True
        # Whitespace cannot disguise a household token or command.
        compact=re.sub(r"\s+","",value)
        return (any(term in value or term.replace(" ","") in compact for term in self.terms)
                or COMMAND.search(value) is not None
                or COMMAND.search(compact) is not None
                or REFERENTIAL.search(compact) is not None)

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

    def reserve(self,key):
        now=self.clock()
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
        self.sessions.pop(key,None)
        while len(self.sessions)>=self.max_sessions:
            self.sessions.pop(next(iter(self.sessions)))
        self.sessions[key]=Session(cid,self.clock()+self.ttl)

    def fail(self,key):
        # Never reuse a potentially partially written AI chat after timeout.
        self.sessions.pop(key,None)

    def release(self,key):
        self.active.discard(key)
