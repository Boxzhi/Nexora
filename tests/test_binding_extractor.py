import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from jinja2 import Environment

path=Path(__file__).resolve().parents[1]/"custom_components/nexora"
pkg=ModuleType("nexora_bindings_test")
pkg.__path__=[str(path)]
sys.modules[pkg.__name__]=pkg
from nexora_bindings_test import binding_extractor as b
from nexora_bindings_test.capability import Resolver

HOME="LuxeHomeQuery"
APP="LuxeApplianceQuery"
LIGHT="LuxeLightQuery"
HOME_BODY="{% if q == 'windows' %}stub{% elif q == 'lid' %}{{ states(D.lid) }}{% endif %}"
APP_BODY="{{ states(devices.w.ids.power) }}"
LIGHT_BODY="{{ states(entity) }}"
def digest(body):
    ast=Environment().parse(body)
    return hashlib.sha256(json.dumps(b._canonical(ast.body),ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
def home_source(grandfather="[]",lid="'sensor.example_lid'"):
    return "{% set D = {'family': {'爸爸': ['device_tracker.example'], '爷爷': "+grandfather+"}, 'lid': "+lid+"} %}"+HOME_BODY
def handler(name,source):
    return SimpleNamespace(intent_type=name,config={"speech":{"text":SimpleNamespace(template=source)}})
def cap(q,target="all"):
    return {"id":"home.test","intent":HOME,"slots":{"luxe_home_query":q,"luxe_home_target":target},"requires":[{"kind":"binding","key":"home.test"}]}

class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.p=patch.dict(b.SCHEMAS,{HOME:("D",digest(HOME_BODY)),APP:("devices",digest(APP_BODY)),LIGHT:("lights",digest(LIGHT_BODY))})
        self.p.start()
        self.addCleanup(self.p.stop)
    def test_static_literal(self):
        self.assertEqual(b.extract(home_source(),HOME)["family"]["爷爷"],[])
    def test_no_execution(self):
        self.assertIsNone(b.extract(home_source("dangerous_function()"),HOME))
    def test_reassigned_map(self):
        self.assertIsNone(b.extract(home_source()+"{% set D = {} %}",HOME))
    def test_unknown_changed_branch(self):
        self.assertIsNone(b.extract(home_source().replace("stub","changed"),HOME))
    def test_duplicate_keys(self):
        self.assertIsNone(b.extract(home_source().replace("'爷爷': []","'爷爷': [], '爷爷': []"),HOME))
    def test_moved_assignment(self):
        self.assertIsNone(b.extract("prefix"+home_source(),HOME))
    def test_reload_and_unbind_without_file(self):
        e=b.BindingExtractor()
        r=Resolver()
        r.extractor=e
        self.assertEqual(e.refresh([handler(HOME,home_source())]),{HOME})
        grandfather=cap("person","爷爷")
        self.assertEqual(r.status(grandfather,lambda _:None),"hidden")
        self.assertEqual(r.status(cap("windows"),lambda _:None),"hidden")
        self.assertEqual(r.status(cap("lid"),lambda _:None),"temporary")
        self.assertEqual(e.refresh([handler(HOME,home_source())]),set())
        e.refresh([handler(HOME,home_source("['device_tracker.grandfather']"))])
        self.assertEqual(r.status(grandfather,lambda _:None),"temporary")
        e.refresh([handler(HOME,home_source())])
        self.assertEqual(r.status(grandfather,lambda _:None),"hidden")
    def test_unknown_schema_retains(self):
        e=b.BindingExtractor()
        r=Resolver()
        r.extractor=e
        e.refresh([handler(HOME,home_source())])
        self.assertEqual(r.status(cap("windows"),lambda _:None),"hidden")
        e.refresh([handler(HOME,home_source().replace("stub","new code"))])
        self.assertEqual(r.status(cap("windows"),lambda _:None),"visible")
    def test_toilet_lid_not_window(self):
        d=b.extract(home_source(),HOME)
        self.assertEqual(b.home_binding(d,cap("windows")["slots"]),())
        self.assertEqual(b.home_binding(d,cap("lid")["slots"]),("sensor.example_lid",))
    def test_explicit_override(self):
        e=b.BindingExtractor()
        e.refresh([handler(HOME,home_source())])
        r=Resolver({"home.test":["device_tracker.example"]})
        r.extractor=e
        self.assertEqual(r.status(cap("person","爷爷"),lambda _:None),"temporary")
        r=Resolver({"home.test":None})
        r.extractor=e
        self.assertEqual(r.status(cap("person","爸爸"),lambda _:None),"hidden")
    def test_dynamic_or_invalid_binding_retained(self):
        self.assertIs(b.home_binding({"family":{"爷爷":"bad"}},cap("person","爷爷")["slots"]),b.UNKNOWN)
    def test_appliance_binding(self):
        d=b.extract("{% set devices = {'w': {'ids': {'power':'switch.example'}}} %}"+APP_BODY,APP)
        self.assertEqual(b.appliance_binding(d,{"luxe_appliance_device":"w","luxe_appliance_query":"power"}),("switch.example",))
        self.assertEqual(b.appliance_binding(d,{"luxe_appliance_device":"w","luxe_appliance_query":"temp"}),())
        self.assertEqual(b.appliance_binding(d,{"luxe_appliance_device":"m","luxe_appliance_query":"temp"}),())
    def test_light_semantic_binding(self):
        e=b.BindingExtractor()
        e.refresh([handler(LIGHT,"{% set lights = {'light.example':['灯','room']} %}"+LIGHT_BODY)])
        c={"intent":LIGHT,"category":"lights.fixture"}
        self.assertEqual(e.binding(c,{"lights.fixture":"light.example"}),("light.example",))
        self.assertEqual(e.binding(c,{"lights.fixture":"light.removed"}),())
        self.assertIs(e.binding(c,{}),b.UNKNOWN)
    def test_removed_handler_clears_cache(self):
        e=b.BindingExtractor()
        e.refresh([handler(HOME,home_source())])
        e.refresh([])
        self.assertIs(e.binding(cap("windows"),{}),b.UNKNOWN)

    def test_verified_empty_and_unimplemented_window_reasons(self):
        e=b.BindingExtractor()
        r=Resolver()
        r.extractor=e
        e.refresh([handler(HOME,home_source())])
        self.assertEqual(r.assess(cap("person","爷爷"),lambda _:None)["reasons"],[{"code":"verified_binding_empty"}])
        self.assertEqual(r.assess(cap("windows"),lambda _:None)["reasons"],[{"code":"verified_window_branch_unimplemented"}])
        e.refresh([handler(HOME,home_source().replace("stub","changed"))])
        self.assertEqual(r.assess(cap("windows"),lambda _:None)["status"],"visible")
