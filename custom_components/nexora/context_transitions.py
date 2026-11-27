"""Conservative registered follow-up transitions. No transcript or entity inference."""
from dataclasses import dataclass
from .semantic_lexicon import describe, ROOMS, DEVICES

@dataclass(frozen=True)
class Selection:
    capability: str
    params: tuple = ()

# Only these metric groups may change within a known device/room.
GROUPS={
 "home":({"temp","hum","room_env"},{"presence","lux","duration","duration_present","duration_absent"},
         {"lock","door","deadbolt","childlock"},{"curtain","curtain_pos"},{"family","family_count"}),
 "lights":({"list_on","count_on","list_off","count_off","total","all_off","all_on","offline","abnormal"},
           {"single_state","brightness","temperature"}),
 "appliance":({"status","mode","action","target","temp","fan","swing","preset","power","fault","program","phase",
               "remaining","door","lock","child","spin","rinse","detergent","softener","water","energy","totalwater",
               "totalenergy","cycles","heat","vent","blow","light","heatlevel","ventlevel","blowlevel","sterilize",
               "steriletime","lightremain","heatremain","position","limits","speed","natural","filters","ppc","ro",
               "days","replace","tds","volume","duration","holiday","count"},),
}
METRICS={
 "home":{"温度":"temp","现在几度":"temp","湿度":"hum","温湿度":"room_env","光照度":"lux","环境亮度":"lux",
         "有人吗":"presence","有人多久":"duration_present","没人多久":"duration_absent",
         "关门状态":"door","关闭状态":"door","上锁状态":"lock","锁了吗":"lock","反锁状态":"deadbolt","反锁了吗":"deadbolt",
         "童锁状态":"childlock","位置":"curtain_pos","开关状态":"curtain","人数":"family_count","在家人员":"family"},
 "lights":{"亮度":"brightness","色温":"temperature","开关状态":"single_state","状态":"single_state",
           "开启数量":"count_on","开了几组":"count_on","亮着几盏":"count_on","哪些灯亮着":"list_on",
           "关闭数量":"count_off","哪些灯关着":"list_off","总数":"total","都关了吗":"all_off","都开了吗":"all_on",
           "离线情况":"offline","异常情况":"abnormal"},
 "appliance":{"状态":"status","开关状态":"power","运行阶段":"phase","洗到哪了":"phase","剩余时间":"remaining",
              "还要多久":"remaining","多久洗好":"remaining","程序":"program","筒门状态":"door","筒门锁":"lock",
              "童锁":"child","故障":"fault","水温":"temp","设定温度":"target","调的几度":"target","设了几度":"target",
              "检测温度":"temp","实际温度":"temp","室内温度":"temp","室温":"temp","现在屋里几度":"temp",
              "风速":"fan","扫风":"swing","模式":"mode","运行模式":"mode","预设模式":"preset",
              "暖风":"heat","换气":"vent","吹风":"blow","照明":"light","暖风档位":"heatlevel",
              "换气档位":"ventlevel","吹风档位":"blowlevel","位置":"position","限位":"limits","风扇档位":"speed",
              "滤芯寿命":"filters","ppc滤芯":"ppc","ro滤芯":"ro","滤芯剩余天数":"days","滤芯更换提醒":"replace",
              "tds":"tds","出水温度":"temp","制水量":"volume","制水耗时":"duration","用水量":"water","用电量":"energy"},
}
APPLIANCE_METRIC_TARGETS={
 "水温":{"w","p"},"出水温度":{"p"},"室温":{"m","s"},"室内温度":{"m","s"},
 "现在屋里几度":{"m","s"},"检测温度":{"m","s","b"},"实际温度":{"m","s","b"},
 "设定温度":{"m","s","b","ac"},"调的几度":{"m","s","b"},"设了几度":{"m","s","b"},
 "用水量":{"w"},"用电量":{"w"},"风扇档位":{"f"}}
REPEAT={"再查一次","再查一下","重新查询","再查一遍","现在呢","现在怎么样"}
AC_ROOMS={"主卧":"m","主卧室":"m","次卧":"s","次卧室":"s"}

class Transitions:
    def __init__(self,menu):
        self.menu=menu
        self.profiles={}
        self.targets={}
        for cap in menu.capabilities.values():
            p=describe(cap)
            if not p:
                continue
            self.profiles[cap["id"]]=p
            item=getattr(menu,"items",{}).get(cap.get("category"))
            name=getattr(item,"name","")
            if p.family=="home":
                names=ROOMS.get(p.target,(p.target,)) if p.target!="all" else ()
            elif p.family=="lights":
                names=ROOMS.get(name,(name,)) if p.target!="all" else ("全屋","家里")
            elif p.family=="appliance":
                names=DEVICES.get(p.target,())
                if p.target in {"m","s"}:
                    names+=tuple(k for k,v in AC_ROOMS.items() if v==p.target)
            else:
                names=()
            for name in names:
                if name:
                    self.targets.setdefault((p.family,name.casefold()),set()).add(p.target)
        self.known_targets={name for family,name in self.targets}
        self.known_metrics=set().union(*(set(m) for m in METRICS.values()))
    def reserved(self,text):
        t=text.removesuffix("呢")
        return text in REPEAT or (text.endswith("呢") and (t in self.known_targets or t in self.known_metrics))
    def select(self,p,target,metric):
        # Home 'all' identifies multiple distinct domains; metric group checks
        # happen in the caller and cannot use availability to disambiguate.
        choices=[x.capability for x in self.profiles.values()
                 if x.family==p.family and x.target==target and x.metric==metric and not x.parameter]
        return Selection(choices[0]) if len(choices)==1 else "当前没有唯一对应的本地查询，请明确查询对象或指标。"
    def route(self,capability,text):
        p=self.profiles.get(capability)
        if p is None or p.family=="utility":
            return None
        t=text.removesuffix("呢")
        if text in REPEAT:
            return Selection(capability)
        targets=self.targets.get((p.family,t),set())
        if text.endswith("呢") and targets:
            if len(targets)!=1:
                return "请明确要查询的设备。"
            target=next(iter(targets))
            if p.family=="appliance" and (target!=p.target and not {target,p.target}<={"m","s"}):
                return "不同类型的家电不能直接继承查询指标，请明确查询项目。"
            if p.family=="lights" and (p.target.startswith("lights.fixtures.")!=target.startswith("lights.fixtures.")):
                return "请明确查询单个灯具还是房间灯光。"
            return self.select(p,target,p.metric)
        metric=METRICS.get(p.family,{}).get(t)
        if metric is not None:
            if p.family=="appliance":
                permitted=APPLIANCE_METRIC_TARGETS.get(t)
                if permitted is not None and p.target not in permitted:
                    return "该设备没有此含义的查询指标，请明确查询对象。"
                if t=="风速" and p.target=="f":
                    metric="speed"
                if t=="开关状态" and p.target in {"m","s","b","f","a","p"}:
                    metric="status"
            if not any(p.metric in g and metric in g for g in GROUPS.get(p.family,())):
                return "当前查询无法直接切换到该指标，请明确查询对象。"
            return self.select(p,p.target,metric)
        if self.reserved(text):
            return "请补充查询对象或指标，不能跨业务模块自动推断。"
        return None
