"""Exact, scoped vocabulary for registered business scenes.

A phrase identifies a scene, not an intent or a device. Ambiguous labels are
not executable; dates and visibility remain the existing planner's concern.
"""
from collections import defaultdict
from .semantic import normalize

EXPLICIT = {
    "scene.utility.summary.primary.overview": ("我家水电气账户概况", "主住所水电气账户概况", "水电气账户概况"),
    "scene.utility.summary.all.overview": ("所有账户概况", "全部账户概况", "所有水电气账户概况", "全部水电气账户概况"),
    "scene.lights.all": ("全屋照明概况", "全屋灯光概况", "家里灯光怎么样"),
    "scene.lights.fixtures.bath_panel": ("卫生间平板灯概况", "人体存在平板灯概况"),
    "scene.lights.fixtures.bath_heater": ("浴霸灯概况", "智能浴霸S1灯概况"),
    "scene.home.env.whole": ("全屋环境温湿度", "全屋温湿度概况", "家里温湿度怎么样"),
    "scene.utility.gas.pay.recent": ("燃气缴费查询最近缴费记录", "最近燃气缴费记录", "最近一次燃气缴费记录", "上次燃气缴费情况", "燃气最近缴费记录"),
    "scene.utility.gas.pay.annual": ("燃气缴费查询年度缴费统计", "今年燃气缴费情况", "燃气年度缴费统计", "今年燃气缴费统计"),
    "scene.home.presence.whole": ("全屋人体感应及光照", "全屋人体感应和光照概况"),
    "scene.appliance.washer.progress": ("洗衣机当前洗衣进度", "海尔洗衣机当前洗衣进度", "洗衣机洗衣进度"),
    "scene.home.family": ("家庭成员概况", "家里人员情况"),
    "scene.home.overview": ("全屋状态概况", "家里整体情况"),
}

def scoped_phrases(sid,names):
    """Keep scope-bearing ancestors; never strip account or date qualifiers."""
    full="".join(names)
    yield full
    yield " · ".join(names)
    if len(names)>2:
        yield "".join(names[1:])
    leaf=names[-1]
    if sid.startswith("scene.utility.electric.") and len(names)>=4:
        # Account label is mandatory for shortened electric paths.
        yield names[2]+"电费"+"".join(names[3:])
        yield names[2]+"的电费"+"".join(names[3:])
        if len(names)==4:
            yield names[2]+leaf
    elif sid.startswith(("scene.utility.water.","scene.utility.gas.")):
        scope=names[1]
        yield scope+"的"+"".join(names[2:])
        # Retain billing-period groups, but allow ordinary scoped payment terms.
        if ".pay." in sid or ".tier." in sid:
            yield scope+leaf
            yield scope.removesuffix("费")+leaf
        if len(names)==4 and names[2] in {"月度账单查询","年度账单查询"}:
            yield leaf+scope+("月度账单" if names[2]=="月度账单查询" else "年度账单")
    elif sid.startswith("scene.utility.summary."):
        yield names[-2]+leaf
    elif sid.startswith("scene.lights.rooms."):
        yield names[-2]+leaf
        yield names[-2]+"的"+leaf
    elif sid.startswith("scene.lights.fixtures."):
        yield leaf+"概况"
    elif sid.startswith("scene.appliance."):
        if len(names)>2:
            yield names[-2]+leaf
            yield names[-2]+"的"+leaf
        else:
            yield leaf+"概况"
    elif sid.startswith("scene.home."):
        if len(names)>2:
            yield leaf+names[-2]
            yield leaf+"的"+names[-2]
        else:
            yield leaf+"概况"

class SceneLanguageIndex:
    def __init__(self, items, scenes):
        candidates = defaultdict(set)
        self.paths = {}
        for sid in scenes:
            node = items[sid]
            names = [node.name]
            while node.parent != "scene":
                node = items[node.parent]
                names.insert(0, node.name)
            path = " · ".join(names)
            self.paths[sid] = path
            phrases = scoped_phrases(sid,names)
            for phrase in (*phrases, *EXPLICIT.get(sid, ())):
                key = normalize(phrase)
                if key:
                    candidates[key].add(sid)
        self.exact = {k: next(iter(v)) for k,v in candidates.items() if len(v)==1}
        self.ambiguous = frozenset(k for k,v in candidates.items() if len(v)>1)

    def match(self, text):
        return self.exact.get(normalize(text))
