"""Validated declarative registry and isolated in-memory menu sessions."""
from dataclasses import dataclass
from datetime import date
import re
from string import Formatter
from time import monotonic
from typing import Any

HELP = {"help", "帮助", "使用指南", "你能做什么"}
EXIT = {"exit", "退出", "关闭菜单"}
BACK = {"0", "back", "返回", "上一级"}
NEXT = {"9", "next", "下一页"}
PREV = {"prev", "上一页"}
RESERVED = HELP | EXIT | BACK | NEXT | PREV
FOOTER = "回复数字选择，help 返回主菜单，exit 退出菜单。"
PARAMETERS = {
    "month": ("month",),
    "year": ("year",),
    "year_month": ("year", "month"),
    "date": ("year", "month", "day"),
    "month_day": ("month", "day"),
}
PROMPTS = {"month": "月份（1–12）", "year": "年份（2000–2099）", "year_month": "年月（YYYY-MM）", "date": "日期（YYYY-MM-DD）", "month_day": "月日（MM-DD）"}
ID = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*\Z")
SLOT = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*\Z")
TRANSLATE = str.maketrans("０１２３４５６７８９－", "0123456789-")

@dataclass(frozen=True)
class Item:
    id: str
    name: str
    parent: str
    order: int
    kind: str
    aliases: tuple = ()
    icon: str = ""

@dataclass
class Session:
    node: str
    page: int
    expires: float
    shown: tuple
    pending: str | None = None

@dataclass(frozen=True)
class Reply:
    text: str = ""
    capability: str | None = None
    sentence: str = ""
    slots: dict | None = None

def parse_parameter(kind, text, today, base_year=None):
    """Parse only an explicitly requested parameter; reject invalid/future dates."""
    if not re.fullmatch(r"[0-9]{1,4}(?:-[0-9]{1,2}){0,2}", text):
        raise ValueError("Invalid number")
    fields = PARAMETERS[kind]
    values = tuple(map(int, text.split("-")))
    if len(values) != len(fields):
        raise ValueError("Wrong number of fields")
    p = dict(zip(fields, values))
    y, m, d = p.get("year", base_year if base_year is not None else today.year), p.get("month", 1), p.get("day", 1)
    if not 2000 <= y <= 2099 or date(y, m, d) > today:
        raise ValueError("Invalid or future date")
    return p

class Menu:
    def __init__(self, catalogs, settings=None, clock=monotonic, ttl=600, max_sessions=256):
        self.clock, self.ttl, self.max_sessions = clock, ttl, max_sessions
        self.settings = {"primary_label": "主账户", "secondary_label": "第二账户", "secondary": "", **(settings or {})}
        self.items = {"root": Item("root", "Nexora · 智能家庭助手", "", 0, "menu")}
        self.capabilities, self.aliases, self.sessions = {}, {}, {}
        if ttl <= 0 or max_sessions < 1:
            raise ValueError("Invalid session bounds")
        for catalog in catalogs:
            self._register(catalog)
        self._add_shortcuts()
        self.children = {key: tuple(sorted((x for x in self.items.values() if x.parent == key), key=lambda x: (x.order, x.id))) for key in self.items}

    def _add(self, item):
        if not ID.fullmatch(item.id) or item.id in self.items or item.parent not in self.items or self.items[item.parent].kind != "menu":
            raise ValueError("Duplicate ID or invalid parent: " + item.id)
        if not isinstance(item.order, int) or not item.name.strip() or len(item.name) > 150:
            raise ValueError("Invalid menu item")
        if item.kind == "menu":
            # Explicit aliases are global. Display names are optional shortcuts
            # only when globally unique; repeated generic labels are navigation-only.
            for alias in item.aliases:
                key = alias.strip().casefold()
                if not key or key in RESERVED or key.isdecimal() or key in self.aliases:
                    raise ValueError("Ambiguous alias: " + key)
                self.aliases[key] = item.id
        self.items[item.id] = item

    def _label(self, name):
        if not isinstance(name, str):
            raise ValueError("Invalid label")
        return name.replace("{primary_label}", self.settings["primary_label"]).replace("{secondary_label}", self.settings["secondary_label"] or "第二账户")

    def _register(self, catalog):
        if not isinstance(catalog, dict) or catalog.get("schema_version") != 1:
            raise ValueError("Unsupported schema")
        module = catalog["module"]
        mid = module["id"]
        icon = module.get("icon", "")
        if not isinstance(icon, str) or len(icon) > 16 or any(ch.isspace() or not ch.isprintable() for ch in icon):
            raise ValueError("Invalid module icon")
        self._add(Item(mid, self._label(module["name"]), "root", module["order"], "menu", (module["name"], *module.get("aliases", [])), icon))
        pending = list(catalog["categories"])
        while pending:
            ready = [x for x in pending if x.get("parent", mid) in self.items]
            if not ready:
                raise ValueError("Category cycle or missing parent")
            for x in ready:
                parent = x.get("parent", mid)
                if not x["id"].startswith(mid + ".") or not (parent == mid or parent.startswith(mid + ".")):
                    raise ValueError("Invalid category namespace")
                self._add(Item(x["id"], self._label(x["name"]), parent, x["order"], "menu", tuple(x.get("aliases", []))))
                pending.remove(x)
        for x in catalog["capabilities"]:
            if x.get("read_only") is not True or not x["id"].startswith(mid + ".") or not x["category"].startswith(mid + "."):
                raise ValueError("Invalid capability namespace or not read-only")
            if not isinstance(x["intent"], str) or not SLOT.fullmatch(x["intent"]):
                raise ValueError("Invalid intent")
            slots = x["slots"]
            if not isinstance(slots, dict) or not all(SLOT.fullmatch(k) and type(v) in (str, int) for k, v in slots.items()):
                raise ValueError("Invalid slots")
            native_slots = x.get("native_slots", {})
            # Only the existing single-light query may resolve a local entity ID
            # from a strict recognition result. No generic wildcard slots.
            if native_slots and (native_slots != {"luxe_light_id": "light"} or x["intent"] != "LuxeLightQuery" or slots.get("light_query") not in {"single_state", "brightness", "temperature"} or "luxe_light_id" in slots or x.get("parameter")):
                raise ValueError("Invalid native slot binding")
            if not isinstance(native_slots, dict):
                raise ValueError("Invalid native slots")
            param = x.get("parameter")
            if x.get("parameter_year_offset", 0) not in (0, -1):
                raise ValueError("Invalid parameter year offset")
            if param is not None and param not in PARAMETERS:
                raise ValueError("Invalid parameter kind")
            allowed = set(PARAMETERS.get(param, ()))
            mapping = x.get("parameter_slots", {})
            if not isinstance(mapping, dict) or set(mapping) != allowed or len(set(mapping.values())) != len(mapping) or any(not isinstance(v, str) or not SLOT.fullmatch(v) or v in slots for v in mapping.values()):
                raise ValueError("Invalid parameter-to-slot mapping")
            fields = set()
            for _, field, spec, conversion in Formatter().parse(x["sentence"]):
                if field is not None:
                    if field not in allowed | {"secondary"} or spec or conversion:
                        raise ValueError("Invalid sentence placeholder")
                    fields.add(field)
            if fields - {"secondary"} != allowed:
                raise ValueError("Missing sentence parameter")
            self._add(Item(x["id"], self._label(x["name"]), x["category"], x["order"], "query"))
            self.capabilities[x["id"]] = dict(x)

    def _add_shortcuts(self):
        # Register implicit names only after ALL modules have been loaded.
        # Explicit aliases remain authoritative; ambiguous labels have no shortcut.
        for x in self.items.values():
            if x.kind != "menu" or x.id == "root":
                continue
            key = x.name.strip().casefold()
            if key not in RESERVED and not key.isdecimal() and sum(y.kind == "menu" and y.name.strip().casefold() == key for y in self.items.values()) == 1:
                self.aliases.setdefault(key, x.id)

    def _prune(self):
        now = self.clock()
        for key, session in list(self.sessions.items()):
            if session.expires <= now:
                self.sessions.pop(key, None)

    def _available(self, item_id, available):
        item = self.items[item_id]
        if item.kind == "query":
            cap = self.capabilities[item_id]
            if "{secondary}" in cap["sentence"] and not self.settings["secondary"]:
                return False
            return available(cap)
        return any(self._available(x.id, available) for x in self.children[item_id])

    def _render(self, key, node, available, page=0):
        items = [x for x in self.children[node] if self._available(x.id, available)]
        page = max(0, min(page, max(0, (len(items)-1)//8)))
        shown = tuple(x.id for x in items[page*8:page*8+8])
        if key not in self.sessions and len(self.sessions) >= self.max_sessions:
            self.sessions.pop(min(self.sessions, key=lambda k:self.sessions[k].expires))
        self.sessions[key] = Session(node, page, self.clock()+self.ttl, shown)
        current = self.items[node]
        lines = [f"{current.icon} {current.name}" if current.icon else current.name, ""]
        for i, item_id in enumerate(shown, 1):
            item = self.items[item_id]
            lines.append(f"{i}. {item.icon} {item.name}" if item.icon else f"{i}. {item.name}")
            if item.kind == "query":
                cap = self.capabilities[item_id]
                if not cap.get("parameter"):
                    sentence = cap["sentence"].format(secondary=self.settings["secondary"])
                    if sentence != item.name:
                        lines.append("   示例：" + sentence)
        if not shown:
            lines.append("当前没有可用的查询能力，请检查意图库。")
        if (page+1)*8 < len(items):
            lines.append("9. 下一页")
        if page:
            lines.append("发送 prev 返回上一页")
        if node != "root":
            lines.append("0. 返回上一级")
        return Reply("\n".join(lines + ["", FOOTER]))

    def _query(self, cap_id, params):
        cap = self.capabilities[cap_id]
        sentence = cap["sentence"].format(secondary=self.settings["secondary"], **params)
        slots = dict(cap["slots"])
        slots.update({cap["parameter_slots"][k]: v for k, v in params.items()})
        return Reply(capability=cap_id, sentence=sentence, slots=slots)

    def route(self, key, text, available=lambda cap: True, today=None):
        self._prune()
        t = text.strip().casefold().translate(TRANSLATE)
        s = self.sessions.get(key)
        if t in HELP:
            return self._render(key, "root", available)
        if t in EXIT:
            self.sessions.pop(key, None)
            return Reply("已退出查询菜单。")
        if t in self.aliases:
            return self._render(key, self.aliases[t], available)
        if s and s.pending:
            if t in BACK:
                return self._render(key, s.node, available, s.page)
            if not re.fullmatch(r"[0-9-]+", t) and t not in NEXT | PREV:
                # A complete independent question remains usable during a date prompt.
                s.pending = None
                return None
            cap_id = s.pending
            if not self._available(cap_id, available):
                return self._render(key, s.node, available, s.page)
            try:
                cap = self.capabilities[cap_id]
                current = today or date.today()
                base_year = current.year - 1 if cap.get("parameter_year_offset") == -1 else current.year
                params = parse_parameter(cap["parameter"], t, current, base_year=base_year)
            except ValueError:
                return Reply("输入无效，请输入" + PROMPTS[self.capabilities[cap_id]["parameter"]] + "，或发送0返回。")
            s.pending = None
            s.expires = self.clock()+self.ttl
            return self._query(cap_id, params)
        if t not in BACK | NEXT | PREV and not (t.isascii() and t.isdigit()):
            return None
        if not s:
            return Reply("当前没有有效菜单，请发送 help。")
        if t in BACK:
            return self._render(key, self.items[s.node].parent or "root", available)
        if t in NEXT | PREV:
            return self._render(key, s.node, available, s.page + (-1 if t in PREV else 1))
        if len(t)!=1 or t not in "12345678" or int(t)>len(s.shown):
            return Reply("无效选项，请发送当前菜单中的数字，或发送 help。")
        cap_id = s.shown[int(t)-1]
        if not self._available(cap_id, available):
            return Reply("该查询已不可用，请发送 help 刷新菜单。")
        if self.items[cap_id].kind == "menu":
            return self._render(key, cap_id, available)
        s.expires = self.clock()+self.ttl
        param = self.capabilities[cap_id].get("parameter")
        if param:
            s.pending = cap_id
            return Reply("请输入" + PROMPTS[param] + "，或发送0返回。")
        return self._query(cap_id, {})
