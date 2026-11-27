"""Validated declarative registry and isolated in-memory menu sessions."""
from dataclasses import dataclass, replace
from datetime import date
import re
from string import Formatter
from time import monotonic
from .capability import validate_requirements
from .followup import Followups
from .context_transitions import Selection

HELP = {"help", "帮助", "使用指南", "你能做什么"}
EXIT = {"exit", "退出", "关闭菜单"}
BACK = {"0", "back", "返回", "上一级"}
PAGE_SIZE = 20
NEXT = {"99", "next", "下一页"}
PREV = {"98", "prev", "上一页"}
# Canonical decimal selection; no leading zeros and no paging commands in paths.
CHOICE = r"(?:[1-9]|1[0-9]|20)"
CHOICE_RE = re.compile(CHOICE)
PATH_RE = re.compile(rf"{CHOICE}(?:\.{CHOICE})*")
DETAIL = {"detail", "完整菜单"}
RESERVED = HELP | EXIT | BACK | NEXT | PREV | DETAIL
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
TRANSLATE = str.maketrans("０１２３４５６７８９－．", "0123456789-.")

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
    view: str = "detail"

@dataclass(frozen=True)
class Reply:
    text: str = ""
    capability: str | None = None
    sentence: str = ""
    slots: dict | None = None
    scene: str | None = None
    params: tuple = ()

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
        self.followups = Followups(self, clock, max_sessions=max_sessions)
        self._add_shortcuts()
        self.scenes = {}
        self.scene_aliases = {}
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
            validate_requirements(x)
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

    def install_scene_layout(self, rows):
        """Separate presentation nodes; original items/capabilities stay intact."""
        from .scene_menu import install
        install(self, rows)

    def navigation_alias(self, text, session=None):
        if self.scenes and (session is None or session.view=="scene"):
            return self.scene_aliases.get(text,self.aliases.get(text))
        return self.aliases.get(text)

    def _parameter_cap(self, item_id):
        if item_id in self.scenes:
            return self.capabilities[self.scenes[item_id].members[0]]
        return self.capabilities[item_id]

    def _selected(self, item_id, params):
        if item_id in self.scenes:
            return Reply(scene=item_id,params=tuple(sorted(params.items())))
        return self._query(item_id,params)

    def _prune(self):
        now = self.clock()
        for key, session in list(self.sessions.items()):
            if session.expires <= now:
                self.sessions.pop(key, None)

    def _available(self, item_id, available):
        item = self.items[item_id]
        if item.kind == "scene":
            return any(self._available(cid,available) for cid in self.scenes[item_id].members if cid not in self.scenes[item_id].supplements)
        if item.kind == "query":
            cap = self.capabilities[item_id]
            if "{secondary}" in cap["sentence"] and not self.settings["secondary"]:
                return False
            return available(cap)
        return any(self._available(x.id, available) for x in self.children[item_id])

    def _render(self, key, node, available, page=0):
        items = [x for x in self.children[node] if self._available(x.id, available)]
        page = max(0, min(page, max(0, (len(items)-1)//PAGE_SIZE)))
        shown = tuple(x.id for x in items[page*PAGE_SIZE:(page+1)*PAGE_SIZE])
        if key not in self.sessions and len(self.sessions) >= self.max_sessions:
            self.sessions.pop(min(self.sessions, key=lambda k:self.sessions[k].expires))
        prior=self.sessions.get(key)
        view="scene" if node=="scene" else "detail" if node=="root" else prior.view if prior else "detail"
        if node.startswith("scene."):
            view="scene"
        self.sessions[key] = Session(node, page, self.clock()+self.ttl, shown, view=view)
        current = self.items[node]
        lines = [f"{current.icon} {current.name}" if current.icon else current.name, ""]
        for i, item_id in enumerate(shown, 1):
            item = self.items[item_id]
            lines.append(f"{i}. {item.icon} {item.name}" if item.icon else f"{i}. {item.name}")
        if not shown:
            lines.append("当前没有可用的查询能力，请检查意图库。")
        if page:
            lines.append("98. 上一页")
        if (page+1)*PAGE_SIZE < len(items):
            lines.append("99. 下一页")
        if node not in {"root","scene"}:
            lines.append("0. 返回上一级")
        if node=="scene":
            lines.extend(["","发送 detail 查看完整菜单。"])
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
        spoken=t.rstrip("？?。！!").strip()
        if t in HELP | DETAIL:
            self.followups.clear(key)
            return self._render(key, "scene" if self.scenes and t in HELP else "root", available)
        if t in EXIT:
            self.sessions.pop(key, None)
            self.followups.clear(key)
            return Reply("已退出查询菜单。")
        if self.followups.has_clarification_choice(key,spoken):
            result=self.followups.route(key,spoken,available,today)
            if isinstance(result,Selection):
                if not self._available(result.capability,available):
                    return Reply("该查询当前不可用，请发送 help。")
                return self._query(result.capability,dict(result.params))
        node=self.navigation_alias(t,s)
        if node is not None:
            self.followups.clear(key)
            if not self._available(node, available):
                return Reply("该分类暂无已配置的查询能力，请发送 help。")
            if node in self.scenes:
                # A direct category shortcut is equivalent to selecting its
                # projected leaf; preserve a valid parent menu for 0/repeat.
                self._render(key,self.items[node].parent,available)
                session=self.sessions[key]
                if node not in session.shown:
                    return Reply("该查询当前不可用，请发送 help。")
                return self.route(key,str(session.shown.index(node)+1),available,today)
            return self._render(key, node, available)
        if s and s.pending:
            if re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", t):
                return Reply("请先完成当前参数输入，或发送0返回。")
            if t in BACK:
                return self._render(key, s.node, available, s.page)
            if not re.fullmatch(r"[0-9-]+", t) and t not in NEXT | PREV:
                # A complete independent question remains usable during a date prompt.
                s.pending = None
                self.followups.clear(key)
                return None
            cap_id = s.pending
            if not self._available(cap_id, available):
                return self._render(key, s.node, available, s.page)
            try:
                cap = self._parameter_cap(cap_id)
                current = today or date.today()
                base_year = current.year - 1 if cap.get("parameter_year_offset") == -1 else current.year
                params = parse_parameter(cap["parameter"], t, current, base_year=base_year)
            except ValueError:
                return Reply("输入无效，请输入" + PROMPTS[self._parameter_cap(cap_id)["parameter"]] + "，或发送0返回。")
            s.pending = None
            s.expires = self.clock()+self.ttl
            return self._selected(cap_id, params)
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", t):
            return self._path(key, t, available, today)
        if t not in BACK | NEXT | PREV and not (t.isascii() and t.isdigit()):
            result = self.followups.route(key, spoken, available,today)
            if isinstance(result,Selection):
                if not self._available(result.capability,available):
                    self.followups.clear(key)
                    return Reply("该查询当前不可用，请发送 help。")
                return self._query(result.capability,dict(result.params))
            if result in self.capabilities:
                return self._query(result, {})
            if isinstance(result, str):
                return Reply(result)
            self.followups.clear(key)
            return None
        if not s:
            return Reply("当前没有有效菜单，请发送 help。")
        if t in BACK:
            self.followups.clear(key)
            parent=self.items[s.node].parent or "root"
            if parent=="root" and s.view=="scene" and self.scenes:
                parent="scene"
            return self._render(key,parent,available)
        if t in NEXT | PREV:
            self.followups.clear(key)
            return self._render(key, s.node, available, s.page + (-1 if t in PREV else 1))
        if not CHOICE_RE.fullmatch(t) or int(t)>len(s.shown):
            return Reply("无效选项，请发送当前菜单中的数字，或发送 help。")
        cap_id = s.shown[int(t)-1]
        if not self._available(cap_id, available):
            return Reply("该查询已不可用，请发送 help 刷新菜单。")
        if self.items[cap_id].kind == "menu":
            self.followups.clear(key)
            return self._render(key, cap_id, available)
        self.followups.clear(key)
        s.expires = self.clock()+self.ttl
        param = self._parameter_cap(cap_id).get("parameter")
        if param:
            s.pending = cap_id
            return Reply("请输入" + PROMPTS[param] + "，或发送0返回。")
        return self._selected(cap_id, {})

    def _path(self, key, text, available, today):
        """Traverse the displayed snapshot first; validate the rest atomically."""
        parts = text.split(".")
        session = self.sessions.get(key)
        if session is None:
            return Reply("当前没有有效菜单，请发送 help。")
        if len(parts) > 10 or not PATH_RE.fullmatch(text):
            return Reply("无效数字路径，请使用1–20逐级选择。")
        original = replace(session)
        for i, part in enumerate(parts):
            s = self.sessions[key]
            n = int(part)-1
            if n >= len(s.shown):
                self.sessions[key] = original
                return Reply("无效数字路径，请按当前菜单选择。")
            item_id = s.shown[n]
            if not self._available(item_id, available):
                self.sessions[key] = original
                return Reply("该查询已不可用，请发送 help 刷新菜单。")
            if self.items[item_id].kind == "menu":
                result = self._render(key, item_id, available)
                continue
            if i != len(parts)-1:
                self.sessions[key] = original
                return Reply("无效数字路径，不能跨越查询或参数输入步骤。")
            self.followups.clear(key)
            return self.route(key, part, available, today)
        self.followups.clear(key)
        return result
