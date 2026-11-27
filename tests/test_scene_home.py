import json
import unittest
from datetime import date
from test_menu import mod, BASE, SET
from nexora_menu_test.scene_layout import home_layout,build_layout
from nexora_menu_test.query_planner import QueryPlanner

class HomeSceneTests(unittest.TestCase):
    def setUp(self):
        self.m=mod.Menu([json.loads(p.read_text()) for p in sorted((BASE/"catalogs").glob("*.json"))],settings=SET)
        self.m.install_scene_layout(build_layout(self.m))
        self.p=QueryPlanner(self.m)
        self.today=date(2026,11,27)
    def ask(self,q,**kw):
        return self.m.route("a",q,today=self.today,**kw)
    def plan(self,q,visible=lambda c:True):
        return self.p.menu_plan(q.scene,dict(q.params),visible,None,self.today)
    def test_home_order_and_family(self):
        r=self.ask("全屋状态")
        self.assertIn("1. 全屋概况",r.text)
        self.assertIn("2. 家庭成员",r.text)
        self.assertIn("8. 其他设备",r.text)
        self.assertEqual(self.plan(self.ask("2")).primary[0].capability,"home.family.family_all")
    def test_environment_room_and_whole(self):
        self.ask("环境温湿度")
        plan=self.plan(self.ask("1"))
        self.assertEqual([s.key.metric for s in plan.primary],["env","temp_max","temp_min","hum_max","hum_min"])
        self.assertEqual(self.plan(self.ask("2")).primary[0].capability,"home.env.master.room_env_master")
        self.assertEqual(self.plan(self.ask("5")).primary[0].capability,"home.env.bathroom.temp_bathroom")
    def test_presence_uses_current_duration_only(self):
        self.ask("人体感应及光照")
        plan=self.plan(self.ask("4"))
        self.assertEqual([s.key.metric for s in plan.primary],["presence","lux","duration"])
        self.assertEqual(len(self.plan(self.ask("3")).primary),2)
    def test_door_and_window_visibility(self):
        visible=lambda c:not c["id"].endswith(".windows_all")
        r=self.ask("门锁及窗帘",available=visible)
        self.assertIn("1. 入户门状态",r.text)
        self.assertIn("2. 全屋窗帘",r.text)
        self.assertNotIn("窗户状态",r.text)
        plan=self.plan(self.ask("1",available=visible),visible)
        self.assertEqual([s.key.metric for s in plan.primary],["door","lock","deadbolt","childlock"])
        self.assertEqual(len(self.plan(self.ask("2",available=visible),visible).primary),3)
        self.assertIn("窗户状态",self.ask("门锁及窗帘").text)
    def test_safety_and_maintenance(self):
        self.assertIn("4. 设备故障",self.ask("安全及异常").text)
        self.assertEqual(self.plan(self.ask("2")).primary[0].capability,"home.safety.water_all_all")
        r=self.ask("电池及维护")
        self.assertIn("1. 低电量设备",r.text)
        self.assertIn("2. 全部设备电量",r.text)
        self.assertNotIn("3.",r.text)
    def test_counts_and_original_registry(self):
        self.assertEqual(sum(cid.startswith("scene.home.") for cid in self.m.scenes),24)
        self.assertEqual(len(self.m.scenes),150)
        self.assertEqual(len(self.m.capabilities),443)
        self.m._render("a","root",lambda c:True)
        self.assertIn("家庭成员",self.ask("4").text)
        self.assertIn("在家人数",self.ask("1").text)
