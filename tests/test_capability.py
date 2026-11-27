import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType
import unittest

path=Path(__file__).resolve().parents[1]/"custom_components/nexora/capability.py"
pkg=ModuleType("nexora_resolver_test")
pkg.__path__=[str(path.parent)]
sys.modules[pkg.__name__]=pkg
spec=importlib.util.spec_from_file_location("nexora_resolver_test.capability",path)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

def cap(feature):
    return {"category":"lights.fixture","requires":[{"kind":"native_light","feature":feature}]}

class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.now=0
        self.r=m.Resolver(clock=lambda:self.now)
        self.r.replace_targets("zh-CN",{"lights.fixture":"light.example"})
        self.state=SimpleNamespace(state="on",attributes={"supported_color_modes":["onoff"]})
    def get(self,e):
        return self.state
    def test_onoff(self):
        self.assertEqual(self.r.status(cap("brightness"),self.get),"hidden")
        self.assertEqual(self.r.status(cap("color_temp"),self.get),"hidden")
        self.assertEqual(self.r.status(cap("presence"),self.get),"visible")
    def test_dimmer(self):
        self.state.attributes["supported_color_modes"]=["brightness"]
        self.assertEqual(self.r.status(cap("brightness"),self.get),"visible")
        self.assertEqual(self.r.status(cap("color_temp"),self.get),"hidden")
    def test_color_temp_off(self):
        self.state.state="off"
        self.state.attributes["supported_color_modes"]=["color_temp"]
        self.assertEqual(self.r.status(cap("brightness"),self.get),"visible")
        self.assertEqual(self.r.status(cap("color_temp"),self.get),"visible")
    def test_unknown_modes_retained(self):
        self.state.attributes={}
        self.assertEqual(self.r.status(cap("brightness"),self.get),"visible")
    def test_offline_preserves_capability(self):
        self.assertEqual(self.r.status(cap("brightness"),self.get),"hidden")
        self.state.state="unavailable"
        self.state.attributes={}
        self.assertEqual(self.r.status(cap("brightness"),self.get),"hidden")
        self.assertEqual(self.r.status(cap("presence"),self.get),"temporary")
        self.state.state="off"
        self.assertEqual(self.r.status(cap("brightness"),self.get),"hidden")
    def test_mode_change(self):
        self.assertEqual(self.r.status(cap("brightness"),self.get),"hidden")
        self.state.attributes={"supported_color_modes":["color_temp"]}
        self.assertEqual(self.r.status(cap("brightness"),self.get),"visible")
        self.assertEqual(self.r.status(cap("color_temp"),self.get),"visible")
    def test_missing_entity_is_not_removal(self):
        self.state=None
        self.assertEqual(self.r.status(cap("brightness"),self.get),"temporary")
    def test_explicit_binding(self):
        self.r=m.Resolver({"home.family.example":None,"appliance.w":["switch.example"]})
        c={"requires":[{"kind":"binding","key":"home.family.example"}]}
        self.assertEqual(self.r.status(c,self.get),"hidden")
        c["requires"][0]["key"]="appliance.w"
        self.state=None
        self.assertEqual(self.r.status(c,self.get),"temporary")
        c["requires"][0]["key"]="unknown"
        self.assertEqual(self.r.status(c,self.get),"visible")
    def test_refresh(self):
        self.assertFalse(self.r.needs_refresh("zh-CN"))
        self.now=300
        self.assertTrue(self.r.needs_refresh("zh-CN"))
    def test_transient_resolution_failure_preserves_modes(self):
        self.assertEqual(self.r.status(cap("brightness"),self.get),"hidden")
        self.r.replace_targets("zh-CN",{})
        self.state=None
        self.assertEqual(self.r.status(cap("brightness"),self.get),"hidden")
        self.r.replace_targets("en",{})
        self.assertEqual(self.r.status(cap("brightness"),self.get),"visible")
    def test_validation(self):
        for raw in ({"a":False},{"a":[]},{"a":["invalid"]}):
            with self.assertRaises(ValueError):m.Resolver(raw)
        self.assertEqual(m.validate_bindings(m.validate_bindings({"a":["light.example"]})),{"a":("light.example",)})
