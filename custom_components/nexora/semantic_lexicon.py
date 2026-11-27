"""Semantic vocabulary and profiles for the original four registered query families.

This module describes queries only. It does not recognize, execute, route, infer
entity IDs, or change the authoritative catalog. Parameter parsing is separate.
"""
from dataclasses import dataclass
from itertools import product

FAMILIES = {"LuxeHomeQuery":"home","LuxeLightQuery":"lights",
            "LuxeApplianceQuery":"appliance","LuxeUtilityQuery":"utility"}
ROOMS = {"卫生间":("卫生间","厕所"),"主卧":("主卧","主卧室"),
         "次卧":("次卧","次卧室"),"儿童房":("儿童房","小孩房"),
         "客餐厅":("客餐厅","客餐厅区域"),"玄关":("玄关","入户玄关")}
WHOLE = ("全屋","家里","家中")
DEVICES = {"w":("洗衣机",),"m":("主卧空调","主卧室空调"),
           "s":("次卧空调","次卧室空调"),"b":("浴霸",),
           "a":("晾衣机","晾衣架"),"f":("餐厅风扇","餐厅吊扇"),
           "p":("净水器",),"ac":("全屋空调","家里空调")}
UTILITIES = {"e":("电费",),"w":("水费",),"g":("燃气费","燃气","天然气费","天然气"),
             "all":("水电气",)}
PERIODS = {"today":("今天","今日"),"yesterday":("昨天","昨日"),
           "before":("前天",),"current":("这个月","本月"),"previous":("上个月","上月"),
           "year":("今年","本年"),"last_year":("去年","上一年")}
# Only grammatically safe substitutions; do not delete arbitrary words,
# negation, time, units, or device targets.
STATUS = ("现在怎么样","目前状态","当前状态","状态如何")
POWER = ("开着没","开着吗","开了没有","有没有开","开了吗","开了没")
FAULT = ("有没有故障","有没有报错","故障了吗")
AMOUNT = ("余额","余额多少","还剩多少钱","还有多少钱","剩多少钱","剩多少","还剩多少","账户余额","余额还有多少","余额还剩多少","账户里还有多少钱","还剩几块钱","还有几块钱")
HOME = {
 "family":("家里都有谁","家里现在有哪些人","现在谁在家","家里现在都有谁"),
 "family_count":("家里几个人","现在几个人在家","家里有多少人"),
 "person":("{s}回家没","{s}在不在家","{s}现在在家没"),
 "temp":("{s}现在几度","{s}室温多少","{s}现在多少度"),
 "hum":("{s}湿度是多少","{s}现在湿度","{s}空气湿度多少"),
 "room_env":("{s}温度和湿度","{s}现在温湿度","{s}温湿度多少"),
 "env":("家里环境怎么样","家里现在的环境","全屋环境情况"),
 "temp_avg":("全屋平均温度","家里平均几度"),
 "temp_max":("家里哪儿最热","家里哪里温度最高"),
 "temp_min":("家里哪儿最冷","家里哪里温度最低"),
 "hum_avg":("全屋平均湿度","家里平均湿度多少"),
 "hum_max":("家里哪里最潮湿","家里哪个房间湿度最高"),
 "hum_min":("家里哪里最干燥","家里哪个房间湿度最低"),
 "presence":("{s}现在有人没","{s}有人没有","{s}现在有没有人","{s}有人没"),
 "lux":("{s}光照强度","{s}环境光照度","{s}光照强度多少"),
 "duration":("{s}人体感应多久了","{s}人体感应持续了多久"),
 "duration_present":("{s}有人多长时间了","{s}有人多久"),
 "duration_absent":("{s}没人多久了","{s}没人多长时间了"),
 "presence_all":("家里哪些房间有人","哪里有人"),
 "lux_all":("家里各处光照度","各房间光照度"),
 "lux_max":("家里哪儿最亮","全屋哪里光照度最高"),
 "lux_min":("家里哪儿最暗","全屋哪里光照度最低"),
 "lock":("大门锁好了吗","入户门锁了没","大门上锁没"),
 "door":("大门关严了吗","入户门关好没","大门关着吗"),
 "deadbolt":("大门反锁了没","入户门反锁了吗"),
 "childlock":("门锁童锁开着没","大门童锁开启了吗"),
 "windows":("家里窗户都关了没","窗户关好了吗"),
 "lid":("马桶盖盖上了吗","马桶盖合上没","马桶盖打开了吗","马桶盖合上了吗"),
 "heater":("燃气热水器开着没","热水器现在开着吗"),
 "water":("{s}漏水了没","{s}有没有漏水报警"),
 "water_all":("家里有没有地方漏水","全屋有漏水没"),
 "battery":("{s}电池还剩多少","{s}还有多少电量","{s}电池电量多少"),
 "batteries":("家里设备电池电量","全屋设备剩余电量"),
 "battery_low":("有哪些设备快没电了","家里哪些设备电量低"),
 "curtain":("{s}开着没","{s}打开了吗","{s}关着吗"),
 "curtain_pos":("{s}开到什么位置了","{s}打开了百分之多少"),
 "curtains":("家里窗帘都是什么状态","全屋窗帘开关情况"),
 "lights":("家里照明情况","全屋灯光概况"),
 "apps_on":("家里还有什么电器没关","家里哪些电器开着"),
 "apps_running":("哪些家电还在运行","家里什么家电在工作"),
 "utility":("家里哪些水电气账户需要充值","家里水电气充值提醒"),
 "safety":("家里有没有安全警报","全屋安全报警情况"),
 "faults":("家里什么设备坏了","有哪些设备报故障"),
 "alerts":("家里有什么异常需要注意","家里有哪些提醒"),
 "overview":("家里现在怎么样","家里目前什么情况"),
}
LIGHT = {
 "list_on":("{s}哪些灯还亮着","{s}哪些灯没关","{s}有哪些灯亮着","{s}还亮着哪些灯"),
 "count_on":("{s}亮着几组灯","{s}亮着几盏灯","{s}有几组灯开着","{s}还有几组灯亮着"),
 "list_off":("{s}哪些灯没开","{s}哪些灯关着"),
 "count_off":("{s}有几组灯关着","{s}关着几盏灯"),
 "total":("{s}一共有几组灯","{s}总共有几组灯"),
 "all_off":("{s}灯全关了没","{s}灯都关了没","{s}灯是不是全关了","{s}灯全关了吗"),
 "all_on":("{s}灯全开了没","{s}灯都开了没"),
 "offline":("{s}有没有灯掉线了","{s}哪些灯离线了"),
 "abnormal":("{s}灯有没有异常","{s}灯具状态正常吗"),
 "single_state":tuple("{s}"+x for x in POWER)+("{s}亮着没","{s}关着吗"),
 "brightness":("{s}现在多亮","{s}亮度多少","{s}亮度百分之多少"),
 "temperature":("{s}色温多少","{s}现在色温","{s}色温几k"),
}
# Common metrics plus device-specific distinctions (e.g. washer water vs
# AC indoor temperature vs purifier water temperature).
COMMON_APPLIANCE = {"status":STATUS,"power":POWER,"fault":FAULT,
 "light":("灯开着没","照明开着吗","照明灯状态"),
 "mode":("当前是什么模式","现在什么模式"),"target":("调的几度","现在调的几度","设了几度","设置的温度多少","设了多少度")}
APPLIANCE = {
 "w":{"status":STATUS+("洗完了没","洗完没","现在洗完了吗"),"program":("选的什么程序","现在洗什么程序"),"phase":("洗到哪了","洗到哪一步"),
      "remaining":("还要多久洗好","还剩多久","多久能洗完"),
      "door":("门关好没","筒门关着吗"),"lock":("门锁锁好了吗","筒门锁上没"),
      "child":("童锁开着没","儿童锁开启了吗"),"temp":("洗衣水温几度","洗涤水温多少"),
      "spin":("脱水多少转","脱水转速多少"),"rinse":("还要漂洗多少次","剩几次漂洗"),
      "detergent":("洗衣液还剩吗","还有洗衣液吗"),"softener":("柔顺剂还剩吗","还有柔顺剂吗"),
      "water":("这次用了多少水","这次洗衣用水量"),"energy":("这次用了多少电","这次洗衣耗电量"),
      "totalwater":("总共用了多少水","累计耗水量"),"totalenergy":("总共用了多少电","累计耗电量"),
      "cycles":("总共洗了几次","累计洗衣次数")},
 "m":{"status":STATUS+POWER,"action":("现在在制冷吗","是不是在制冷"),"temp":("测到几度","室内现在几度","室温多少","实际温度多少"),
      "fan":("风速几档","风速多少"),"swing":("扫风开着没","摆风开启了吗"),"preset":("预设什么模式","预设模式是什么")},
 "s":{},
 "b":{"heat":("暖风开着没","暖风开启了吗"),"vent":("换气开着没","排气开着吗"),
      "blow":("吹风开着没","吹风开启了吗"),"heatlevel":("暖风几档","取暖几档"),
      "ventlevel":("换气几档","排气档位多少"),"blowlevel":("吹风几档","吹风档位多少"),
      "temp":("现在测到几度","当前温度多少"),"sterilize":("杀菌开着没","正在杀菌吗"),
      "steriletime":("杀菌还要多久","杀菌剩余时间"),"lightremain":("灯延时还有多久","照明延时剩余时间"),
      "heatremain":("延时关机还要多久","延时关闭剩余时间")},
 "a":{"light":("照明功能开着没","照明开着吗","照明功能状态"),"position":("现在到什么位置了","降到哪了","位置多少"),"limits":("上下限位多少","上下限位设置是多少")},
 "f":{"light":("照明功能开着没","照明开着吗","照明功能状态"),"speed":("几档","风速几档"),"natural":("自然风什么场景","自然风场景是什么")},
 "p":{"filters":("滤芯还剩多少","滤芯剩余寿命"),"ppc":("ppc滤芯还剩多少","ppc寿命多少"),
      "ro":("ro滤芯还剩多少","ro寿命多少"),"days":("滤芯还能用几天","滤芯还可以用多久"),
      "replace":("滤芯该换了吗","滤芯需要更换吗"),"tds":("出水tds多少","水的tds多少"),
      "temp":("出水几度","水温多少"),"volume":("上次制了多少水","最近一次制水量多少"),
      "duration":("上次制水用了多久","最近制水耗时"),"holiday":("假期模式开着没","假期模式开启了吗"),
      "mode":("现在什么出水模式","出水模式是什么")},
 "ac":{"status":("家里哪台空调还开着","哪些空调没关"),"count":("家里开了几台空调","有几台空调开着","家里还有几台空调开着"),
       "temp":("两台空调各自室温","两台空调测到几度"),"target":("两台空调分别调了几度","两台空调各设了几度")},
}
APPLIANCE["s"]=APPLIANCE["m"]
# Safe, whole phrases with the period/account composed separately. Do not
# conflate latest bill, current calendar period, cumulative bills or payment.
UTILITY = {
 "e":{"balance":tuple("{s}"+x for x in AMOUNT),"debt":("电费欠费没","电费有没有欠费"),
      "daily":("最近一天用了几度电","最近一天耗电多少"),"latest_usage":("最新一期用了几度电","最近月度用电多少"),
      "latest_cost":("最新一期电费多少","最近月度电费多少"),"year_usage":("今年总共用了几度电","今年用了几度电"),
      "year_cost":("今年电费花了多少","今年电费多少"),"update":("电费余额几点更新的","电费余额更新了没"),
      "h_day":("{p}用了几度电","{p}耗电多少","{p}用电量多少"),
      "h_month_usage":("{p}用了几度电","{p}耗电多少","{p}用电量多少"),
      "h_month_cost":("{p}电费花了多少","{p}电费多少","{p}电费多少钱"),
      "h_year_usage":("{p}账单累计用了几度电","{p}账单累计用电多少"),
      "h_year_cost":("{p}账单电费合计多少","{p}账单累计电费多少"),
      "h_avg":("{p}每天平均用了几度电","{p}平均每天用电量"),
      "h_coverage":("电费历史从什么时候开始","用电历史覆盖多久")},
 "w":{"balance":tuple("{s}"+x for x in AMOUNT),"debt":("水费欠费没","水费有没有欠费"),
      "latest_usage":("这期用了多少吨水","这期用水多少"),"latest_cost":("这期水费多少钱","这期水费多少"),
      "read":("水表上次什么时候抄的","水费上次抄表时间"),"meter":("水表这期读数多少","本期水表读数是多少"),
      "update":("水务数据几点更新的","水务数据更新了没"),
      "history_usage":("{p}用了几吨水","{p}用水多少","{p}用水量多少"),
      "history_cost":("{p}水费花了多少","{p}水费多少钱","{p}水费多少"),
      "h_year_usage":("{p}账单累计用了几吨水","{p}账单累计用水多少"),
      "h_year_cost":("{p}账单水费合计多少","{p}账单累计水费多少"),
      "h_coverage":("用水历史覆盖多久","水费历史从什么时候开始")},
 "g":{"balance":tuple("{s}"+x for x in AMOUNT),"debt":("燃气欠费没","燃气费有没有欠费"),
      "latest_usage":("这期用了多少方气","这期用气多少"),"latest_cost":("这期燃气费多少钱","这期燃气账单多少"),
      "prior_usage":("上一期用了多少方气","上期用气多少"),"read":("燃气表上次什么时候抄的","燃气上次抄表时间"),
      "meter":("燃气表这期读数多少","本期燃气表读数是多少"),"year_usage":("今年总共用了多少方气","今年累计用气多少"),
      "settlement":("这期燃气账单结清了没","本期燃气账单交清了吗"),"update":("燃气数据几点更新的","燃气数据更新了没"),
      "last_pay":("上次交了多少燃气费","燃气上次交了多少钱"),"last_pay_date":("燃气上次什么时候交的费","上次燃气缴费是哪天"),
      "last_pay_channel":("燃气上次在哪交的费","上次燃气缴费渠道是什么"),
      "year_pay":("今年交了多少燃气费","今年燃气总共缴了多少钱"),"year_pay_count":("今年燃气交了几次","今年燃气缴费几次"),
      "payment_update":("燃气缴费记录几点更新的","燃气缴费记录更新了没"),
      "tier":("现在是第几档气价","燃气现在第几阶梯","现在是几档气价"),
      "h_month_usage":("{p}用了多少方气","{p}用气多少","{p}用气量多少"),
      "h_month_cost":("{p}燃气费花了多少","{p}燃气费多少钱","{p}燃气费多少"),
      "h_year_usage":("{p}账单累计用了多少方气","{p}账单累计用气多少"),
      "h_year_cost":("{p}账单燃气费合计多少","{p}账单累计燃气费多少"),
      "h_coverage":("燃气历史覆盖多久","燃气历史从什么时候开始")},
 "all":{"balances":("水电气账户各剩多少钱","水电气余额分别是多少"),"debts":("水电气有没有欠费账户","水电气欠费情况"),
        "low":("哪些账户该充值了","水电气哪些账户要充值"),"updates":("水电气什么时候更新的","水电气数据更新了没")},
}
for _n,_cn in ((1,"一"),(2,"二"),(3,"三")):
    UTILITY["g"][f"tier{_n}_price"]=(f"燃气第{_cn}档多少钱一方",f"燃气第{_n}阶梯气价多少")
    UTILITY["g"][f"tier{_n}_used"]=(f"燃气第{_cn}档用了多少方",f"燃气第{_n}阶梯用了多少气")
    if _n<3:
        UTILITY["g"][f"tier{_n}_remaining"]=(f"燃气第{_cn}档还有多少方",f"燃气第{_n}阶梯剩余额度")
        UTILITY["g"][f"tier{_n}_limit"]=(f"燃气第{_cn}档额度多少",f"燃气第{_n}阶梯限额")

@dataclass(frozen=True)
class Profile:
    capability: str
    family: str
    target: str
    metric: str
    period: str
    parameter: str
    account: str

def describe(cap):
    family=FAMILIES.get(cap.get("intent"))
    if family is None:
        return None
    slots=cap.get("slots",{})
    if family=="home":
        target,metric=slots.get("luxe_home_target",""),slots.get("luxe_home_query","")
    elif family=="lights":
        target,metric=slots.get("luxe_light_scope",cap.get("category","")),slots.get("light_query","")
    elif family=="appliance":
        target,metric=slots.get("luxe_appliance_device",""),slots.get("luxe_appliance_query","")
    else:
        target,metric=slots.get("utility_kind",""),slots.get("utility_metric","")
    if not target or not metric:
        return None
    return Profile(cap["id"],family,target,metric,slots.get("utility_period",""),
                   cap.get("parameter") or "",slots.get("luxe_utility_property",""))

def patterns(cap,menu):
    """Generate candidate whole phrases; parameterized entries are described
    but intentionally not expanded into spoken dates in this phase."""
    p=describe(cap)
    if p is None or p.parameter:
        return set()
    item=getattr(menu,"items",{}).get(cap.get("category"))
    name=getattr(item,"name","")
    if p.family=="home":
        subjects=ROOMS.get(p.target,(p.target,))
        if p.metric in {"curtain","curtain_pos"}:
            # Preserve the catalog's specific curtain target (客厅 vs 客餐厅).
            prefix=cap["sentence"].split("窗帘",1)[0]+"窗帘"
            subjects=(prefix,)
        templates=HOME.get(p.metric,())
    elif p.family=="lights":
        subjects=WHOLE if p.target=="all" else ROOMS.get(name,(name,))
        templates=LIGHT.get(p.metric,())
        if p.target=="all":
            templates+= {"list_on":("哪些灯没关","哪些灯还亮着"),"offline":("有没有灯掉线了",)}.get(p.metric,())
    elif p.family=="appliance":
        subjects=DEVICES.get(p.target,())
        specific=APPLIANCE.get(p.target,{})
        templates=specific.get(p.metric,COMMON_APPLIANCE.get(p.metric,()))
        if p.target!="ac":
            templates=tuple("{s}"+x for x in templates)
        # Implicit objects only for distinctive activities, not bare state.
        if p.target=="w":
            templates+= {"phase":("洗到哪了","洗到哪一步了"),"remaining":("还有多久洗好","还有多久洗完"),
                         "status":("衣服洗好了吗",)}.get(p.metric,())
        if p.target=="p":
            templates+= {"filters":("滤芯还剩多少",),"replace":("滤芯该换了吗","滤芯要换了吗")}.get(p.metric,())
    else:
        subjects=UTILITIES.get(p.target,())
        templates=UTILITY.get(p.target,{}).get(p.metric,())
        if p.target=="all" and p.period=="all":
            # Do not collapse primary and all-account aggregates.
            templates={"balances":("所有账户各剩多少钱","所有账户余额分别是多少"),
                       "debts":("所有账户有没有欠费","所有账户欠费没"),
                       "low":("所有账户哪些该充值了","全部账户哪些要充值"),
                       "updates":("所有账户什么时候更新的","全部账户数据更新了没")}.get(p.metric,())
    periods=PERIODS.get(p.period,("",))
    phrases={t.format(s=s,p=period) for t,s,period in product(templates,subjects,periods)}
    if p.family=="utility" and p.target=="e":
        settings=getattr(menu,"settings",{})
        if p.account=="l":
            secondary=settings.get("secondary","")
            labels={secondary,settings.get("secondary_label","")} - {""}
            if not secondary:
                return set()
            phrases={label+sep+q for q,label,sep in product(phrases,labels,("","的"))}
        elif p.account=="j":
            label=settings.get("primary_label","")
            if label:
                phrases|={label+sep+q for q,sep in product(phrases,("","的"))}
    return {q for q in phrases if q}
