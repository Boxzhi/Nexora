"""Scene presentation only; original intent speech remains authoritative.

Recognized contracts may remove repeated labels, never invent numbers or
change data coverage. Unfamiliar, conflicting and incomplete replies retain
their original wording, and failures remain attributed to the member.
"""
import re
from .reply_format import render_section

GOOD={"ok","partial_data","data_gap","state_limit","capability_limit"}
MONEY=r"-?\d+(?:\.\d+)?元"
QUANTITY=r"-?\d+(?:\.\d+)?(?:度|吨|立方米|元)"
OWNER=r"(?P<owner>[^：:。；\n]{1,70}?)"
MONTH=re.compile(OWNER+r"(?P<period>\d{4}年\d{1,2}月)(?:账单)?(?P<metric>用电量|电费|用水量|水费|用气量|燃气费)：(?P<value>"+QUANTITY+r")(?P<qual>（[^）\n]+）)?。")
YEAR=re.compile(OWNER+r"(?P<period>\d{4}年)账单累计(?P<metric>用电量|电费|用水量|水费|用气量|燃气费)：(?P<value>"+QUANTITY+r")(?P<qual>（[^）\n]+）)?。")
DEVICE_NAMES={"w":"海尔洗衣机","m":"主卧空调","s":"次卧空调","b":"米家浴霸","a":"米家晾衣机","f":"餐厅风扇","p":"米家净水器"}
LIGHT_NAMES={"all":"全屋","ke_ting":"客厅","can_ting":"餐厅","zhu_wo":"主卧","ci_wo":"次卧","er_tong_fang":"儿童房","xuan_guan":"玄关","guo_dao":"过道","chu_fang":"厨房","wei_sheng_jian":"卫生间","yang_tai":"阳台"}
PAYMENT_LABELS={
    "last_pay":("最近缴费金额","缴费金额"),
    "last_pay_date":("最近缴费时间","缴费时间"),
    "last_pay_channel":("最近缴费渠道","缴费渠道"),
    "year_pay":("年度燃气缴费金额","累计缴费"),
    "year_pay_count":("年度缴费次数","缴费次数"),
    "payment_update":("缴费历史更新时间","数据更新时间"),
}

def _bill_pair(plan,rows):
    month=".monthly." in plan.menu_scene
    year=".annual." in plan.menu_scene
    if not (month or year) or len(rows)!=2 or any(kind not in {"ok","partial_data"} for step,kind,text in rows):
        return None
    a,b=rows
    ka,kb=a[0].key,b[0].key
    if (ka.family,ka.target,ka.account,ka.period,a[0].params)!=(kb.family,kb.target,kb.account,kb.period,b[0].params):
        return None
    pattern=MONTH if month else YEAR
    x,y=pattern.fullmatch(a[2]),pattern.fullmatch(b[2])
    if not x or not y or any(x[k]!=y[k] for k in ("owner","period","qual")):
        return None
    if ka.family!="utility" or (x["metric"],y["metric"])!={"e":("用电量","电费"),"w":("用水量","水费"),"g":("用气量","燃气费")}.get(ka.target):
        return None
    if not x["value"].endswith({"用电量":"度","用水量":"吨","用气量":"立方米"}[x["metric"]]) or not y["value"].endswith("元"):
        return None
    heading=x["owner"]+" · "+x["period"]+("账单" if month else "度账单累计")
    lines=[heading,"",x["metric"]+"："+x["value"],y["metric"]+"："+y["value"]]
    if x["qual"]:
        lines.extend(("",x["qual"]))
    return "\n".join(lines)

def _payment(rows):
    lines=[]
    for step,kind,text in rows:
        names=PAYMENT_LABELS.get(step.key.metric)
        if kind in GOOD and names and step.key.family=="utility" and step.key.target=="g":
            match=re.fullmatch(r"华润燃气"+re.escape(names[0])+r"：([^。\n]+)。",text)
            if match:
                text=names[1]+"："+match[1]
        lines.append(text)
    return lines

def _tier(rows):
    # Retain conflicting or missing values verbatim. A quota is never
    # substituted for prepaid gas or the actual remaining physical amount.
    actual={}
    for step,kind,text in rows:
        m=re.fullmatch(r"华润燃气第([12])阶梯剩余气量：(\d+(?:\.\d+)?)立方米。",text)
        if kind=="ok" and m and step.key.metric=="tier"+m[1]+"_remaining":
            actual[m[1]]=m[2]
    lines=[]
    group=None
    for step,kind,text in rows:
        if step.key.metric=="tier":
            m=re.fullmatch(r"华润燃气按最近阶梯数据处于第([123])阶梯；第一阶梯剩余(\d+(?:\.\d+)?)立方米，第二阶梯剩余(\d+(?:\.\d+)?)立方米。",text)
            if kind=="ok" and m and actual=={"1":m[2],"2":m[3]}:
                text="按最近阶梯数据处于第"+m[1]+"阶梯。"
            lines.append(text)
            continue
        m=re.fullmatch(r"tier([123])_(price|used|remaining|limit)",step.key.metric)
        if m and step.key.family=="utility" and step.key.target=="g":
            if group!=m[1]:
                group=m[1]
                lines.extend(("",("第一","第二","第三")[int(group)-1]+"阶梯"))
            label={"price":"气价","used":"周期累计已用","remaining":"剩余气量","limit":"总额度"}[m[2]]
            x=re.fullmatch(r"华润燃气第"+group+r"阶梯"+label+r"：([^。\n]+)。",text)
            if kind in GOOD and x:
                text=label+"："+x[1]
        lines.append(text)
    return lines

def _scoped_lights(rows):
    lines=[]
    for step,kind,text in rows:
        name=LIGHT_NAMES.get(step.key.target)
        metric=step.key.metric
        if kind=="ok" and name and step.key.family=="lights":
            if metric=="total":
                x=re.fullmatch(re.escape(name)+r"共有(\d+)组灯具。",text)
                if x:
                    text="灯具总数："+x[1]+"组"
            elif metric in {"list_on","list_off"}:
                verb="开启" if metric=="list_on" else "关闭"
                x=re.fullmatch(re.escape(name)+r"当前有(\d+)组灯具"+verb+r"：([^。\n]+)。",text)
                if x:
                    text="已"+verb+"："+x[1]+"组（"+x[2]+"）"
            elif metric=="offline" and text==name+"暂未检测到不可用灯具。":
                text="离线检查：暂未检测到不可用灯具。"
        lines.append(text)
    return lines

def _fixture(plan,rows):
    # Only an exact state reply establishes the display name; other fields
    # must match that same target and prefix before any label is removed.
    name=None
    for step,kind,text in rows:
        if step.key.metric=="single_state" and kind=="ok":
            x=re.fullmatch(r"([^：:。；\n]{1,60})当前(已开启|已关闭)。",text)
            if x:
                name=x[1]
    if not name or name!=plan.title.rsplit(" · ",1)[-1]:
        return [text for _,_,text in rows]
    target=rows[0][0].key.target
    lines=[]
    unavailable=[]
    for step,kind,text in rows:
        if step.key.target==target and kind in GOOD:
            if step.key.metric=="single_state" and text.startswith(name+"当前"):
                text="状态："+text[len(name+"当前"):]
            elif step.key.metric in {"brightness","temperature"}:
                attr="亮度" if step.key.metric=="brightness" else "色温"
                if text==name+"当前已关闭，无法获取实时"+attr+"。" and kind=="state_limit":
                    unavailable.append(attr)
                    continue
                if text.startswith(name+"当前"+attr+"："):
                    text=text[len(name+"当前"):]
        lines.append(text)
    if unavailable:
        lines.append("实时"+"、".join(unavailable)+"：灯具已关闭，无法获取。")
    return lines

def _device(plan,rows):
    targets={step.key.target for step,_,_ in rows if step.key.family=="appliance"}
    name=DEVICE_NAMES.get(next(iter(targets))) if len(targets)==1 else None
    if not name or any(step.key.family!="appliance" for step,_,_ in rows):
        return plan.title,[text for _,_,text in rows]
    leaf=plan.title.rsplit(" · ",1)[-1]
    heading=name if plan.menu_scene in {"scene.appliance.airer","scene.appliance.fan"} else name+" · "+leaf
    lines=[]
    for step,kind,text in rows:
        if kind in GOOD and text.startswith(name):
            text=text[len(name):].lstrip("：:")
        # The same exact device-state limitation can be shared by several
        # metrics. Never remove an independently attributed error.
        if kind=="state_limit" and text in lines:
            continue
        lines.append(text)
    return heading,lines

def _presence(rows):
    # A duration reply may already include exactly the same presence state.
    # Drop the shorter duplicate only when both replies explicitly agree.
    skip=set()
    for step,kind,text in rows:
        if step.key.metric!="presence" or kind!="ok":
            continue
        x=re.fullmatch(r"([^：。\n]+)：(未检测到人体|已检测到人体|检测到人体)。",text)
        if x and any(other.key.target==step.key.target and other.key.metric=="duration"
                and ok=="ok" and re.fullmatch(re.escape(x[1]+"："+x[2])+r"，设备报告已持续[^。\n]+。",v)
                for other,ok,v in rows):
            skip.add(step)
    return [text for step,_,text in rows if step not in skip]

def compose_menu(plan,run,label,normalize):
    by_step={o.step:o for o in run.outcomes}
    rows=[]
    completed=True
    for step in plan.primary+plan.supplements:
        o=by_step.get(step)
        if o and o.kind=="skipped" and step in plan.supplements:
            continue
        if o is None or o.kind not in GOOD or not o.speech.strip():
            rows.append((step,"error",label(step)+"："+(o.error if o and o.error else "查询未完成。")))
            if step in plan.primary:
                completed=False
        else:
            rows.append((step,o.kind,normalize(step.key,o.speech)))
    combined=_bill_pair(plan,rows)
    if combined is not None:
        return combined,completed
    heading=plan.title
    scene=plan.menu_scene
    if scene.startswith("scene.utility.gas.pay."):
        heading="华润燃气 · "+heading.rsplit(" · ",1)[-1]
        lines=_payment(rows)
    elif scene=="scene.utility.gas.tier.details":
        heading="华润燃气 · 阶梯详情"
        lines=_tier(rows)
    elif scene.startswith("scene.lights.fixtures."):
        lines=_fixture(plan,rows)
    elif scene.startswith("scene.lights."):
        lines=_scoped_lights(rows)
    elif scene.startswith("scene.appliance."):
        heading,lines=_device(plan,rows)
    elif scene.startswith("scene.home.presence."):
        lines=_presence(rows)
    else:
        lines=[text for _,_,text in rows]
    # Single existing aggregate replies already contain their own heading.
    # Multi-field scenes get a readable title and stable result order.
    if len(rows)==1 and not plan.supplements and rows[0][1]!="error" and not scene.startswith("scene.lights.fixtures."):
        return rows[0][2],completed
    return render_section(heading,lines),completed
