"""Conservative household fallback guard and isolated AI conversation state.

The classifier is not a permissions boundary for a third-party agent.
No device IDs, state values or local chat history are forwarded by this layer.
"""
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
# Recognize only likely real-time household questions. General education and
# explicit device commands retain the configured fallback Agent's behavior.
LIVE = re.compile(r"现在|当前|实时|今天|昨天|前天|本月|上月|这个月|上个月|今年|去年|余额|欠费|还剩|还有多少|多少钱|多少度|用量|费用|光照(?:度|强度)?|亮度|温度|湿度|电量|状态|多久|在家吗|有人吗|无人吗|开着吗|关了吗|锁了吗|坏了|故障|可用吗|在线吗|是不是|是否|有没有|有多亮")
EDUCATION = re.compile(r"^(?:请问|请|帮我|给我|请帮我)?(?:介绍|解释|科普|讲解|什么是|如何|怎么|怎样|为什么|写|编写|设计|制定|推荐|比较|分析一下.*原理)")
CONTROL = re.compile(r"^(?:(?:请|帮我|麻烦|能不能|可以|给我|把|将|给|你能|一下)\s*)*(?:打开|关闭|开启|关掉|开灯|关灯|启动|停止|暂停|恢复|设置|调节|调整|调高|调低|解锁|上锁|反锁|执行|控制|turn on|turn off|unlock|lock |set )")
ENTITY = re.compile(r"(?:switch|light|sensor|binary_sensor|climate|cover|lock|camera)\.[a-z0-9_]+",re.I)
GUARD_REPLY = "这条家庭实时查询尚未匹配已注册的查询能力，无法确认实际数据。请明确设备、账户和查询项目，或发送 help。"
AI_PROMPT = ("涉及家庭实时数据时，仅依据可验证的数据来源回答；无法验证时请明确说明，"
             "不要推测设备是否存在或实际状态。其他任务遵循原有代理配置及权限。")

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
            return False
        compact=re.sub(r"\s+","",value)
        if CONTROL.search(value) or CONTROL.search(compact):
            return False
        # Educational requests are not real-time reads unless explicitly
        # referring to a concrete current household condition.
        if (EDUCATION.search(compact) or re.search(r"(?:怎么|如何|怎样)(?:清洁|保养|省电|使用|安装|配置|设置|维修|工作)",compact)):
            if not re.search(r"我家|家里|家中|当前|现在|实时|今天|刚才",compact):
                return False
        if ENTITY.fullmatch(value):
            return True
        household=any(term in value or term.replace(" ","") in compact for term in self.terms)
        return household and LIVE.search(compact) is not None

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
