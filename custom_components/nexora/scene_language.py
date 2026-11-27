"""Exact, scoped vocabulary for registered business scenes.

A phrase identifies a scene, not an intent or a device. Ambiguous labels are
not executable; dates and visibility remain the existing planner's concern.
"""
from collections import defaultdict
from .semantic import normalize

EXPLICIT = {
    "scene.utility.summary.primary.overview": ("我家水电气账户概况", "主住所水电气账户概况", "水电气账户概况"),
    "scene.utility.summary.all.overview": ("所有账户概况", "全部账户概况", "所有水电气账户概况", "全部水电气账户概况"),
    "scene.lights.all": ("全屋照明概况", "全屋灯光概况"),
    "scene.appliance.washer.progress": ("洗衣机当前洗衣进度", "海尔洗衣机当前洗衣进度"),
    "scene.home.env.whole": ("全屋环境温湿度", "全屋温湿度概况"),
}

class SceneLanguageIndex:
    def __init__(self, items, scenes):
        candidates = defaultdict(set)
        self.paths = {}
        for sid in scenes:
            node = items[sid]
            names = [node.name]
            while node.parent != "scene":
                node = items[node.parent]
                names.insert(0, node.name)
            path = " · ".join(names)
            self.paths[sid] = path
            phrases = (path, "".join(names), "".join(names[1:])) if len(names)>2 else (path, "".join(names))
            for phrase in (*phrases, *EXPLICIT.get(sid, ())):
                key = normalize(phrase)
                if key:
                    candidates[key].add(sid)
        self.exact = {k: next(iter(v)) for k,v in candidates.items() if len(v)==1}
        self.ambiguous = frozenset(k for k,v in candidates.items() if len(v)>1)

    def match(self, text):
        return self.exact.get(normalize(text))
