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
        b.leaf(p,"lights.fixtures",fixture.name,fixture.order,ids(p,"single_state","brightness","temperature"),anchor=p+".single_state",alias=p)
    b.leaf("lights.abnormal","lights","灯光异常",40,ids("lights.abnormal","offline","abnormal"),anchor="lights.abnormal.abnormal",alias="lights.abnormal")
    return b.rows

def build_layout(menu):
    return utility_layout()+lights_layout(menu)
