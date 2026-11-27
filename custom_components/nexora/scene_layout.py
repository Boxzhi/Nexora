"""Presentation only: registered capability IDs remain the execution authority."""
from .scene_menu import Node

class Layout:
    def __init__(self):
        self.rows=[]
    def group(self,id,parent,name,order,alias=""):
        self.rows.append(Node("scene."+id,"scene."+parent if parent else "scene",name,order,alias_of=alias))
    def leaf(self,id,parent,name,order,members,*,anchor="",supplements=(),stop_on=(),alias=""):
        self.rows.append(Node("scene."+id,"scene."+parent,name,order,tuple(members),anchor,tuple(supplements),tuple(stop_on),alias))

def ids(prefix,*metrics):
    return tuple(prefix+"."+m for m in metrics)

def history(b,prefix,parent,water=False):
    hist=prefix+".history"
    usage,cost=("history_usage","history_cost") if water else ("h_month_usage","h_month_cost")
    b.group(parent+".monthly",parent,"月度账单查询",60)
    periods=[("current","本月"),("previous","上月"),("year","今年指定月份"),("last_year","去年指定月份")]
    if not water:
        periods.append(("explicit","指定年月"))
    for i,(period,name) in enumerate(periods,1):
        members=(f"{hist}.{usage}.{usage}_{period}",f"{hist}.{cost}.{cost}_{period}")
        b.leaf(parent+".monthly."+period,parent+".monthly",name,i,members,anchor=members[1])
    b.group(parent+".annual",parent,"年度账单查询",70)
    for i,(period,name) in enumerate((("year","今年"),("last_year","去年"),("explicit","指定年份")),1):
        members=tuple(f"{hist}.{metric}.{metric}_{period}" for metric in ("h_year_usage","h_year_cost"))
        b.leaf(parent+".annual."+period,parent+".annual",name,i,members,anchor=members[1])

def utility_layout():
    b=Layout()
    b.group("utility","","水电气",100,"utility")
    b.group("utility.electric","utility","电费",10,"utility.electric")
    for code,label,order in (("j","{primary_label}",10),("l","{secondary_label}",20)):
        p="utility.electric."+code
        basic=p+".basic"
        hist=p+".history"
        b.group(p,"utility.electric",label,order,p)
        b.leaf(p+".balance",p,"账户余额",10,ids(basic,"balance","debt","update"),anchor=basic+".balance")
        b.leaf(p+".recent",p,"最近用电",20,ids(basic,"daily")+ids(hist,"h_avg_current"),anchor=basic+".daily")
        b.leaf(p+".latest",p,"最新月度账单",30,ids(basic,"latest_usage","latest_cost"),anchor=basic+".latest_cost")
        b.leaf(p+".year",p,"本年用电统计",40,ids(basic,"year_usage","year_cost"),anchor=basic+".year_cost")
        b.group(p+".day",p,"日用电查询",50,hist+".day")
        for i,(period,name) in enumerate((("today","今天"),("yesterday","昨天"),("before","前天"),("explicit","指定日期"),("year","今年指定日期")),1):
            cid=hist+".day.h_day_"+period
            b.leaf(p+".day."+period,p+".day",name,i,(cid,),anchor=cid)
        history(b,p,p)
        b.leaf(p+".data",p,"数据详情",80,ids(basic,"update")+ids(hist,"h_coverage"))
    p="utility.water"
    b.group(p,"utility","水费",20,p)
    b.leaf(p+".balance",p,"账户余额",10,ids(p,"balance","debt"),anchor=p+".balance")
    b.leaf(p+".bill",p,"本期账单",20,ids(p,"latest_usage","latest_cost","read","meter"),anchor=p+".latest_cost")
    history(b,p,p,water=True)
    b.leaf(p+".data",p,"数据详情",80,ids(p,"update")+ids(p+".history","h_coverage"))
    p="utility.gas"
    basic=p+".basic"
    b.group(p,"utility","燃气费",30,p)
    b.leaf(p+".balance",p,"账户余额",10,ids(basic,"balance","debt"),anchor=basic+".balance")
    b.leaf(p+".bill",p,"本期账单",20,ids(basic,"latest_usage","latest_cost","prior_usage","read","meter","settlement","year_usage"),anchor=basic+".latest_cost")
    b.group(p+".pay",p,"燃气缴费查询",30,p+".pay")
    pay=p+".pay"
    b.leaf(pay+".recent",pay,"最近缴费记录",10,ids(pay,"last_pay","last_pay_date","last_pay_channel","payment_update"),anchor=pay+".last_pay")
    b.leaf(pay+".annual",pay,"年度缴费统计",20,ids(pay,"year_pay","year_pay_count","payment_update"),anchor=pay+".year_pay")
    tier=p+".tier"
    b.group(tier,p,"燃气阶梯查询",40,tier)
    b.leaf(tier+".current",tier,"当前用气阶梯",10,ids(tier,"tier"),anchor=tier+".tier")
    b.leaf(tier+".details",tier,"各阶梯详细数据",20,ids(tier,"tier","tier1_price","tier1_used","tier1_remaining","tier1_limit","tier2_price","tier2_used","tier2_remaining","tier2_limit","tier3_price","tier3_used"))
    history(b,p,p)
    b.leaf(p+".data",p,"数据详情",80,ids(basic,"update")+ids(p+".history","h_coverage"))
    p="utility.summary"
    b.group(p,"utility","综合查询",40,p)
    for code,label,order,suffix in (("primary","主住所",10,""),("all","全部账户",20,"_all")):
        s=p+"."+code
        b.group(s,p,label,order,s)
        b.leaf(s+".overview",s,"账户概况",10,ids(s,*[x+suffix for x in ("balances","debts","low")]),anchor=s+".balances"+suffix)
        b.leaf(s+".data",s,"数据更新时间",20,ids(s,"updates"+suffix),anchor=s+".updates"+suffix)
    return b.rows

def lights_layout(menu):
    b=Layout()
    b.group("lights","","灯光",200,"lights")
    b.leaf("lights.all","lights","全屋照明概况",10,ids("lights.all","total","list_on","list_off")+ids("lights.abnormal","offline"),anchor="lights.all.list_on",alias="lights.all")
    b.group("lights.rooms","lights","按房间查询",20,"lights.rooms")
    for room in menu.children["lights.rooms"]:
        p=room.id
        b.group(p,"lights.rooms",room.name,room.order,p)
        b.leaf(p+".overview",p,"照明状态",10,ids(p,"total","list_on","list_off","offline"),anchor=p+".list_on")
        b.leaf(p+".issues",p,"灯光异常",20,ids(p,"offline","abnormal"),anchor=p+".abnormal")
    b.group("lights.fixtures","lights","按灯具查询",30,"lights.fixtures")
    for fixture in menu.children["lights.fixtures"]:
        p=fixture.id
        name={"lights.fixtures.bath_panel":"卫生间平板灯","lights.fixtures.bath_heater":"浴霸灯"}.get(p,fixture.name)
        b.leaf(p,"lights.fixtures",name,fixture.order,ids(p,"single_state","brightness","temperature"),anchor=p+".single_state",alias=p)
    b.leaf("lights.abnormal","lights","灯光异常",40,ids("lights.abnormal","offline","abnormal"),anchor="lights.abnormal.abnormal",alias="lights.abnormal")
    return b.rows

def appliance_layout():
    b=Layout()
    b.group("appliance","","家电",300,"appliance")
    p="appliance.washer"
    b.group(p,"appliance","洗衣机",10,p)
    b.leaf(p+".progress",p,"当前洗衣进度",10,ids(p,"status","power","program","phase","remaining"),
        anchor=p+".status",supplements=ids(p,"program","phase","remaining"),stop_on=("device_off","cycle_not_running"))
    b.leaf(p+".settings",p,"洗涤参数",20,ids(p,"temp","spin","rinse"))
    b.leaf(p+".doors",p,"筒门及锁状态",30,ids(p,"door","lock","child"))
    b.leaf(p+".detergents",p,"洗涤剂余量",40,ids(p,"detergent","softener"))
    b.leaf(p+".consumption",p,"用水用电统计",50,ids(p,"water","energy","totalwater","totalenergy","cycles"))
    b.leaf(p+".fault",p,"故障状态",60,ids(p,"fault"),anchor=p+".fault")
    p="appliance.ac"
    b.group(p,"appliance","空调",20,p)
    a=p+".all"
    b.leaf(a,p,"全部空调",10,ids(a,"status","count","temp","target"),anchor=a+".status",alias=a)
    for target,name,order in (("master","主卧空调",20),("secondary","次卧空调",30)):
        a=p+"."+target
        b.group(a,p,name,order,a)
        b.leaf(a+".overview",a,"运行状态",10,ids(a,"status","temp","mode","action","target"),
            anchor=a+".status",supplements=ids(a,"mode","action","target"),stop_on=("device_off",))
        b.leaf(a+".settings",a,"运行参数",20,ids(a,"status","target","fan","swing","preset"),
            anchor=a+".status",supplements=ids(a,"target","fan","swing","preset"),stop_on=("device_off",))
    p="appliance.bath"
    b.group(p,"appliance","浴霸",30,p)
    b.leaf(p+".overview",p,"当前运行状态",10,ids(p,"status","mode"),anchor=p+".status")
    b.leaf(p+".heating",p,"取暖及温度",20,ids(p,"heat","heatlevel","temp","target"))
    b.leaf(p+".ventilation",p,"通风及吹风",30,ids(p,"vent","ventlevel","blow","blowlevel"))
    b.leaf(p+".sterilization",p,"杀菌状态",40,ids(p,"sterilize","steriletime"))
    b.leaf(p+".timers",p,"延时关闭",50,ids(p,"lightremain","heatremain"))
    b.leaf(p+".fault",p,"故障状态",60,ids(p,"fault"),anchor=p+".fault")
    p="appliance.airer"
    b.leaf(p,"appliance","晾衣机",40,ids(p,"status","position","limits","light","fault"),anchor=p+".status",alias=p)
    p="appliance.fan"
    b.leaf(p,"appliance","餐厅风扇",50,ids(p,"status","light","speed","mode","natural"),
        anchor=p+".status",supplements=ids(p,"speed","mode","natural"),stop_on=("device_off",),alias=p)
    p="appliance.purifier"
    b.group(p,"appliance","净水器",60,p)
    b.leaf(p+".overview",p,"当前运行状态",10,ids(p,"status","holiday","mode"),anchor=p+".status")
    b.leaf(p+".filter_health",p,"滤芯健康",20,ids(p,"filters","days","replace"),anchor=p+".filters")
    b.leaf(p+".water",p,"水质及水温",30,ids(p,"tds","temp"))
    b.leaf(p+".recent",p,"最近制水记录",40,ids(p,"volume","duration"))
    b.leaf(p+".fault",p,"故障状态",50,ids(p,"fault"),anchor=p+".fault")
    return b.rows

def home_layout():
    b=Layout()
    b.group("home","","全屋状态",400,"home")
    p="home.overview"
    b.leaf(p,"home","全屋概况",10,ids(p,"overview_all"),anchor=p+".overview_all",alias=p)
    p="home.family"
    b.leaf(p,"home","家庭成员",20,ids(p,"family_all"),anchor=p+".family_all",alias=p)
    p="home.env"
    b.group(p,"home","环境温湿度",30,p)
    b.leaf(p+".whole",p,"全屋环境",10,ids(p,"env_all","temp_max_all","temp_min_all","hum_max_all","hum_min_all"),anchor=p+".env_all")
    for i,(key,name) in enumerate((("master","主卧"),("secondary","次卧"),("living_dining","客餐厅"),("bathroom","卫生间")),2):
        q=p+"."+key
        members=ids(q,("temp_" if key=="bathroom" else "room_env_")+key)
        b.leaf(q,p,name,i*10,members,anchor=members[0],alias=q)
    p="home.presence"
    b.group(p,"home","人体感应及光照",40,p)
    b.leaf(p+".whole",p,"全屋感应概况",10,ids(p,"presence_all_all","lux_all_all","lux_max_all","lux_min_all"),anchor=p+".presence_all_all")
    for i,(key,name,duration) in enumerate((("entry","玄关",True),("living","客厅",False),("balcony","阳台",True),("kitchen","厨房",False),("bathroom","卫生间",True)),2):
        q=p+"."+key
        members=ids(q,"presence_"+key,"lux_"+key)+ (ids(q,"duration_"+key) if duration else ())
        b.leaf(q,p,name,i*10,members,anchor=members[0],alias=q)
    p="home.access"
    b.group(p,"home","门锁及窗帘",50,p)
    q=p+".door"
    b.leaf(q,p,"入户门状态",10,ids(q,"door_all","lock_all","deadbolt_all","childlock_all"),anchor=q+".door_all",alias=q)
    q=p+".curtains"
    b.leaf(q,p,"全屋窗帘",20,ids(q,"curtain_pos_master","curtain_pos_secondary","curtain_pos_living_dining"),alias=q)
    b.leaf(p+".windows",p,"窗户状态",30,ids(p+".door","windows_all"),anchor=p+".door.windows_all")
    p="home.safety"
    b.group(p,"home","安全及异常",60,p)
    for i,(metric,name) in enumerate((("alerts_all","家庭异常概况"),("water_all_all","水浸检测"),("safety_all","安全报警"),("faults_all","设备故障")),1):
        cid=p+"."+metric
        b.leaf(cid,p,name,i*10,(cid,),anchor=cid)
    p="home.battery"
    b.group(p,"home","电池及维护",70,p)
    b.leaf(p+".low",p,"低电量设备",10,ids(p,"battery_low_all"),anchor=p+".battery_low_all")
    b.leaf(p+".all",p,"全部设备电量",20,ids(p,"batteries_all"),anchor=p+".batteries_all")
    p="home.devices"
    b.group(p,"home","其他设备",80,p)
    b.leaf(p+".lid",p,"马桶盖状态",10,ids(p,"lid_all"),anchor=p+".lid_all")
    b.leaf(p+".heater",p,"燃气热水器状态",20,ids(p,"heater_all"),anchor=p+".heater_all")
    return b.rows

def build_layout(menu):
    return utility_layout()+lights_layout(menu)+appliance_layout()+home_layout()
