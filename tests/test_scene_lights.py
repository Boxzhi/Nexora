import unittest
import json
from datetime import date
from test_menu import mod, BASE, SET
from nexora_menu_test.scene_layout import lights_layout
from nexora_menu_test.query_planner import QueryPlanner

class LightsSceneTests(unittest.TestCase):
    def setUp(self):
        self.m=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],settings=SET)
        self.m.install_scene_layout(lights_layout(self.m))
        self.p=QueryPlanner(self.m)
        self.today=date(2026,11,27)
    def ask(self,q,**kw):
        return self.m.route("a",q,today=self.today,**kw)
    def plan(self,reply,visible=lambda c:True):
        return self.p.menu_plan(reply.scene,dict(reply.params),visible,None,self.today)
    def test_room_selection(self):
        self.ask("灯光")
        self.assertIn("客厅",self.ask("2").text)
        r=self.ask("1")
        self.assertIn("1. 照明状态",r.text)
        self.assertIn("2. 灯光异常",r.text)
        self.assertNotIn("3.",r.text)
        plan=self.plan(self.ask("1"))
        self.assertEqual([s.capability.rsplit(".",1)[1] for s in plan.primary],["total","list_on","list_off","offline"])
    def test_fixture_no_submenu_and_dynamic_modes(self):
        visible=lambda c:not c["id"].endswith((".brightness",".temperature"))
        self.ask("灯光")
        self.assertIn("客厅吸顶灯",self.ask("3").text)
        q=self.ask("1",available=visible)
        self.assertEqual(q.scene,"scene.lights.fixtures.living_ceiling")
        self.assertEqual([s.capability for s in self.plan(q,visible).primary],["lights.fixtures.living_ceiling.single_state"])
        self.assertEqual(len(self.plan(q).primary),3)
        self.assertIn("按灯具查询",self.m.items[self.m.sessions["a"].node].name)
    def test_alias_and_original(self):
        r=self.ask("客厅吸顶灯")
        self.assertEqual(r.scene,"scene.lights.fixtures.living_ceiling")
        self.assertEqual(self.ask("detail").text,self.ask("help").text)
        self.assertEqual(self.ask("客厅吸顶灯").scene,"scene.lights.fixtures.living_ceiling")
        self.m._render("a","root",lambda c:True)
        self.assertIn("开关状态",self.ask("客厅吸顶灯").text)
    def test_count_and_scope(self):
        self.assertEqual(len(self.m.scenes),37)
        self.assertEqual(len([x for x in self.m.capabilities if x.startswith("lights.")]),144)
        self.assertIn("lights.rooms.ke_ting.all_off",self.m.capabilities)
        self.assertIn("lights.rooms.ke_ting.count_on",self.m.capabilities)
