"""Declarative capability requirements; no rendering of business templates."""
import re
from time import monotonic

DIM = frozenset({"brightness","color_temp","hs","xy","rgb","rgbw","rgbww","white"})
KNOWN = DIM | {"onoff"}
FEATURES = {"presence","brightness","color_temp"}
BINDING_ID = re.compile(r"[a-z][a-z0-9_.]*\Z")
ENTITY_ID = re.compile(r"[a-z][a-z0-9_]*\.[a-z0-9_]+\Z")

def validate_requirements(cap):
    rules = cap.get("requires", [])
    if not isinstance(rules, list) or len(rules)>8:
        raise ValueError("Invalid requires")
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("Invalid requirement")
        kind=rule.get("kind")
        if kind=="binding":
            if set(rule)!={"kind","key"} or not isinstance(rule["key"],str) or not BINDING_ID.fullmatch(rule["key"]):
                raise ValueError("Invalid binding requirement")
        elif kind=="native_light":
            expected={"single_state":"presence","brightness":"brightness","temperature":"color_temp"}.get(cap.get("slots",{}).get("light_query"))
            if set(rule)!={"kind","feature"} or cap.get("intent")!="LuxeLightQuery" or cap.get("native_slots")!={"luxe_light_id":"light"} or rule.get("feature")!=expected or expected not in FEATURES:
                raise ValueError("Invalid light requirement")
        else:
            raise ValueError("Unknown capability requirement")

def validate_bindings(raw):
    if not isinstance(raw,dict):
        raise ValueError("Invalid bindings")
    result={}
    for key,value in raw.items():
        if not isinstance(key,str) or not BINDING_ID.fullmatch(key):
            raise ValueError("Invalid binding key")
        if value is None:
            result[key]=None
        elif isinstance(value,list) and value and all(isinstance(v,str) and ENTITY_ID.fullmatch(v) for v in value):
            result[key]=tuple(value)
        else:
            raise ValueError("Binding must be null or a non-empty entity ID list")
    return result

class Resolver:
    """Keep unknown/temporarily unavailable capabilities visible.

    Explicitly empty local bindings are authoritative. A configured ID that is
    temporarily absent in the state machine is not proof of removal.
    """
    def __init__(self, bindings=None, clock=monotonic, ttl=300):
        self.bindings=validate_bindings(bindings or {})
        self.clock,self.ttl=clock,ttl
        self.targets={}
        self.modes={}
        self.language=None
        self.expires=0

    def invalidate(self):
        self.expires=0

    def replace_targets(self, language, targets):
        self.targets=targets
        self.language=language
        self.expires=self.clock()+self.ttl
        self.modes={k:v for k,v in self.modes.items() if k in targets.values()}

    def needs_refresh(self, language):
        return self.language!=language or self.clock()>=self.expires

    def observe(self, entity, state):
        if state is None or getattr(state,"state",None) not in {"on","off"}:
            return
        raw=state.attributes.get("supported_color_modes")
        if isinstance(raw,(list,tuple,set,frozenset)) and raw and all(isinstance(x,str) and x in KNOWN for x in raw):
            self.modes[entity]=frozenset(raw)
        else:
            # Unknown metadata on a live entity is not a proven unsupported mode.
            self.modes.pop(entity,None)

    def status(self, cap, get_state):
        """Return hidden, temporary or visible; only hidden affects numbering."""
        result="visible"
        for rule in cap.get("requires",[]):
            if rule["kind"]=="binding":
                key=rule["key"]
                if key not in self.bindings:
                    continue
                ids=self.bindings[key]
                if ids is None:
                    return "hidden"
                if all((s:=get_state(e)) is None or s.state in {"unknown","unavailable"} for e in ids):
                    result="temporary"
            elif rule["kind"]=="native_light":
                entity=self.targets.get(cap["category"])
                if not entity:
                    continue
                state=get_state(entity)
                self.observe(entity,state)
                modes=self.modes.get(entity)
                feature=rule["feature"]
                if modes and ((feature=="brightness" and not modes & DIM) or (feature=="color_temp" and "color_temp" not in modes)):
                    return "hidden"
                if state is None or state.state in {"unknown","unavailable"}:
                    result="temporary"
        return result
