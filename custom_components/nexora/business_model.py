"""Business vocabulary and declarative read-only query policies.

Phase one: metadata only. No text recognition, execution, visibility filtering,
service calls, or changes to the existing routing path. The original catalog is
the sole authority for executable capabilities.
"""
from dataclasses import dataclass
from types import MappingProxyType

from .semantic_lexicon import FAMILIES, describe

# Value dimensions are semantic categories, not assertions about the exact
# unit/shape returned by external intent_scripts. Different meanings with the
# same dimension remain different metrics.
UTILITY_DIMENSIONS = {
    "money": "balance latest_cost year_cost h_month_cost h_year_cost history_cost last_pay year_pay balances",
    "consumption": "daily latest_usage year_usage h_day h_month_usage h_year_usage history_usage prior_usage",
    "daily_average_consumption": "h_avg",
    "status": "debt settlement debts low",
    "timestamp": "update read last_pay_date payment_update updates",
    "meter_reading": "meter",
    "date_coverage": "h_coverage",
    "payment_channel": "last_pay_channel",
    "count": "year_pay_count",
    "tier_summary": "tier",
    "unit_price": "tier1_price tier2_price tier3_price",
    "tier_consumption": "tier1_used tier2_used tier3_used",
    "tier_remaining_quota": "tier1_remaining tier2_remaining",
    "tier_quota_limit": "tier1_limit tier2_limit",
}
LIGHT_DIMENSIONS = {
    "device_list": "list_on list_off",
    "light_group_count": "count_on count_off total",
    "status": "all_off all_on offline abnormal single_state",
    "brightness": "brightness",
    "color_temperature": "temperature",
}
APPLIANCE_DIMENSIONS = {
    "status": "status power door lock child fault detergent softener swing heat vent blow light sterilize holiday replace",
    "mode": "program mode preset natural",
    "cycle_phase": "phase",
    "operating_action": "action",
    "duration": "remaining steriletime lightremain heatremain duration days",
    "setpoint_temperature": "target",
    "temperature": "temp",
    "rotation_speed": "spin",
    "count": "rinse cycles count",
    "water_consumption": "water totalwater",
    "water_production": "volume",
    "electric_consumption": "energy totalenergy",
    "speed_setting": "fan speed heatlevel ventlevel blowlevel",
    "position": "position limits",
    "filter_life": "filters ppc ro",
    "tds": "tds",
}
HOME_DIMENSIONS = {
    "person_list": "family",
    "person_count": "family_count",
    "status": "person presence lock door deadbolt childlock windows lid water water_all heater curtain safety faults battery_low",
    "temperature": "temp temp_avg temp_max temp_min",
    "humidity": "hum hum_avg hum_max hum_min",
    "environment_summary": "room_env env",
    "illuminance": "lux lux_all lux_max lux_min",
    "duration": "duration duration_present duration_absent",
    "room_presence_summary": "presence_all",
    "battery_level": "battery batteries",
    "position": "curtain_pos",
    "device_summary": "curtains lights apps_on apps_running utility alerts overview",
}

def _dimension_index(groups):
    index = {}
    for dimension, names in groups.items():
        for metric in names.split():
            if metric in index:
                raise ValueError("Duplicate semantic metric: " + metric)
            index[metric] = dimension
    return MappingProxyType(index)

DIMENSIONS = MappingProxyType({
    "utility": _dimension_index(UTILITY_DIMENSIONS),
    "lights": _dimension_index(LIGHT_DIMENSIONS),
    "appliance": _dimension_index(APPLIANCE_DIMENSIONS),
    "home": _dimension_index(HOME_DIMENSIONS),
})

@dataclass(frozen=True, order=True)
class QueryKey:
    family: str
    target: str
    metric: str
    period: str = ""
    parameter: str = ""
    account: str = ""

@dataclass(frozen=True)
class Capability:
    key: QueryKey
    capability_id: str
    dimension: str
    intent: str
    requires_native_target: bool

def _dimension(p):
    result = DIMENSIONS[p.family][p.metric]
    if p.family == "appliance" and p.metric == "temp":
        return {"w": "wash_water_temperature", "p": "outlet_water_temperature",
                "m": "ac_detected_temperature", "s": "ac_detected_temperature",
                "ac": "ac_detected_temperature", "b": "heater_detected_temperature"}[p.target]
    if p.family == "home" and p.metric == "temp":
        return "room_environment_temperature"
    if p.family == "utility" and result == "consumption":
        return {"e": "electric_consumption", "w": "water_consumption", "g": "gas_consumption"}[p.target]
    return result

class BusinessRegistry:
    """Immutable index of registered meanings. Never resolve using availability."""

    def __init__(self, capabilities):
        index, by_id = {}, {}
        for cap in capabilities.values():
            p = describe(cap)
            if p is None:
                # A malformed member of a known family is a schema error.
                if cap.get("intent") in FAMILIES:
                    raise ValueError("Incomplete registered capability: " + str(cap.get("id")))
                continue
            key = QueryKey(p.family, p.target, p.metric, p.period, p.parameter, p.account)
            item = Capability(key, p.capability, _dimension(p), cap["intent"],
                              bool(cap.get("native_slots")))
            if key in index or item.capability_id in by_id:
                raise ValueError("Duplicate registered meaning: " + repr(key))
            index[key] = item
            by_id[item.capability_id] = item
        self.by_key = MappingProxyType(index)
        self.by_id = MappingProxyType(by_id)

    def require(self, key):
        """Fail closed for an absent key; never substitute another object or period."""
        return self.by_key[key]

@dataclass(frozen=True)
class PolicyKey:
    family: str
    target: str
    goal: str
    account: str = ""
    period: str = ""

@dataclass(frozen=True)
class Scene:
    """Bounded ordered capabilities, not an execution plan.

    Primary answers the question; supplements add useful context. Stop rules
    may suppress supplements only; never suppress an explicit primary query.
    These are contracts for the later executor, not implemented here.
    """
    primary: tuple
    supplements: tuple = ()
    stop_on: tuple = ()
    caveat: str = ""

@dataclass(frozen=True)
class DefaultPolicy:
    key: PolicyKey
    scene: Scene
    rationale: str

def _q(family, target, metric, account="", period=""):
    return QueryKey(family, target, metric, period=period, account=account)

def _policy(family, target, goal, primary, supplements=(), *,
            account="", period="", stop_on=(), caveat="", rationale=""):
    return DefaultPolicy(
        PolicyKey(family, target, goal, account, period),
        Scene(tuple(primary), tuple(supplements), tuple(stop_on), caveat),
        rationale,
    )

# Each policy is scoped to a semantic goal, not a whole utterance.
# No generic "all" wildcard; it is a specific registered aggregate.
def policies(registry):
    result = []

    def same(f, t, g, main, extras=(), *, a="", period="", stop=(), note="", reason=""):
        result.append(_policy(f,t,g,
            [_q(f,t,m,a,period) for m in main],
            [_q(f,t,m,a,period) for m in extras],
            account=a,period=period,stop_on=stop,caveat=note,rationale=reason))

    for target, accounts in (("e", ("j","l")), ("w", ("j",)), ("g", ("j",))):
        for account in accounts:
            same("utility",target,"remaining_unspecified",("balance",),a=account,
                 reason="无实物单位时，账户剩余默认金额；回复明确账户及元。")
            same("utility",target,"payment_needed",("debt","balance"),a=account,
                 reason="同时提供欠费及余额；充值建议须依据实际阈值，不推断不存在的付款记录。")
    same("utility","g","remaining_physical",("tier1_remaining","tier2_remaining"),a="j",
         note="无法查询实际剩余燃气量；以下仅为阶梯剩余额度。",
         reason="明确量纲后给出可用相关数据，不返回金额或表读数。")
    for period in ("","all"):
        same("utility","all","account_health",("balances","debts","low"),a="j",period=period,
             reason="主住所和全部账户严格区分。")
    # Each room/whole-home light scope has the same semantic scene, but
    # fixture targets never inherit room counting metrics.
    scopes=sorted({k.target for k in registry.by_key if k.family=="lights" and k.metric=="count_on"})
    for target in scopes:
        same("lights",target,"overview",("count_on",),("list_on",),
             stop=("no_lights_on",),reason="先给开启灯组数量，仅有开启灯组时补充清单。")
        same("lights",target,"any_lights_on",("list_on",),
             reason="查询开启灯组；不将查询解释为关闭操作。")
    for target, room in (("m","主卧"),("s","次卧")):
        same("appliance",target,"temperature_unspecified",("target","temp"),
             reason="设定与检测温度均来自空调，不替换为房间传感器。")
        same("appliance",target,"overview",("status",),("target","temp"),
             stop=("device_off",),reason="关机不继续查询运行参数。")
        result.append(_policy("appliance",target,"temperature_when_off",
            [_q("appliance",target,"status"),_q("home",room,"temp")],
            caveat="房间环境温度来自独立环境查询，并非空调检测温度。",
            rationale="仅在后续决策确认空调无运行参数且需要补充时使用。"))
    same("appliance","ac","temperature_unspecified",("target","temp"),
         reason="已有两台空调聚合能力，避免逐台重复执行。")
    same("appliance","ac","overview",("status",),("target","temp"),
         stop=("all_devices_off",),reason="聚合空调状态。")
    same("appliance","w","progress",("status",),("phase","remaining"),
         stop=("device_off","cycle_not_running"),reason="运行时补充阶段和剩余时间。")
    same("appliance","p","overview",("status",),("filters","replace"),
         reason="使用已有滤芯综合查询，不重复查询 PPC/RO。")
    same("appliance","p","maintenance",("filters","replace"),
         reason="滤芯寿命和更换提醒。")
    same("appliance","b","temperature_unspecified",("target","temp"),
         reason="浴霸设定与检测温度，禁止代替室温。")
    for target in ("主卧","次卧","客餐厅"):
        same("home",target,"environment",("room_env",),reason="优先已有温湿度综合能力。")
    same("home","卫生间","environment",("temp",),
         note="卫生间当前仅注册温度查询。",reason="不推断不存在的湿度能力。")
    same("home","all","environment",("env",),reason="使用现有全屋环境查询。")
    same("home","all","entry_safety",("door","lock","deadbolt"),
         reason="关门、上锁、反锁为独立安全状态。")
    same("home","all","family_presence",("family",),
         reason="使用在家人员查询；不从未知状态推断人数。")
    same("home","all","alerts",("alerts",),reason="优先已有全屋提醒聚合能力。")
    same("home","all","overview",("overview",),reason="优先已有全屋概况能力。")
    result.append(_policy("home","阳台","brightness_unspecified",
         [_q("home","阳台","lux"),_q("lights","yang_tai","list_on")],
         caveat="环境光照度与灯具开关状态是不同指标。",
         rationale="同时回答环境亮度与照明状态，不冒充灯具亮度百分比。"))
    return tuple(result)

# Cross-domain links are explicit, narrowly scoped and labeled. No fallback
# from one account/device to another is authorized by these relationships.
CROSS_SCOPE = MappingProxyType({
    PolicyKey("appliance","m","temperature_when_off"): frozenset({("home","主卧")}),
    PolicyKey("appliance","s","temperature_when_off"): frozenset({("home","次卧")}),
    PolicyKey("home","阳台","brightness_unspecified"): frozenset({("lights","yang_tai")}),
})
MAX_SCENE_QUERIES = 4
MAX_MENU_QUERIES = 12
STOP_CONDITIONS = frozenset({"no_lights_on","device_off","all_devices_off","cycle_not_running"})

class PolicyRegistry:
    """Validate all references at construction; no execution or side effects."""
    def __init__(self, registry, definitions=None):
        index = {}
        for rule in policies(registry) if definitions is None else definitions:
            scene = rule.scene
            members = scene.primary + scene.supplements
            if (rule.key in index or not scene.primary or not rule.rationale
                    or len(members) > MAX_SCENE_QUERIES or len(set(members)) != len(members)
                    or (scene.stop_on and not scene.supplements)
                    or not set(scene.stop_on) <= STOP_CONDITIONS):
                raise ValueError("Invalid default policy: " + repr(rule.key))
            for member in members:
                registry.require(member)
                if member.parameter:
                    raise ValueError("Default scene cannot invent a dynamic date")
                if member.account != rule.key.account:
                    raise ValueError("Default scene cannot change account")
                if (member.family,member.target)!=(rule.key.family,rule.key.target):
                    if not scene.caveat or (member.family,member.target) not in CROSS_SCOPE.get(rule.key,()):
                        raise ValueError("Unapproved cross-scope scene")
                if rule.key.period != member.period:
                    raise ValueError("Default scene cannot change period")
            index[rule.key] = rule
        self.by_key = MappingProxyType(index)

    def get(self, key):
        """No fallback policy when the requested meaning is absent."""
        return self.by_key.get(key)
