"""Read-only static adapters for known, locally installed Intent Script schemas.

Never render, evaluate, import or execute a template. Unknown structures and
nonliteral expressions are not proof of absence. Fingerprints exclude the
actual binding dictionary; household entity IDs never enter the source tree.
"""
import hashlib
import json
import re

from jinja2 import Environment, nodes

SCHEMAS = {
    "LuxeHomeQuery": ("D", "25442cd3957cdebd83ebcf896be79d8831812402c3c2c72a6e636e43abc54cff"),
    "LuxeApplianceQuery": ("devices", "e9c8b6f0059bdc564395bba350f2d4f0228138040bf347d3642e3c15858b80c8"),
    "LuxeLightQuery": ("lights", "0d163904c8a7f95c005dbf28e809871a2a64c3f7807bbfbb47315fb85f979e11"),
}
ENTITY = re.compile(r"[a-z][a-z0-9_]*\.[a-z0-9_]+\Z")
UNKNOWN = object()
MISSING = object()
MAX_SOURCE = 128_000


def _canonical(node):
    if isinstance(node, nodes.Node):
        return [type(node).__name__, *(_canonical(getattr(node, k)) for k in node.fields)]
    if isinstance(node, (tuple, list)):
        return [_canonical(x) for x in node]
    return node


def _literal(node, depth=0):
    if depth > 12:
        raise ValueError("Binding nesting limit")
    if isinstance(node, nodes.Const) and type(node.value) in (str, int, float, bool, type(None)):
        return node.value
    if isinstance(node, (nodes.List, nodes.Tuple)):
        return [_literal(x, depth+1) for x in node.items]
    if isinstance(node, nodes.Dict):
        result = {}
        for pair in node.items:
            key = _literal(pair.key, depth+1)
            if type(key) is not str or key in result:
                raise ValueError("Invalid binding dictionary key")
            result[key] = _literal(pair.value, depth+1)
        return result
    raise ValueError("Nonliteral binding")


def extract(source, intent):
    """Return the verified static dictionary, or None (unrecognized schema)."""
    schema = SCHEMAS.get(intent)
    if not schema or not isinstance(source, str) or len(source)>MAX_SOURCE:
        return None
    name, expected = schema
    try:
        tree = Environment().parse(source.strip())
        assignments = [n for n in tree.find_all(nodes.Assign)
                       if isinstance(n.target,nodes.Name) and n.target.name==name]
        if len(assignments)!=1 or assignments[0] not in tree.body:
            return None
        assign = assignments[0]
        # Require the dictionary at the original first statement. Moving it
        # after business logic is not an equivalent schema.
        if tree.body[0] is not assign:
            return None
        body = [n for n in tree.body if n is not assign]
        digest = hashlib.sha256(json.dumps(_canonical(body),ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
        if digest != expected:
            return None
        data = _literal(assign.node)
        return data if isinstance(data,dict) else None
    except Exception:
        return None


def _get(data,*path):
    for key in path:
        if data is MISSING:
            return MISSING
        if not isinstance(data,dict):
            return UNKNOWN
        data = data.get(key,MISSING)
    return data


def _ids(value):
    """Entity tuples, empty tuple (explicit absence), or UNKNOWN."""
    if value is UNKNOWN:
        return UNKNOWN
    if value is MISSING or value is None or value=="":
        return ()
    if isinstance(value,str):
        return (value,) if ENTITY.fullmatch(value) else UNKNOWN
    if isinstance(value,(list,tuple)):
        if all(isinstance(x,str) and ENTITY.fullmatch(x) for x in value):
            return tuple(value)
    return UNKNOWN


def _combine(*values):
    if any(x is UNKNOWN for x in values):
        return UNKNOWN
    return tuple(dict.fromkeys(x for group in values for x in group))


def home_binding(d,slots):
    q,t=slots.get("luxe_home_query"),slots.get("luxe_home_target")
    if q=="windows":
        # Verified Home 1.0.1 has an unimplemented window branch. The lid
        # binding is a different semantic role, never a window binding.
        return ()
    if q=="person":
        ids=_ids(_get(d,"family",t))
        if ids is not UNKNOWN and any(not e.startswith(("device_tracker.","person.")) for e in ids):
            return UNKNOWN
        return ids
    if q=="temp" and t=="卫生间":
        return _ids(_get(d,"app","b","main"))
    if q in {"temp","hum"}:
        return _ids(_get(d,"climate",t,q))
    if q=="room_env":
        return _combine(*(_ids(_get(d,"climate",t,k)) for k in ("temp","hum")))
    if q in {"presence","lux","duration","duration_present","duration_absent"}:
        if q=="lux":
            return _ids(_get(d,"rooms",t,"lux"))
        if q=="presence":
            return _ids(_get(d,"rooms",t,"presence"))
        kind=_get(d,"rooms",t,"kind")
        # ES3 duration uses last_changed; radar uses duration sensors.
        if kind=="es3":
            return _ids(_get(d,"rooms",t,"presence"))
        if kind=="radar":
            return _combine(*(_ids(_get(d,"rooms",t,k)) for k in ("presence","present","absent")))
        return UNKNOWN
    if q in {"water","battery","curtain","curtain_pos"}:
        group={"water":"water","battery":"batteries","curtain":"curtains","curtain_pos":"curtains"}[q]
        return _ids(_get(d,group,t))
    if q in {"lid","heater"}:
        return _ids(_get(d,q))
    if q=="lock":
        return _combine(_ids(_get(d,"lock")),_ids(_get(d,"lockevent")))
    if q in {"door","deadbolt","childlock"}:
        return _ids(_get(d,"lock"))
    return UNKNOWN


APP_FIELDS = {
    "w": {"status":("power","cycle","phase","mode","program"),"power":("power",),"program":("program",),"phase":("phase",),"remaining":("hh","mm"),"fault":("message","phase")},
    "b": {"status":("light","heat","vent","blow"),"temp":("temp","main"),"mode":("main",),"target":("target",),"steriletime":("steriletime",),"lightremain":("lightremain",),"heatremain":("heatremain",)},
    "a": {"status":("main","final","moving","speed","fault"),"position":("final","moving"),"limits":("upper","lower")},
    "f": {"status":("main",),"speed":("main",),"mode":("main",),"natural":("natural",)},
    "p": {"status":("main",),"fault":("fault","bits"),"filters":("ppc","ro"),"replace":("ppc","ro"),"days":("ppcd","rod")},
}


def appliance_binding(d,slots):
    device,q=slots.get("luxe_appliance_device"),slots.get("luxe_appliance_query")
    if device=="ac":
        return _combine(*(_ids(_get(d,k,"ids","main")) for k in ("m","s")))
    if device in {"m","s"}:
        return _ids(_get(d,device,"ids","main"))
    if device not in APP_FIELDS or not isinstance(q,str):
        return UNKNOWN
    fields=APP_FIELDS[device].get(q,(q,))
    return _combine(*(_ids(_get(d,device,"ids",k)) for k in fields))


class BindingExtractor:
    """Cache by current handler and source text, not a polling timer."""
    def __init__(self):
        self.sources={}
        self.data={}
        self.revision=0

    def refresh(self,handlers):
        sources={}
        for h in handlers:
            if h.intent_type not in SCHEMAS:
                continue
            speech=h.config.get("speech")
            template=speech.get("text") if isinstance(speech,dict) else None
            source=getattr(template,"template",None)
            if isinstance(source,str):
                sources[h.intent_type]=source
        changed={k for k in self.sources.keys()|sources.keys() if self.sources.get(k)!=sources.get(k)}
        for k in changed:
            self.data.pop(k,None)
            if k in sources:
                value=extract(sources[k],k)
                if value is not None:
                    self.data[k]=value
        self.sources=sources
        if changed:
            self.revision+=1
        return changed

    def binding(self,cap,targets):
        name=cap.get("intent")
        d=self.data.get(name)
        if d is None:
            return UNKNOWN
        slots=cap.get("slots",{})
        if name=="LuxeHomeQuery":
            return home_binding(d,slots)
        if name=="LuxeApplianceQuery":
            return appliance_binding(d,slots)
        if name=="LuxeLightQuery":
            entity=targets.get(cap.get("category"))
            if entity:
                if entity not in d:
                    return ()
                return (entity,)
        return UNKNOWN
